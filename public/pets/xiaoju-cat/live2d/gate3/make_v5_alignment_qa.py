from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter


ROOT = Path(__file__).resolve().parent
PACKAGE = ROOT.parents[1]
CANDIDATE = ROOT / "candidates" / "xiaoju-body-no-forelegs-v5-alpha.png"
EXACT_HEAD_NECK_TAIL = PACKAGE / "live2d" / "planet-scene-source" / "layers-v2" / "10_Cat_Body_Base.png"
PLANET_FOREGROUND = PACKAGE / "live2d" / "planet-scene-source" / "layers-v2" / "50_Planet_Foreground.png"
BACKGROUND = PACKAGE / "live2d" / "planet-background-v1.png"
OUT_EXPANDED = ROOT / "qa" / "gate3-v5-hidden-volume-alignment.png"
OUT_SCENE = ROOT / "qa" / "gate3-v5-scene-alignment.png"


def open_rgba(path: Path) -> Image.Image:
    return Image.open(path).convert("RGBA")


candidate = open_rgba(CANDIDATE)
exact = open_rgba(EXACT_HEAD_NECK_TAIL)
planet = open_rgba(PLANET_FOREGROUND)
background = open_rgba(BACKGROUND)

if candidate.size != exact.size:
    # The generator may round one canvas edge by a pixel. Normalize to the
    # approved 1370x1148 scene before any mask or alignment operation.
    candidate = candidate.resize(exact.size, Image.Resampling.LANCZOS)

if not (candidate.size == exact.size == planet.size == background.size):
    raise ValueError("Gate 3 alignment inputs must share the 1370x1148 scene canvas")

# v5 is not allowed to replace approved visible identity pixels. Retain only
# its hidden torso/hip/hind-limb material, with a feathered transition beneath
# the approved neck. Suppress its separate tail because the original tail is
# already an approved unique visual source.
keep = Image.new("L", candidate.size, 0)
draw = ImageDraw.Draw(keep)
draw.rectangle((300, 540, candidate.width, candidate.height), fill=255)
draw.polygon(((300, 540), (465, 500), (760, 520), (970, 650), (970, 790), (300, 790)), fill=255)
draw.polygon(((90, 570), (350, 570), (430, 760), (430, 1010), (165, 1010), (80, 840)), fill=255)
keep = keep.filter(ImageFilter.GaussianBlur(18))

candidate_alpha = candidate.getchannel("A")
candidate.putalpha(Image.composite(candidate_alpha, Image.new("L", candidate.size, 0), keep))

# Keep the approved head and tail, but do not keep the old triangular neck
# cutout all the way to the bottom of the canvas. A soft lower head/neck overlap
# lets the reconstructed chest continue underneath without a paper-cut seam.
exact_keep = Image.new("L", exact.size, 0)
exact_draw = ImageDraw.Draw(exact_keep)
exact_draw.ellipse((315, -90, 1175, 785), fill=255)
exact_draw.polygon(((310, 560), (485, 500), (830, 575), (790, 735), (470, 770), (330, 700)), fill=255)
exact_draw.polygon(((55, 540), (325, 540), (345, 990), (245, 1095), (55, 975)), fill=255)
exact_keep = exact_keep.filter(ImageFilter.GaussianBlur(12))
exact_alpha = exact.getchannel("A")
exact.putalpha(Image.composite(exact_alpha, Image.new("L", exact.size, 0), exact_keep))

expanded = Image.new("RGBA", candidate.size, (20, 22, 28, 255))
expanded.alpha_composite(candidate)
expanded.alpha_composite(exact)
expanded.save(OUT_EXPANDED)

scene = background.copy()
scene.alpha_composite(candidate)
scene.alpha_composite(exact)
scene.alpha_composite(planet)
scene.save(OUT_SCENE)

print(OUT_EXPANDED)
print(OUT_SCENE)
