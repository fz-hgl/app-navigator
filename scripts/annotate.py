#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
annotate.py — 在 APP 截图上画操作标注（红框 + 序号 + 中文标签 + 箭头）

坐标采用归一化 0-1000 体系：左上角 [0,0]，右下角 [1000,1000]，
与图片实际像素尺寸无关，便于看图后直接给出。

用法：
  python annotate.py --image <原图> --output <输出图> --marks '<JSON数组>'
  python annotate.py --image <原图> --output <输出图> --marks-file <marks.json>

marks 示例：
  [
    {"seq":1, "shape":"box",   "box":[120,300,880,420], "label":"点这里"},
    {"seq":2, "shape":"point", "point":[500,150],       "label":"搜索框"}
  ]
可选字段 "color": "#RRGGBB" 可覆盖单个标注颜色。
"""
import argparse
import json
import math
import os
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

NORM = 1000.0
FONT_CANDIDATES = [
    "C:/Windows/Fonts/msyhbd.ttc",
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/simhei.ttf",
    "C:/Windows/Fonts/simsun.ttc",
    "/System/Library/Fonts/PingFang.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]

RED = (230, 52, 43, 255)
WHITE = (255, 255, 255, 255)
LABEL_BG = (22, 22, 24, 225)


def hex2rgba(s, default=RED):
    if not s:
        return default
    s = s.lstrip("#")
    if len(s) != 6:
        return default
    try:
        return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4)) + (255,)
    except ValueError:
        return default


def load_font(size):
    for p in FONT_CANDIDATES:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    return ImageFont.load_default()


def norm_to_px(coord, w, h):
    return (
        max(0, min(w - 1, int(round(coord[0] / NORM * w)))),
        max(0, min(h - 1, int(round(coord[1] / NORM * h)))),
    )


def draw_arrow(draw, start, end, color, width, head_len):
    draw.line([start, end], fill=color, width=width)
    ang = math.atan2(end[1] - start[1], end[0] - start[0])
    a1 = (end[0] - head_len * math.cos(ang - 0.5), end[1] - head_len * math.sin(ang - 0.5))
    a2 = (end[0] - head_len * math.cos(ang + 0.5), end[1] - head_len * math.sin(ang + 0.5))
    draw.polygon([end, a1, a2], fill=color)


def main():
    ap = argparse.ArgumentParser(description="在截图上画操作标注")
    ap.add_argument("--image", required=True, help="原图路径")
    ap.add_argument("--output", required=True, help="输出图路径")
    ap.add_argument("--marks", help="标注 JSON 数组字符串")
    ap.add_argument("--marks-file", help="标注 JSON 文件路径（推荐，避免中文转义问题）")
    args = ap.parse_args()

    if args.marks_file:
        with open(args.marks_file, "r", encoding="utf-8") as f:
            marks = json.load(f)
    elif args.marks:
        marks = json.loads(args.marks)
    else:
        print("ERROR: need --marks or --marks-file", file=sys.stderr)
        sys.exit(1)

    if not isinstance(marks, list):
        print("ERROR: marks must be a JSON array", file=sys.stderr)
        sys.exit(1)

    img = Image.open(args.image).convert("RGBA")
    w, h = img.size
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    base = max(12, int(min(w, h) * 0.012))
    font_label = load_font(max(18, int(base * 1.6)))
    font_seq = load_font(max(16, int(base * 1.4)))
    drawn = 0

    for m in marks:
        seq = m.get("seq")
        label = m.get("label", "")
        shape = m.get("shape", "box")
        color = hex2rgba(m.get("color"), RED)

        if shape == "box":
            p1 = norm_to_px(m["box"][:2], w, h)
            p2 = norm_to_px(m["box"][2:4], w, h)
            x1, x2 = min(p1[0], p2[0]), max(p1[0], p2[0])
            y1, y2 = min(p1[1], p2[1]), max(p1[1], p2[1])
            draw.rounded_rectangle([x1, y1, x2, y2], radius=base,
                                   outline=color, width=max(3, base // 2))
            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
            anchor_x, anchor_y = x1, y1
        elif shape == "point":
            cx, cy = norm_to_px(m["point"], w, h)
            r = max(18, int(base * 1.8))
            draw.ellipse([cx - r, cy - r, cx + r, cy + r],
                         outline=color, width=max(3, base // 2))
            draw.ellipse([cx - r // 4, cy - r // 4, cx + r // 4, cy + r // 4], fill=color)
            x1, y1, x2, y2 = cx - r, cy - r, cx + r, cy + r
            anchor_x, anchor_y = x1, y1
        else:
            continue
        drawn += 1

        if seq is not None:
            r = max(16, int(base * 1.5))
            sx, sy = anchor_x, anchor_y
            draw.ellipse([sx - r, sy - r, sx + r, sy + r], fill=color)
            txt = str(seq)
            bbox = draw.textbbox((0, 0), txt, font=font_seq)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            draw.text((sx - tw / 2, sy - th / 2 - bbox[1]), txt, fill=WHITE, font=font_seq)

        if label:
            bbox = draw.textbbox((0, 0), label, font=font_label)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            pad = max(6, base // 2)
            lw, lh = tw + pad * 2, th + pad * 2
            lx = max(4, min(w - lw - 4, cx - lw / 2))
            if y1 - lh - base > 4:
                ly = y1 - lh - base
                arrow_start, arrow_end = (cx, ly + lh), (cx, y1)
            else:
                ly = min(h - lh - 4, y2 + base)
                arrow_start, arrow_end = (cx, ly), (cx, y2)
            draw.rounded_rectangle([lx, ly, lx + lw, ly + lh], radius=base,
                                   fill=LABEL_BG, outline=color, width=max(2, base // 3))
            draw.text((lx + pad, ly + pad - bbox[1]), label, fill=WHITE, font=font_label)
            draw_arrow(draw, arrow_start, arrow_end, color,
                       max(2, base // 4), max(8, base))

    out = Image.alpha_composite(img, overlay).convert("RGB")
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out.save(out_path)
    print(json.dumps({"ok": True, "output": str(out_path), "size": [w, h], "marks": drawn},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
