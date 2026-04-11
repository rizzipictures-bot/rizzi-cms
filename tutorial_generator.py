#!/usr/bin/env python3
"""
Tutorial Generator — Genera video-saggi filosofici sull'archivio fotografico.

Formato: 60-90 secondi verticali (9:16) per TikTok/Instagram Reels/YouTube Shorts.
Struttura: citazione filosofica + immagini del progetto in movimento + voce narrante (testo).

Il video non è un tutorial tecnico ma un video-saggio:
"Perché archiviare è un atto di pensiero."
"""

import os, json, random, textwrap, subprocess, tempfile
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
import numpy as np

# ── ElevenLabs Voice Clone ─────────────────────────────────────────────────────
ELEVENLABS_API_KEY = os.environ.get('ELEVENLABS_API_KEY', '')
ELEVENLABS_VOICE_ID = os.environ.get('ELEVENLABS_VOICE_ID', 'BNBjRw6icTfq1GkqWkrH')  # Alessandro Rizzi

def _generate_voice_narration(text, output_mp3_path, api_key=None, voice_id=None):
    """
    Genera audio narrato con la voce clonata di Alessandro Rizzi tramite ElevenLabs.
    Restituisce True se riuscito, False altrimenti.
    """
    import urllib.request, urllib.error
    
    key = api_key or ELEVENLABS_API_KEY
    vid = voice_id or ELEVENLABS_VOICE_ID
    
    if not key or not vid:
        return False
    
    url = f'https://api.elevenlabs.io/v1/text-to-speech/{vid}'
    payload = json.dumps({
        'text': text,
        'model_id': 'eleven_multilingual_v2',
        'voice_settings': {
            'stability': 0.5,
            'similarity_boost': 0.85,
            'style': 0.2,
            'use_speaker_boost': True
        }
    }).encode('utf-8')
    
    req = urllib.request.Request(url, data=payload, method='POST')
    req.add_header('xi-api-key', key)
    req.add_header('Content-Type', 'application/json')
    req.add_header('Accept', 'audio/mpeg')
    
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            audio_data = resp.read()
        with open(output_mp3_path, 'wb') as f:
            f.write(audio_data)
        return True
    except Exception as e:
        print(f'ElevenLabs error: {e}')
        return False


