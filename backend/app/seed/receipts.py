"""Receipt images drawn from text on an off-white background, so the demonstration needs no stock photos. The same name
always gives the same bytes, which is what lets two expenses carry an identical receipt."""

from io import BytesIO

from PIL import Image, ImageDraw, ImageFont

from app.seed.data import RECEIPTS

WIDTH, HEIGHT = 480, 640
PAPER = (250, 248, 240)
INK = (40, 40, 48)
RULE = (190, 186, 176)


def receipt_image(name: str) -> bytes:
    shop, number, amount, lines = RECEIPTS[name]
    image = Image.new("RGB", (WIDTH, HEIGHT), PAPER)
    draw = ImageDraw.Draw(image)
    title = ImageFont.load_default(size=26)
    body = ImageFont.load_default(size=20)
    draw.text((30, 36), shop, fill=INK, font=title)
    draw.line([(30, 84), (WIDTH - 30, 84)], fill=RULE, width=2)
    draw.text((30, 104), f"Receipt no. {number}", fill=INK, font=body)
    row = 168
    for line in lines:
        draw.text((30, row), line, fill=INK, font=body)
        row += 36
    draw.line([(30, row + 12), (WIDTH - 30, row + 12)], fill=RULE, width=2)
    draw.text((30, row + 36), "Total (PKR)", fill=INK, font=body)
    draw.text((290, row + 36), amount, fill=INK, font=title)
    draw.text((30, HEIGHT - 70), "Thank you", fill=RULE, font=body)
    out = BytesIO()
    image.save(out, format="JPEG", quality=88)
    return out.getvalue()
