#!/usr/bin/env python3
"""
Rizzi CMS — App locale per gestione contenuti del sito
Avvio: python3 app.py  →  http://localhost:5151

  http://localhost:5151/      → Sito pubblico (prototipo)
  http://localhost:5151/cms   → CMS (gestione contenuti)
  http://localhost:5151/api/  → API REST
"""

import os, json, uuid, shutil, base64, threading
from pathlib import Path
from flask import Flask, request, jsonify, send_from_directory, send_file
from PIL import Image
import numpy as np

BASE   = Path(__file__).parent

# Su Render il Disk è montato su /opt/render/project/src/uploads
# Il db.json viene salvato in uploads/_data/ che è SUL DISK persistente
# In locale usiamo data/ relativa al progetto
_IS_RENDER = bool(os.environ.get('RENDER'))

UPLOAD = BASE / 'uploads'
DATA   = UPLOAD / '_data' if _IS_RENDER else BASE / 'data'

# ── AUTO-TRIM BORDI MONOCROMATICI ──────────────────────────────────────────────
def auto_trim_border(im, threshold=18, min_strip=2, max_strip_pct=0.08):
    """
    Ritaglia automaticamente bordi monocromatici (bianchi, grigi, neri) da un'immagine PIL.
    - threshold: tolleranza colore (0-255); bordi con std_dev < threshold vengono rimossi
    - min_strip: minimo px da rimuovere per lato perché valga la pena
    - max_strip_pct: massimo % del lato che può essere rimosso (evita crop aggressivi)
    Restituisce l'immagine croppata (o l'originale se nessun bordo trovato).
    """
    arr = np.array(im.convert('RGB'), dtype=np.float32)
    h, w = arr.shape[:2]
    max_rows = int(h * max_strip_pct)
    max_cols = int(w * max_strip_pct)

    def row_is_border(row_pixels):
        """True se la riga ha bassa varianza (monocromatica)"""
        return float(row_pixels.std()) < threshold

    def col_is_border(col_pixels):
        return float(col_pixels.std()) < threshold

    top = 0
    while top < max_rows and row_is_border(arr[top]):
        top += 1

    bottom = h
    while (h - bottom) < max_rows and row_is_border(arr[bottom - 1]):
        bottom -= 1

    left = 0
    while left < max_cols and col_is_border(arr[:, left]):
        left += 1

    right = w
    while (w - right) < max_cols and col_is_border(arr[:, right - 1]):
        right -= 1

    # Applica solo se c'è qualcosa da rimuovere
    if top >= min_strip or (h - bottom) >= min_strip or left >= min_strip or (w - right) >= min_strip:
        return im.crop((left, top, right, bottom))
    return im
# ───────────────────────────────────────────────────────────────────────────────

# ── LETTURA KEYWORDS IPTC ────────────────────────────────────────
def read_iptc_keywords(fpath):
    """
    Legge le keywords IPTC/XMP da un file immagine.
    Restituisce una lista di stringhe (mai None).
    NON legge caption/description — solo keywords.
    Supporta: IPTC IIM (tag 2:25), XMP dc:subject, XMP lr:hierarchicalSubject.
    Legge anche dai raw bytes per massima compatibilità con DxO/Photoshop/Lightroom.
    """
    import re as _re
    keywords = []
    try:
        # Metodo 1: iptcinfo3 (IPTC IIM standard, tag 2:25)
        try:
            from iptcinfo3 import IPTCInfo
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter('ignore')
                info = IPTCInfo(str(fpath), force=True)
            kws = info.data.get(25, [])  # tag 25 = Keywords
            for k in kws:
                if isinstance(k, bytes):
                    k = k.decode('utf-8', errors='ignore')
                k = k.strip()
                if k:
                    keywords.append(k)
        except Exception:
            pass

        # Metodo 2: Pillow EXIF/XMP (info dict)
        if not keywords:
            try:
                from PIL import Image as _PILImg
                with _PILImg.open(str(fpath)) as im:
                    xmp = im.info.get('xmp', b'')
                    if isinstance(xmp, bytes):
                        xmp = xmp.decode('utf-8', errors='ignore')
                    if xmp:
                        matches = _re.findall(
                            r'<(?:dc:subject|lr:hierarchicalSubject)>.*?<rdf:Bag>(.*?)</rdf:Bag>',
                            xmp, _re.DOTALL
                        )
                        for bag in matches:
                            items = _re.findall(r'<rdf:li[^>]*>(.*?)</rdf:li>', bag)
                            keywords.extend([i.strip() for i in items if i.strip()])
            except Exception:
                pass

        # Metodo 3: raw bytes — legge XMP direttamente dal file binario
        # Funziona con JPEG/JPG salvati da DxO PhotoLab, Photoshop, Lightroom
        # anche quando Pillow non espone l'XMP nell'info dict
        if not keywords:
            try:
                with open(str(fpath), 'rb') as _f:
                    _raw = _f.read()
                # Cerca il blocco XMP (<?xpacket o <x:xmpmeta)
                for _marker in (b'<?xpacket', b'<x:xmpmeta'):
                    _pos = _raw.find(_marker)
                    if _pos != -1:
                        _end = _raw.find(b'</x:xmpmeta>', _pos)
                        if _end == -1:
                            _end = _pos + 65536  # max 64 KB
                        _xmp = _raw[_pos:_end + len(b'</x:xmpmeta>')].decode('utf-8', errors='ignore')
                        # dc:subject (standard XMP)
                        _matches = _re.findall(
                            r'<dc:subject>\s*<rdf:(?:Bag|Seq|Alt)>(.*?)</rdf:(?:Bag|Seq|Alt)>',
                            _xmp, _re.DOTALL
                        )
                        for _bag in _matches:
                            _items = _re.findall(r'<rdf:li[^>]*>(.*?)</rdf:li>', _bag)
                            keywords.extend([i.strip() for i in _items if i.strip()])
                        # lr:hierarchicalSubject (Lightroom)
                        _matches2 = _re.findall(
                            r'<lr:hierarchicalSubject>\s*<rdf:(?:Bag|Seq|Alt)>(.*?)</rdf:(?:Bag|Seq|Alt)>',
                            _xmp, _re.DOTALL
                        )
                        for _bag in _matches2:
                            _items = _re.findall(r'<rdf:li[^>]*>(.*?)</rdf:li>', _bag)
                            keywords.extend([i.strip() for i in _items if i.strip()])
                        # photoshop:Keywords (attributo inline, formato alternativo)
                        _kw_attr = _re.findall(r'photoshop:Keywords="([^"]+)"', _xmp)
                        for _kw in _kw_attr:
                            keywords.extend([k.strip() for k in _kw.split(';') if k.strip()])
                        if keywords:
                            break
            except Exception:
                pass

    except Exception:
        pass

    # Deduplicazione case-insensitive preservando l'originale
    seen = set()
    result = []
    for k in keywords:
        if k.lower() not in seen:
            seen.add(k.lower())
            result.append(k)
    return result


def merge_keywords_str(existing_str, new_list):
    """
    Aggiunge new_list alle keywords esistenti (stringa CSV).
    Non sovrascrive mai le keywords esistenti.
    """
    existing_set = {k.strip().lower() for k in existing_str.split(',') if k.strip()}
    added = [k for k in new_list if k.strip() and k.strip().lower() not in existing_set]
    if not added:
        return existing_str
    if existing_str.strip():
        return existing_str.rstrip(', ') + ', ' + ', '.join(added)
    return ', '.join(added)


