from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'source/masters/gate3-line-master-candidate-v1.png'
OUT=ROOT/'qa/v2-leg-coordinate-grid.png'
box=(145,610,355,900); scale=3
im=Image.open(SOURCE).convert('RGB').crop(box).resize(((box[2]-box[0])*scale,(box[3]-box[1])*scale),Image.Resampling.NEAREST)
board=Image.new('RGB',(im.width+55,im.height+55),'white'); board.paste(im,(45,45)); d=ImageDraw.Draw(board)
for x in range(box[0],box[2]+1,5):
    sx=45+(x-box[0])*scale; d.line((sx,45,sx,45+im.height),fill=(70,140,240),width=1); d.text((sx+1,46),str(x),fill=(30,80,160),font=ImageFont.load_default())
for y in range(box[1],box[3]+1,5):
    sy=45+(y-box[1])*scale; d.line((45,sy,45+im.width,sy),fill=(70,140,240),width=1); d.text((46,sy+1),str(y),fill=(30,80,160),font=ImageFont.load_default())
d.text((45,10),'双腿原始线稿坐标网格（5px）',fill=(20,30,40),font=ImageFont.load_default()); board.save(OUT); print(OUT)
