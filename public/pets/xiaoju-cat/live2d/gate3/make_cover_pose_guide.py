from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "qa" / "gate3-composite.png"
OUTPUT = ROOT / "qa" / "gate3-cover-pose-skeleton-guide.png"


def label(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, color: tuple[int, int, int, int]) -> None:
    font = ImageFont.load_default(size=18)
    x, y = xy
    box = draw.textbbox((x, y), text, font=font, stroke_width=2)
    draw.rounded_rectangle((box[0] - 5, box[1] - 3, box[2] + 5, box[3] + 3), 5, fill=(0, 0, 0, 170))
    draw.text((x, y), text, font=font, fill=color, stroke_width=2, stroke_fill=(0, 0, 0, 230))


def chain(draw: ImageDraw.ImageDraw, points: list[tuple[int, int]], color: tuple[int, int, int, int], width: int) -> None:
    draw.line(points, fill=color, width=width, joint="curve")
    for x, y in points:
        r = 11
        draw.ellipse((x - r, y - r, x + r, y + r), fill=color, outline=(255, 255, 255, 255), width=3)


image = Image.open(SOURCE).convert("RGBA")
veil = Image.new("RGBA", image.size, (0, 0, 0, 0))
draw = ImageDraw.Draw(veil)

# De-emphasize the source art while retaining the approved composition.
draw.rectangle((0, 0, image.width, image.height), fill=(4, 8, 24, 72))

rest_l = [(480, 765), (525, 820), (610, 815), (670, 785)]
rest_r = [(930, 710), (1005, 735), (1070, 690), (1100, 650)]
cover_l = [(480, 765), (535, 650), (610, 520), (685, 420)]
cover_r = [(930, 710), (990, 610), (910, 500), (875, 405)]

chain(draw, rest_l, (66, 224, 255, 225), 10)
chain(draw, rest_r, (66, 224, 255, 225), 10)
chain(draw, cover_l, (255, 66, 190, 245), 13)
chain(draw, cover_r, (255, 66, 190, 245), 13)

body = [(760, 650), (705, 790), (610, 900), (500, 980), (365, 950)]
chain(draw, body, (255, 200, 48, 235), 11)

for point in [(520, 860), (920, 735)]:
    x, y = point
    draw.rectangle((x - 14, y - 14, x + 14, y + 14), fill=(90, 255, 110, 235), outline=(255, 255, 255, 255), width=3)

label(draw, (30, 34), "CYAN: rest on rim", (66, 224, 255, 255))
label(draw, (30, 66), "MAGENTA: cover eyes", (255, 66, 190, 255))
label(draw, (30, 98), "YELLOW: neck -> chest -> pelvis -> tail root", (255, 200, 48, 255))
label(draw, (30, 130), "GREEN: chest contact locks", (90, 255, 110, 255))

Image.alpha_composite(image, veil).save(OUTPUT)
print(OUTPUT)