# ── AI TAGGING (asincrono, non blocca l'upload) ──────────────────
def ai_tag_image(fpath, img_data, db_ref, pid):
    """Chiama GPT-4o mini per generare keyword per una foto. Eseguito in background."""
    try:
        import openai
        client = openai.OpenAI()  # usa OPENAI_API_KEY dall'ambiente
        with open(str(fpath), 'rb') as f:
            b64 = base64.b64encode(f.read()).decode()
        ext = Path(str(fpath)).suffix.lower().replace('.jpg', 'jpeg').replace('.jpeg', 'jpeg').replace('.png', 'png').replace('.webp', 'webp')
        if ext not in ['jpeg', 'png', 'webp']: ext = 'jpeg'
        resp = client.chat.completions.create(
            model='gpt-4.1-mini',
            max_tokens=120,
            messages=[{
                'role': 'user',
                'content': [
                    {'type': 'image_url', 'image_url': {'url': f'data:image/{ext};base64,{b64}', 'detail': 'low'}},
                    {'type': 'text', 'text': 'List 8-12 concise English keywords describing this photo (subject, mood, colors, setting, style). Respond ONLY with a comma-separated list, no explanations.'}
                ]
            }]
        )
        new_keywords = resp.choices[0].message.content.strip()
        # Aggiorna il db: APPEND alle keyword esistenti (non sovrascrive)
        db = load_db()
        p = next((p for p in db['projects'] if p['id'] == pid), None)
        if p:
            img = next((i for i in p['images'] if i['id'] == img_data['id']), None)
            if img:
                existing = img.get('keywords', '').strip()
                if existing:
                    # Unisce e deduplica (case-insensitive)
                    existing_set = {k.strip().lower() for k in existing.split(',') if k.strip()}
                    new_list = [k.strip() for k in new_keywords.split(',') if k.strip()]
                    added = [k for k in new_list if k.lower() not in existing_set]
                    img['keywords'] = existing + (', ' + ', '.join(added) if added else '')
                else:
                    img['keywords'] = new_keywords
                save_db(db)
    except Exception as e:
        pass  # tagging fallisce silenziosamente, non blocca nulla

STATIC = BASE / 'static'
DATA.mkdir(exist_ok=True)
UPLOAD.mkdir(exist_ok=True)

DB_FILE = DATA / 'db.json'

# ─────────────────────────────────────────────
# DB helpers
# ─────────────────────────────────────────────
def load_db():
    if DB_FILE.exists():
        with open(DB_FILE) as f:
            db = json.load(f)
    else:
        db = {}
    # Garantisce che tutte le chiavi esistano
    db.setdefault('projects', [])
    db.setdefault('categories', [])
    db.setdefault('texts', {})
    db.setdefault('settings', {})
    # Migrazione: garantisce che tutte le categorie del sito siano presenti
    REQUIRED_CATS = [
        {'id': 'cities',       'name': 'Cities',              'order': 0, 'visible': True},
        {'id': 'miscellanea',  'name': 'Miscellanea',          'order': 1, 'visible': True, 'layout': 'cities'},
        {'id': 'archive',      'name': 'Archive',             'order': 2, 'visible': True},
        {'id': 'interview',    'name': 'Interview',           'order': 3, 'visible': True},
        {'id': 'books',        'name': 'Books',               'order': 4, 'visible': True},
        {'id': 'sculptures',   'name': 'Sculptures Project',  'order': 5, 'visible': True},
        {'id': 'biography',    'name': 'Biography',           'order': 6, 'visible': True},
        {'id': 'contact',      'name': 'Contact',             'order': 7, 'visible': True},
        {'id': 'index',        'name': 'Index (foto laterale)', 'order': 8, 'visible': True},
    ]
    existing_ids = {c['id'] for c in db['categories']}
    changed = False
    for cat in REQUIRED_CATS:
        if cat['id'] not in existing_ids:
            db['categories'].append(cat)
            changed = True
    if changed:
        save_db(db)
    return db

def save_db(db):
    with open(DB_FILE, 'w') as f:
        json.dump(db, f, indent=2, ensure_ascii=False)

def thumb_path(filename):
    return UPLOAD / 'thumbs' / filename

# ─────────────────────────────────────────────
# Flask app
# ─────────────────────────────────────────────
app = Flask(__name__, static_folder=str(STATIC))

@app.after_request
def cors(r):
    r.headers['Access-Control-Allow-Origin']  = '*'
    r.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    r.headers['Access-Control-Allow-Methods'] = 'GET,POST,PUT,DELETE,OPTIONS'
    return r

# ── Sito pubblico (prototipo) ───────────────────────────
# http://localhost:5151/  →  sito
def _serve_site_index():
    """Serve index.html con no-cache per garantire sempre la versione aggiornata."""
    from flask import make_response
    resp = make_response(send_file(STATIC / 'site' / 'index.html'))
    resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    return resp

@app.route('/')
def site_root():
    return _serve_site_index()

@app.route('/site')
@app.route('/site/')
def site_index():
    return _serve_site_index()

@app.route('/site/<path:filename>')
def serve_site_static(filename):
    return send_from_directory(STATIC / 'site', filename)

# ── CMS ───────────────────────────────────────
# http://localhost:5151/cms  →  CMS
@app.route('/cms')
@app.route('/cms/')
def cms_index():
    return send_file(STATIC / 'index.html')

# ── Upload files ──────────────────────────────
@app.route('/uploads/<path:filename>')
def serve_upload(filename):
    return send_from_directory(UPLOAD, filename)

# ── CATEGORIES ────────────────────────────────
@app.route('/api/categories', methods=['GET'])
def get_categories():
    db = load_db()
    cats = sorted(db['categories'], key=lambda c: c.get('order', 0))
    return jsonify(cats)

@app.route('/api/categories', methods=['POST'])
def create_category():
    db = load_db()
    data = request.json
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'error': 'name required'}), 400
    # Accetta ID personalizzato se fornito, altrimenti genera UUID
    custom_id = data.get('id', '').strip()
    cat_id = custom_id if custom_id else str(uuid.uuid4())[:8]
    cat = {
        'id':      cat_id,
        'name':    name,
        'order':   data.get('order', len(db['categories'])),
        'visible': data.get('visible', True),
    }
    if data.get('layout'):
        cat['layout'] = data['layout']
    db['categories'].append(cat)
    save_db(db)
    return jsonify(cat), 201

@app.route('/api/categories/<cid>', methods=['PUT'])
def update_category(cid):
    db = load_db()
    cat = next((c for c in db['categories'] if c['id'] == cid), None)
    if not cat: return jsonify({'error': 'not found'}), 404
    data = request.json
    for k in ['name', 'order', 'visible']:
        if k in data:
            cat[k] = data[k]
    save_db(db)
    return jsonify(cat)

@app.route('/api/categories/<cid>', methods=['DELETE'])
def delete_category(cid):
    db = load_db()
    db['categories'] = [c for c in db['categories'] if c['id'] != cid]
    # Rimuovi l'assegnazione dai progetti
    for p in db['projects']:
        if p.get('category_id') == cid:
            p['category_id'] = None
    save_db(db)
    return jsonify({'ok': True})

@app.route('/api/categories/reorder', methods=['PUT'])
def reorder_categories():
    db = load_db()
    order = request.json.get('order', [])  # lista di id in ordine
    for i, cid in enumerate(order):
        cat = next((c for c in db['categories'] if c['id'] == cid), None)
        if cat:
            cat['order'] = i
    save_db(db)
    return jsonify({'ok': True})

# ── PROJECTS ──────────────────────────────────
@app.route('/api/projects', methods=['GET'])
def get_projects():
    db = load_db()
    category_id = request.args.get('category_id')
    projects = db['projects']
    if category_id:
        projects = [p for p in projects if p.get('category_id') == category_id]
    return jsonify(projects)

@app.route('/api/projects', methods=['POST'])
def create_project():
    db = load_db()
    data = request.json
    project = {
        'id':          str(uuid.uuid4())[:8],
        'title':          data.get('title', 'Senza titolo'),
        'year':           data.get('year', ''),
        'place':          data.get('place', ''),
        'publication':    data.get('publication', ''),
        'category_id':    data.get('category_id', None),  # ID della categoria madre
        'subtitle':       data.get('subtitle', ''),
        'description':    data.get('description', ''),
        'technique':      data.get('technique', ''),
        'medium':         data.get('medium', ''),
        'prints':         data.get('prints', ''),
        'editions':       data.get('editions', ''),
        'keywords_manual': data.get('keywords_manual', ''),
        'sections':       data.get('sections', ['archive']),  # sezioni in cui appare il progetto (default: solo archive)
        'images':         [],
        'texts':          [],
        'order':          len(db['projects']),
    }
    db['projects'].append(project)
    save_db(db)
    return jsonify(project), 201

@app.route('/api/projects/<pid>', methods=['GET'])
def get_project(pid):
    db = load_db()
    p = next((p for p in db['projects'] if p['id'] == pid), None)
    if not p: return jsonify({'error': 'not found'}), 404
    return jsonify(p)

@app.route('/api/projects/<pid>', methods=['PUT'])
def update_project(pid):
    db = load_db()
    p = next((p for p in db['projects'] if p['id'] == pid), None)
    if not p: return jsonify({'error': 'not found'}), 404
    data = request.json
    for k in ['title','year','place','publication','category_id','subtitle','description','order',
             'technique','medium','prints','editions','keywords_manual','sections']:
        if k in data:
            p[k] = data[k]
    save_db(db)
    return jsonify(p)

