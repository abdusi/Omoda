import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from PIL import Image

from content import SUBJECTS, build, digest, prepare_bank
from sync_ntc import ALL_SPECS, discover


class ContentTests(unittest.TestCase):
    def fixture(self, root):
        assets = root / "assets"
        assets.mkdir()
        fragment = {"text": "Матни тоҷикӣ", "image": "", "width": 1, "height": 1, "visual": False}
        for sid in SUBJECTS:
            questions = [{"id": f"{sid}-{i}", "number": i, "page": 1, "source": "source.pdf",
                          "prompt": dict(fragment), "options": [dict(fragment) for _ in range(4)], "correct": 0}
                         for i in range(1, 26)]
            if sid == "math":
                image = assets / "questions/math/1_q.webp"
                image.parent.mkdir(parents=True)
                Image.new("RGB", (12, 8), "white").save(image)
                questions[0]["prompt"].update(image="questions/math/1_q.webp", width=12, height=8, visual=True)
            (assets / f"{sid}.json").write_text(json.dumps(questions, ensure_ascii=False), encoding="utf-8")
        return assets

    def test_reproducible_packs_match_catalog_and_keep_tajik_text(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            assets = self.fixture(root)
            a = build(assets, root / "a")
            b = build(assets, root / "b")
            self.assertEqual(a, b)
            for release in a["subjects"]:
                folder = root / "a" / release["path"]
                self.assertEqual(release["bankSha256"], digest((folder / "bank.json").read_bytes()))
                self.assertEqual(release["packSha256"], digest((folder / "pack.zip").read_bytes()))
                with zipfile.ZipFile(folder / "pack.zip") as archive:
                    self.assertEqual(release["unpackedBytes"], sum(i.file_size for i in archive.infolist()))
                    self.assertIn("Матни тоҷикӣ", archive.read("bank.json").decode())
                    self.assertEqual(len(archive.namelist()), 2 if release["id"] == "math" else 1)

    def test_answer_or_image_change_changes_version_and_year_is_versioned(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            assets = self.fixture(root)
            a = build(assets, root / "a")
            path = assets / "tajik.json"
            questions = json.loads(path.read_text("utf-8"))
            questions[0]["correct"] = 3
            path.write_text(json.dumps(questions), encoding="utf-8")
            b = build(assets, root / "b")
            changed = [s["id"] for s, t in zip(a["subjects"], b["subjects"]) if s["version"] != t["version"]]
            self.assertEqual(changed, ["tajik"])
            c = build(assets, root / "c", year=2027)
            self.assertTrue(all(s["version"] != t["version"] for s, t in zip(b["subjects"], c["subjects"])))

    def test_rejects_invalid_key_and_escaping_image(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            assets = self.fixture(root)
            path = assets / "math.json"
            questions = json.loads(path.read_text("utf-8"))
            questions[0]["prompt"]["image"] = "../escape.webp"
            path.write_text(json.dumps(questions), encoding="utf-8")
            with self.assertRaises(ValueError):
                prepare_bank(assets, "math")
            questions[0]["correct"] = 4
            path.write_text(json.dumps(questions), encoding="utf-8")
            with self.assertRaises(ValueError):
                prepare_bank(assets, "math")


class DiscoveryTests(unittest.TestCase):
    def page(self):
        cells = []
        for sid, spec in ALL_SPECS.items():
            # Keys deliberately do not follow a filename suffix convention.
            cells.append(f'<td><a href="/images/{spec[2]}.pdf">Questions</a>'
                         '<a href="/images/open-type.pdf">Other section</a>'
                         f'<a href="/images/keys_2026/{sid}.pdf">Keys</a></td>')
        return "<table><tr>" + "".join(cells) + "</tr></table>"

    def test_pairs_by_table_cell_not_filename_and_ignores_component_b(self):
        page = self.page() + '<table><td><a href="/images/A1-ALL_Tj.pdf">B</a><a href="/images/keys_2025/b.pdf">B key</a></td></table>'
        pairs, year = discover(page)
        self.assertEqual(year, 2026)
        self.assertEqual(len(pairs), 10)
        self.assertTrue(pairs["math"]["keysUrl"].endswith("/math.pdf"))

    def test_missing_key_or_changed_layout_fails_closed(self):
        with self.assertRaises(ValueError):
            discover(self.page().replace("/images/keys_2026/math.pdf", "/images/no-key.pdf"))
        with self.assertRaises(ValueError):
            discover("<p>Unavailable</p>")

    def test_external_source_and_mixed_years_rejected(self):
        with self.assertRaises(ValueError):
            discover(self.page().replace("/images/A1-ALL_Tj.pdf", "https://untrusted.example/A1-ALL_Tj.pdf"))
        with self.assertRaises(ValueError):
            discover(self.page().replace("/keys_2026/math.pdf", "/keys_2027/math.pdf"))


if __name__ == "__main__":
    unittest.main()
