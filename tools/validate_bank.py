"""Verify imported JSON, image integrity, source-key mapping and schema."""
import json
import sys
from pathlib import Path
from PIL import Image
from import_bank import SPECS, CLUSTER5_SPECS, CLUSTER4_SPECS, CLUSTER3_SPECS, answer_keys

root = Path(__file__).resolve().parents[1]
assets = root / "app/src/main/assets"
source = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.home() / "Downloads/ММТ 2кластер"
source5 = Path(sys.argv[2]) if len(sys.argv) > 2 else Path.home() / "Downloads/ММТ 5кластер"
source4 = Path(sys.argv[3]) if len(sys.argv) > 3 else Path.home() / "Downloads/ММТ 4кластер"
source3 = Path(sys.argv[4]) if len(sys.argv) > 4 else Path.home() / "Downloads/ММТ 3 кластер"
total = 0
for sid, _, stem, _, start in SPECS + CLUSTER5_SPECS + CLUSTER4_SPECS + CLUSTER3_SPECS:
    questions = json.loads((assets/f"{sid}.json").read_text(encoding="utf-8"))
    folder = source3 if sid == "literature" else source4 if sid in {"history", "law"} else source5 if sid in {"biology", "chemistry", "physics"} else source
    keys = answer_keys(folder/f"{stem}_key.pdf", start)
    assert len(questions) >= 25
    assert len({q["id"] for q in questions}) == len(questions)
    if sid in {"biology", "chemistry", "physics", "history", "law", "literature"}:
        assert {q["number"] for q in questions} == set(keys), (sid, "Incomplete single-choice import")
    for q in questions:
        assert len(q["options"]) == 4
        assert q["correct"] == "ABCD".index(keys[q["number"]]), q["id"]
        for fi, fragment in enumerate([q["prompt"], *q["options"]]):
            assert fragment["visual"] or fragment["text"].strip(), q["id"]
            path = (assets/fragment["image"]).resolve()
            assert path.is_relative_to(assets.resolve())
            with Image.open(path) as image:
                assert image.size == (fragment["width"], fragment["height"])
                image.verify()
            if fi and fragment["visual"]:
                with Image.open(path) as image:
                    gray = image.convert("L")
                    width, height = gray.size
                    for row in [0, height-1]:
                        assert sum(pixel < 100 for pixel in gray.crop((0,row,width,row+1)).get_flattened_data()) <= 1, (q["id"], fi, "ink touches crop edge")
    total += len(questions)
    print(f"{sid}: {len(questions)} questions, keys and images OK")
print(f"Total: {total}; all checks passed")