@app.route('/api/projects/<pid>', methods=['DELETE'])
def delete_project(pid):
    db = load_db()
    db['projects'] = [p for p in db['projects'] if p['id'] != pid]
    save_db(db)
    return jsonify({'ok': True})

# ── IMAGES ────────────────────────────────────
@app.route('/api/projects/<pid>/images', methods=['POST'])
def upload_images(pid):
    db = load_db()
    p = next((p for p in db['projects'] if p['id'] == pid), None)
    if not p: return jsonify({'error': 'not found'}), 404

    results = []
    (UPLOAD / 'thumbs').mkdir(exist_ok=True)

    for file in request.files.getlist('files'):
        ext  = Path(file.filename).suffix.lower()
        if ext not in ['.jpg','.jpeg','.png','.webp','.tiff','.tif']:
            continue
        fname = str(uuid.uuid4())[:12] + ext
        fpath = UPLOAD / fname
        file.save(str(fpath))

        # ── LEGGI KEYWORDS DAL FILE ORIGINALE (prima dell'ottimizzazione) ──
        # IMPORTANTE: Pillow rimuove l'XMP durante il salvataggio ottimizzato.
        # Bisogna leggere i metadati dal file originale prima di qualsiasi conversione.
        iptc_kws_original = read_iptc_keywords(fpath)

        # Conversione automatica + aspect ratio + thumbnail
        MAX_SIDE = 2500   # px lato lungo massimo
        WEB_QUALITY = 88  # qualità JPG per l'originale ottimizzato
        try:
            with Image.open(str(fpath)) as im:
                # Converti in RGB (gestisce PNG con trasparenza, TIFF, ecc.)
                if im.mode not in ('RGB', 'L'):
                    im = im.convert('RGB')

                # ── CORREGGI ORIENTAMENTO EXIF (fondamentale per foto da fotocamera) ──
                # Senza questo, una foto orizzontale con EXIF rotation=6 viene letta
                # come verticale e l'aspect ratio risulta invertita.
                from PIL import ImageOps
                im = ImageOps.exif_transpose(im)

                # ── auto_trim_border DISABILITATO ──
                # Rimosso: ritagliava i bordi monocromatici modificando le proporzioni
                # originali delle foto in modo indesiderato.
                # im = auto_trim_border(im)

                w, h = im.size
                ar   = round(w / h, 4)

                # Ridimensiona se troppo grande
                if max(w, h) > MAX_SIDE:
                    if w >= h:
                        new_w, new_h = MAX_SIDE, int(MAX_SIDE / ar)
                    else:
                        new_h, new_w = MAX_SIDE, int(MAX_SIDE * ar)
                    im = im.resize((new_w, new_h), Image.LANCZOS)
                    w, h = new_w, new_h

                # Salva sempre come JPG ottimizzato (sovrascrive il file originale)
                fname_jpg = str(uuid.uuid4())[:12] + '.jpg'
                fpath_jpg = UPLOAD / fname_jpg
                im.save(str(fpath_jpg), 'JPEG', quality=WEB_QUALITY, optimize=True)
                # Rimuovi il file originale se era in formato diverso
                if fpath != fpath_jpg:
                    try: fpath.unlink()
                    except: pass
                fpath = fpath_jpg
                fname = fname_jpg
                ext   = '.jpg'

                # Thumbnail
                tw = 400
                th = int(400 / ar)
                thumb = im.copy()
                thumb.thumbnail((tw, th), Image.LANCZOS)
                tname = 'thumb_' + fname
                thumb.save(str(UPLOAD / 'thumbs' / tname), 'JPEG', quality=82)
        except Exception as e:
            ar    = 1.0
            tname = fname

        # ── USA LE KEYWORDS LETTE DAL FILE ORIGINALE (prima dell'ottimizzazione) ──
        iptc_kws = iptc_kws_original
        iptc_str = ', '.join(iptc_kws) if iptc_kws else ''

        img_data = {
            'id':       str(uuid.uuid4())[:8],
            'file':     fname,
            'thumb':    'thumbs/' + tname,
            'ar':       ar,
            'caption':  '',
            'keywords': iptc_str,  # IPTC prima; AI aggiungerà in append
        }
        p['images'].append(img_data)
        results.append(img_data)

        # ── AI TAGGING: solo se abilitato nelle settings (default: OFF) ──
        # L'utente può attivarlo manualmente dal CMS con il bottone "Tag AI"
        # oppure per singola foto con il bottone nella griglia immagini
        db_check = load_db()
        ai_enabled = db_check.get('settings', {}).get('ai_tagging_auto', False)
        if ai_enabled:
            t = threading.Thread(
                target=ai_tag_image,
                args=(fpath, img_data, None, pid),
                daemon=True
            )
            t.start()

    save_db(db)
    return jsonify(results), 201

@app.route('/api/projects/<pid>/images/<iid>', methods=['DELETE'])
def delete_image(pid, iid):
    db = load_db()
    p = next((p for p in db['projects'] if p['id'] == pid), None)
    if not p: return jsonify({'error': 'not found'}), 404
    img = next((i for i in p['images'] if i['id'] == iid), None)
    if img:
        try: (UPLOAD / img['file']).unlink(missing_ok=True)
        except: pass
        p['images'] = [i for i in p['images'] if i['id'] != iid]
    save_db(db)
    return jsonify({'ok': True})

@app.route('/api/tag-all', methods=['POST'])
def tag_all_images():
    """Avvia il tagging AI per tutte le foto che non hanno ancora keyword."""
    db = load_db()
    count = 0
    for p in db['projects']:
        for img in p.get('images', []):
            if not img.get('keywords'):
                fpath = UPLOAD / img['file']
                if fpath.exists():
                    t = threading.Thread(target=ai_tag_image, args=(fpath, img, None, p['id']), daemon=True)
                    t.start()
                    count += 1
    return jsonify({'ok': True, 'started': count})

@app.route('/api/projects/<pid>/images/<iid>/tag-ai', methods=['POST'])
def tag_image_ai(pid, iid):
    """Avvia il tagging AI per una foto già caricata (utile per foto esistenti)."""
    db = load_db()
    p = next((p for p in db['projects'] if p['id'] == pid), None)
    if not p: return jsonify({'error': 'not found'}), 404
    img = next((i for i in p['images'] if i['id'] == iid), None)
    if not img: return jsonify({'error': 'not found'}), 404
    fpath = UPLOAD / img['file']
    if not fpath.exists(): return jsonify({'error': 'file not found'}), 404
    t = threading.Thread(target=ai_tag_image, args=(fpath, img, None, pid), daemon=True)
    t.start()
    return jsonify({'ok': True, 'message': 'tagging avviato in background'})

@app.route('/api/projects/<pid>/images/<iid>/caption', methods=['PUT'])
def update_caption(pid, iid):
    db = load_db()
    p = next((p for p in db['projects'] if p['id'] == pid), None)
    if not p: return jsonify({'error': 'not found'}), 404
    img = next((i for i in p['images'] if i['id'] == iid), None)
    if img:
        img['caption'] = request.json.get('caption', '')
    save_db(db)
    return jsonify(img)

# ── TEXTS ─────────────────────────────────────
@app.route('/api/projects/<pid>/texts', methods=['POST'])
def add_text(pid):
    db = load_db()
    p = next((p for p in db['projects'] if p['id'] == pid), None)
    if not p: return jsonify({'error': 'not found'}), 404
    block = {
        'id':      str(uuid.uuid4())[:8],
        'type':    request.json.get('type', 'body'),
        'content': request.json.get('content', ''),
        'order':   len(p.get('texts', [])),
    }
    if 'texts' not in p: p['texts'] = []
    p['texts'].append(block)
    save_db(db)
    return jsonify(block), 201

@app.route('/api/projects/<pid>/texts/<tid>', methods=['PUT'])
def update_text(pid, tid):
    db = load_db()
    p = next((p for p in db['projects'] if p['id'] == pid), None)
    if not p: return jsonify({'error': 'not found'}), 404
    block = next((t for t in p.get('texts', []) if t['id'] == tid), None)
    if not block: return jsonify({'error': 'not found'}), 404
    for k in ['type','content','order']:
        if k in request.json:
            block[k] = request.json[k]
    save_db(db)
    return jsonify(block)

