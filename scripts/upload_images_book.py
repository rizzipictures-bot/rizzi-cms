#!/usr/bin/env python3.11
"""
Carica le 8 immagini di Image Book Vol. I nel CMS via API multipart.
Il server è già in ascolto su localhost:5151.
"""
import requests
import json
import os
from pathlib import Path

API = "http://localhost:5151/api"
PROJECT_ID = "e503393b"

# Lista immagini da caricare (nella cartella /home/ubuntu/upload/)
images = [
    "/home/ubuntu/upload/Screenshot2026-04-13alle15.12.14.png",  # copertina libro
    "/home/ubuntu/upload/Screenshot2026-04-13alle15.12.24.png",  # edificio/recinzione
    "/home/ubuntu/upload/Screenshot2026-04-13alle15.12.33.png",  # persona con cappello
    "/home/ubuntu/upload/Screenshot2026-04-13alle15.12.42.png",  # corridoio hotel
    "/home/ubuntu/upload/Screenshot2026-04-13alle15.12.51.png",  # protesta piazza
    "/home/ubuntu/upload/Screenshot2026-04-13alle15.13.00.png",  # senzatetto porta
    "/home/ubuntu/upload/Screenshot2026-04-13alle15.13.12.png",  # senzatetto vicino
    "/home/ubuntu/upload/Screenshot2026-04-13alle15.13.19.png",  # muro blu
]

# Prima aggiorna sc_section via PUT
print("Aggiornamento sc_section...")
r = requests.put(f"{API}/projects/{PROJECT_ID}", json={
    "sc_section": "images-book",
    "subtitle": "Sculptures — Image Book Volume I",
    "title": "Image Book Vol. I"
})
print(f"  sc_section: {r.json().get('sc_section')}")

# Carica le immagini
print("\nCaricamento immagini...")
files_to_upload = []
for img_path in images:
    if os.path.exists(img_path):
        files_to_upload.append(('files', (Path(img_path).name, open(img_path, 'rb'), 'image/png')))
    else:
        print(f"  MANCANTE: {img_path}")

if files_to_upload:
    r = requests.post(f"{API}/projects/{PROJECT_ID}/images", files=files_to_upload)
    result = r.json()
    print(f"  Caricate: {len(result)} immagini")
    for img in result:
        print(f"    - {img.get('url', img.get('file', '?'))}")
else:
    print("  Nessuna immagine trovata!")

# Chiudi i file
for _, f in files_to_upload:
    f[1].close()

print("\nDone.")
