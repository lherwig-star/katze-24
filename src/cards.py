"""Deal-Karten als fertiges Bild (PNG) fuer Instagram/Facebook-Posts.

Nutzt Pillow (reines Python) statt HTML+Screenshot-Tool - damit laeuft das
genauso einfach im Cloud-Crawl wie der Rest der Pipeline, ohne dass ein
Browser (Playwright/Chromium) heruntergeladen werden muss.

Farben/Schrift sind bewusst als Konstanten oben in der Datei, damit ihr das
Design anpassen koennt (z.B. wenn ihr ein echtes Logo statt der gezeichneten
Pfote habt), ohne den Rest der Logik verstehen zu muessen.

Emojis sind hier bewusst NICHT genutzt: Pillow kann farbige Emoji-Glyphen
nur mit Zusatzaufwand (COLR/Bitmap-Fonts, versionsabhaengig) rendern - die
Pfote wird deshalb aus einfachen Kreisen gezeichnet statt "🐾" zu schreiben.
"""

from __future__ import annotations

import io
import logging
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont

from src.models import Deal

log = logging.getLogger(__name__)

SIZE = 1080  # Instagram/Facebook-Quadrat
BG = "#FDF6EC"
ACCENT = "#E8734A"
DARK = "#2B2320"
GRAY = "#9C9188"
WHITE = "#FFFFFF"
PLACEHOLDER_BG = "#F3ECE1"

FONT_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"

CATEGORY_LABELS = {
    "Futter": "FUTTER",
    "Streu": "STREU",
    "Spielzeug": "SPIELZEUG",
}


def _font(weight: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT_DIR / f"Poppins-{weight}.ttf"), size)


def _draw_paw(draw: ImageDraw.ImageDraw, x: float, y: float,
              scale: float = 1.0, fill: str = ACCENT) -> None:
    """Einfache Pfoten-Form aus Kreisen - kein Emoji-Font noetig."""
    r = 22 * scale
    draw.ellipse([x - r, y - r, x + r, y + r], fill=fill)
    toe_r = 9 * scale
    for ox, oy in [(-20, -30), (0, -36), (20, -30), (-32, -8)]:
        cx, cy = x + ox * scale, y + oy * scale
        draw.ellipse([cx - toe_r, cy - toe_r, cx + toe_r, cy + toe_r], fill=fill)


def _fetch_product_image(url: str | None) -> Image.Image | None:
    """Echtes Produktfoto vom Shop laden. None bei Fehlern - dann zeigt
    build_card() stattdessen einen gezeichneten Platzhalter."""
    if not url:
        return None
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        return Image.open(io.BytesIO(resp.content)).convert("RGBA")
    except Exception:
        log.warning("Produktbild nicht ladbar: %s", url)
        return None


def _wrap_text(
    draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: float
) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        trial = f"{current} {word}".strip()
        if draw.textlength(trial, font=font) <= max_width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _eur(cents: float) -> str:
    return f"{cents / 100:.2f} €".replace(".", ",")


