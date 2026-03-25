"""Genera keywords AI per tutte le foto di Istanbul che non hanno ancora keywords."""
import json, base64, os
from pathlib import Path

BASE   = Path(__file__).parent
UPLOAD = BASE / 'data' / 'uploads'
DB_FILE = BASE / 'data' / 'db.json'

def load_db():
    with open(DB_FILE) as f:
        return json.load(f)

def save_db(db):
    with open(DB_FILE, 'w') as f:
        json.dump(db, f, indent=2, ensure_ascii=False)

def merge_keywords(existing, new_kws):
    """Aggiunge nuove keywords senza sovrascrivere quelle esistenti."""
    existing_set = {k.strip().lower() for k in existing.split(',') if k.strip()}
    new_list = [k.strip() for k in new_kws.split(',') if k.strip()]
    added = [k for k in new_list if k.lower() not in existing_set]
    if existing.strip():
        return existing + (', ' + ', '.join(added) if added else '')
    return ', '.join(new_list)

import openai
client = openai.OpenAI()

db = load_db()
istanbul = next((p for p in db['projects'] if 'istanbul' in p.get('title','').lower()), None)
if not istanbul:
    print("Progetto Istanbul non trovato")
    exit(1)

print(f"Progetto: {istanbul['title']} — {len(istanbul['images'])} foto")

for i, img in enumerate(istanbul['images']):
    existing = img.get('keywords', '').strip()
    
    # Trova il file immagine
    fname = img.get('filename') or img.get('file') or img.get('url','').split('/')[-1]
    fpath = UPLOAD / fname if fname else None
    
    if not fpath or not fpath.exists():
        # Prova a trovare il file cercando per id
        candidates = list(UPLOAD.glob(f"{img.get('id','?')}*"))
        if candidates:
            fpath = candidates[0]
        else:
            print(f"  [{i+1}/12] {img.get('id','?')} — file non trovato, skip")
            continue
    
    print(f"  [{i+1}/12] {fpath.name} — tagging...", end='', flush=True)
    
    try:
        ext = fpath.suffix.lower().lstrip('.')
        if ext in ['jpg', 'jpeg']: ext = 'jpeg'
        elif ext == 'png': ext = 'png'
        elif ext == 'webp': ext = 'webp'
        else: ext = 'jpeg'
        
        with open(str(fpath), 'rb') as f:
            b64 = base64.b64encode(f.read()).decode()
        
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
        new_kws = resp.choices[0].message.content.strip()
        img['keywords'] = merge_keywords(existing, new_kws)
        save_db(db)
        print(f" OK → {img['keywords'][:60]}...")
    except Exception as e:
        print(f" ERRORE: {e}")

print("\nDone! Keywords salvate nel database.")