def _merge_audio_video(video_path, audio_path, output_path):
    """
    Unisce audio e video con ffmpeg. Se l'audio è più corto del video, lo ripete.
    Se più lungo, lo taglia.
    """
    cmd = [
        'ffmpeg', '-y',
        '-i', video_path,
        '-i', audio_path,
        '-c:v', 'copy',
        '-c:a', 'aac',
        '-b:a', '192k',
        '-shortest',  # taglia all'elemento più corto
        '-movflags', '+faststart',
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0

# ── Costanti video ─────────────────────────────────────────────────────────────
# Risoluzione ridotta per Render free plan (512MB RAM): 540x960 = 9:16
W, H = 540, 960
FPS  = 30
FONT_REGULAR = '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf'
FONT_BOLD    = '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf'
FONT_LIGHT   = '/usr/share/fonts/truetype/liberation/LiberationSansNarrow-Regular.ttf'
FONT_ITALIC  = '/usr/share/fonts/truetype/liberation/LiberationSans-Italic.ttf'

def _load_font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except:
        return ImageFont.load_default()

def _fit_image(img, target_w, target_h, bg_color=(0,0,0), contain=False):
    """Ridimensiona coprendo tutto il frame (cover mode)."""
    img = img.convert('RGB')
    iw, ih = img.size
    scale = max(target_w / iw, target_h / ih) if not contain else min(target_w / iw, target_h / ih)
    new_w = int(iw * scale)
    new_h = int(ih * scale)
    img = img.resize((new_w, new_h), Image.LANCZOS)
    # Crop al centro
    x = (new_w - target_w) // 2
    y = (new_h - target_h) // 2
    img = img.crop((x, y, x + target_w, y + target_h))
    return img

def _darken(img, factor=0.45):
    """Scurisce un'immagine per rendere il testo leggibile sopra."""
    enhancer = ImageEnhance.Brightness(img)
    return enhancer.enhance(factor)

def _add_grain(img, intensity=0.03):
    arr = np.array(img, dtype=np.float32)
    noise = np.random.normal(0, intensity * 255, arr.shape)
    arr = np.clip(arr + noise, 0, 255).astype(np.uint8)
    return Image.fromarray(arr)

def _wrap_text(text, font, max_width, draw):
    """Wrappa il testo per adattarsi alla larghezza massima."""
    words = text.split()
    lines = []
    current_line = []
    
    for word in words:
        test_line = ' '.join(current_line + [word])
        bbox = draw.textbbox((0, 0), test_line, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current_line.append(word)
        else:
            if current_line:
                lines.append(' '.join(current_line))
            current_line = [word]
    
    if current_line:
        lines.append(' '.join(current_line))
    
    return lines

def _make_quote_frame(quote_text, author, opera, bg_photo=None, n_frames=90):
    """
    Genera frame con citazione filosofica.
    Se bg_photo è fornita, la usa come sfondo scurito.
    Altrimenti usa sfondo nero.
    """
    frames = []
    
    font_quote  = _load_font(FONT_ITALIC, 38)
    font_author = _load_font(FONT_BOLD, 28)
    font_opera  = _load_font(FONT_LIGHT, 22)
    
    # Sfondo
    if bg_photo:
        bg = _fit_image(bg_photo, W, H, contain=False)
        bg = _darken(bg, factor=0.35)
        bg = _add_grain(bg, intensity=0.02)
    else:
        bg = Image.new('RGB', (W, H), (8, 8, 8))
    
    # Overlay semitrasparente per leggibilità
    overlay = Image.new('RGBA', (W, H), (0, 0, 0, 120))
    bg_rgba = bg.convert('RGBA')
    bg_rgba = Image.alpha_composite(bg_rgba, overlay)
    img = bg_rgba.convert('RGB')
    
    draw = ImageDraw.Draw(img)
    
    # Virgolette decorative
    font_big_quote = _load_font(FONT_BOLD, 120)
    draw.text((60, H//2 - 320), '"', font=font_big_quote, fill=(255, 255, 255, 80))
    
    # Testo citazione (wrappato)
    max_text_w = W - 140
    lines = _wrap_text(quote_text, font_quote, max_text_w, draw)
    
    # Calcola altezza totale del testo
    line_h = 52
    total_h = len(lines) * line_h
    start_y = H//2 - total_h//2 - 40
    
    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font_quote)
        lw = bbox[2] - bbox[0]
        x = (W - lw) // 2
        y = start_y + i * line_h
        # Ombra
        draw.text((x+2, y+2), line, font=font_quote, fill=(0, 0, 0, 180))
        draw.text((x, y), line, font=font_quote, fill=(255, 255, 255))
    
    # Linea separatrice
    sep_y = start_y + total_h + 30
    draw.rectangle([W//2 - 60, sep_y, W//2 + 60, sep_y + 1], fill=(200, 200, 200, 180))
    
    # Autore
    bbox_a = draw.textbbox((0, 0), author, font=font_author)
    aw = bbox_a[2] - bbox_a[0]
    draw.text(((W - aw) // 2, sep_y + 15), author, font=font_author, fill=(220, 220, 220))
    
    # Opera
    if opera:
        bbox_o = draw.textbbox((0, 0), opera, font=font_opera)
        ow = bbox_o[2] - bbox_o[0]
        draw.text(((W - ow) // 2, sep_y + 50), opera, font=font_opera, fill=(160, 160, 160))
    
    return [img] * n_frames

def _make_photo_with_text_frame(photo, text_lines, n_frames=60):
    """Foto grande con testo sovrapposto in basso."""
    frames = []
    
    font_text = _load_font(FONT_LIGHT, 32)
    
    bg = _fit_image(photo, W, H, contain=False)
    bg = _darken(bg, factor=0.6)
    
    img = bg.copy()
    draw = ImageDraw.Draw(img)
    
    # Gradiente scuro in basso
    for y in range(H - 300, H):
        alpha = (y - (H - 300)) / 300
        overlay_color = (0, 0, 0)
        draw.rectangle([0, y, W, y+1], fill=tuple(int(c * alpha) for c in overlay_color))
    
    # Testo in basso
    y_start = H - 250
    for line in text_lines:
        bbox = draw.textbbox((0, 0), line, font=font_text)
        lw = bbox[2] - bbox[0]
        draw.text(((W - lw) // 2, y_start), line, font=font_text, fill=(240, 240, 240))
        y_start += 45
    
    return [img] * n_frames

def _make_title_card(title, subtitle, n_frames=45):
    """Card titolo del tutorial."""
    font_title = _load_font(FONT_BOLD, 52)
    font_sub   = _load_font(FONT_LIGHT, 30)
    font_brand = _load_font(FONT_REGULAR, 24)
    
    img = Image.new('RGB', (W, H), (5, 5, 5))
    draw = ImageDraw.Draw(img)
    
    # Linea decorativa
    draw.rectangle([80, H//2 - 80, W - 80, H//2 - 78], fill=(255, 255, 255))
    
    # Titolo
    bbox = draw.textbbox((0, 0), title, font=font_title)
    tw = bbox[2] - bbox[0]
    draw.text(((W - tw) // 2, H//2 - 60), title, font=font_title, fill=(255, 255, 255))
    
    # Sottotitolo
    if subtitle:
        lines = _wrap_text(subtitle, font_sub, W - 160, draw)
        y = H//2 + 20
        for line in lines:
            bbox2 = draw.textbbox((0, 0), line, font=font_sub)
            lw = bbox2[2] - bbox2[0]
            draw.text(((W - lw) // 2, y), line, font=font_sub, fill=(160, 160, 160))
            y += 42
    
    # Brand
    brand = 'rizzipictures.com'
    bbox3 = draw.textbbox((0, 0), brand, font=font_brand)
    bw = bbox3[2] - bbox3[0]
    draw.text(((W - bw) // 2, H - 120), brand, font=font_brand, fill=(100, 100, 100))
    
    return [img] * n_frames

def _open_ffmpeg_pipe(output_path, fps=FPS):
    """Apre un processo ffmpeg che legge frame raw RGB da stdin."""
    cmd = [
        'ffmpeg', '-y',
        '-f', 'rawvideo',
        '-vcodec', 'rawvideo',
        '-s', f'{W}x{H}',
        '-pix_fmt', 'rgb24',
        '-r', str(fps),
        '-i', 'pipe:0',
        '-c:v', 'libx264',
        '-preset', 'fast',
        '-crf', '23',
        '-pix_fmt', 'yuv420p',
        '-movflags', '+faststart',
        output_path
    ]
    return subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)


def _write_frame(proc, img):
    """Scrive un frame PIL nel pipe ffmpeg."""
    proc.stdin.write(img.tobytes())


def _close_ffmpeg_pipe(proc):
    """Chiude il pipe e attende la fine di ffmpeg."""
    proc.stdin.close()
    proc.wait()
    if proc.returncode != 0:
        raise RuntimeError('ffmpeg pipe error')


def _frames_to_video(frames, output_path, fps=FPS):
    """Converte frame PIL in video MP4 (legacy, usato solo se necessario)."""
    proc = _open_ffmpeg_pipe(output_path, fps)
    try:
        for frame in frames:
            _write_frame(proc, frame)
    finally:
        _close_ffmpeg_pipe(proc)
    return output_path

def generate_tutorial(project, images_dir, output_path, corpus_path=None, quote_id=None, custom_narration=None, elevenlabs_api_key=None):
    """
    Genera un video-saggio filosofico per un progetto fotografico.
    
    Args:
        project: dict con title, subtitle, year, place, images
        images_dir: Path alla directory delle immagini
        output_path: Path di output del video MP4
        corpus_path: Path al JSON del corpus filosofico (opzionale)
        quote_id: ID specifico della citazione da usare (opzionale, altrimenti random)
        custom_narration: Testo libero per la narrazione vocale (opzionale, sovrascrive la citazione)
        elevenlabs_api_key: API key ElevenLabs (opzionale, usa env var se non fornita)
    
    Returns:
        dict con output_path e metadati del tutorial generato
    """
    title    = project.get('title', 'Untitled')
    subtitle = project.get('subtitle', '')
    year     = str(project.get('year', ''))
    place    = project.get('place', '')
    images   = project.get('images', [])
    
    # Carica il corpus filosofico
    quotes = []
    if corpus_path and Path(corpus_path).exists():
        with open(corpus_path) as f:
            corpus = json.load(f)
            quotes = corpus.get('corpus', [])
    
    # Seleziona una citazione
    if quotes:
        if quote_id:
            quote = next((q for q in quotes if q['id'] == quote_id), random.choice(quotes))
        else:
            quote = random.choice(quotes)
    else:
        # Fallback
        quote = {
            'citazione_it': 'L\'archivio non è mai un deposito passivo ma una pratica attiva di costruzione del presente attraverso il passato.',
            'autore': 'Gabriella Giannachi',
            'opera': 'Archiviare tutto',
            'tema': 'archivio come laboratorio di memoria'
        }
    
    # Carica le immagini — pre-resize immediato per evitare di processare file da 20-50MB
    photos_pil = []
    for img_data in images[:12]:  # fino a 12 foto per ~25 secondi
        fpath = Path(images_dir) / img_data.get('file', '')
        if fpath.exists():
            try:
                with Image.open(str(fpath)) as im:
                    im_rgb = im.convert('RGB')
                    # Pre-resize: thumbnail mantiene aspect ratio, max 2x risoluzione target
                    im_rgb.thumbnail((W * 2, H * 2), Image.LANCZOS)
                    photos_pil.append(im_rgb.copy())
            except:
                pass

    if not photos_pil:
        raise ValueError('Nessuna immagine disponibile per il progetto')

    # Pre-calcola i frame fitted una sola volta per ogni foto (cover mode)
    fitted_photos = [_fit_image(p, W, H, contain=False) for p in photos_pil]

    # ── Generazione video STREAMING (senza accumulare frame in memoria) ──────────
    FPS_OUT = 24  # 24fps: 20% meno frame da encodare rispetto a 30fps
    video_no_audio = output_path.replace('.mp4', '_noaudio.mp4')
    proc = _open_ffmpeg_pipe(video_no_audio, fps=FPS_OUT)
    total_frames = 0

    def _write_section(frames_list):
        nonlocal total_frames
        for f in frames_list:
            _write_frame(proc, f)
            total_frames += 1

    try:
        # ── Struttura tutorial ~25 secondi ────────────────────────────────────────
        # 1. Title card (1.5 sec = 36 frame)
        tutorial_subtitle = f'Archivio — {title}'
        _write_section(_make_title_card(tutorial_subtitle, quote.get('tema', ''), n_frames=36))

        # 2. Prima foto con luogo/anno sovrapposto (2 sec = 48 frame)
        img_with_text = fitted_photos[0].copy()
        img_with_text = _darken(img_with_text, factor=0.6)
        draw_tmp = ImageDraw.Draw(img_with_text)
        font_text = _load_font(FONT_LIGHT, 32)
        y_start = H - 250
        for line in [place, year]:
            if line:
                bbox = draw_tmp.textbbox((0, 0), line, font=font_text)
                lw = bbox[2] - bbox[0]
                draw_tmp.text(((W - lw) // 2, y_start), line, font=font_text, fill=(240, 240, 240))
                y_start += 45
        for _ in range(48):
            _write_frame(proc, img_with_text)
            total_frames += 1

        # 3. Citazione filosofica su sfondo foto (3 sec = 72 frame)
        bg_photo_pre = fitted_photos[1] if len(fitted_photos) > 1 else fitted_photos[0]
        _write_section(_make_quote_frame(
            quote['citazione_it'], quote['autore'], quote.get('opera', ''),
            bg_photo=bg_photo_pre, n_frames=72
        ))

        # 4. Sequenza foto con ritmo easing (lento → veloce → lento)
        #    Usa le foto dalla 2 in poi (la 0 è già mostrata, la 1 è lo sfondo citazione)
        seq_photos = fitted_photos[2:]
        n_seq = len(seq_photos)
        if n_seq > 0:
            import math
            def _seq_dur(i, total):
                if total <= 1: return 36
                t = i / (total - 1)
                ease = abs(math.cos(math.pi * t))
                return max(6, int(6 + (36 - 6) * ease))  # da 6 a 36 frame
            seq_durations = [_seq_dur(i, n_seq) for i in range(n_seq)]
            for fitted, d in zip(seq_photos, seq_durations):
                for _ in range(d):
                    _write_frame(proc, fitted)
                    total_frames += 1

        # 5. Citazione in bianco su nero (2 sec = 48 frame)
        _write_section(_make_quote_frame(
            quote['citazione_it'], quote['autore'], quote.get('opera', ''),
            bg_photo=None, n_frames=48
        ))

        # 6. Ultima foto con overlay (1.5 sec = 36 frame) — se disponibile
        if len(fitted_photos) > 1:
            last_img = fitted_photos[-1].copy()
            last_img = _darken(last_img, factor=0.65)
            draw_last = ImageDraw.Draw(last_img)
            font_last = _load_font(FONT_LIGHT, 28)
            site_text = 'rizzipictures.com'
            bbox_s = draw_last.textbbox((0, 0), site_text, font=font_last)
            sw = bbox_s[2] - bbox_s[0]
            draw_last.text(((W - sw) // 2, H - 80), site_text, font=font_last, fill=(180, 180, 180))
            for _ in range(36):
                _write_frame(proc, last_img)
                total_frames += 1

        # 7. Title card finale (1.5 sec = 36 frame)
        _write_section(_make_title_card(
            title,
            f'{subtitle} — {place}, {year}' if subtitle else f'{place}, {year}',
            n_frames=36
        ))
    finally:
        _close_ffmpeg_pipe(proc)
    
    # Genera narrazione con voce clonata (ElevenLabs)
    has_voice = False
    if custom_narration and custom_narration.strip():
        # Usa il testo personalizzato dell'utente
        narration_text = custom_narration.strip()
    else:
        # Usa la citazione filosofica selezionata
        narration_text = (
            f"{title}. {place}, {year}.\n\n"
            f"{quote['citazione_it']}\n\n"
            f"— {quote['autore']}"
        )
    
    with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmp_audio:
        tmp_audio_path = tmp_audio.name
    
    try:
        has_voice = _generate_voice_narration(
            narration_text,
            tmp_audio_path,
            api_key=elevenlabs_api_key
        )
    except Exception as e:
        print(f'Voce non generata: {e}')
        has_voice = False
    
    if has_voice and Path(tmp_audio_path).exists() and Path(tmp_audio_path).stat().st_size > 1000:
        # Unisce audio e video
        merged_ok = _merge_audio_video(video_no_audio, tmp_audio_path, output_path)
        if not merged_ok:
            # Fallback: usa il video senza audio
            import shutil
            shutil.copy(video_no_audio, output_path)
        # Pulizia
        try:
            os.unlink(tmp_audio_path)
            os.unlink(video_no_audio)
        except:
            pass
    else:
        # Nessun audio — rinomina il video senza audio come output finale
        import shutil
        shutil.copy(video_no_audio, output_path)
        try:
            os.unlink(video_no_audio)
        except:
            pass
    
    return {
        'output_path': output_path,
        'duration_sec': total_frames / FPS,
        'has_voice': has_voice,
        'quote_used': {
            'id': quote.get('id', ''),
            'autore': quote['autore'],
            'opera': quote.get('opera', ''),
            'tema': quote.get('tema', '')
        },
        'photos_used': len(photos_pil),
        'total_frames': total_frames
    }


if __name__ == '__main__':
    import sys
    if len(sys.argv) < 3:
        print('Usage: python3 tutorial_generator.py <project_json> <output.mp4> [corpus.json]')
        sys.exit(1)
    
    with open(sys.argv[1]) as f:
        project = json.load(f)
    
    corpus_path = sys.argv[3] if len(sys.argv) > 3 else None
    result = generate_tutorial(project, 'uploads', sys.argv[2], corpus_path=corpus_path)
    print(json.dumps(result, indent=2))