@app.route('/api/projects/<pid>/texts/<tid>', methods=['DELETE'])
def delete_text(pid, tid):
    db = load_db()
    p = next((p for p in db['projects'] if p['id'] == pid), None)
    if not p: return jsonify({'error': 'not found'}), 404
    p['texts'] = [t for t in p.get('texts', []) if t['id'] != tid]
    save_db(db)
    return jsonify({'ok': True})

# ── EXPORT ────────────────────────────────────
@app.route('/api/export', methods=['GET'])
def export_all():
    db = load_db()
    return jsonify(db)

@app.route('/api/export/<pid>', methods=['GET'])
def export_project(pid):
    db = load_db()
    p = next((p for p in db['projects'] if p['id'] == pid), None)
    if not p: return jsonify({'error': 'not found'}), 404
    return jsonify(p)

# ── SETTINGS ──────────────────────────────────
@app.route('/api/settings', methods=['GET'])
def get_settings():
    db = load_db()
    return jsonify(db.get('settings', {}))

@app.route('/api/settings', methods=['PUT'])
def update_settings():
    db = load_db()
    db['settings'].update(request.json)
    save_db(db)
    return jsonify(db['settings'])

# ── LANDING PHOTO ──────────────────────────────────────────
@app.route('/api/settings/landing-photo', methods=['POST'])
def upload_landing_photo():
    """Carica la foto della landing page (sostituisce quella precedente)."""
    if 'file' not in request.files:
        return jsonify({'error': 'nessun file'}), 400
    f = request.files['file']
    if not f.filename:
        return jsonify({'error': 'nome file vuoto'}), 400

    UPLOAD.mkdir(exist_ok=True)
    ext = Path(f.filename).suffix.lower() or '.jpg'
    fname = f'landing{ext}'
    fpath = UPLOAD / fname

    # Salva e ottimizza
    img = Image.open(f.stream).convert('RGB')
    max_side = 2500
    if max(img.size) > max_side:
        img.thumbnail((max_side, max_side), Image.LANCZOS)
    img.save(str(fpath), 'JPEG', quality=88, optimize=True)
    # Rinomina sempre come .jpg
    final_path = UPLOAD / 'landing.jpg'
    if fpath != final_path:
        fpath.rename(final_path)

    # Salva il riferimento nel db
    db = load_db()
    db['settings']['landing_photo'] = 'landing.jpg'
    save_db(db)
    return jsonify({'ok': True, 'file': 'landing.jpg', 'url': f'/uploads/landing.jpg'})

@app.route('/api/settings/landing-photo', methods=['DELETE'])
def delete_landing_photo():
    """Rimuove la foto landing personalizzata (torna alla foto di default)."""
    db = load_db()
    db['settings'].pop('landing_photo', None)
    save_db(db)
    fpath = UPLOAD / 'landing.jpg'
    if fpath.exists():
        fpath.unlink()
    return jsonify({'ok': True})

# ── REORDER IMAGES ──────────────────────────────────────────
@app.route('/api/projects/<pid>/images/reorder', methods=['PUT'])
def reorder_images(pid):
    """Riordina le immagini di un progetto. Body: {order: [id1, id2, ...]}"""
    db = load_db()
    p = next((p for p in db['projects'] if p['id'] == pid), None)
    if not p: return jsonify({'error': 'not found'}), 404
    order = request.json.get('order', [])
    img_map = {img['id']: img for img in p.get('images', [])}
    p['images'] = [img_map[iid] for iid in order if iid in img_map]
    # Aggiunge eventuali immagini non presenti nell'order (sicurezza)
    ordered_ids = set(order)
    for img in img_map.values():
        if img['id'] not in ordered_ids:
            p['images'].append(img)
    save_db(db)
    return jsonify({'ok': True})

# ── MIGRAZIONE IMMAGINI ──────────────────────────────────────
# Allinea i nomi nel db.json con i file UUID fisici in uploads/
# Logica: se img.file non esiste fisicamente ma c'è un solo file UUID
# nella cartella con la stessa estensione, aggiorna il record.
# Chiamare UNA SOLA VOLTA dopo l'aggiornamento.
@app.route('/api/migrate-images', methods=['POST'])
def migrate_images():
    db = load_db()
    # Lista tutti i file UUID nella cartella uploads (esclude thumbs/)
    uuid_files = [f.name for f in UPLOAD.iterdir()
                  if f.is_file() and not f.name.startswith('thumb_')]
    # Costruisce un set dei file che esistono fisicamente
    existing = set(uuid_files)

    fixed = 0
    broken = []
    for p in db['projects']:
        for img in p.get('images', []):
            fname = img.get('file', '')
            if fname not in existing:
                # Il file non esiste con questo nome — cerca un match per UUID
                # (il CMS salva con UUID, quindi tutti i file validi hanno formato UUID)
                broken.append({'project': p['title'], 'file': fname})

    # Strategia: ricostruisce i record immagine abbinando per ordine
    # Se un progetto ha N immagini e N file UUID nella cartella, li abbina in ordine
    for p in db['projects']:
        bad_imgs = [img for img in p.get('images', []) if img.get('file','') not in existing]
        if not bad_imgs:
            continue
        # Trova i file UUID non ancora assegnati ad altri progetti
        assigned = set()
        for pp in db['projects']:
            for im in pp.get('images', []):
                if im.get('file','') in existing:
                    assigned.add(im['file'])
        # File UUID disponibili (non assegnati)
        available = sorted([f for f in uuid_files if f not in assigned])
        for i, img in enumerate(bad_imgs):
            if i < len(available):
                old = img['file']
                img['file'] = available[i]
                # Aggiorna anche il thumb
                ext = Path(available[i]).suffix
                tname = 'thumbs/thumb_' + available[i].replace(ext, '.jpg')
                if (UPLOAD / tname.replace('thumbs/','thumbs/')).exists():
                    img['thumb'] = tname
                fixed += 1

    save_db(db)
    return jsonify({'ok': True, 'fixed': fixed, 'broken_before': broken})# ── RICERCA SEMANTICA AI ───────────────────────────────────────
@app.route('/api/search', methods=['POST'])
def semantic_search():
    """Ricerca semantica AI: dato un testo libero, restituisce gli ID dei progetti pertinenti."""
    try:
        import openai
        data = request.json
        q = data.get('q', '').strip()
        projects = data.get('projects', [])
        if not q or not projects:
            return jsonify({'ids': []})

        # Costruisce il contesto per GPT
        proj_list = '\n'.join([
            f"ID:{p['id']} | {p.get('year','')} | {p.get('title','')} | {p.get('subtitle','')} | {p.get('place','')} | keywords: {p.get('keywords','')}"
            for p in projects
        ])
        prompt = f"""You are a photo archive search assistant. Given a user query, return the IDs of the most relevant projects.

User query: \"{q}\"

Projects:
{proj_list}

Return ONLY a JSON array of matching project IDs (strings), e.g. ["abc123", "def456"]. Return [] if nothing matches. No explanations."""

        client = openai.OpenAI()
        resp = client.chat.completions.create(
            model='gpt-4.1-mini',
            max_tokens=200,
            messages=[{'role': 'user', 'content': prompt}]
        )
        import re
        text = resp.choices[0].message.content.strip()
        # Estrai l'array JSON dalla risposta
        match = re.search(r'\[.*?\]', text, re.DOTALL)
        if match:
            ids = json.loads(match.group())
        else:
            ids = []
        return jsonify({'ids': ids})
    except Exception as e:
        return jsonify({'ids': [], 'error': str(e)})

