# MDPilot 吉祥物设计文档

## 吉祥物概述

MDPilot 的吉祥物是一只**像素风章鱼**，佩戴飞行员头盔，风格简洁、居中、萌系可爱。

### 设计特征

| 特征 | 描述 |
|------|------|
| 类型 | 像素风章鱼 |
| 画布 | 36×36 → 512×512 (NEAREST 升采样) |
| 头饰 | 飞行员头盔：护目镜推额头 + 耳机罩 + 镜带 |
| 眼睛 | 萌系大眼 5×4（日系 moe 风格），3 个白色高光，无嘴 |
| 腮红 | 粉色腮红 (255, 160, 170) |
| 触手 | 6 条短触手外展（扇形分布，50°/30°/10°/10°/30°/50°） |
| 锥形 | 根部 2px → 尖端 1px |
| 禁忌 | 无分子元素（纯飞行员形象） |

### 配色表

```
HELMET        = (70, 78, 90)       深灰岩色
HELMET_HI     = (100, 108, 120)    高光
HELMET_DARK   = (50, 55, 65)       阴影
GOGGLE_FRAME  = (180, 185, 195)    银色镜框
GOGGLE_LENS   = (80, 140, 180)     蓝色镜片
GOGGLE_HI     = (200, 220, 240)    镜片反光
STRAP         = (90, 95, 105)      镜带
EARPAD        = (60, 65, 75)       耳罩
BODY          = (88, 166, 255)     蓝色身体
BODY_DARK     = (55, 120, 210)     身体阴影
EYE_WHITE     = (255, 255, 255)    眼白
EYE_BLACK     = (30, 30, 30)       瞳孔
BLUSH         = (255, 160, 170)    腮红
TENTACLE      = (100, 180, 255)    触手
```

### 居中验证

```
Visual center: (18.0, 18.5)
Canvas center:  (18, 18)
Offset: (+0.0, +0.5)  ← 基本完美
```

---

## 文件清单

| 文件 | 说明 |
|------|------|
| `mdpilot_octopus.jpg` | 原始终版吉祥物图片（来自会话产出） |
| `mdpilot_octopus_recreated.png` | 脚本复刻版 512×512 |
| `mdpilot_octopus_36x36_source.png` | 脚本复刻版 36×36 像素源图 |
| `draw_mascot.py` | 完整 Python 绘制脚本 |
| `mascot-design-guide.md` | 本文档 |

---

## 完整绘制脚本

