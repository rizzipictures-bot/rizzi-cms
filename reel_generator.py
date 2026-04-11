#!/usr/bin/env python3
"""
Reel Generator — Genera un video Reel Instagram/TikTok da un progetto fotografico.

Struttura ritmica cinematografica (ispirata a Barbero/Balsamini):
  - Intro lenta: titolo + prime 2 foto (durata lunga, respiro)
  - Accelerazione progressiva: le foto si accorciano sempre di più
  - Picco veloce: flash rapidissimi (2-3 frame per foto)
  - Rallentamento finale: ultime 2 foto più lunghe + outro

Stile visivo:
  - Cover mode (foto riempie tutto il frame, no bordi neri)
  - Per stile "digital": foto a piena pagina, tagli netti, titolo minimale
  - Per stile "analog": grana intensa, toni caldi, sfondo granoso dietro le foto

Output: MP4 verticale 540x960 (9:16), pronto per Instagram Reels / TikTok
"""

import os, json, subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
import numpy as np

# ── Costanti video ─────────────────────────────────────────────────────────────
W, H   = 540, 960
FPS    = 24
FONT_REGULAR = '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf'
FONT_BOLD    = '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf'
FONT_LIGHT   = '/usr/share/fonts/truetype/liberation/LiberationSansNarrow-Regular.ttf'

BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
GRAY  = (160, 160, 160)


def _load_font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except:
        return ImageFont.load_default()


def _fit_cover(img, target_w=W, target_h=H):
    """Cover mode: la foto riempie tutto il frame, nessun bordo nero."""
    img = img.convert('RGB')
    iw, ih = img.size
    scale = max(target_w / iw, target_h / ih)
    new_w = int(iw * scale)
    new_h = int(ih * scale)
    img = img.resize((new_w, new_h), Image.LANCZOS)
    x = (new_w - target_w) // 2
    y = (new_h - target_h) // 2
    return img.crop((x, y, x + target_w, y + target_h))


def _add_grain(img, intensity=0.04):
    """Grana analogica."""
    arr = np.array(img, dtype=np.float32)
    noise = np.random.normal(0, intensity * 255, arr.shape)
    return Image.fromarray(np.clip(arr + noise, 0, 255).astype(np.uint8))


def _darken(img, factor=0.5):
    return ImageEnhance.Brightness(img).enhance(factor)