# ── GENERAZIONE TESTI AI ──────────────────────────────────────
@app.route('/api/ai-write', methods=['POST'])
def ai_write():
    """Genera testi AI per i campi del CMS su richiesta dell'utente."""
    try:
        import openai
        data = request.json
        field   = data.get('field', '')      # es. 'description', 'caption', 'biography'
        hint    = data.get('hint', '').strip()  # indicazione breve dell'utente
        context = data.get('context', {})    # dati del progetto/foto per contestualizzare
        lang    = data.get('lang', 'it')     # lingua output: 'it' o 'en'

        lang_label = 'Italian' if lang == 'it' else 'English'

        # Costruisce il prompt in base al campo richiesto
        if field == 'description':
            title    = context.get('title', '')
            year     = context.get('year', '')
            place    = context.get('place', '')
            subtitle = context.get('subtitle', '')
            keywords = context.get('keywords', '')
            prompt = f"""You are a professional photography critic and writer. Write a short project description (2-4 sentences, max 120 words) in {lang_label} for a photography project with these details:
- Title: {title}
- Year: {year}
- Place: {place}
- Subtitle/genre: {subtitle}
- Keywords: {keywords}
- Photographer's note: {hint}

Write in a concise, evocative style suitable for a photography portfolio. Do not use marketing language. Return only the text, no titles or labels."""

        elif field == 'caption':
            title    = context.get('title', '')
            place    = context.get('place', '')
            year     = context.get('year', '')
            keywords = context.get('keywords', '')
            prompt = f"""You are a photography editor. Write a short caption (1-2 sentences, max 60 words) in {lang_label} for a photograph from the series "{title}" ({place}, {year}).
Keywords visible in the image: {keywords}
Photographer's note: {hint}

Return only the caption text, no labels."""

        elif field == 'biography':
            prompt = f"""You are a professional writer specializing in artist biographies. Write a short biography (3-5 sentences, max 200 words) in {lang_label} for a photographer.
Notes provided: {hint}

Write in third person, professional tone. Return only the biography text."""

        elif field == 'interview':
            prompt = f"""You are a journalist writing an interview with a photographer. Based on these notes or bullet points, write a flowing interview excerpt (Q&A format or narrative, max 300 words) in {lang_label}.
Notes: {hint}

Return only the interview text."""

        elif field == 'book_description':
            title    = context.get('title', '')
            year     = context.get('year', '')
            prompt = f"""You are a publisher's editor. Write a short book description (2-4 sentences, max 120 words) in {lang_label} for a photography book.
- Book title: {title}
- Year: {year}
- Notes: {hint}

Return only the description text."""

        elif field == 'title_suggestion':
            place    = context.get('place', '')
            year     = context.get('year', '')
            subtitle = context.get('subtitle', '')
            prompt = f"""Suggest 5 short, evocative titles (max 4 words each) in {lang_label} for a photography project.
- Place: {place}
- Year: {year}
- Genre/subtitle: {subtitle}
- Notes: {hint}

Return only a numbered list of 5 titles, one per line."""

        else:
            return jsonify({'error': 'Campo non supportato'}), 400

        client = openai.OpenAI()
        resp = client.chat.completions.create(
            model='gpt-4.1-mini',
            max_tokens=400,
            messages=[{'role': 'user', 'content': prompt}]
        )
        text = resp.choices[0].message.content.strip()
        return jsonify({'text': text})

    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ── SEED CITIES ───────────────────────────────────────────
@app.route('/api/seed-cities', methods=['POST'])
def seed_cities():
    """Aggiunge 15 progetti vuoti con nomi di città internazionali.
    Idempotente: non duplica se esistono già."""
    cities = [
        'Tokyo', 'Londra', 'Berlino', 'Città del Messico', 'Mumbai',
        'Lagos', 'Buenos Aires', 'Shanghai', 'Istanbul', 'Cairo',
        'Los Angeles', 'Amsterdam', 'Nairobi', 'Seoul', 'Lisbona'
    ]
    db = load_db()
    existing_titles = {p['title'] for p in db['projects']}
    added = []
    max_order = max((p.get('order', 0) for p in db['projects']), default=0)
    for i, city in enumerate(cities):
        if city in existing_titles:
            continue
        project = {
            'id':          str(uuid.uuid4())[:8],
            'title':       city,
            'year':        '',
            'place':       city,
            'publication': '',
            'category_id': 'archive',
            'category':    'Photography',
            'subtitle':    '',
            'description': '',
            'section':     'archive',
            'images':      [],
            'texts':       [],
            'order':       max_order + i + 1,
        }
        db['projects'].append(project)
        added.append(city)
    save_db(db)
    return jsonify({'ok': True, 'added': added, 'skipped': [c for c in cities if c not in added]})

# ── KEYWORDS: re-scan IPTC + aggiornamento manuale ──────────────
@app.route('/api/projects/<pid>/images/<iid>/keywords', methods=['PUT'])
def update_image_keywords(pid, iid):
    """Aggiorna le keywords manuali di una foto (append, non sovrascrive IPTC/AI)."""
    db = load_db()
    p = next((p for p in db['projects'] if p['id'] == pid), None)
    if not p: return jsonify({'error': 'not found'}), 404
    img = next((i for i in p.get('images', []) if i['id'] == iid), None)
    if not img: return jsonify({'error': 'not found'}), 404
    manual_kws = request.json.get('keywords', '')
    replace    = request.json.get('replace', False)
    if replace:
        # Sovrascrittura completa (editing manuale)
        img['keywords'] = manual_kws.strip()
    else:
        # Append (non sovrascrive IPTC/AI)
        img['keywords'] = merge_keywords_str(img.get('keywords', ''),
                                              [k.strip() for k in manual_kws.split(',') if k.strip()])
    save_db(db)
    return jsonify({'ok': True, 'keywords': img['keywords']})


@app.route('/api/projects/<pid>/images/<iid>/rescan-iptc', methods=['POST'])
def rescan_iptc(pid, iid):
    """Ri-legge le keywords IPTC da una foto già caricata e le aggiunge in append."""
    db = load_db()
    p = next((p for p in db['projects'] if p['id'] == pid), None)
    if not p: return jsonify({'error': 'not found'}), 404
    img = next((i for i in p.get('images', []) if i['id'] == iid), None)
    if not img: return jsonify({'error': 'not found'}), 404
    # Cerca il file fisico (supporta sia campo 'file' che 'filename')
    fname = img.get('file') or img.get('filename', '')
    fpath = (UPLOAD / fname) if fname else None
    if not fpath or not fpath.exists():
        return jsonify({'error': 'file not found on disk', 'path': str(fpath)}), 404
    iptc_kws = read_iptc_keywords(fpath)
    if iptc_kws:
        img['keywords'] = merge_keywords_str(img.get('keywords', ''), iptc_kws)
        save_db(db)
    return jsonify({'ok': True, 'iptc_found': len(iptc_kws), 'keywords': img.get('keywords', '')})


@app.route('/api/projects/<pid>/rescan-iptc-all', methods=['POST'])
def rescan_iptc_all(pid):
    """Ri-legge le keywords IPTC da tutte le foto di un progetto."""
    db = load_db()
    p = next((p for p in db['projects'] if p['id'] == pid), None)
    if not p: return jsonify({'error': 'not found'}), 404
    total_added = 0
    for img in p.get('images', []):
        fname = img.get('file') or img.get('filename', '')
        fpath = (UPLOAD / fname) if fname else None
        if not fpath or not fpath.exists():
            continue
        iptc_kws = read_iptc_keywords(fpath)
        if iptc_kws:
            before = img.get('keywords', '')
            img['keywords'] = merge_keywords_str(before, iptc_kws)
            if img['keywords'] != before:
                total_added += 1
    save_db(db)
    return jsonify({'ok': True, 'updated': total_added})


# ── UPDATE (fetch + checkout selettivo, preserva data/) ──────
@app.route('/api/update', methods=['POST'])
def update_from_github():
    import subprocess
    def run(cmd):
        return subprocess.run(cmd, cwd=str(BASE), capture_output=True, text=True, timeout=30)
    try:
        # 1. Scarica i nuovi commit senza toccare i file locali
        r1 = run(['git', 'fetch', 'origin', 'main'])
        if r1.returncode != 0:
            return jsonify({'ok': False, 'error': r1.stdout + r1.stderr})
        # 2. Aggiorna solo static/ e app.py dalla versione remota (forza sovrascrittura)
        files_to_update = ['static/', 'app.py', 'RizziCMS_launcher.applescript']
        r2 = run(['git', 'checkout', 'origin/main', '--'] + files_to_update)
        if r2.returncode != 0:
            return jsonify({'ok': False, 'error': r2.stdout + r2.stderr})
        # 3. Aggiorna HEAD senza merge (evita conflitti su data/db.json)
        run(['git', 'update-ref', 'refs/heads/main', 'origin/main'])
        output = r1.stdout + r2.stdout
        return jsonify({'ok': True, 'output': output})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})