```python
#!/usr/bin/env python3
"""
MDPilot Mascot — Pixel Art Octopus with Pilot Helmet
Canvas: 36×36 → 512×512 (NEAREST upscale)

V13 FINAL — Centered at (18.0, ~18.5) ≈ (18, 18)
"""

from PIL import Image, ImageDraw

size = 36
cx = size // 2  # 18
img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)

# ── Color Palette ───────────────────────────────────────
HELMET       = (70, 78, 90)
HELMET_HI    = (100, 108, 120)
HELMET_DARK  = (50, 55, 65)
GOGGLE_FRAME = (180, 185, 195)
GOGGLE_LENS  = (80, 140, 180)
GOGGLE_HI    = (200, 220, 240)
STRAP        = (90, 95, 105)
EARPAD       = (60, 65, 75)
BODY         = (88, 166, 255)
BODY_DARK    = (55, 120, 210)
EYE_WHITE    = (255, 255, 255)
EYE_BLACK    = (30, 30, 30)
BLUSH        = (255, 160, 170)
TENTACLE     = (100, 180, 255)

Y = 4  # vertical offset for centering

# ── Helper ──────────────────────────────────────────────
def draw_tapered(points, color=TENTACLE):
    n = len(points)
    for i, (x, y) in enumerate(points):
        if i < max(n // 3, 1):
            for t in range(2):
                px = x + t
                if 0 <= px < size and 0 <= y < size:
                    draw.point((px, y), fill=color)
        else:
            if 0 <= x < size and 0 <= y < size:
                draw.point((x, y), fill=color)

# ── Section 1: Pilot Helmet (rows 3+Y – 7+Y) ──────────
for y in range(3 + Y, 8 + Y):
    for x in range(cx - 7, cx + 7):
        draw.point((x, y), fill=HELMET)
for x in range(cx - 4, cx + 4):
    draw.point((x, 3 + Y), fill=HELMET_HI)
for x in range(cx - 7, cx - 4):
    draw.point((x, 7 + Y), fill=HELMET_DARK)
for x in range(cx + 4, cx + 7):
    draw.point((x, 7 + Y), fill=HELMET_DARK)

# Goggles on forehead
for y in range(6 + Y, 8 + Y):
    for x in range(cx - 6, cx - 2):
        draw.point((x, y), fill=GOGGLE_FRAME)
    for x in range(cx - 5, cx - 3):
        draw.point((x, y), fill=GOGGLE_LENS)
    for x in range(cx + 1, cx + 5):
        draw.point((x, y), fill=GOGGLE_FRAME)
    for x in range(cx + 2, cx + 4):
        draw.point((x, y), fill=GOGGLE_LENS)
draw.point((cx - 5, 6 + Y), fill=GOGGLE_HI)
draw.point((cx + 2, 6 + Y), fill=GOGGLE_HI)
for x in range(cx - 2, cx + 1):
    draw.point((x, 7 + Y), fill=GOGGLE_FRAME)

# Ear pads
for y in range(5 + Y, 8 + Y):
    for x in range(cx - 9, cx - 7):
        draw.point((x, y), fill=EARPAD)
    for x in range(cx + 7, cx + 9):
        draw.point((x, y), fill=EARPAD)

# Strap
for x in range(cx - 9, cx + 9):
    draw.point((x, 5 + Y), fill=STRAP)

# ── Section 2: Body (rows 8+Y – 20+Y) ──────────────────
for y in range(8 + Y, 21 + Y):
    w = 8 if y < 10 + Y else 9
    for x in range(cx - w, cx + w):
        draw.point((x, y), fill=BODY)
for y in range(14 + Y, 21 + Y):
    for x in range(cx + 4, cx + 9):
        if 0 <= x < size and 0 <= y < size and img.getpixel((x, y))[3] > 0:
            draw.point((x, y), fill=BODY_DARK)

# ── Section 3: Moe Eyes (5×4 each) ─────────────────────
ey = 11 + Y

# Left eye
for y in range(ey, ey + 4):
    for x in range(cx - 7, cx - 2):
        draw.point((x, y), fill=EYE_WHITE)
draw.point((cx - 7, ey), fill=(0, 0, 0, 0))
draw.point((cx - 3, ey), fill=(0, 0, 0, 0))
for y in range(ey + 1, ey + 3):
    for x in range(cx - 6, cx - 3):
        draw.point((x, y), fill=EYE_BLACK)
draw.point((cx - 3, ey + 1), fill=EYE_WHITE)
draw.point((cx - 5, ey),     fill=EYE_WHITE)
draw.point((cx - 6, ey + 1), fill=EYE_WHITE)

# Right eye
for y in range(ey, ey + 4):
    for x in range(cx + 2, cx + 7):
        draw.point((x, y), fill=EYE_WHITE)
draw.point((cx + 2, ey), fill=(0, 0, 0, 0))
draw.point((cx + 6, ey), fill=(0, 0, 0, 0))
for y in range(ey + 1, ey + 3):
    for x in range(cx + 3, cx + 6):
        draw.point((x, y), fill=EYE_BLACK)
draw.point((cx + 2, ey + 1), fill=EYE_WHITE)
draw.point((cx + 4, ey),     fill=EYE_WHITE)
draw.point((cx + 5, ey + 1), fill=EYE_WHITE)

# Blush
for x in range(cx - 9, cx - 7):
    draw.point((x, ey + 2), fill=BLUSH)
    draw.point((x, ey + 3), fill=BLUSH)
for x in range(cx + 7, cx + 9):
    draw.point((x, ey + 2), fill=BLUSH)
    draw.point((x, ey + 3), fill=BLUSH)

# ── Section 4: 6 Tapered Tentacles ─────────────────────
tb = 21 + Y
t1 = [(cx - 5, tb), (cx - 7, tb + 2), (cx - 9, tb + 3), (cx - 10, tb + 4)]
t2 = [(cx - 3, tb), (cx - 4, tb + 2), (cx - 5, tb + 3), (cx - 6, tb + 4)]
t3 = [(cx - 1, tb), (cx - 1, tb + 2), (cx - 2, tb + 3), (cx - 2, tb + 4)]
t4 = [(cx + 1, tb), (cx + 1, tb + 2), (cx + 1, tb + 3), (cx + 1, tb + 4)]
t5 = [(cx + 3, tb), (cx + 4, tb + 2), (cx + 5, tb + 3), (cx + 5, tb + 4)]
t6 = [(cx + 5, tb), (cx + 7, tb + 2), (cx + 8, tb + 3), (cx + 9, tb + 4)]
for t in [t1, t2, t3, t4, t5, t6]:
    draw_tapered(t)

# ── Centering Check ────────────────────────────────────
bbox = img.getbbox()
vcx = (bbox[0] + bbox[2]) / 2
vcy = (bbox[1] + bbox[3]) / 2
print(f"Center: ({vcx:.1f}, {vcy:.1f}) vs ({cx}, {cx})")

# ── Upscale & Save ─────────────────────────────────────
out = img.resize((512, 512), Image.NEAREST)
out.save("mdpilot_octopus_recreated.png")
img.save("mdpilot_octopus_36x36_source.png")
```

---

## 迭代历史

```
V1:  基础形状 + 头盔面罩 + DNA 螺旋，5 触手，32×32
V2:  飞行员头盔（护目镜、耳罩、原子轨道模型）
V3:  5→2 触手，对称弯曲
V4:  4 触手，对称
V5:  4 触手等距
V6:  萌系眼睛（3×4），腮红，4 触手
V7:  萌系眼睛 5×4，4 触手 V 形扇面
V8:  6 触手，画布→36×36
V9:  去除嘴巴
V10: DNA 螺旋王冠
V11: 去除所有分子元素，纯飞行员
V12: 触手缩短至 1/3，重新居中
V13: 锥形触手（2px→1px），自然扇形角度，居中 (18.0, 18.5)≈(18,18)
```
