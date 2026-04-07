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
# Il db.json è escluso da Git (.gitignore) quindi i deploy non lo sovrascrivono
_IS_RENDER = bool(os.environ.get('RENDER'))

UPLOAD = BASE / 'uploads'
DATA   = BASE / 'data'

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
        {'id': 'cities',     'name': 'Cities',              'order': 0, 'visible': True},
        {'id': 'archive',    'name': 'Archive',             'order': 1, 'visible': True},
        {'id': 'interview',  'name': 'Interview',           'order': 2, 'visible': True},
        {'id': 'books',      'name': 'Books',               'order': 3, 'visible': True},
        {'id': 'sculptures', 'name': 'Sculptures Project',  'order': 4, 'visible': True},
        {'id': 'biography',  'name': 'Biography',           'order': 5, 'visible': True},
        {'id': 'contact',    'name': 'Contact',             'order': 6, 'visible': True},
        {'id': 'index',      'name': 'Index (foto laterale)', 'order': 7, 'visible': True},
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
    cat = {
        'id':      str(uuid.uuid4())[:8],
        'name':    name,
        'order':   len(db['categories']),
        'visible': data.get('visible', True),
    }
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
             'technique','medium','prints','editions','keywords_manual']:
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

                # ── RIMUOVI BORDI MONOCROMATICI (bianco/grigio/nero) ──
                im = auto_trim_border(im)

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
    # Le keywords manuali vengono aggiunte in append (non sovrascrivono)
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

if __name__ == '__main__':
    print('\n  Rizzi CMS — avviato su http://localhost:5151')
    print('  Sito:  http://localhost:5151/')
    print('  CMS:   http://localhost:5151/cms\n')
    app.run(host='0.0.0.0', port=5151, debug=False)