# ── SEED ISTANBUL IMAGES ──────────────────────────────────────────────────
@app.route('/api/seed-istanbul-images', methods=['POST'])
def seed_istanbul_images():
    """Scarica 12 foto di Istanbul da Unsplash e le aggiunge al progetto Istanbul."""
    import urllib.request
    import hashlib

    # Picsum Photos — seed fissi, sempre le stesse foto, nessuna autenticazione richiesta
    ISTANBUL_PHOTOS = [
        'https://picsum.photos/seed/ist01/1200/800',
        'https://picsum.photos/seed/ist02/1200/800',
        'https://picsum.photos/seed/ist03/1200/800',
        'https://picsum.photos/seed/ist04/1200/800',
        'https://picsum.photos/seed/ist05/1200/800',
        'https://picsum.photos/seed/ist06/1200/800',
        'https://picsum.photos/seed/ist07/1200/800',
        'https://picsum.photos/seed/ist08/1200/800',
        'https://picsum.photos/seed/ist09/1200/800',
        'https://picsum.photos/seed/ist10/1200/800',
        'https://picsum.photos/seed/ist11/1200/800',
        'https://picsum.photos/seed/ist12/1200/800',
    ]

    db = load_db()
    # Trova progetto Istanbul
    project = next((p for p in db['projects'] if 'istanbul' in p.get('title','').lower()), None)
    if not project:
        return jsonify({'ok': False, 'error': 'Progetto Istanbul non trovato'})

    # Svuota le immagini esistenti (potrebbero avere percorsi sbagliati)
    project['images'] = []
    UPLOAD.mkdir(exist_ok=True)
    (UPLOAD / 'thumbs').mkdir(exist_ok=True)

    added = []
    for url in ISTANBUL_PHOTOS:
        try:
            uid = str(uuid.uuid4())[:8]
            fname = uid + '.jpg'
            fpath = UPLOAD / fname
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = resp.read()
            with open(str(fpath), 'wb') as f:
                f.write(data)
            # Crea thumb
            try:
                from PIL import Image as PILImage
                import io
                im = PILImage.open(io.BytesIO(data))
                im.thumbnail((400, 400))
                tname = 'thumb_' + fname
                im.save(str(UPLOAD / 'thumbs' / tname), 'JPEG', quality=82)
                thumb_url = '/uploads/thumbs/' + tname
            except:
                thumb_url = '/uploads/' + fname
            img_record = {
                'id':    uid,
                'file':  fname,
                'url':   '/uploads/' + fname,
                'thumb': thumb_url,
                'tags':  [],
                'ar':    1.5,
            }
            project['images'].append(img_record)
            added.append(fname)
        except Exception as e:
            continue

    save_db(db)
    return jsonify({'ok': True, 'added': len(added), 'files': added})

@app.route('/api/sysinfo')
def sysinfo():
    """Endpoint di diagnostica: mostra i path reali usati dal server."""
    import os
    storage = Path('/opt/render/project/storage')
    return jsonify({
        'RENDER_env': os.environ.get('RENDER', ''),
        'IS_RENDER': _IS_RENDER,
        'storage_exists': storage.exists(),
        'storage_ls': os.listdir(str(storage)) if storage.exists() else [],
        'UPLOAD_path': str(UPLOAD),
        'DATA_path': str(DATA),
        'DB_FILE_path': str(DB_FILE),
        'DB_FILE_exists': DB_FILE.exists(),
        'uploads_count': len(list(UPLOAD.glob('*.jpg'))) if UPLOAD.exists() else -1,
        'BASE_path': str(BASE),
        'cwd': os.getcwd(),
    })

# ─# ── IMAGE PROCESSING ────────────────────────────────────────────

def _make_lut_from_points(points):
    """
    Costruisce una LUT 256 valori da punti di controllo [(x0,y0),(x1,y1),...]
    usando interpolazione lineare a tratti. x e y sono in [0,255].
    """
    lut = np.zeros(256, dtype=np.float32)
    pts = sorted(points, key=lambda p: p[0])
    for i in range(256):
        # Trova il segmento che contiene i
        for j in range(len(pts) - 1):
            x0, y0 = pts[j]
            x1, y1 = pts[j+1]
            if x0 <= i <= x1:
                if x1 == x0:
                    lut[i] = y0
                else:
                    t = (i - x0) / (x1 - x0)
                    lut[i] = y0 + t * (y1 - y0)
                break
        else:
            if i <= pts[0][0]:
                lut[i] = pts[0][1]
            else:
                lut[i] = pts[-1][1]
    return np.clip(lut, 0, 255)


# Preset fotografo: dizionario con curve R, G, B (punti di controllo)
# e shift canali per split toning ombre/luci
PHOTOGRAPHER_PRESETS = {
    # ── GUIDO GUIDI ──────────────────────────────────────────────────────────
    # Toni freddi e desaturati, dominante turchese/verde, contrasto morbido,
    # ombre aperte, luci compresse. Pellicola italiana anni 70-80.
    'guido_guidi': {
        'curve_r': [(0,8),(64,62),(128,120),(192,178),(255,230)],   # rossi leggermente abbassati
        'curve_g': [(0,6),(64,65),(128,126),(192,186),(255,240)],   # verdi quasi neutri
        'curve_b': [(0,12),(64,70),(128,135),(192,196),(255,248)],  # blu alzati (freddo)
        'split_shadow_rgb': (0, 4, 8),   # ombre leggermente blu-turchese
        'split_hi_rgb':     (3, 2, 0),   # luci leggermente calde
    },
    # ── ALEC SOTH ────────────────────────────────────────────────────────────
    # Toni naturali e attenuati, aspetto filmico, contrasto ridotto,
    # ombre aperte (faded), palette malinconica con verdi spenti e blu.
    'alec_soth': {
        'curve_r': [(0,15),(64,72),(128,128),(192,182),(255,238)],  # ombre alzate (faded)
        'curve_g': [(0,12),(64,70),(128,128),(192,183),(255,240)],  # neutro con ombre aperte
        'curve_b': [(0,18),(64,74),(128,130),(192,184),(255,238)],  # blu leggermente alzati
        'split_shadow_rgb': (2, 3, 6),   # ombre leggermente fredde
        'split_hi_rgb':     (4, 3, 0),   # luci leggermente calde
    },
    # ── ANDREAS GURSKY ───────────────────────────────────────────────────────
    # Colori saturi e vividi, contrasto alto, toni caldi dorati nelle luci,
    # ombre fredde profonde. Aspetto quasi iperreale e pittorico.
    'andreas_gursky': {
        'curve_r': [(0,0),(64,58),(128,132),(192,200),(255,255)],   # S-curve marcata, caldi
        'curve_g': [(0,0),(64,55),(128,128),(192,196),(255,252)],   # S-curve
        'curve_b': [(0,0),(64,50),(128,122),(192,188),(255,248)],   # blu leggermente abbassati
        'split_shadow_rgb': (0, 0, 12),  # ombre fredde blu
        'split_hi_rgb':     (8, 5, 0),   # luci dorate
    },
    # ── PHILIP-LORCA DICORCIA ────────────────────────────────────────────────
    # Cinematografico, flash su soggetti, sfondi freddi scuri, soggetti caldi.
    # Contrasto elevato, ombre profonde, luci brillanti e direzionali.
    'philip_lorca_dicorcia': {
        'curve_r': [(0,0),(48,30),(128,135),(200,210),(255,255)],   # contrasto alto, caldi
        'curve_g': [(0,0),(48,28),(128,128),(200,200),(255,252)],   # S-curve
        'curve_b': [(0,5),(48,35),(128,122),(200,190),(255,245)],   # blu ombre alzati
        'split_shadow_rgb': (0, 2, 14),  # ombre blu profonde
        'split_hi_rgb':     (10, 6, 0),  # luci calde arancio
    },
    # ── THOMAS STRUTH ────────────────────────────────────────────────────────
    # Fedeltà cromatica quasi scientifica, neutralità, curva quasi lineare,
    # colori naturali senza manipolazioni evidenti. Scuola di Düsseldorf.
    'thomas_struth': {
        'curve_r': [(0,2),(64,63),(128,127),(192,191),(255,253)],   # quasi lineare
        'curve_g': [(0,2),(64,63),(128,127),(192,191),(255,253)],   # quasi lineare
        'curve_b': [(0,2),(64,63),(128,127),(192,191),(255,253)],   # quasi lineare
        'split_shadow_rgb': (0, 0, 0),   # nessun viraggio
        'split_hi_rgb':     (0, 0, 0),   # nessun viraggio
    },
    # ── CHRISTOPHER ANDERSON ─────────────────────────────────────────────────
    # Caldo e cinematografico, toni dorati/aranciati, neri schiacciati ma
    # leggermente sollevati (matte), verdi verso oliva/senape, pelle calda.
    'christopher_anderson': {
        'curve_r': [(0,8),(64,72),(128,138),(192,205),(255,255)],   # rossi alzati, caldi
        'curve_g': [(0,6),(64,65),(128,128),(192,192),(255,248)],   # verdi verso oliva
        'curve_b': [(0,4),(64,52),(128,112),(192,172),(255,225)],   # blu abbassati
        'split_shadow_rgb': (6, 4, 0),   # ombre calde
        'split_hi_rgb':     (10, 7, 0),  # luci dorate
    },
}


