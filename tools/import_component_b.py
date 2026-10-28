"""Use the reviewed visual extractor for B; isolate keys, question IDs and image paths."""
import json
from pathlib import Path
import re
import shutil
from io import BytesIO
import pdfplumber
from pypdf import PdfReader

from import_bank import extract
from pdf_clean import without_watermarks

B_SPECS = [
    ("b_math", "Математика", "B-Math_tj", 1, 1),
    ("b_physics", "Физика", "B-Physics_tj", 1, 1),
    ("b_geography", "География", "B-Geography_tj", 1, 1),
    ("b_literature", "Адабиёти тоҷик", "B-TjLiterature_tj", 1, 1),
    ("b_english", "Забони англисӣ", "B-En_tj_ru", 40, 6),
    ("b_history", "Таърих", "B-History_tj", 1, 1),
    ("b_biology", "Биология", "B-Biology_tj", 1, 1),
    ("b_chemistry", "Химия", "B-Chemistry_tj", 1, 1),
]


def parse_key_texts(texts):
    result = {}
    explicitly_blank = set()
    for text in texts:
        # Matching/short-answer sections can start on the same page as the last keys.
        stop = re.search(r"БАРОИ\s+МУАЙЯН|ҶАВОБИ\s+КӮТОҲ|НАМУНАИ\s+СУБТЕСТ", text)
        single_choice = text[:stop.start()] if stop else text
        normalized = single_choice.translate(str.maketrans("АВС", "ABC"))
        explicitly_blank.update(int(n) for n in re.findall(r"(?m)^[ \t]*(\d+)[ \t]*$", normalized))
        for number, value in re.findall(r"(?m)^\s*(\d+)\s+(\S+)\s*$", normalized):
            if value not in "ABCD" or len(value) != 1:
                raise ValueError(f"Unsupported answer key {number}: {value}")
            number = int(number)
            if number in result:
                raise ValueError(f"Duplicate key {number}")
            result[number] = value
        if stop:
            break
    if not result:
        raise ValueError("Incomplete single-choice keys")
    missing = set(range(1, max(result) + 1)) - set(result)
    if not missing.issubset(explicitly_blank):
        raise ValueError(f"Incomplete single-choice keys: {sorted(missing)}")
    return result


def answer_keys_b(path, start):
    return parse_key_texts(p.extract_text() or "" for p in PdfReader(path).pages[start:])


def keys_and_layout(source, spec):
    sid, _, stem, start, key_start = spec
    keys = answer_keys_b(source / f"{stem}_key.pdf", key_start)
    clean, _ = without_watermarks(source / f"{stem}.pdf")
    numbers = set()
    end_page = None
    with pdfplumber.open(BytesIO(clean)) as pdf:
        for index in range(start, len(pdf.pages)):
            page = pdf.pages[index]
            header = (page.extract_text() or "")[:450]
            if re.search(r"БАРОИ\s+МУАЙЯН|ҶАВОБИ\s+КӮТОҲ|НАМУНАИ\s+СУБТЕСТ", header):
                end_page = index
                break
            horizontal = page.filter(lambda obj: obj.get("object_type") != "char" or
                (abs(obj.get("matrix", (1, 0, 0, 1, 0, 0))[1]) < .01 and
                 abs(obj.get("matrix", (1, 0, 0, 1, 0, 0))[2]) < .01))
            numbers.update(int(w["text"]) for w in horizontal.extract_words()
                           if w["text"].isdigit() and 48 <= w["x0"] <= 70 and 45 < w["top"] < 780)
            page.close()
    if not numbers:
        raise ValueError(f"{sid}: no single-choice question markers")
    missing = sorted(numbers - keys.keys())
    orphan = sorted(keys.keys() - numbers)
    valid = {number: value for number, value in keys.items() if number in numbers}
    if not valid:
        raise ValueError(f"{sid}: no questions with official keys")
    return valid, end_page, missing, orphan


def extract_b(source, limit, spec, *, output_root):
    sid, title, stem, start, key_start = spec
    base_id = sid.removeprefix("b_")
    keys, end_page, missing, orphan = keys_and_layout(source, spec)
    extract(source, limit, [(base_id, title, stem, start, key_start)],
            report_name=f"{sid}.json", output_root=output_root,
            key_reader=lambda path, start: keys, minimum_count=1, end_page=end_page)
    assets = Path(output_root) / "app/src/main/assets"
    original = assets / f"{base_id}.json"
    questions = json.loads(original.read_text("utf-8"))
    for question in questions:
        question["id"] = f"{sid}-{question['number']}"
        for fragment in [question["prompt"], *question["options"]]:
            if fragment["image"]:
                fragment["image"] = f"questions/{sid}/{Path(fragment['image']).name}"
    (assets / f"{sid}.json").write_text(json.dumps(questions, ensure_ascii=False), encoding="utf-8")
    original.unlink()
    shutil.move(str(assets / "questions" / base_id), str(assets / "questions" / sid))
    report_path = Path(output_root) / "tools" / f"{sid}.json"
    report = json.loads(report_path.read_text("utf-8"))
    report[0].update(subject=sid, excludedMissingKeys=missing, orphanKeys=orphan)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
