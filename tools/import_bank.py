"""Import a reviewed, bounded set of single-choice items from the supplied 2026 PDFs.

Keep visual fragments for formula/diagram fidelity and text for accessibility.
Never infer answers: every imported item must have exactly one matching key.
"""
import argparse
import json
import re
from io import BytesIO
from pathlib import Path
import pdfplumber
import pypdfium2 as pdfium
from pypdf import PdfReader
from PIL import Image, ImageChops
from pdf_clean import without_watermarks

ROOT = Path(__file__).resolve().parents[1]
SPECS = [
    ("tajik", "Забони тоҷикӣ", "A1-ALL_Tj", 1, 1),
    ("math", "Математика", "A2-12_Math_tj", 1, 1),
    ("geography", "География", "A3-2_Geography_tj", 1, 1),
    ("english", "Забони англисӣ", "A4-234_En", 83, 11),
]
CLUSTER5_SPECS = [
    ("biology", "Биология", "A2-5_Biology_tj", 1, 1),
    ("chemistry", "Химия", "A3-15_Chemistry_tj", 1, 1),
    ("physics", "Физика", "A4-15_Physics_tj", 1, 1),
]
CLUSTER4_SPECS = [
    ("history", "Таърих", "A2-34_History_tj", 1, 1),
    ("law", "Ҳуқуқ", "A3-4_Law_tj", 1, 1),
]
CLUSTER3_SPECS = [
    ("literature", "Адабиёти тоҷик", "A3-3_TjLiterature_tj", 1, 1),
]
LETTERS = {"А)": "A", "A)": "A", "В)": "B", "B)": "B",
           "С)": "C", "C)": "C", "D)": "D"}


def answer_keys(path, start):
    result = {}
    for page in PdfReader(path).pages[start:]:
        text = page.extract_text() or ""
        if "БАРОИ МУАЙЯН" in text or "ҶАВОБИ КӮТОҲ" in text:
            break
        for number, letter in re.findall(r"(?m)^\s*(\d+)\s+([ABCD])\s*$", text):
            number = int(number)
            if number in result:
                raise ValueError(f"Duplicate key {path.name}:{number}")
            result[number] = letter
    return result


