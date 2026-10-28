import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from PIL import Image

from content import SUBJECTS, build, digest, prepare_bank
from sync_ntc import ALL_SPECS, discover
from exam_catalog import A_SUBJECTS, B_SUBJECTS, ALL_SUBJECTS, CLUSTERS
from import_component_b import parse_key_texts


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
        tables = []
        for component in ("A", "B"):
            rows = []
            for group in CLUSTERS[component]:
                cells = []
                for sid in group:
                    spec = ALL_SPECS[sid]
                    cells.append(f'<td><a href="/images/{spec[2]}.pdf">Questions</a>'
                                 '<a href="/images/open-type.pdf">Other section</a>'
                                 f'<a href="/images/keys_2026/{sid}.pdf">Keys</a>'
                                 '<a href="/images/foreign-german.pdf">German</a>'
                                 '<a href="/images/foreign-arabic.pdf">Arabic</a></td>')
                rows.append("<tr>" + "".join(cells) + "</tr>")
            tables.append("<table>" + "".join(rows) + "</table>")
        return "".join(tables)

    def test_pairs_each_component_by_cell_and_ignores_other_foreign_languages(self):
        pairs, year = discover(self.page())
        self.assertEqual(year, 2026)
        self.assertEqual(len(pairs), 18)
        self.assertTrue(pairs["math"]["keysUrl"].endswith("/math.pdf"))
        self.assertIn("/B-Math_tj.pdf", pairs["b_math"]["questionsUrl"])
        self.assertNotEqual(pairs["english"]["questionsUrl"], pairs["b_english"]["questionsUrl"])
        self.assertFalse(any("german" in p["questionsUrl"] or "arabic" in p["questionsUrl"] for p in pairs.values()))

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


class ComponentBTests(unittest.TestCase):
    def test_cyrillic_key_letters_and_same_page_section_boundary(self):
        self.assertEqual(parse_key_texts(["1 А\n2 В\n3 С\n4 D\nБАРОИ МУАЙЯН\n1 2\n"]),
                         {1: "A", 2: "B", 3: "C", 4: "D"})

    def test_explicitly_blank_key_is_quarantined_but_unexplained_gap_fails(self):
        self.assertEqual(parse_key_texts(["1 A\n2 \n3 C\n"]), {1: "A", 3: "C"})
        with self.assertRaises(ValueError):
            parse_key_texts(["1 A\n3 C\n"])
        with self.assertRaises(ValueError):
            parse_key_texts(["1 E\n"])

    def test_v2_includes_B_and_legacy_catalog_remains_A_only(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            assets = ContentTests().fixture(root)
            template = json.loads((assets / "tajik.json").read_text("utf-8"))
            for sid in B_SUBJECTS:
                if sid == "tajik":
                    continue
                bank = template[:18] if sid == "b_english" else template
                bank = [dict(q, id=f"{sid}-{q['number']}") for q in bank]
                (assets / f"{sid}.json").write_text(json.dumps(bank), encoding="utf-8")
            v2 = build(assets, root / "out", include_b=True)
            legacy = json.loads((root / "out/catalog.json").read_text("utf-8"))
            self.assertEqual(v2["schema"], 2)
            self.assertEqual({s["id"] for s in v2["subjects"]}, set(ALL_SUBJECTS))
            self.assertEqual({s["id"] for s in legacy["subjects"]}, set(A_SUBJECTS))
            self.assertEqual(legacy["schema"], 1)
            self.assertEqual(next(s["count"] for s in v2["subjects"] if s["id"] == "b_english"), 18)
            self.assertEqual([c["grade"] for c in v2["components"]], [11, 9])


if __name__ == "__main__":
    unittest.main()
