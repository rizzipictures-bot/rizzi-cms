#!/usr/bin/env python3
"""
Rizzi CMS — App locale per gestione contenuti del sito
Avvio: python3 app.py  →  http://localhost:5151

  http://localhost:5151/      → Sito pubblico (prototipo)
  http://localhost:5151/cms   → CMS (gestione contenuti)
  http://localhost:5151/api/  → API REST
"""

import os, json, uuid, shutil
from pathlib import Path
from flask import Flask, request, jsonify, send_from_directory, send_file
from PIL import Image

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

        # Aspect ratio e thumbnail
        try:
            with Image.open(str(fpath)) as im:
                w, h = im.size
                ar   = round(w / h, 4)
                tw = 400
                th = int(400 / ar)
                thumb = im.copy()
                thumb.thumbnail((tw, th), Image.LANCZOS)
                tname = 'thumb_' + fname.replace(ext, '.jpg')
                thumb.save(str(UPLOAD / 'thumbs' / tname), 'JPEG', quality=82)
        except Exception as e:
            ar    = 1.0
            tname = fname

        img_data = {
            'id':    str(uuid.uuid4())[:8],
            'file':  fname,
            'thumb': 'thumbs/' + tname,
            'ar':    ar,
            'caption': '',
        }
        p['images'].append(img_data)
        results.append(img_data)

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

if __name__ == '__main__':
    print('\n  Rizzi CMS — avviato su http://localhost:5151')
    print('  Sito:  http://localhost:5151/')
    print('  CMS:   http://localhost:5151/cms\n')
    app.run(host='0.0.0.0', port=5151, debug=False)