def crop_image(page_image, box, scale, path, extra_boxes=()):
    pieces = []
    for bounds_box in [box, *extra_boxes]:
        image = page_image.crop(tuple(round(n * scale) for n in bounds_box)).convert("RGB")
        ink = ImageChops.difference(image, Image.new("RGB", image.size, "white"))
        bounds = ink.convert("L").point(lambda v: 255 if v > 60 else 0).getbbox()
        if not bounds:
            if extra_boxes:
                continue
            raise ValueError(f"Empty image: {path}")
        l, t, r, b = bounds
        pieces.append(image.crop((max(0, l-6), max(0, t-6), min(image.width, r+6), min(image.height, b+6))))
    assert pieces, f"No visible content: {path}"
    image = Image.new("RGB", (max(p.width for p in pieces), sum(p.height for p in pieces)+16*(len(pieces)-1)), "white")
    y = 0
    for piece in pieces:
        image.paste(piece, ((image.width-piece.width)//2, y))
        y += piece.height+16
    image.save(path, "WEBP", lossless=True)
    return {"image": f"questions/{path.parent.name}/{path.name}",
            "width": image.width, "height": image.height}


def extract(source, limit, specs=SPECS, report_name="import-report.json", *, output_root=None,
            key_reader=answer_keys, minimum_count=25, end_page=None):
    output_root = Path(output_root) if output_root is not None else ROOT
    assets = output_root / "app/src/main/assets"
    assets.mkdir(parents=True, exist_ok=True)
    report = []
    for sid, title, stem, start, key_start in specs:
        keys = key_reader(source / f"{stem}_key.pdf", key_start)
        cap = min(limit or max(keys), max(keys))
        images = assets / "questions" / sid
        images.mkdir(parents=True, exist_ok=True)
        items, skipped = [], []
        clean_bytes, removed = without_watermarks(source / f"{stem}.pdf")
        doc = pdfium.PdfDocument(clean_bytes)
        with pdfplumber.open(BytesIO(clean_bytes)) as pdf:
            for pi in range(start, min(end_page, len(pdf.pages)) if end_page is not None else len(pdf.pages)):
                page = pdf.pages[pi]
                # pdfplumber marks 45-degree watermark glyphs as upright too.
                # Read horizontal text after removing tagged watermark objects.
                horizontal = page.filter(lambda obj: obj.get("object_type") != "char" or
                                         (abs(obj.get("matrix", (1, 0, 0, 1, 0, 0))[1]) < .01 and
                                          abs(obj.get("matrix", (1, 0, 0, 1, 0, 0))[2]) < .01))
                words = horizontal.extract_words()
                markers = sorted([w for w in words if w["text"].isdigit()
                                  and 48 <= w["x0"] <= 70 and 45 < w["top"] < 780], key=lambda w: w["top"])
                wanted = [w for w in markers if 1 <= int(w["text"]) <= cap]
                if not wanted:
                    if items and markers and min(int(w["text"]) for w in markers) > cap:
                        break
                    continue
                scale = 2.4
                bitmap = doc[pi].render(scale=scale).to_pil()
                ink_mask = bitmap.convert("L").point(lambda value: 255 if value < 140 else 0)
                row_cache = {}
                for marker in wanted:
                    number = int(marker["text"])
                    end = next((w["top"]-5 for w in markers if w["top"] > marker["top"]+5), 790)
                    region = [w for w in words if marker["top"]-2 <= w["top"] < end and w["x0"] >= 82 and w["upright"]]
                    labels = sorted([w for w in region if w["text"] in LETTERS], key=lambda w: (round(w["top"]/5), w["x0"]))
                    if len(labels) != 4 or [LETTERS[w["text"]] for w in labels] != list("ABCD") or number not in keys:
                        skipped.append({"number": number, "page": pi+1, "reason": "ambiguous markers or missing key"})
                        continue
                    first = labels[0]
                    if first["top"] <= marker["top"]+10:
                        skipped.append({"number": number, "page": pi+1, "reason": "prompt/answer layout needs review"})
                        continue
                    # Figures beside the answers belong to the question, not to
                    # individual options. Move them below the prompt intact.
                    figure_objects = [obj for obj in page.images + page.curves + page.lines
                                      if obj["x0"] >= 140 and obj["x1"] <= 553
                                      and marker["top"]-12 <= obj["top"] < end
                                      and obj["bottom"] <= end+2
                                      and max(obj["width"], obj["height"]) > 5]
                    side_figures = []
                    stem_text = " ".join(w["text"] for w in region if w["top"] < first["top"]-3)
                    shared_image = any(obj.get("object_type") == "image" and len({round(w["top"]/6) for w in labels
                                        if obj["top"] <= w["top"]+7 <= obj["bottom"]}) >= 2 for obj in figure_objects)
                    if figure_objects and (shared_image or re.search(r"расм|харита|портрет|нақша|график|диаграмма|тасвир|схема|ҷадвал|конфигуратсия|номенклатура|орбитал|тарозу|занҷир|[Мм]одда ба кадом синф", stem_text, re.I)):
                        bottom = max(obj["bottom"] for obj in figure_objects)
                        if bottom > first["top"]-3:
                            embedded = [obj for obj in figure_objects if obj.get("object_type") == "image"]
                            if sid == "chemistry" and not embedded:
                                left = min(obj["x0"] for obj in figure_objects)
                                top = min(obj["top"] for obj in figure_objects)
                                right = max(obj["x1"] for obj in figure_objects)
                                atoms = [w for w in region if max(180, left-80) <= w["x0"] <= right+50
                                         and max(marker["bottom"]+2, top-24) <= w["top"] <= bottom+24
                                         and re.search(r"[A-Za-z0-9]", w["text"]) and w["text"] not in LETTERS]
                                figure_objects.extend(atoms)
                                bottom = max(obj["bottom"] for obj in figure_objects)
                            margin = 1 if embedded else 7
                            side_figures = [(min(obj["x0"] for obj in figure_objects)-margin,
                                             min(obj["top"] for obj in figure_objects)-margin,
                                             min(553, max(obj["x1"] for obj in figure_objects)+margin),
                                             min(end, bottom+margin))]
                    answer_right = min((box[0]-3 for box in side_figures), default=553)
                    cache_key = round(answer_right, 1)
                    if cache_key not in row_cache:
                        row_cache[cache_key] = ink_mask.crop((round(90*scale), 0, round(answer_right*scale), bitmap.height)).getprojection()[1]
                    projection = row_cache[cache_key]

                    def split_before(top):
                        earlier = [w["bottom"] for w in labels if w["top"] < top-6]
                        lower = max(top-26, max(earlier)+1 if earlier else marker["bottom"]+1)
                        lo, hi = max(0, round(lower*scale)), min(len(projection), round((top+1)*scale))
                        gaps, begin = [], None
                        for row in range(lo, hi):
                            if not projection[row] and begin is None:
                                begin = row
                            if projection[row] and begin is not None:
                                if row-begin >= round(2*scale): gaps.append((begin, row))
                                begin = None
                        if begin is not None and hi-begin >= round(2*scale): gaps.append((begin, hi))
                        return sum(gaps[-1])/2/scale if gaps else top-3

                    prompt_end = split_before(first["top"])
                    prompt_words = [w for w in region if w["top"] < prompt_end and
                                    not any(box[0] <= w["x0"] <= box[2] and box[1] <= w["top"] <= box[3] for box in side_figures)]
                    boxes = [(84, marker["top"]-1, 553, prompt_end)]
                    if side_figures:
                        figure_top = min(obj["top"] for obj in figure_objects)
                        crossing = [w["top"] for w in prompt_words if w["top"] < figure_top < w["bottom"]]
                        if crossing:
                            figure_top = min(crossing)
                        boxes = []
                        if figure_top > marker["top"]+2:
                            boxes.append((84, marker["top"]-1, 553, min(prompt_end, figure_top)))
                        if figure_top < prompt_end:
                            boxes.append((84, max(marker["top"]-1, figure_top), answer_right, prompt_end))
                        boxes.extend(side_figures)
                    prompt = crop_image(bitmap, boxes[0], scale, images/f"{number}_q.webp", boxes[1:])
                    prompt["text"] = " ".join(w["text"] for w in prompt_words)
                    has_graphic = any(obj["top"] < prompt_end and obj["bottom"] > marker["top"] and obj["x1"] > 84
                                      for obj in page.images + page.curves)
                    prompt["visual"] = sid in {"math", "biology", "chemistry", "physics", "literature"} or has_graphic or bool(side_figures) or bool(re.search(
                        r"ишорашуда|таъкидшуда|зерхат|ҷудошуда|underlined|highlighted", prompt["text"], re.I))
                    choices = []
                    for oi, label in enumerate(labels):
                        same_row = [w for w in labels if abs(w["top"]-label["top"]) < 6 and w["x0"] > label["x0"]+5]
                        next_rows = [w["top"] for w in labels if w["top"] > label["top"]+6]
                        right = min(w["x0"] for w in same_row)-4 if same_row else answer_right
                        bottom = split_before(min(next_rows)) if next_rows else end
                        # On the final row, exclude following topic headings and page footer.
                        content = [w for w in region if label["x1"]+1 <= w["x0"] < right and label["top"]-3 <= w["top"] < bottom]
                        # End final vertical choice at its last nearby line, before section gaps.
                        if oi == 3 and content:
                            headings = [w["top"] for w in content if w["top"] > label["bottom"]+5
                                        and len(w["text"]) >= 5 and w["text"].isupper()
                                        and re.search(r"[А-ЯҲҶҒҚӢӮ]", w["text"])]
                            heading_start = min(headings, default=bottom)
                            content = [w for w in content if w["top"] < heading_start]
                            line_end = max([label["bottom"], *(w["bottom"] for w in content)])
                            graphic_ends = [obj["bottom"] for obj in page.curves + page.lines + page.images
                                            if label["top"]-12 <= obj["top"] and obj["bottom"] < heading_start-1
                                            and label["x1"]+2 < obj["x0"] and obj["x1"] < right
                                            and obj["width"] < right-label["x1"]-5]
                            bottom = min(bottom, heading_start, max([line_end+3, *(value+3 for value in graphic_ends)]))
                            content = [w for w in content if w["top"] < bottom]
                        choice = crop_image(bitmap, (label["x1"]+2, split_before(label["top"]), right, bottom), scale, images/f"{number}_{oi}.webp")
                        choice["text"] = " ".join(w["text"] for w in content)
                        choice["visual"] = sid in {"math", "biology", "chemistry", "physics", "literature"}
                        choices.append(choice)
                    items.append({"id": f"{sid}-{number}", "number": number, "page": pi+1,
                                  "source": f"{stem}.pdf", "prompt": prompt, "options": choices,
                                  "correct": "ABCD".index(keys[number])})
                if markers and max(int(w["text"]) for w in markers) >= cap:
                    break
                page.close()
        doc.close()
        assert len(items) >= minimum_count, (sid, len(items), skipped)
        assert len({q["id"] for q in items}) == len(items), [
            (q["id"], q["page"]) for q in items if sum(x["id"] == q["id"] for x in items) > 1]
        (assets/f"{sid}.json").write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
        report.append({"subject": sid, "title": title, "count": len(items), "range": [1, cap], "skipped": skipped,
                       "watermark_blocks_removed": sum(removed), "watermark_pages": len([n for n in removed if n])})
        print(f"{sid}: {len(items)} questions; {len(skipped)} skipped", flush=True)
    (output_root/"tools").mkdir(parents=True, exist_ok=True)
    (output_root/"tools"/report_name).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--cluster", choices=["2", "3", "4", "5"], default="2")
    args = parser.parse_args()
    specs = {"2": SPECS, "3": CLUSTER3_SPECS, "4": CLUSTER4_SPECS, "5": CLUSTER5_SPECS}[args.cluster]
    extract(args.source, args.limit, specs, "import-report.json" if args.cluster == "2" else f"import-report-cluster{args.cluster}.json")