def _make_title_frame(title, subtitle, year_place, style='digital'):
    """
    Frame titolo: foto sfocata/granosa come sfondo + testo centrato sopra.
    Stile Balsamini: titolo grande, sottotitolo piccolo, linee sottili.
    """
    bg_color   = BLACK if style == 'digital' else (12, 10, 8)
    text_color = WHITE if style == 'digital' else (240, 235, 220)
    gray_color = (120, 120, 120) if style == 'digital' else (160, 150, 130)

    img  = Image.new('RGB', (W, H), bg_color)
    draw = ImageDraw.Draw(img)

    font_title = _load_font(FONT_BOLD, 80)
    font_sub   = _load_font(FONT_LIGHT, 32)
    font_small = _load_font(FONT_LIGHT, 24)

    # Linea orizzontale sopra
    line_y = H // 2 - 130
    draw.rectangle([60, line_y, W - 60, line_y + 1], fill=text_color)

    # Titolo
    bbox = draw.textbbox((0, 0), title, font=font_title)
    tw = bbox[2] - bbox[0]
    draw.text(((W - tw) // 2, H // 2 - 115), title, font=font_title, fill=text_color)

    # Sottotitolo
    if subtitle:
        bbox2 = draw.textbbox((0, 0), subtitle, font=font_sub)
        sw = bbox2[2] - bbox2[0]
        draw.text(((W - sw) // 2, H // 2 - 15), subtitle, font=font_sub, fill=gray_color)

    # Anno / Luogo
    if year_place:
        bbox3 = draw.textbbox((0, 0), year_place, font=font_small)
        yw = bbox3[2] - bbox3[0]
        draw.text(((W - yw) // 2, H // 2 + 35), year_place, font=font_small, fill=gray_color)

    # Linea orizzontale sotto
    line_y2 = H // 2 + 80
    draw.rectangle([60, line_y2, W - 60, line_y2 + 1], fill=text_color)

    return img


def _make_final_frame(title, website='rizzipictures.com', style='digital'):
    """Frame finale minimalista."""
    bg_color   = BLACK if style == 'digital' else (12, 10, 8)
    text_color = WHITE if style == 'digital' else (240, 235, 220)
    gray_color = (120, 120, 120) if style == 'digital' else (160, 150, 130)

    img  = Image.new('RGB', (W, H), bg_color)
    draw = ImageDraw.Draw(img)

    font_title = _load_font(FONT_BOLD, 60)
    font_site  = _load_font(FONT_LIGHT, 28)

    bbox = draw.textbbox((0, 0), title, font=font_title)
    tw = bbox[2] - bbox[0]
    draw.text(((W - tw) // 2, H // 2 - 50), title, font=font_title, fill=text_color)

    bbox2 = draw.textbbox((0, 0), website, font=font_site)
    sw = bbox2[2] - bbox2[0]
    draw.text(((W - sw) // 2, H // 2 + 30), website, font=font_site, fill=gray_color)

    return img


def _make_photo_with_overlay(fitted, title, year_place, style='digital'):
    """
    Foto grande (cover) con titolo e anno sovrapposti in basso.
    Stile sito: come la visualizzazione con sfondo granoso che si apre con il +.
    """
    img = fitted.copy()

    # Gradiente scuro in basso per leggibilità testo
    overlay = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    draw_ov = ImageDraw.Draw(overlay)
    for y in range(H - 280, H):
        alpha = int(200 * (y - (H - 280)) / 280)
        draw_ov.rectangle([0, y, W, y + 1], fill=(0, 0, 0, alpha))
    img = Image.alpha_composite(img.convert('RGBA'), overlay).convert('RGB')

    if style == 'analog':
        img = _add_grain(img, intensity=0.025)

    draw = ImageDraw.Draw(img)
    font_title = _load_font(FONT_BOLD, 38)
    font_small = _load_font(FONT_LIGHT, 24)

    text_color = WHITE if style == 'digital' else (240, 235, 220)

    # Titolo in basso
    bbox = draw.textbbox((0, 0), title, font=font_title)
    tw = bbox[2] - bbox[0]
    draw.text(((W - tw) // 2, H - 130), title, font=font_title, fill=text_color)

    if year_place:
        bbox2 = draw.textbbox((0, 0), year_place, font=font_small)
        yw = bbox2[2] - bbox2[0]
        draw.text(((W - yw) // 2, H - 85), year_place, font=font_small, fill=(180, 180, 180))

    return img


def _open_ffmpeg_pipe(output_path):
    cmd = [
        'ffmpeg', '-y',
        '-f', 'rawvideo', '-vcodec', 'rawvideo',
        '-s', f'{W}x{H}', '-pix_fmt', 'rgb24', '-r', str(FPS),
        '-i', 'pipe:0',
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '22',
        '-pix_fmt', 'yuv420p', '-movflags', '+faststart',
        output_path
    ]
    return subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)


def _write_frames(proc, frame, n):
    """Scrive n copie dello stesso frame nel pipe ffmpeg."""
    raw = frame.tobytes()
    for _ in range(n):
        proc.stdin.write(raw)


def generate_reel(project, images_dir, output_path, style='digital'):
    """
    Genera un Reel video con ritmo cinematografico lento→veloce→lento.

    Args:
        project:    dict con title, subtitle, year, place, images
        images_dir: Path alla directory delle immagini
        output_path: Path di output del video MP4
        style:      'digital' o 'analog'
    """
    title    = project.get('title', 'Untitled')
    subtitle = project.get('subtitle', '')
    year     = str(project.get('year', ''))
    place    = project.get('place', '')
    images   = project.get('images', [])

    year_place = ' — '.join(filter(None, [year, place]))

    # ── Carica fino a 16 foto, pre-resize immediato ────────────────────────────
    photos_pil = []
    for img_data in images[:16]:
        fpath = Path(images_dir) / img_data.get('file', '')
        if fpath.exists():
            try:
                with Image.open(str(fpath)) as im:
                    im_rgb = im.convert('RGB')
                    im_rgb.thumbnail((W * 2, H * 2), Image.LANCZOS)
                    photos_pil.append(im_rgb.copy())
            except:
                pass

    if not photos_pil:
        raise ValueError('Nessuna immagine disponibile per il progetto')

    n = len(photos_pil)

    # ── Pre-calcola tutte le foto in cover mode ────────────────────────────────
    fitted = [_fit_cover(p) for p in photos_pil]
    if style == 'analog':
        fitted = [_add_grain(p, intensity=0.03) for p in fitted]

    # ── Calcola la durata per ogni foto con curva easing ──────────────────────
    # Ritmo: lento (48f) → accelera → picco veloce (2f) → rallenta → lento (48f)
    # La curva è una gaussiana invertita: lunga agli estremi, brevissima al centro
    #
    # Distribuzione frame per foto:
    #   - prime 2 foto: 48 frame (2 sec) — intro lenta
    #   - poi scende progressivamente fino a 2 frame nel picco
    #   - ultime 2 foto: 36 frame (1.5 sec) — outro lenta
    #   - ultima foto: frame con overlay titolo/luogo

    def _easing_duration(i, total):
        """Curva easing: lunga agli estremi, brevissima al centro."""
        if total <= 2:
            return 36
        # Normalizza posizione 0..1
        t = i / (total - 1)
        # Curva: coseno smorzato — massimo agli estremi, minimo al centro
        import math
        # ease: 1 agli estremi, 0 al centro
        ease = abs(math.cos(math.pi * t))
        # Range: da 2 frame (picco) a 48 frame (intro/outro)
        min_f, max_f = 2, 48
        return max(min_f, int(min_f + (max_f - min_f) * ease))

    durations = [_easing_duration(i, n) for i in range(n)]

    # Le ultime 2 foto sempre più lunghe (rallentamento finale)
    if n >= 2:
        durations[-1] = 48
    if n >= 3:
        durations[-2] = 36

    # ── Apri pipe ffmpeg e scrivi i frame ──────────────────────────────────────
    proc = _open_ffmpeg_pipe(output_path)
    total_frames = 0

    try:
        # 1. INTRO: titolo (1.5 sec = 36 frame)
        title_frame = _make_title_frame(title, subtitle, year_place, style=style)
        _write_frames(proc, title_frame, 36)
        total_frames += 36

        # 2. PRIMA FOTO con overlay testo (stile sito: foto grande + titolo/luogo)
        #    Dura come l'easing della prima foto ma almeno 36 frame
        first_with_overlay = _make_photo_with_overlay(fitted[0], title, year_place, style=style)
        d0 = max(durations[0], 36)
        _write_frames(proc, first_with_overlay, d0)
        total_frames += d0

        # 3. SEQUENZA RITMICA: tutte le foto con easing lento→veloce→lento
        #    (salta la prima già mostrata)
        for i in range(1, n):
            f = fitted[i]
            d = durations[i]

            # Taglio netto — nessuna dissolvenza (stile Barbero/Balsamini)
            _write_frames(proc, f, d)
            total_frames += d

        # 4. OUTRO: ultima foto ancora visibile + titolo finale
        #    (solo se abbiamo più di 1 foto)
        if n > 1:
            # Ultima foto con overlay (come la prima)
            last_with_overlay = _make_photo_with_overlay(fitted[-1], title, year_place, style=style)
            _write_frames(proc, last_with_overlay, 36)
            total_frames += 36

        # 5. FRAME FINALE: titolo + sito (1.5 sec = 36 frame)
        final_frame = _make_final_frame(title, style=style)
        _write_frames(proc, final_frame, 36)
        total_frames += 36

    finally:
        proc.stdin.close()
        proc.wait()

    if proc.returncode != 0:
        raise RuntimeError('ffmpeg pipe error (reel)')

    return output_path


if __name__ == '__main__':
    import sys
    if len(sys.argv) < 3:
        print('Usage: python3 reel_generator.py <project_json> <output.mp4> [digital|analog]')
        sys.exit(1)
    with open(sys.argv[1]) as f:
        project = json.load(f)
    style = sys.argv[3] if len(sys.argv) > 3 else 'digital'
    generate_reel(project, 'uploads', sys.argv[2], style=style)
    print(f'Reel generato: {sys.argv[2]}')