def build_card(deal: Deal) -> Image.Image:
    """Eine fertige Deal-Karte (1080x1080 PNG) fuer Instagram/Facebook."""
    o = deal.offer
    img = Image.new("RGB", (SIZE, SIZE), BG)
    draw = ImageDraw.Draw(img)

    bold_brand = _font("Bold", 30)
    bold_price = _font("Bold", 46)
    bold_badge = _font("Bold", 30)
    semibold_pill = _font("SemiBold", 22)
    semibold_title = _font("SemiBold", 32)
    regular = _font("Regular", 20)

    # --- Header: Logo + Marke + Kategorie-Pille ---
    _draw_paw(draw, 76, 92, fill=ACCENT)
    draw.text((112, 66), "SparPfote", font=bold_brand, fill=DARK)

    label = CATEGORY_LABELS.get(o.category or "", (o.category or "Sonstiges").upper())
    label_w = draw.textlength(label, font=semibold_pill)
    pill_w = label_w + 40
    pill_box = [SIZE - 40 - pill_w, 58, SIZE - 40, 58 + 46]
    draw.rounded_rectangle(pill_box, radius=23, fill=DARK)
    draw.text((pill_box[0] + 20, 69), label, font=semibold_pill, fill=BG)

    # --- Weisse Inhalts-Karte ---
    card_top, card_margin = 170, 50
    card_box = [card_margin, card_top, SIZE - card_margin, SIZE - 140]
    draw.rounded_rectangle(card_box, radius=36, fill=WHITE)

    # --- Produktfoto (oder Platzhalter) ---
    photo_area = 420
    photo_box_top = card_top + 40
    photo = _fetch_product_image(o.image_url)
    if photo:
        photo.thumbnail((photo_area, photo_area))
        px = (SIZE - photo.width) // 2
        py = photo_box_top + (photo_area - photo.height) // 2
        img.paste(photo, (px, py), photo)
    else:
        cx, cy = SIZE // 2, photo_box_top + photo_area // 2
        draw.ellipse([cx - 140, cy - 140, cx + 140, cy + 140], fill=PLACEHOLDER_BG)
        _draw_paw(draw, cx, cy + 10, scale=2.2, fill=GRAY)

    # --- Rabatt-Kreis ---
    if deal.discount_pct > 0:
        bx, by, br = SIZE - card_margin - 70, card_top - 10, 78
        draw.ellipse([bx - br, by - br, bx + br, by + br], fill=ACCENT)
        badge_text = f"-{deal.discount_pct:.0f}%"
        tw = draw.textlength(badge_text, font=bold_badge)
        draw.text((bx - tw / 2, by - 18), badge_text, font=bold_badge, fill=WHITE)

    # --- Titel (max. 2 Zeilen) ---
    title_y = photo_box_top + photo_area + 30
    lines = _wrap_text(draw, o.title, semibold_title, SIZE - 2 * card_margin - 80)[:2]
    for i, line in enumerate(lines):
        tw = draw.textlength(line, font=semibold_title)
        draw.text(((SIZE - tw) / 2, title_y + i * 40), line, font=semibold_title, fill=DARK)

    # --- Grundpreis ---
    y = title_y + len(lines) * 40 + 14
    if o.price_per_unit_cents and o.unit:
        gp_text = f"Grundpreis: {_eur(o.price_per_unit_cents)}/{o.unit}"
        tw = draw.textlength(gp_text, font=regular)
        draw.text(((SIZE - tw) / 2, y), gp_text, font=regular, fill=GRAY)
        y += 34

    # --- Preiszeile ---
    price_text = _eur(o.price_cents)
    old_text = _eur(deal.ref_price_cents) if deal.discount_pct > 0 else ""
    pw = draw.textlength(price_text, font=bold_price)
    ow = draw.textlength(old_text, font=regular) if old_text else 0
    gap = 16
    total_w = pw + (gap + ow if old_text else 0)
    start_x = (SIZE - total_w) / 2
    draw.text((start_x, y + 6), price_text, font=bold_price, fill=ACCENT)
    if old_text:
        ox, oy = start_x + pw + gap, y + 24
        draw.text((ox, oy), old_text, font=regular, fill=GRAY)
        draw.line([ox - 4, oy + 12, ox + ow + 4, oy + 12], fill=GRAY, width=2)

    # --- Footer ---
    footer_text = f"Link im WhatsApp-Kanal  ·  {o.shop}.de"
    tw = draw.textlength(footer_text, font=regular)
    draw.text(((SIZE - tw) / 2, SIZE - 95), footer_text, font=regular, fill=GRAY)
    _draw_paw(draw, 70, SIZE - 56, scale=0.5, fill="#E8DFD2")

    return img


def save_cards(deals: list[Deal], out_dir: Path, limit: int = 10) -> list[Path]:
    """Fuer die besten `limit` Deals je eine PNG-Datei erzeugen."""
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for i, deal in enumerate(deals[:limit], start=1):
        img = build_card(deal)
        path = out_dir / f"deal_{i:02d}_{deal.offer.shop}_{deal.offer.product_id}.png"
        img.save(path)
        paths.append(path)
    return paths
