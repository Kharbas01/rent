"""Combine one or more captured/uploaded images into a single multi-page PDF.

Kept deliberately simple for Phase 1: each image is auto-oriented (EXIF),
lightly sharpened/contrast-boosted, and centred on an A4 page. Full AI-based
auto edge-detection and perspective correction is scoped for Phase 2.
"""

from io import BytesIO

from PIL import Image, ImageEnhance, ImageOps
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from app.errors import bad_request

MAX_PAGES = 40


def _auto_enhance(img: Image.Image) -> Image.Image:
    """Light, safe auto-enhance: fix orientation, lift contrast/sharpness a touch."""
    img = ImageOps.exif_transpose(img) or img
    img = img.convert("RGB")
    img = ImageEnhance.Contrast(img).enhance(1.12)
    img = ImageEnhance.Sharpness(img).enhance(1.25)
    img = ImageEnhance.Brightness(img).enhance(1.04)
    return img


def images_to_pdf(image_bytes_list: list[bytes]) -> bytes:
    if not image_bytes_list:
        raise bad_request("No pages to combine into a PDF.")
    if len(image_bytes_list) > MAX_PAGES:
        raise bad_request(f"Too many pages in one document (max {MAX_PAGES}).")

    buffer = BytesIO()
    page_width, page_height = A4
    margin = 8 * mm
    max_w = page_width - 2 * margin
    max_h = page_height - 2 * margin

    c = canvas.Canvas(buffer, pagesize=A4)
    for raw in image_bytes_list:
        try:
            img = Image.open(BytesIO(raw))
            img.load()
        except Exception as exc:  # noqa: BLE001
            raise bad_request("One of the captured pages could not be read as an image.") from exc

        img = _auto_enhance(img)
        img_w, img_h = img.size
        scale = min(max_w / img_w, max_h / img_h)
        draw_w, draw_h = img_w * scale, img_h * scale
        x = (page_width - draw_w) / 2
        y = (page_height - draw_h) / 2

        page_buffer = BytesIO()
        img.save(page_buffer, format="JPEG", quality=88)
        page_buffer.seek(0)

        c.drawImage(ImageReader(page_buffer), x, y, width=draw_w, height=draw_h)
        c.showPage()

    c.save()
    return buffer.getvalue()