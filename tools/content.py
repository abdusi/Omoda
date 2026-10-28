"""Build deterministic, versioned text banks and offline packs for the Android app."""
import argparse
import copy
import hashlib
import json
from pathlib import Path, PurePosixPath
import zipfile

from PIL import Image
from exam_catalog import A_SUBJECTS, ALL_SUBJECTS, COMPONENTS

SUBJECTS = A_SUBJECTS  # Compatibility for callers that export the original A seed.
SOURCE_PAGE = "https://www.ntc.tj/tj/ba-dovtalab/testho.html"


def encode(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":")) + "\n").encode("utf-8")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def asset_path(root, name):
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or "\\" in name or not name:
        raise ValueError(f"Unsafe asset path: {name!r}")
    target = (root / name).resolve()
    if not target.is_relative_to(root.resolve()):
        raise ValueError(f"Asset outside bank: {name!r}")
    return target


def prepare_bank(assets, sid):
    questions = json.loads((assets / f"{sid}.json").read_text(encoding="utf-8"))
    if not 1 <= len(questions) <= 10000 or len({q["id"] for q in questions}) != len(questions):
        raise ValueError(f"{sid}: a nonempty bank of unique questions required")
    questions = copy.deepcopy(questions)
    images = {}
    for q in questions:
        if len(q["options"]) != 4 or type(q["correct"]) is not int or q["correct"] not in range(4):
            raise ValueError(f"Invalid options/key: {q['id']}")
        for fragment in [q["prompt"], *q["options"]]:
            if not fragment["visual"]:
                if not fragment["text"].strip() or "(cid:" in fragment["text"]:
                    raise ValueError(f"Unreadable text: {q['id']}")
                fragment["image"] = ""
                fragment.pop("sha256", None)
                continue
            name = fragment["image"]
            image_path = asset_path(assets, name)
            data = image_path.read_bytes()
            with Image.open(image_path) as image:
                if image.size != (fragment["width"], fragment["height"]):
                    raise ValueError(f"Image size mismatch: {name}")
                image.verify()
            fragment["sha256"] = digest(data)
            images[name] = data
    return questions, images


def build(assets, output, *, year=2026, source_page=SOURCE_PAGE, provenance=None, include_b=False):
    output.mkdir(parents=True, exist_ok=True)
    catalog = {"schema": 1, "year": year, "sourcePage": source_page, "subjects": []}
    for sid in ALL_SUBJECTS if include_b else A_SUBJECTS:
        questions, images = prepare_bank(assets, sid)
        bank = encode(questions)
        version = digest(str(year).encode("ascii") + b"\n" + bank)
        relative = f"banks/{sid}/{version}"
        directory = output / relative
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "bank.json").write_bytes(bank)
        for name, data in sorted(images.items()):
            target = directory / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        package = directory / "pack.zip"
        # Stored entries are byte-identical across OS/zlib versions; WebP is already compressed.
        with zipfile.ZipFile(package, "w", compression=zipfile.ZIP_STORED) as archive:
            for name, data in [("bank.json", bank), *sorted(images.items())]:
                info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
                info.create_system = 3
                info.compress_type = zipfile.ZIP_STORED
                info.external_attr = 0o100644 << 16
                archive.writestr(info, data)
        catalog["subjects"].append({
            "id": sid, "version": version, "year": year, "count": len(questions), "path": relative + "/",
            "bankSha256": digest(bank), "packSha256": digest(package.read_bytes()),
            "packBytes": package.stat().st_size,
            "unpackedBytes": len(bank) + sum(map(len, images.values())),
            "source": (provenance or {}).get(sid, {}),
        })
    (output / "catalog.json").write_bytes(encode(catalog))
    legacy = dict(catalog, subjects=[s for s in catalog["subjects"] if s["id"] in A_SUBJECTS])
    (output / "catalog.json").write_bytes(encode(legacy))
    catalog_v2 = dict(catalog, schema=2, components=COMPONENTS)
    (output / "catalog-v2.json").write_bytes(encode(catalog_v2))
    return catalog_v2


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assets", type=Path, default=Path("app/src/main/assets"))
    parser.add_argument("--output", type=Path, default=Path(".content"))
    parser.add_argument("--year", type=int, default=2026)
    parser.add_argument("--include-b", action="store_true")
    args = parser.parse_args()
    result = build(args.assets, args.output, year=args.year, include_b=args.include_b)
    print(f"Published locally: {sum(s['count'] for s in result['subjects'])} questions")
