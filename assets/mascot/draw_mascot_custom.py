#!/usr/bin/env python3
"""
像素画 PIL 绘制脚本 — 由 png_to_script.py 自动生成
原图尺寸: 32×32
颜色数量: 13
左右对称: 否
"""

from PIL import Image, ImageDraw

W, H = 32, 32
img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
d = ImageDraw.Draw(img)

# ── 调色板 ──
C00 = (34, 157, 255)  # #229DFF
C01 = (255, 254, 254)  # #FFFEFE
C02 = (62, 179, 255)  # #3EB3FF
C03 = (59, 59, 59)  # #3B3B3B
C04 = (168, 168, 171)  # #A8A8AB
C05 = (82, 82, 82)  # #525252
C06 = (48, 48, 48)  # #303030
C07 = (56, 56, 56)  # #383838
C08 = (0, 0, 0)  # #000000
C09 = (23, 106, 173)  # #176AAD
C10 = (242, 105, 146)  # #F26992
C11 = (191, 190, 190)  # #BFBEBE
C12 = (126, 210, 255)  # #7ED2FF

# ── 逐像素绘制 ──
def px(x, y, c):
    if 0 <= x < W and 0 <= y < H:
        d.point((x, y), fill=c)

# 行 7
for x in range(9, 23): px(x, 7, C03)

# 行 8
for x in range(7, 9): px(x, 8, C07)
for x in range(9, 11): px(x, 8, C03)
px(11, 8, C11)
for x in range(12, 14): px(x, 8, C04)
for x in range(14, 18): px(x, 8, C05)
px(18, 8, C11)
for x in range(19, 21): px(x, 8, C04)
for x in range(21, 23): px(x, 8, C03)
for x in range(23, 25): px(x, 8, C07)

# 行 9
px(7, 9, C06)
px(8, 9, C07)
for x in range(9, 11): px(x, 9, C06)
px(11, 9, C04)
px(12, 9, C12)
for x in range(13, 19): px(x, 9, C04)
px(19, 9, C12)
px(20, 9, C04)
for x in range(21, 23): px(x, 9, C06)
px(23, 9, C07)
px(24, 9, C06)

# 行 10
px(7, 10, C06)
px(8, 10, C07)
for x in range(9, 11): px(x, 10, C06)
for x in range(11, 14): px(x, 10, C04)
for x in range(14, 18): px(x, 10, C06)
for x in range(18, 21): px(x, 10, C04)
for x in range(21, 23): px(x, 10, C06)
px(23, 10, C07)
px(24, 10, C06)

# 行 11
px(7, 11, C06)
px(8, 11, C07)
for x in range(9, 23): px(x, 11, C05)
px(23, 11, C07)
px(24, 11, C06)

# 行 12
px(7, 12, C07)
px(8, 12, C00)
for x in range(9, 14): px(x, 12, C01)
for x in range(14, 18): px(x, 12, C00)
for x in range(18, 23): px(x, 12, C01)
px(23, 12, C00)
px(24, 12, C07)

# 行 13
px(8, 13, C00)
px(9, 13, C01)
for x in range(10, 13): px(x, 13, C08)
px(13, 13, C01)
for x in range(14, 18): px(x, 13, C00)
for x in range(18, 20): px(x, 13, C01)
for x in range(20, 22): px(x, 13, C08)
px(22, 13, C01)
px(23, 13, C00)

# 行 14
px(8, 14, C00)
px(9, 14, C01)
for x in range(10, 13): px(x, 14, C08)
px(13, 14, C01)
for x in range(14, 18): px(x, 14, C00)
px(18, 14, C01)
for x in range(19, 22): px(x, 14, C08)
px(22, 14, C01)
px(23, 14, C00)

# 行 15
for x in range(8, 10): px(x, 15, C10)
for x in range(10, 14): px(x, 15, C01)
for x in range(14, 18): px(x, 15, C00)
for x in range(18, 22): px(x, 15, C01)
for x in range(22, 24): px(x, 15, C10)

# 行 16
for x in range(9, 20): px(x, 16, C00)
for x in range(20, 23): px(x, 16, C09)

# 行 17
for x in range(9, 20): px(x, 17, C00)
for x in range(20, 23): px(x, 17, C09)

# 行 18
for x in range(9, 13): px(x, 18, C02)
px(14, 18, C02)
px(17, 18, C02)
px(19, 18, C02)
px(20, 18, C00)
for x in range(21, 23): px(x, 18, C02)

# 行 19
px(9, 19, C02)
px(11, 19, C02)
px(14, 19, C02)
px(17, 19, C02)
px(20, 19, C02)
px(22, 19, C02)

# 行 20
px(8, 20, C09)
px(11, 20, C09)
px(13, 20, C02)
px(18, 20, C02)
px(20, 20, C09)
px(23, 20, C09)

# 行 21
px(7, 21, C02)
px(10, 21, C02)
px(13, 21, C02)
px(18, 21, C02)
px(21, 21, C02)
px(24, 21, C02)

# 行 22
px(6, 22, C02)
px(25, 22, C02)

# ── 升采样 & 保存 ──
out = img.resize((512, 512), Image.NEAREST)
out.save("pixel_art_output.png")
img.save("pixel_art_source.png")
print(f"Done! Sprite: {W}×{H} → 512×512")