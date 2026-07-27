#!/usr/bin/env python3
"""Genera le icone PWA in public/icons/ (da rilanciare solo se cambia la grafica)."""
import pathlib
from PIL import Image, ImageDraw

OUT = pathlib.Path(__file__).resolve().parent.parent / "public" / "icons"
BG, GOLD, DIM = "#0a0a0b", "#c8a24b", "#3fa372"


def draw(size: int, padding: float) -> Image.Image:
    """Tre candele ascendenti su fondo scuro: leggibile anche a 60px."""
    s = size * 4  # supersampling
    img = Image.new("RGB", (s, s), BG)
    d = ImageDraw.Draw(img)
    p = s * padding
    w = s - 2 * p

    body = w * 0.20
    wick = max(2, int(w * 0.035))
    # (centro x, cima corpo, fondo corpo, colore) — scala ascendente
    candles = (
        (0.16, 0.62, 0.92, DIM),
        (0.50, 0.38, 0.74, GOLD),
        (0.84, 0.10, 0.52, GOLD),
    )
    for fx, top, bot, col in candles:
        cx = p + w * fx
        d.line([(cx, p + w * (top - 0.08)), (cx, p + w * (bot + 0.06))], fill=col, width=wick)
        d.rounded_rectangle(
            [cx - body / 2, p + w * top, cx + body / 2, p + w * bot],
            radius=body * 0.28, fill=col,
        )
    return img.resize((size, size), Image.LANCZOS)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, size, pad in (
        ("icon-180.png", 180, 0.17),
        ("icon-192.png", 192, 0.17),
        ("icon-512.png", 512, 0.17),
        ("icon-maskable-512.png", 512, 0.27),  # margine per il crop circolare Android
    ):
        draw(size, pad).save(OUT / name)
        print("scritta:", OUT / name)


if __name__ == "__main__":
    main()
