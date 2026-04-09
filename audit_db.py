#!/usr/bin/env python3
"""Analisi completa del db.json per il CMS audit"""
import json

with open('data/db.json') as f:
    db = json.load(f)

print("=" * 70)
print("CATEGORIE")
print("=" * 70)
for c in db.get('categories', []):
    print(f"  id={c['id']:15} name={c['name']:25} order={c.get('order','?')} visible={c.get('visible','?')}")

print()
print("=" * 70)
print("PROGETTI")
print("=" * 70)
for p in db.get('projects', []):
    imgs = p.get('images', [])
    kw_count = sum(1 for i in imgs if i.get('keywords', '').strip())
    texts = p.get('texts', [])
    technique = p.get('technique', '')
    medium = p.get('medium', '')
    prints = p.get('prints', '')
    editions = p.get('editions', '')
    keywords_manual = p.get('keywords_manual', '')
    print(f"  {p['title']:25} cat={p.get('category_id','?'):12} imgs={len(imgs):3} kw={kw_count:3} texts={len(texts):2} technique={repr(technique)[:20]} medium={repr(medium)[:20]}")
    if keywords_manual:
        print(f"    keywords_manual: {keywords_manual[:60]}")
    if prints or editions:
        print(f"    prints={prints} editions={editions}")

print()
print("=" * 70)
print("CAMPI MANCANTI NEL BACKEND (update_project)")
print("=" * 70)
print("  Campi aggiornati da PUT /api/projects/<pid>:")
print("  title, year, place, publication, category_id, subtitle, description, order")
print()
print("  Campi usati dal sito ma NON aggiornabili via CMS:")
print("  - technique / medium  (usato in popup media type)")
print("  - prints / editions   (usato in popup media type)")
print("  - keywords_manual     (campo nel form ma NON salvato nel backend!)")
print("  - section             (legacy, ora rimpiazzato da category_id)")
print()
print("=" * 70)
print("FLUSSO IPTC/AI")
print("=" * 70)
print("  Upload foto:")
print("  1. IPTC letto sincrono → img.keywords = iptc_str")
print("  2. AI tagging avviato in background (SEMPRE, non opzionale)")
print()
print("  Problema: AI tagging parte SEMPRE al caricamento.")
print("  Richiesta utente: AI keywords opzionali, attivabili manualmente prima della pubblicazione.")
print()
print("  Soluzione da implementare:")
print("  - Aggiungere flag 'ai_tagging_enabled' nelle settings (default: False)")
print("  - Bottone 'Tag AI' nel CMS per attivarlo manualmente su singola foto o su tutto")
print("  - Il bottone 'Tag AI' nell'header del CMS già esiste ma deve essere il SOLO modo per avviare l'AI")

print()
print("=" * 70)
print("CATEGORIE MANCANTI NEL DEFAULT")
print("=" * 70)
existing_ids = {c['id'] for c in db.get('categories', [])}
required_ids = {'cities', 'archive', 'interview', 'books', 'sculptures', 'biography', 'contact', 'index'}
missing = required_ids - existing_ids
extra = existing_ids - required_ids - {'cities', 'archive', 'interview', 'books', 'sculptures', 'biography', 'contact', 'index'}
print(f"  Richieste dal sito: {sorted(required_ids)}")
print(f"  Presenti nel db:    {sorted(existing_ids)}")
print(f"  Mancanti:           {sorted(missing)}")
print(f"  Extra (UUID):       {sorted(extra)}")
