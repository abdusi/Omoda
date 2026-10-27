import unittest
from io import BytesIO
from pypdf import PdfReader, PdfWriter
from pypdf.generic import DecodedStreamObject, NameObject
from pdf_clean import without_watermarks


def fixture(content):
    writer = PdfWriter()
    page = writer.add_blank_page(595, 842)
    stream = DecodedStreamObject()
    stream.set_data(content)
    page[NameObject("/Contents")] = writer._add_object(stream)
    output = BytesIO()
    writer.write(output)
    output.seek(0)
    return output


class WatermarkTest(unittest.TestCase):
    def operations(self, content):
        return PdfReader(BytesIO(content)).pages[0].get_contents().operations

    def test_removes_marked_watermark_keeps_formula_and_figure_operations(self):
        before = b"0 g BT (formula x squared) Tj ET 10 20 30 40 re S "
        watermark = b"/Artifact << /Subtype /Watermark >> BDC q .707 .707 -.707 .707 0 0 cm .75 g BT (watermark) Tj ET Q EMC "
        after = b"20 30 m 40 50 l S BT (answer 4) Tj ET"
        cleaned, counts = without_watermarks(fixture(before + watermark + after))
        self.assertEqual([1], counts)
        self.assertEqual(self.operations(cleaned), PdfReader(fixture(before + after)).pages[0].get_contents().operations)

    def test_preserves_unmarked_rotated_text_and_non_watermark_artifacts(self):
        data = b"q .707 .707 -.707 .707 0 0 cm .75 g BT (legitimate figure label) Tj ET Q /Artifact << /Subtype /Header >> BDC BT (header) Tj ET EMC"
        cleaned, counts = without_watermarks(fixture(data))
        self.assertEqual([0], counts)
        self.assertEqual(self.operations(cleaned), PdfReader(fixture(data)).pages[0].get_contents().operations)

    def test_nested_marked_content_does_not_leak_watermark(self):
        data = b"/Artifact << /Subtype /Watermark >> BDC /Span BMC BT (watermark) Tj ET EMC EMC BT (question) Tj ET"
        cleaned, counts = without_watermarks(fixture(data))
        self.assertEqual([1], counts)
        self.assertEqual(self.operations(cleaned), PdfReader(fixture(b"BT (question) Tj ET")).pages[0].get_contents().operations)


if __name__ == "__main__":
    unittest.main()
