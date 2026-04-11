#!/usr/bin/env python3
"""
Reel Generator — Genera un video Reel Instagram/TikTok da un progetto fotografico.

Il video mostra in sequenza rapida:
1. Schermata titolo (progetto + anno + luogo)
2. Griglia overview (tutte le foto in griglia)
3. Foto singole grandi (una per una, con dissolvenza)
4. Foto con effetto grana analogica
5. Schermata finale (titolo + sito)

Output: MP4 verticale 1080x1920 (9:16), pronto per Instagram Reels / TikTok
"""

import os, json, tempfile, shutil, subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
import numpy as np

# ── Costanti video ─────────────────────────────────────────────────────────────
# Risoluzione ridotta per Render free plan (512MB RAM): 540x960 = 9:16
W, H = 540, 960
FPS  = 30
FONT_REGULAR = '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf'
FONT_BOLD    = '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf'
FONT_LIGHT   = '/usr/share/fonts/truetype/liberation/LiberationSansNarrow-Regular.ttf'

# ── Colori ─────────────────────────────────────────────────────────────────────
BLACK  = (0, 0, 0)
WHITE  = (255, 255, 255)
GRAY   = (180, 180, 180)
CREAM  = (245, 242, 235)

def _load_font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except:
        return ImageFont.load_default()

def _fit_image(img, target_w, target_h, bg_color=BLACK, contain=True):
    """Ridimensiona un'immagine per adattarla a target_w x target_h mantenendo l'aspect ratio."""
    img = img.convert('RGB')
    iw, ih = img.size
    scale = min(target_w / iw, target_h / ih) if contain else max(target_w / iw, target_h / ih)
    new_w = int(iw * scale)
    new_h = int(ih * scale)
    img = img.resize((new_w, new_h), Image.LANCZOS)
    canvas = Image.new('RGB', (target_w, target_h), bg_color)
    x = (target_w - new_w) // 2
    y = (target_h - new_h) // 2
    canvas.paste(img, (x, y))
    return canvas

def _add_grain(img, intensity=0.04):
    """Aggiunge grana analogica a un'immagine PIL."""
    arr = np.array(img, dtype=np.float32)
    noise = np.random.normal(0, intensity * 255, arr.shape)
    arr = np.clip(arr + noise, 0, 255).astype(np.uint8)
    return Image.fromarray(arr)

