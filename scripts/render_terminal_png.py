#!/usr/bin/env python3
"""Render terminal-style text output as PNG for work evidence."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def render_terminal_png(
    text: str,
    output_path: Path,
    *,
    title: str = "",
    width: int = 1200,
    font_size: int = 16,
    padding: int = 24,
    bg_color: str = "#1e1e1e",
    fg_color: str = "#d4d4d4",
    title_color: str = "#569cd6",
    accent_color: str = "#4ec9b0",
) -> None:
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    if title:
        lines = [title, "─" * min(len(title) + 20, 80), *lines]

    try:
        font = ImageFont.truetype("consola.ttf", font_size)
        title_font = ImageFont.truetype("consola.ttf", font_size + 2)
    except OSError:
        try:
            font = ImageFont.truetype("C:/Windows/Fonts/consola.ttf", font_size)
            title_font = ImageFont.truetype("C:/Windows/Fonts/consola.ttf", font_size + 2)
        except OSError:
            font = ImageFont.load_default()
            title_font = font

    line_height = int(font_size * 1.5)
    height = padding * 2 + line_height * len(lines) + 20

    img = Image.new("RGB", (width, height), bg_color)
    draw = ImageDraw.Draw(img)

    # Terminal header bar
    draw.rectangle([0, 0, width, 36], fill="#2d2d2d")
    for i, color in enumerate(["#ff5f56", "#ffbd2e", "#27c93f"]):
        draw.ellipse([16 + i * 22, 12, 28 + i * 22, 26], fill=color)

    y = padding + 20
    for idx, line in enumerate(lines):
        use_font = title_font if idx == 0 and title else font
        color = title_color if idx == 0 and title else fg_color
        if "healthy" in line.lower() or "passed" in line.lower() or "pass" in line.lower() or "8/8" in line:
            color = accent_color
        if "error" in line.lower() and "no error" not in line.lower():
            color = "#f44747"
        draw.text((padding, y), line, fill=color, font=use_font)
        y += line_height

    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, "PNG")


def main() -> None:
    parser = argparse.ArgumentParser(description="Render terminal text as PNG")
    parser.add_argument("input", type=Path, help="Input text file")
    parser.add_argument("output", type=Path, help="Output PNG path")
    parser.add_argument("--title", default="", help="Optional title line")
    args = parser.parse_args()
    text = args.input.read_text(encoding="utf-8", errors="replace")
    render_terminal_png(text, args.output, title=args.title)


if __name__ == "__main__":
    main()
