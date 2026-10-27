"""Remove only PDF content explicitly tagged /Artifact /Subtype /Watermark.

No pixel erasing or colour thresholding: original text, formulae and drawings
outside the tagged block remain byte-for-byte identical as PDF operations.
"""
from io import BytesIO
from pypdf import PdfReader, PdfWriter


def without_watermarks(path):
    reader = PdfReader(path)
    writer = PdfWriter()
    removed = []
    for page in reader.pages:
        target = writer.add_page(page)
        content = target.get_contents()
        kept, stack, count = [], [], 0
        for operands, operator in content.operations:
            if operator in (b"BDC", b"BMC"):
                props = operands[1] if operator == b"BDC" and len(operands) > 1 else None
                if hasattr(props, "get_object"):
                    props = props.get_object()
                watermark = hasattr(props, "get") and props.get("/Subtype") == "/Watermark"
                parent_removed = any(stack)
                stack.append(bool(watermark) or parent_removed)
                if watermark and not parent_removed:
                    count += 1
                if not stack[-1]:
                    kept.append((operands, operator))
            elif operator == b"EMC":
                dropping = stack.pop() if stack else False
                if not dropping:
                    kept.append((operands, operator))
            elif not any(stack):
                kept.append((operands, operator))
        assert not stack, "Unbalanced marked content"
        content.operations = kept
        target.replace_contents(content)
        removed.append(count)
    output = BytesIO()
    writer.write(output)
    return output.getvalue(), removed