def _apply_photographer_curve(arr, preset_name, intensity=1.0):
    """
    Applica la curva tonale e il split toning del preset fotografo.
    arr: numpy array float32 shape (H, W, 3) con valori 0-255.
    intensity: float 0.0-1.0 (0=nessun effetto, 1=preset completo).
              Implementato come blend lineare tra originale e preset al 100%.
    Restituisce arr modificato (float32, 0-255).
    """
    preset = PHOTOGRAPHER_PRESETS.get(preset_name)
    if not preset:
        return arr

    intensity = float(np.clip(intensity, 0.0, 1.0))
    if intensity <= 0.01:
        return arr

    # Costruisci LUT per R, G, B
    lut_r = _make_lut_from_points(preset['curve_r'])
    lut_g = _make_lut_from_points(preset['curve_g'])
    lut_b = _make_lut_from_points(preset['curve_b'])

    # Applica LUT per canale
    idx = np.clip(arr.astype(np.int32), 0, 255)
    result = arr.copy()
    result[:,:,0] = lut_r[idx[:,:,0]]
    result[:,:,1] = lut_g[idx[:,:,1]]
    result[:,:,2] = lut_b[idx[:,:,2]]

    # Split toning ombre
    sr, sg, sb = preset.get('split_shadow_rgb', (0,0,0))
    if sr or sg or sb:
        lum = result.mean(axis=2, keepdims=True) / 255.0
        shadow_mask = np.clip(1.0 - lum * 3.5, 0, 1)
        result[:,:,0] = np.clip(result[:,:,0] + shadow_mask[:,:,0] * sr, 0, 255)
        result[:,:,1] = np.clip(result[:,:,1] + shadow_mask[:,:,0] * sg, 0, 255)
        result[:,:,2] = np.clip(result[:,:,2] + shadow_mask[:,:,0] * sb, 0, 255)

    # Split toning luci
    hr, hg, hb = preset.get('split_hi_rgb', (0,0,0))
    if hr or hg or hb:
        lum = result.mean(axis=2, keepdims=True) / 255.0
        hi_mask = np.clip((lum - 0.6) * 3.5, 0, 1)
        result[:,:,0] = np.clip(result[:,:,0] + hi_mask[:,:,0] * hr, 0, 255)
        result[:,:,1] = np.clip(result[:,:,1] + hi_mask[:,:,0] * hg, 0, 255)
        result[:,:,2] = np.clip(result[:,:,2] + hi_mask[:,:,0] * hb, 0, 255)

    # Blend con l'originale in base all'intensità
    # intensity=1.0 → preset puro; intensity=0.5 → 50% preset + 50% originale
    if intensity < 1.0:
        result = arr * (1.0 - intensity) + result * intensity

    return np.clip(result, 0, 255)


def _medium_format_acutance(arr, strength):
    """
    Simula l'acutanza e la morbidezza tipiche del medio/grande formato
    (pellicola 6x7, 10x12, Hasselblad 907X 100MP).

    Tecnica: Frequency Separation a 3 bande tramite Pillow GaussianBlur.
    - Bassa frequenza  (radius ~5px): struttura globale, toni, colori — invariata
    - Media frequenza  (radius ~1.5px): bordi, texture, struttura — POTENZIATA
      (questo è l'acutanza: sensazione di nitidezza senza halo)
    - Alta frequenza   (residuo): micro-dettagli, rumore — RIDOTTA leggermente
      (questo è la morbidezza: la pellicola non ha rumore digitale)

    arr: numpy float32 (H, W, 3) valori 0-255
    strength: float 0.0-1.0 (0=nessun effetto, 1=massimo)
    Restituisce arr modificato (float32, 0-255).
    Usa solo Pillow (nessuna dipendenza esterna aggiuntiva).
    """
    from PIL import ImageFilter

    if strength <= 0.01:
        return arr

    # Converti in immagine PIL per usare GaussianBlur
    im_orig = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))

    # Bassa frequenza: blur forte (struttura globale)
    im_low  = im_orig.filter(ImageFilter.GaussianBlur(radius=5.0))
    # Media frequenza: blur leggero (bordi e texture)
    im_mid  = im_orig.filter(ImageFilter.GaussianBlur(radius=1.5))

    # Converti in numpy float32
    orig = np.array(im_orig, dtype=np.float32)
    low  = np.array(im_low,  dtype=np.float32)
    mid  = np.array(im_mid,  dtype=np.float32)

    band_mid  = mid - low        # frequenze medie: bordi, struttura
    band_high = orig - mid       # frequenze alte: micro-dettagli, rumore

    # === BOOST SELETTIVO ===
    # Le frequenze medie vengono amplificate (acutanza)
    # Le frequenze alte vengono leggermente ridotte (morbidezza pellicola)
    mid_boost  = 1.0 + strength * 2.2   # da 1.0 a 3.2
    high_scale = 1.0 - strength * 0.35  # da 1.0 a 0.65

    # Ricostruisci l'immagine
    result = low + band_mid * mid_boost + band_high * high_scale
    result = np.clip(result, 0.0, 255.0)

    return result.astype(np.float32)


