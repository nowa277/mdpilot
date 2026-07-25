#!/usr/bin/env python3
"""
PNG → PIL 绘制脚本转换器
将任意像素画 PNG 自动转换为 Python PIL 逐像素绘制脚本。

用法：
  python png_to_script.py input.png [output.py]

输出脚本可直接运行，复刻原图（NEAREST 升采样到 512×512）。
"""

import sys
import os
from PIL import Image

def analyze_colors(img):
    """提取所有非透明颜色及其坐标"""
    colors = {}
    w, h = img.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = img.getpixel((x, y))
            if a > 0:
                hex_color = f"#{r:02X}{g:02X}{b:02X}"
                if hex_color not in colors:
                    colors[hex_color] = (r, g, b)
    return colors

def find_symmetry_axis(img):
    """检测是否左右对称"""
    w, h = img.size
    cx = w // 2
    asym = 0
    for y in range(h):
        for x in range(cx):
            mx = w - 1 - x
            if mx < w:
                lp = img.getpixel((x, y))
                rp = img.getpixel((mx, y))
                if lp != rp and (lp[3] > 0 or rp[3] > 0):
                    asym += 1
    return asym == 0

def generate_script(img, output_path):
    """生成 PIL 绘制脚本"""
    w, h = img.size
    colors = analyze_colors(img)
    is_sym = find_symmetry_axis(img)

    # 颜色命名（按出现频率排序）
    color_coords = {}
    for y in range(h):
        for x in range(w):
            r, g, b, a = img.getpixel((x, y))
            if a > 0:
                hc = f"#{r:02X}{g:02X}{b:02X}"
                if hc not in color_coords:
                    color_coords[hc] = []
                color_coords[hc].append((x, y))

    # 按坐标数量排序命名
    sorted_colors = sorted(color_coords.items(), key=lambda x: -len(x[1]))
    color_names = {}
    for i, (hc, _) in enumerate(sorted_colors):
        color_names[hc] = f"C{i:02d}"

    lines = []
    lines.append('#!/usr/bin/env python3')
    lines.append('"""')
    lines.append(f'像素画 PIL 绘制脚本 — 由 png_to_script.py 自动生成')
    lines.append(f'原图尺寸: {w}×{h}')
    lines.append(f'颜色数量: {len(colors)}')
    lines.append(f'左右对称: {"是" if is_sym else "否"}')
    lines.append('"""')
    lines.append('')
    lines.append('from PIL import Image, ImageDraw')
    lines.append('')
    lines.append(f'W, H = {w}, {h}')
    lines.append('img = Image.new("RGBA", (W, H), (0, 0, 0, 0))')
    lines.append('d = ImageDraw.Draw(img)')
    lines.append('')
    lines.append('# ── 调色板 ──')

    for hc, coords in sorted_colors:
        name = color_names[hc]
        rgb = colors[hc]
        lines.append(f'{name} = {rgb}  # {hc}')

    lines.append('')
    lines.append('# ── 逐像素绘制 ──')
    lines.append('def px(x, y, c):')
    lines.append('    if 0 <= x < W and 0 <= y < H:')
    lines.append('        d.point((x, y), fill=c)')
    lines.append('')

    # 按行分组绘制，每行注释
    for y in range(h):
        row_pixels = []
        for x in range(w):
            r, g, b, a = img.getpixel((x, y))
            if a > 0:
                hc = f"#{r:02X}{g:02X}{b:02X}"
                row_pixels.append((x, color_names[hc]))

        if row_pixels:
            lines.append(f'# 行 {y}')
            # 合并连续同色像素
            runs = []
            current_x, current_c = row_pixels[0]
            run_start = current_x
            for x, c in row_pixels[1:]:
                if c == current_c and x == current_x + 1:
                    current_x = x
                else:
                    runs.append((run_start, current_x, current_c))
                    current_x, current_c = x, c
                    run_start = x
            runs.append((run_start, current_x, current_c))

            for start, end, c in runs:
                if start == end:
                    lines.append(f'px({start}, {y}, {c})')
                else:
                    lines.append(f'for x in range({start}, {end + 1}): px(x, {y}, {c})')
            lines.append('')

    # 升采样保存
    lines.append('# ── 升采样 & 保存 ──')
    lines.append('out = img.resize((512, 512), Image.NEAREST)')
    lines.append('out.save("pixel_art_output.png")')
    lines.append('img.save("pixel_art_source.png")')
    lines.append('print(f"Done! Sprite: {W}×{H} → 512×512")')

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    print(f"Generated: {output_path}")
    print(f"  Size: {w}×{h}")
    print(f"  Colors: {len(colors)}")
    print(f"  Symmetric: {is_sym}")
    print(f"  Lines: {len(lines)}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python png_to_script.py input.png [output.py]")
        print("")
        print("将像素画 PNG 转换为 PIL 逐像素绘制脚本。")
        print("输出脚本可直接 python 运行，复刻原图。")
        sys.exit(1)

    input_png = sys.argv[1]
    if len(sys.argv) >= 3:
        output_py = sys.argv[2]
    else:
        base = os.path.splitext(input_png)[0]
        output_py = f"{base}_script.py"

    img = Image.open(input_png).convert("RGBA")
    generate_script(img, output_py)
