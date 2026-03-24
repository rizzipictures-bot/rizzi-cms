# Rizzi CMS — Guida rapida

App locale per gestire i contenuti del sito di Alessandro Rizzi.
Nessun Prismic, nessun Cloudinary. Tutto gira sul tuo computer.

## Avvio

**macOS / Linux**
```bash
chmod +x start.sh
./start.sh
```

**Windows**
Doppio click su `start.bat`

**Manuale**
```bash
pip3 install flask pillow
python3 app.py
```
Poi apri `http://localhost:5151` nel browser.

---

## Struttura

```
rizzi-cms/
├── app.py          # Backend (Flask)
├── start.sh        # Avvio macOS/Linux
├── start.bat       # Avvio Windows
├── static/
│   └── index.html  # Interfaccia
├── data/
│   └── db.json     # Database locale (JSON)
└── uploads/        # Foto caricate
    └── thumbs/     # Thumbnail auto-generate
```

---

## Funzionalità

### Progetti
- Crea, modifica, elimina progetti
- Sezioni: **Archive** · **Interview** · **About**
- Campi: titolo, anno, luogo, categoria, pubblicazione, sottotitolo, descrizione

### Foto
- Drag & drop direttamente dalla cartella del computer
- Formati: JPG, PNG, WEBP, TIFF
- Thumbnail generate automaticamente (400px)
- Elimina singola foto

### Testi (per sezione)
- **Testo** — paragrafo corpo
- **Pull quote** — citazione in evidenza
- **Didascalia** — caption immagine
- **Domanda** — per pagine Interview
- **Risposta** — per pagine Interview

### Preview
- Colonna destra: anteprima live del progetto
- Toggle Light / Dark per la preview

### Export
- Bottone **Export JSON** in alto: scarica tutto il database
- Usato dallo script di generazione del sito statico

---

## Shortcut

| Azione | Come |
|--------|------|
| Nuovo progetto | Bottone `+ Progetto` |
| Filtra per sezione | Sidebar: Tutti / Archive / Interview / About |
| Cambia tema UI | Bottone `☽` in alto |
| Export dati | Bottone `Export JSON` |