@app.route('/api/projects/<pid>/images/adjust', methods=['POST'])
def adjust_images(pid):
    """Applica correzioni manuali (luminosità, contrasto, saturazione) a una o più foto."""
    from PIL import ImageEnhance
    db   = load_db()
    p    = next((x for x in db['projects'] if x['id'] == pid), None)
    if not p: return jsonify({'error': 'not found'}), 404

    data       = request.json or {}
    image_ids  = data.get('ids', [])          # lista id foto; vuota = tutte
    brightness       = float(data.get('brightness', 1.0))   # 0.5 – 2.0
    contrast          = float(data.get('contrast',   1.0))
    saturation        = float(data.get('saturation', 1.0))
    sharpness         = float(data.get('sharpness',  1.0))
    temp_shift        = float(data.get('temp_shift', 0.0))   # -50 … +50 (caldo/freddo)
    tint_shift        = float(data.get('tint_shift', 0.0))   # -50 … +50 (verde/magenta)
    shadows_lift      = float(data.get('shadows_lift', 0.0)) # 0 … 40
    highlights_comp   = float(data.get('highlights_comp', 0.0)) # 0 … 40
    curve_preset      = data.get('curve_preset', None)  # nome preset fotografo
    preset_intensity  = float(data.get('preset_intensity', 1.0))  # 0.0-1.0 intensità preset
    mf_acutance       = float(data.get('mf_acutance', 0.0))  # 0.0-1.0 acutanza medio formato

    targets = [i for i in p.get('images', []) if not image_ids or i['id'] in image_ids]
    updated = []

    # Directory per i backup originali
    orig_dir = UPLOAD / 'originals'
    orig_dir.mkdir(exist_ok=True)

    for img in targets:
        fpath = UPLOAD / img['file']
        if not fpath.exists(): continue
        try:
            # Crea backup originale se non esiste ancora
            # Il backup viene usato come sorgente per TUTTE le correzioni,
            # garantendo che gli stili non si sommino mai.
            orig_path = orig_dir / img['file'].replace('/', '_')
            if not orig_path.exists():
                import shutil
                shutil.copy2(str(fpath), str(orig_path))

            # Legge SEMPRE dall'originale (non dalla versione già modificata)
            with Image.open(str(orig_path)) as im:
                if im.mode != 'RGB': im = im.convert('RGB')

                if brightness != 1.0:
                    im = ImageEnhance.Brightness(im).enhance(brightness)
                if contrast != 1.0:
                    im = ImageEnhance.Contrast(im).enhance(contrast)
                if saturation != 1.0:
                    im = ImageEnhance.Color(im).enhance(saturation)
                if sharpness != 1.0:
                    im = ImageEnhance.Sharpness(im).enhance(sharpness)

                # Correzioni avanzate: temperatura, tinta, ombre, luci, curve preset
                needs_arr = (abs(temp_shift) > 0.5 or abs(tint_shift) > 0.5 or
                             shadows_lift > 0.5 or highlights_comp > 0.5 or
                             curve_preset or mf_acutance > 0.01)
                if needs_arr:
                    arr = np.array(im, dtype=np.float32)
                    # Temperatura: shift R e B
                    if abs(temp_shift) > 0.5:
                        shift = temp_shift * 0.8
                        arr[:,:,0] = np.clip(arr[:,:,0] + shift, 0, 255)   # R
                        arr[:,:,2] = np.clip(arr[:,:,2] - shift, 0, 255)   # B
                    # Tinta: shift G (negativo=verde, positivo=magenta)
                    if abs(tint_shift) > 0.5:
                        arr[:,:,1] = np.clip(arr[:,:,1] + tint_shift * 0.6, 0, 255)
                    # Shadows lift: alza le ombre senza toccare le luci
                    if shadows_lift > 0.5:
                        lum = arr.mean(axis=2, keepdims=True) / 255.0
                        shadow_mask = np.clip(1.0 - lum * 3.0, 0, 1)
                        arr = np.clip(arr + shadow_mask * shadows_lift, 0, 255)
                    # Highlights compress: abbassa le luci senza toccare le ombre
                    if highlights_comp > 0.5:
                        lum = arr.mean(axis=2, keepdims=True) / 255.0
                        hi_mask = np.clip((lum - 0.55) * 3.0, 0, 1)
                        arr = np.clip(arr - hi_mask * highlights_comp, 0, 255)
                    # Curve preset fotografo (con intensità variabile)
                    if curve_preset:
                        arr = _apply_photographer_curve(arr, curve_preset, preset_intensity)
                    # Acutanza medio formato (frequency separation)
                    if mf_acutance > 0.01:
                        arr = _medium_format_acutance(arr, mf_acutance)
                    im = Image.fromarray(arr.astype(np.uint8))

                im.save(str(fpath), 'JPEG', quality=88, optimize=True)

                # Rigenera thumbnail
                tpath = UPLOAD / img.get('thumb', 'thumbs/' + img['file'])
                tpath.parent.mkdir(exist_ok=True)
                thumb = im.copy()
                thumb.thumbnail((400, 400), Image.LANCZOS)
                thumb.save(str(tpath), 'JPEG', quality=82)

            updated.append(img['id'])
        except Exception as e:
            import traceback; traceback.print_exc()
            pass

    save_db(db)
    return jsonify({'ok': True, 'updated': updated})


@app.route('/api/projects/<pid>/images/reset', methods=['POST'])
def reset_images(pid):
    """Ripristina le foto alla versione originale (dal backup creato alla prima modifica)."""
    import shutil
    db = load_db()
    p  = next((x for x in db['projects'] if x['id'] == pid), None)
    if not p: return jsonify({'error': 'not found'}), 404

    data      = request.json or {}
    image_ids = data.get('ids', [])  # vuota = tutte

    targets  = [i for i in p.get('images', []) if not image_ids or i['id'] in image_ids]
    orig_dir = UPLOAD / 'originals'
    restored = []

    for img in targets:
        fpath     = UPLOAD / img['file']
        orig_path = orig_dir / img['file'].replace('/', '_')
        if not orig_path.exists():
            # Nessun backup: la foto non è mai stata modificata, niente da fare
            restored.append(img['id'])
            continue
        try:
            # Ripristina il file originale
            shutil.copy2(str(orig_path), str(fpath))
            # Rigenera thumbnail dall'originale
            with Image.open(str(orig_path)) as im:
                if im.mode != 'RGB': im = im.convert('RGB')
                tpath = UPLOAD / img.get('thumb', 'thumbs/' + img['file'])
                tpath.parent.mkdir(exist_ok=True)
                thumb = im.copy()
                thumb.thumbnail((400, 400), Image.LANCZOS)
                thumb.save(str(tpath), 'JPEG', quality=82)
            restored.append(img['id'])
        except Exception as e:
            import traceback; traceback.print_exc()

    return jsonify({'ok': True, 'restored': restored})



@app.route('/api/projects/<pid>/images/auto-balance', methods=['POST'])
def auto_balance(pid):
    """Uniforma automaticamente colore e luminosità di tutte le foto selezionate verso la media."""
    import numpy as np

    db   = load_db()
    p    = next((x for x in db['projects'] if x['id'] == pid), None)
    if not p: return jsonify({'error': 'not found'}), 404

    data      = request.json or {}
    image_ids = data.get('ids', [])   # vuota = tutte

    targets = [
        i for i in p.get('images', [])
        if not image_ids or i['id'] in image_ids
    ]
    if not targets: return jsonify({'error': 'nessuna foto selezionata'}), 400

    # Carica tutte le immagini e calcola l'istogramma medio per canale
    arrays = []
    for img in targets:
        fpath = UPLOAD / img['file']
        if fpath.exists():
            try:
                arrays.append(np.array(Image.open(str(fpath)).convert('RGB'), dtype=np.float32))
            except: pass

    if not arrays: return jsonify({'error': 'nessun file leggibile'}), 400

    # Calcola immagine di riferimento media (media pixel per pixel, stessa dimensione)
    # Usiamo la mediana delle medie di luminosità come target
    mean_brightness = float(np.median([a.mean() for a in arrays]))
    mean_r = float(np.median([a[:,:,0].mean() for a in arrays]))
    mean_g = float(np.median([a[:,:,1].mean() for a in arrays]))
    mean_b = float(np.median([a[:,:,2].mean() for a in arrays]))

    updated = []
    for img, arr in zip(targets, arrays):
        fpath = UPLOAD / img['file']
        if not fpath.exists(): continue
        try:
            # Correggi ogni canale verso la media
            corrected = arr.copy()
            for ch, target_mean in enumerate([mean_r, mean_g, mean_b]):
                ch_mean = corrected[:,:,ch].mean()
                if ch_mean > 1:
                    corrected[:,:,ch] = np.clip(corrected[:,:,ch] * (target_mean / ch_mean), 0, 255)

            result = Image.fromarray(corrected.astype(np.uint8))
            result.save(str(fpath), 'JPEG', quality=88, optimize=True)

            # Rigenera thumbnail
            tpath = UPLOAD / img.get('thumb', 'thumbs/' + img['file'])
            tpath.parent.mkdir(exist_ok=True)
            thumb = result.copy()
            thumb.thumbnail((400, 400), Image.LANCZOS)
            thumb.save(str(tpath), 'JPEG', quality=82)

            updated.append(img['id'])
        except Exception as e:
            pass

    save_db(db)
    return jsonify({'ok': True, 'updated': updated,
                    'target': {'brightness': mean_brightness, 'r': mean_r, 'g': mean_g, 'b': mean_b}})


# ── RICALCOLA ASPECT RATIO (correzione EXIF orientation) ────────────────────
@app.route('/api/fix-ar', methods=['POST'])
def fix_aspect_ratios():
    """Ricalcola l'aspect ratio di tutte le foto applicando la correzione EXIF orientation.
    Da chiamare una volta dopo l'aggiornamento per correggere le foto già caricate."""
    from PIL import ImageOps
    db = load_db()
    fixed = 0
    errors = []
    for p in db['projects']:
        for img in p.get('images', []):
            fpath = UPLOAD / img.get('file', '')
            if not fpath.exists():
                continue
            try:
                with Image.open(str(fpath)) as im:
                    im = ImageOps.exif_transpose(im)
                    w, h = im.size
                    new_ar = round(w / h, 4)
                    old_ar = img.get('ar', 1.0)
                    if abs(new_ar - old_ar) > 0.01:  # aggiorna solo se cambia significativamente
                        img['ar'] = new_ar
                        fixed += 1
            except Exception as e:
                errors.append({'file': img.get('file', ''), 'error': str(e)})
    save_db(db)
    return jsonify({'ok': True, 'fixed': fixed, 'errors': errors})


if __name__ == '__main__':
    print('\n  Rizzi CMS — avviato su http://localhost:5151')
    print('  Sito:  http://localhost:5151/')
    print('  CMS:   http://localhost:5151/cms\n')
    app.run(host='0.0.0.0', port=5151, debug=False)
