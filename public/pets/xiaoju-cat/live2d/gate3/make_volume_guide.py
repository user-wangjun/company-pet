from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT.parent.parent / "three-view-preview.png"
OUTPUT = ROOT / "qa" / "gate3-xiaoju-volume-guide.png"


def ellipse(draw, box, color, label, label_xy):
    draw.ellipse(box, fill=color, outline=(255, 255, 255, 230), width=3)
    draw.text(label_xy, label, font=ImageFont.load_default(size=18), fill=(255, 255, 255, 255), stroke_width=2, stroke_fill=(0, 0, 0, 230))


image = Image.open(SOURCE).convert("RGBA")
overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
draw = ImageDraw.Draw(overlay)

# Front-view volumes.
ellipse(draw, (120, 110, 480, 440), (255, 70, 90, 72), "HEAD", (250, 130))
ellipse(draw, (160, 360, 470, 710), (70, 150, 255, 72), "RIBCAGE", (245, 470))
ellipse(draw, (135, 555, 500, 770), (255, 190, 60, 72), "PELVIS", (260, 650))

# Side-view volumes show depth that the prone pose must retain.
ellipse(draw, (635, 105, 930, 455), (255, 70, 90, 72), "HEAD", (735, 130))
ellipse(draw, (730, 300, 1035, 710), (70, 150, 255, 72), "RIBCAGE", (815, 455))
ellipse(draw, (790, 540, 1120, 765), (255, 190, 60, 72), "PELVIS", (900, 645))

# Back view confirms pelvis and ribcage are separate masses.
ellipse(draw, (1280, 105, 1605, 455), (255, 70, 90, 72), "HEAD", (1400, 130))
ellipse(draw, (1290, 310, 1605, 705), (70, 150, 255, 72), "RIBCAGE", (1380, 460))
ellipse(draw, (1260, 545, 1640, 775), (255, 190, 60, 72), "PELVIS", (1410, 650))

draw.rounded_rectangle((18, 18, 640, 86), 8, fill=(0, 0, 0, 185))
draw.text((30, 28), "RED head | BLUE ribcage | GOLD pelvis", font=ImageFont.load_default(size=22), fill=(255, 255, 255, 255))
draw.text((30, 56), "These volumes may overlap and rotate, but may not collapse.", font=ImageFont.load_default(size=18), fill=(255, 255, 255, 255))

Image.alpha_composite(image, overlay).save(OUTPUT)
print(OUTPUT)
