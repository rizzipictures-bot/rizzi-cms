# Guida al Deploy — Rizzi CMS

## Architettura consigliata

```
[GitHub repo privato]
        │
        ├── Backend + CMS (Flask) ──► Render.com (gratuito)
        │         │                        │
        │         │                   Disk persistente
        │         │                   (foto + db.json)
        │
        └── Sito pubblico (HTML) ──► Vercel (gratuito)
```

---

## Passo 1 — Creare l'account su Render

1. Vai su **https://render.com** e crea un account gratuito
2. Collega il tuo account GitHub a Render
3. Clicca **"New +"** → **"Web Service"**
4. Seleziona il repository `rizzi-cms`
5. Impostazioni:
   - **Name**: `rizzi-cms`
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120`
   - **Plan**: Free (o Starter $7/mese per il Disk persistente)

> **IMPORTANTE**: Il piano gratuito di Render NON include Disk persistente.
> Per salvare le foto caricate in modo permanente serve il piano **Starter ($7/mese)**.
> In alternativa puoi usare **Cloudinary** (gratuito fino a 25 GB) — vedi Passo 3.

### Variabili d'ambiente su Render
Nel dashboard Render → Environment, aggiungi:
```
SECRET_KEY = (genera una stringa casuale lunga)
OPENAI_API_KEY = sk-... (la tua chiave OpenAI per il Tag AI)
```

---

## Passo 2 — Deploy del sito pubblico su Vercel

1. Vai su **https://vercel.com** e crea un account gratuito
2. Clicca **"New Project"** → importa il repository GitHub
3. **Framework Preset**: Other (nessun framework)
4. **Root Directory**: `static/site`
5. **Build Command**: (lascia vuoto)
6. **Output Directory**: `.` (punto)
7. Clicca **Deploy**

### Configurare l'URL del CMS nel sito pubblico
Dopo il deploy su Render, otterrai un URL tipo `https://rizzi-cms.onrender.com`.
Aggiorna questa riga nel file `static/site/index.html`:

```javascript
// Cerca questa riga (circa riga 8720):
const CMS_API = window.location.origin.includes('localhost')
  ? 'http://localhost:5151/api'
  : 'https://rizzi-cms.onrender.com/api';  // ← metti qui il tuo URL Render
```

---

## Passo 3 — Cloudinary per le foto (opzionale ma consigliato)

Cloudinary permette di salvare le foto su cloud invece che sul server Render.
Questo è necessario se usi il piano gratuito di Render (no Disk persistente).

1. Crea account gratuito su **https://cloudinary.com**
2. Dal dashboard copia: **Cloud Name**, **API Key**, **API Secret**
3. Aggiungi su Render nelle variabili d'ambiente:
   ```
   CLOUDINARY_CLOUD_NAME = il-tuo-cloud-name
   CLOUDINARY_API_KEY = 123456789
   CLOUDINARY_API_SECRET = abc123...
   ```
4. Il codice è già predisposto per Cloudinary — basta aggiungere le variabili.

> **Senza Cloudinary**: le foto vengono salvate sul Disk di Render ($7/mese).
> **Con Cloudinary**: le foto vanno su cloud, Render rimane gratuito.

---

## Passo 4 — Dominio personalizzato (opzionale)

Se hai un dominio (es. `alessandrorizzi.com`):

**Su Vercel** (sito pubblico):
1. Dashboard Vercel → Settings → Domains
2. Aggiungi `alessandrorizzi.com`
3. Segui le istruzioni per aggiornare i DNS del tuo dominio

**Su Render** (CMS):
1. Dashboard Render → Settings → Custom Domains
2. Aggiungi `cms.alessandrorizzi.com`
3. Aggiorna il DNS con il CNAME fornito da Render

---

## Workflow di caricamento contenuti

### Sequenza consigliata per ogni nuovo progetto:

1. **Apri il CMS** → `https://rizzi-cms.onrender.com/cms`
2. Clicca **"+ Progetto"**
3. Compila: Titolo, Anno, Luogo, Sezione (Cities/Archive/Interview)
4. Aggiungi: Tecnica, Supporto, Stampe, Edizioni
5. Vai al tab **"Foto"**
6. **Trascina le foto** (alta risoluzione, qualsiasi formato) nella zona upload
   - Il CMS le ridimensiona automaticamente a max 2500px, qualità 88%
   - Le thumbnail vengono generate automaticamente (400px)
   - Le keyword IPTC vengono estratte automaticamente
7. **Riordina le foto** con drag & drop nella griglia
8. **Seleziona la foto Overview**: passa il mouse su una foto → clicca **"☆ OV"**
   - La stella ★ dorata indica che la foto è selezionata per l'Overview
   - Puoi selezionare più foto per lo stesso progetto
9. Vai al tab **"Testi"** e aggiungi la descrizione del progetto
10. Clicca **"SALVA"**

### Keywords:
- **IPTC**: estratte automaticamente all'upload (se presenti nei metadati della foto)
- **Manuali**: aggiunte nel campo "Keywords manuali" separati da virgola
- **AI**: clicca **"✶"** su singola foto o **"✶ Tag AI"** per tutto il progetto
  - L'AI analizza visivamente la foto e genera keyword descrittive
  - Le keyword AI si aggiungono a quelle IPTC, non le sostituiscono

---

## Struttura del repository

```
rizzi-cms/
├── app.py              ← Backend Flask (API + CMS)
├── requirements.txt    ← Dipendenze Python
├── Procfile            ← Comando di avvio per Render
├── render.yaml         ← Configurazione Render
├── data/
│   └── db.json         ← Database JSON (categorie, progetti, testi)
├── uploads/            ← Foto caricate (NON in git — gestite da Render Disk)
│   └── thumbs/         ← Thumbnail generate automaticamente
└── static/
    ├── index.html      ← CMS frontend (admin panel)
    └── site/
        └── index.html  ← Sito pubblico
```

---

## Avvio locale (sviluppo)

```bash
cd rizzi-cms
pip3 install -r requirements.txt
python3 app.py
# Sito:  http://localhost:5151
# CMS:   http://localhost:5151/cms
```
