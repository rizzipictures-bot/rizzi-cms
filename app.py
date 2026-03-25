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

BASE   = Path(__file__).parent
DATA   = BASE / 'data'
UPLOAD = BASE / 'uploads'
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
    # Migrazione: se non ci sono categorie, crea quelle di default
    if not db['categories']:
        db['categories'] = [
            {'id': 'cities',    'name': 'Cities',    'order': 0, 'visible': True},
            {'id': 'archive',   'name': 'Archive',   'order': 1, 'visible': True},
            {'id': 'interview', 'name': 'Interview', 'order': 2, 'visible': True},
        ]
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

# ── Sito pubblico (prototipo) ─────────────────
# http://localhost:5151/  →  sito
@app.route('/')
def site_root():
    return send_file(STATIC / 'site' / 'index.html')

@app.route('/site')
@app.route('/site/')
def site_index():
    return send_file(STATIC / 'site' / 'index.html')

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
        'title':       data.get('title', 'Senza titolo'),
        'year':        data.get('year', ''),
        'place':       data.get('place', ''),
        'publication': data.get('publication', ''),
        'category_id': data.get('category_id', None),  # ID della categoria madre
        'subtitle':    data.get('subtitle', ''),
        'description': data.get('description', ''),
        'images':      [],
        'texts':       [],
        'order':       len(db['projects']),
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
    for k in ['title','year','place','publication','category_id','subtitle','description','order']:
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

        # Conversione automatica + aspect ratio + thumbnail
        MAX_SIDE = 2500   # px lato lungo massimo
        WEB_QUALITY = 88  # qualità JPG per l'originale ottimizzato
        try:
            with Image.open(str(fpath)) as im:
                # Converti in RGB (gestisce PNG con trasparenza, TIFF, ecc.)
                if im.mode not in ('RGB', 'L'):
                    im = im.convert('RGB')
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

        img_data = {
            'id':      str(uuid.uuid4())[:8],
            'file':    fname,
            'thumb':   'thumbs/' + tname,
            'ar':      ar,
            'caption': '',
            'keywords': '',  # verrà popolato dal thread AI
        }
        p['images'].append(img_data)
        results.append(img_data)

        # Avvia auto-tagging AI in background (non blocca la risposta)
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

# ── UPDATE (solo git pull, nessun restart) ─────────────────
@app.route('/api/update', methods=['POST'])
def update_from_github():
    import subprocess
    try:
        result = subprocess.run(
            ['git', 'pull', 'origin', 'main'],
            cwd=str(BASE),
            capture_output=True,
            text=True,
            timeout=30
        )
        output = result.stdout + result.stderr
        if result.returncode != 0:
            return jsonify({'ok': False, 'error': output})
        return jsonify({'ok': True, 'output': output})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})

if __name__ == '__main__':
    print('\n  Rizzi CMS — avviato su http://localhost:5151')
    print('  Sito:  http://localhost:5151/')
    print('  CMS:   http://localhost:5151/cms\n')
    app.run(host='0.0.0.0', port=5151, debug=False)
