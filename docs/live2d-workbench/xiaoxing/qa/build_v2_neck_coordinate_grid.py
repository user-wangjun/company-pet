from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'source/masters/gate3-line-master-candidate-v1.png'
OUT=ROOT/'qa/v2-neck-coordinate-grid.png'
box=(195,205,310,270); scale=6
im=Image.open(SOURCE).convert('RGB').crop(box).resize(((box[2]-box[0])*scale,(box[3]-box[1])*scale),Image.Resampling.NEAREST)
board=Image.new('RGB',(im.width+40,im.height+40),'white'); board.paste(im,(30,30)); d=ImageDraw.Draw(board)
for x in range(box[0],box[2]+1,5):
    sx=30+(x-box[0])*scale; d.line((sx,30,sx,30+im.height),fill=(70,140,240),width=1); d.text((sx+1,31),str(x),fill=(30,80,160),font=ImageFont.load_default())
for y in range(box[1],box[3]+1,5):
    sy=30+(y-box[1])*scale; d.line((30,sy,30+im.width,sy),fill=(70,140,240),width=1); d.text((31,sy+1),str(y),fill=(30,80,160),font=ImageFont.load_default())
d.text((30,8),'领口原始线稿坐标网格（5px）',fill=(20,30,40),font=ImageFont.load_default()); board.save(OUT); print(OUT)
