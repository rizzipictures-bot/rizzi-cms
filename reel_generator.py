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


def _make_title_frame(title, subtitle, year_place, style='digital', fw=W, fh=H):
    """
    Frame titolo: sfondo nero + testo centrato.
    Supporta sia verticale (9:16) che orizzontale (16:9).
    """
    bg_color   = BLACK if style == 'digital' else (12, 10, 8)
    text_color = WHITE if style == 'digital' else (240, 235, 220)
    gray_color = (120, 120, 120) if style == 'digital' else (160, 150, 130)

    img  = Image.new('RGB', (fw, fh), bg_color)
    draw = ImageDraw.Draw(img)

    # Scala font in base alla larghezza
    fs_title = max(40, int(fw * 0.148))
    fs_sub   = max(18, int(fw * 0.059))
    fs_small = max(14, int(fw * 0.044))
    font_title = _load_font(FONT_BOLD, fs_title)
    font_sub   = _load_font(FONT_LIGHT, fs_sub)
    font_small = _load_font(FONT_LIGHT, fs_small)

    cx, cy = fw // 2, fh // 2
    margin = int(fw * 0.11)

    # Linea orizzontale sopra
    line_y = cy - int(fh * 0.135)
    draw.rectangle([margin, line_y, fw - margin, line_y + 1], fill=text_color)

    # Titolo
    bbox = draw.textbbox((0, 0), title, font=font_title)
    tw = bbox[2] - bbox[0]
    draw.text(((fw - tw) // 2, cy - int(fh * 0.12)), title, font=font_title, fill=text_color)

    # Sottotitolo
    if subtitle:
        bbox2 = draw.textbbox((0, 0), subtitle, font=font_sub)
        sw = bbox2[2] - bbox2[0]
        draw.text(((fw - sw) // 2, cy - int(fh * 0.015)), subtitle, font=font_sub, fill=gray_color)

    # Anno / Luogo
    if year_place:
        bbox3 = draw.textbbox((0, 0), year_place, font=font_small)
        yw = bbox3[2] - bbox3[0]
        draw.text(((fw - yw) // 2, cy + int(fh * 0.036)), year_place, font=font_small, fill=gray_color)

    # Linea orizzontale sotto
    line_y2 = cy + int(fh * 0.083)
    draw.rectangle([margin, line_y2, fw - margin, line_y2 + 1], fill=text_color)

    return img


def _make_final_frame(title, website='rizzipictures.com', style='digital', fw=W, fh=H):
    """Frame finale minimalista."""
    bg_color   = BLACK if style == 'digital' else (12, 10, 8)
    text_color = WHITE if style == 'digital' else (240, 235, 220)
    gray_color = (120, 120, 120) if style == 'digital' else (160, 150, 130)

    img  = Image.new('RGB', (fw, fh), bg_color)
    draw = ImageDraw.Draw(img)

    fs_title = max(36, int(fw * 0.111))
    fs_site  = max(16, int(fw * 0.052))
    font_title = _load_font(FONT_BOLD, fs_title)
    font_site  = _load_font(FONT_LIGHT, fs_site)

    cx, cy = fw // 2, fh // 2

    bbox = draw.textbbox((0, 0), title, font=font_title)
    tw = bbox[2] - bbox[0]
    draw.text(((fw - tw) // 2, cy - int(fh * 0.052)), title, font=font_title, fill=text_color)

    bbox2 = draw.textbbox((0, 0), website, font=font_site)
    sw = bbox2[2] - bbox2[0]
    draw.text(((fw - sw) // 2, cy + int(fh * 0.031)), website, font=font_site, fill=gray_color)

    return img


def _make_photo_with_overlay(fitted, title, year_place, style='digital', fw=W, fh=H):
    """
    Foto grande (cover) con titolo e anno sovrapposti in basso.
    Stile sito: come la visualizzazione con sfondo granoso che si apre con il +.
    """
    img = fitted.copy()
    if img.size != (fw, fh):
        img = _fit_cover(img, target_w=fw, target_h=fh)

    # Gradiente scuro in basso per leggibilità testo
    grad_h = int(fh * 0.29)
    overlay = Image.new('RGBA', (fw, fh), (0, 0, 0, 0))
    draw_ov = ImageDraw.Draw(overlay)
    for y in range(fh - grad_h, fh):
        alpha = int(200 * (y - (fh - grad_h)) / grad_h)
        draw_ov.rectangle([0, y, fw, y + 1], fill=(0, 0, 0, alpha))
    img = Image.alpha_composite(img.convert('RGBA'), overlay).convert('RGB')

    if style == 'analog':
        img = _add_grain(img, intensity=0.025)

    draw = ImageDraw.Draw(img)
    fs_title = max(24, int(fw * 0.070))
    fs_small = max(14, int(fw * 0.044))
    font_title = _load_font(FONT_BOLD, fs_title)
    font_small = _load_font(FONT_LIGHT, fs_small)

    text_color = WHITE if style == 'digital' else (240, 235, 220)

    # Titolo in basso
    bbox = draw.textbbox((0, 0), title, font=font_title)
    tw = bbox[2] - bbox[0]
    draw.text(((fw - tw) // 2, fh - int(fh * 0.135)), title, font=font_title, fill=text_color)

    if year_place:
        bbox2 = draw.textbbox((0, 0), year_place, font=font_small)
        yw = bbox2[2] - bbox2[0]
        draw.text(((fw - yw) // 2, fh - int(fh * 0.088)), year_place, font=font_small, fill=(180, 180, 180))

    return img


def _open_ffmpeg_pipe(output_path, frame_w=W, frame_h=H):
    cmd = [
        'ffmpeg', '-y',
        '-f', 'rawvideo', '-vcodec', 'rawvideo',
        '-s', f'{frame_w}x{frame_h}', '-pix_fmt', 'rgb24', '-r', str(FPS),
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
    proc = _open_ffmpeg_pipe(output_path, frame_w=vw, frame_h=vh)
    total_frames = 0

    try:
        # 1. INTRO: titolo (1.5 sec = 36 frame)
        title_frame = _make_title_frame(title, subtitle, year_place, style=style, fw=vw, fh=vh)
        _write_frames(proc, title_frame, 36)
        total_frames += 36

        # 2. PRIMA FOTO con overlay testo (stile sito: foto grande + titolo/luogo)
        #    Dura come l'easing della prima foto ma almeno 36 frame
        first_with_overlay = _make_photo_with_overlay(fitted[0], title, year_place, style=style, fw=vw, fh=vh)
        d0 = max(durations[0], 36)
        _write_frames(proc, first_with_overlay, d0)
        total_frames += d0

        # 3. SEQUENZA RITMICA: tutte le foto con easing lento→veloce→lento
        #    (salta la prima già mostrata)
        for i in range(1, n):
            f = fitted[i]
            d = durations[i]
            _write_frames(proc, f, d)
            total_frames += d

        # 4. OUTRO: ultima foto ancora visibile + titolo finale
        #    (solo se abbiamo più di 1 foto)
        if n > 1:
            last_with_overlay = _make_photo_with_overlay(fitted[-1], title, year_place, style=style, fw=vw, fh=vh)
            _write_frames(proc, last_with_overlay, 36)
            total_frames += 36

        # 5. FRAME FINALE: titolo + sito (1.5 sec = 36 frame)
        final_frame = _make_final_frame(title, style=style, fw=vw, fh=vh)
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