def _make_title_frame(title, subtitle, year_place, bg=BLACK, text_color=WHITE, n_frames=60):
    """Genera un frame con titolo centrato."""
    frames = []
    font_title = _load_font(FONT_BOLD, 72)
    font_sub   = _load_font(FONT_REGULAR, 36)
    font_small = _load_font(FONT_LIGHT, 28)
    
    img = Image.new('RGB', (W, H), bg)
    draw = ImageDraw.Draw(img)
    
    # Linea decorativa
    draw.rectangle([80, H//2 - 120, W - 80, H//2 - 118], fill=text_color)
    
    # Titolo
    bbox = draw.textbbox((0, 0), title, font=font_title)
    tw = bbox[2] - bbox[0]
    draw.text(((W - tw) // 2, H//2 - 100), title, font=font_title, fill=text_color)
    
    # Sottotitolo
    if subtitle:
        bbox2 = draw.textbbox((0, 0), subtitle, font=font_sub)
        sw = bbox2[2] - bbox2[0]
        draw.text(((W - sw) // 2, H//2 - 10), subtitle, font=font_sub, fill=GRAY)
    
    # Anno / Luogo
    if year_place:
        bbox3 = draw.textbbox((0, 0), year_place, font=font_small)
        yw = bbox3[2] - bbox3[0]
        draw.text(((W - yw) // 2, H//2 + 50), year_place, font=font_small, fill=GRAY)
    
    # Linea decorativa bassa
    draw.rectangle([80, H//2 + 100, W - 80, H//2 + 102], fill=text_color)
    
    return [img] * n_frames

def _make_grid_frames(images_pil, n_frames=90):
    """Genera frame con griglia di foto (stile Overview del sito)."""
    frames = []
    n = len(images_pil)
    if n == 0:
        return [Image.new('RGB', (W, H), WHITE)] * n_frames
    
    # Calcola griglia
    cols = 3
    rows = (n + cols - 1) // cols
    cell_w = (W - 40) // cols
    cell_h = int(cell_w * 0.75)
    
    img = Image.new('RGB', (W, H), WHITE)
    
    for i, photo in enumerate(images_pil[:cols * rows]):
        row = i // cols
        col = i % cols
        x = 20 + col * cell_w + 2
        y = 80 + row * cell_h + 2
        thumb = _fit_image(photo, cell_w - 4, cell_h - 4, bg_color=WHITE, contain=True)
        img.paste(thumb, (x, y))
    
    return [img] * n_frames

def _make_photo_frames(photo_pil, duration_frames=45, with_grain=False, fade_in=True):
    """Genera frame per una singola foto grande con eventuale fade-in."""
    frames = []
    base = _fit_image(photo_pil, W, H, bg_color=BLACK, contain=True)
    
    if with_grain:
        base = _add_grain(base, intensity=0.035)
    
    if fade_in:
        fade_frames = min(15, duration_frames // 3)
        for i in range(fade_frames):
            alpha = i / fade_frames
            dark = Image.new('RGB', (W, H), BLACK)
            blended = Image.blend(dark, base, alpha)
            frames.append(blended)
        frames += [base] * (duration_frames - fade_frames)
    else:
        frames = [base] * duration_frames
    
    return frames

def _make_final_frame(title, website='rizzipictures.com', n_frames=60):
    """Genera il frame finale con titolo e sito."""
    font_title = _load_font(FONT_BOLD, 56)
    font_site  = _load_font(FONT_LIGHT, 30)
    
    img = Image.new('RGB', (W, H), BLACK)
    draw = ImageDraw.Draw(img)
    
    # Titolo
    bbox = draw.textbbox((0, 0), title, font=font_title)
    tw = bbox[2] - bbox[0]
    draw.text(((W - tw) // 2, H//2 - 60), title, font=font_title, fill=WHITE)
    
    # Sito
    bbox2 = draw.textbbox((0, 0), website, font=font_site)
    sw = bbox2[2] - bbox2[0]
    draw.text(((W - sw) // 2, H//2 + 20), website, font=font_site, fill=GRAY)
    
    return [img] * n_frames

def _frames_to_video(frames, output_path, fps=FPS):
    """Converte una lista di frame PIL in un video MP4 via ffmpeg pipe (low memory)."""
    cmd = [
        'ffmpeg', '-y',
        '-f', 'rawvideo', '-vcodec', 'rawvideo',
        '-s', f'{W}x{H}', '-pix_fmt', 'rgb24', '-r', str(fps),
        '-i', 'pipe:0',
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
        '-pix_fmt', 'yuv420p', '-movflags', '+faststart',
        output_path
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
    try:
        for frame in frames:
            proc.stdin.write(frame.tobytes())
    finally:
        proc.stdin.close()
        proc.wait()
    if proc.returncode != 0:
        raise RuntimeError('ffmpeg pipe error (reel)')
    return output_path

def generate_reel(project, images_dir, output_path, style='digital'):
    """
    Genera un Reel video da un progetto fotografico.
    
    Args:
        project: dict con title, subtitle, year, place, images (lista di {file, ar})
        images_dir: Path alla directory delle immagini
        output_path: Path di output del video MP4
        style: 'digital' (bianco/nero) o 'analog' (grana + toni caldi)
    
    Returns:
        output_path se successo
    """
    title    = project.get('title', 'Untitled')
    subtitle = project.get('subtitle', '')
    year     = str(project.get('year', ''))
    place    = project.get('place', '')
    images   = project.get('images', [])
    
    year_place = ' — '.join(filter(None, [year, place]))
    
    # Carica le immagini
    photos_pil = []
    for img_data in images[:12]:  # max 12 foto per il reel
        fpath = Path(images_dir) / img_data.get('file', '')
        if fpath.exists():
            try:
                with Image.open(str(fpath)) as im:
                    photos_pil.append(im.copy().convert('RGB'))
            except:
                pass
    
    if not photos_pil:
        raise ValueError('Nessuna immagine disponibile per il progetto')
    
    # Stile analogico: toni caldi + grana
    bg_color    = BLACK if style == 'digital' else (20, 18, 15)
    text_color  = WHITE if style == 'digital' else (240, 235, 220)
    
    all_frames = []
    
    # 1. Frame titolo (2 sec)
    all_frames += _make_title_frame(title, subtitle, year_place, 
                                     bg=bg_color, text_color=text_color, n_frames=60)
    
    # 2. Griglia overview (3 sec)
    all_frames += _make_grid_frames(photos_pil, n_frames=90)
    
    # 3. Foto singole grandi (0.5-1 sec ciascuna)
    for i, photo in enumerate(photos_pil[:8]):
        duration = 30 if len(photos_pil) > 6 else 45
        all_frames += _make_photo_frames(photo, duration_frames=duration, 
                                          with_grain=(style == 'analog'),
                                          fade_in=(i == 0))
    
    # 4. Se stile analogico: alcune foto con grana intensa
    if style == 'analog' and len(photos_pil) >= 3:
        for photo in photos_pil[:3]:
            all_frames += _make_photo_frames(photo, duration_frames=20, 
                                              with_grain=True, fade_in=False)
    
    # 5. Frame finale (2 sec)
    all_frames += _make_final_frame(title, n_frames=60)
    
    # Genera il video
    return _frames_to_video(all_frames, output_path, fps=FPS)


if __name__ == '__main__':
    # Test rapido
    import sys
    if len(sys.argv) < 3:
        print('Usage: python3 reel_generator.py <project_json> <output.mp4>')
        sys.exit(1)
    
    with open(sys.argv[1]) as f:
        project = json.load(f)
    
    generate_reel(project, 'uploads', sys.argv[2])
    print(f'Reel generato: {sys.argv[2]}')
