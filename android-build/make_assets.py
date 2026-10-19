"""Replace Capacitor's placeholder launcher icons and splash screens with the Tokyo Gigs art.

Usage:  python android-build/make_assets.py android/app/src/main/res

Every image keeps the size of the file it replaces, so this keeps working if the
Capacitor template changes its densities or adds splash variants.
"""
import re
import sys
from pathlib import Path

from PIL import Image, ImageDraw

INK = (27, 34, 54)
PINK = (255, 72, 176)
BLUE = (0, 120, 191)
PAPER = (236, 239, 242)


def disc(size: int, scale: float, bg) -> Image.Image:
    """The record motif: pink disc with grooves, centre hole, offset blue 'mis-print' edge."""
    S = size * 4
    im = Image.new("RGBA", (S, S), bg)
    d = ImageDraw.Draw(im)
    r = S * scale / 2
    cx = cy = S / 2
    off = S * scale * 0.032
    d.ellipse([cx - r + off, cy - r + off, cx + r + off, cy + r + off], fill=BLUE)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=PINK)
    for k in (0.78, 0.6):
        rr = r * k
        d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], outline=INK, width=max(2, int(S * scale * 0.01)))
    h = r * 0.2
    d.ellipse([cx - h, cy - h, cx + h, cy + h], fill=PAPER)
    return im.resize((size, size), Image.LANCZOS)


def legacy_icon(w: int, round_: bool) -> Image.Image:
    im = disc(w, 0.74, INK + (255,))
    mask = Image.new("L", (w * 4, w * 4), 0)
    md = ImageDraw.Draw(mask)
    if round_:
        md.ellipse([0, 0, w * 4, w * 4], fill=255)
    else:
        md.rounded_rectangle([0, 0, w * 4, w * 4], radius=w * 4 * 0.18, fill=255)
    im.putalpha(mask.resize((w, w), Image.LANCZOS))
    return im


def splash(w: int, h: int) -> Image.Image:
    im = Image.new("RGB", (w, h), PAPER)
    s = int(min(w, h) * 0.32)
    art = disc(s, 0.9, (0, 0, 0, 0))
    im.paste(art, ((w - s) // 2, (h - s) // 2), art)
    return im


def main(res: Path) -> None:
    done = 0
    for f in sorted(res.rglob("*.png")):
        w, h = Image.open(f).size
        name = f.name
        if name == "ic_launcher_foreground.png":
            # adaptive icon: 108dp canvas, only the middle ~66% is always visible
            disc(w, 0.56, (0, 0, 0, 0)).save(f)
        elif name == "ic_launcher.png":
            legacy_icon(w, round_=False).save(f)
        elif name == "ic_launcher_round.png":
            legacy_icon(w, round_=True).save(f)
        elif name.startswith("splash"):
            splash(w, h).save(f)
        else:
            continue
        done += 1
    bg = res / "values" / "ic_launcher_background.xml"
    if bg.exists():
        bg.write_text(re.sub(r"#[0-9A-Fa-f]{6,8}", "#1B2236", bg.read_text()))
        done += 1
    if done == 0:
        sys.exit(f"no launcher icons or splash images found under {res}")
    print(f"replaced {done} icon/splash files")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
