"""
Script one-shot: genera i meta SEO dai progetti reali del CMS su Render
e aggiorna direttamente il file index.html del sito pubblico.
"""
import json, re, os
from pathlib import Path
from collections import Counter
import openai

# ── Dati reali dal CMS (già recuperati) ──────────────────────────────────────
PROJECTS = [
    {"title": "Bagnoli",            "year": 2002, "place": "Napoli",          "publication": "Personal",                    "images": 4},
    {"title": "Marche",             "year": 2002, "place": "Ancona",          "publication": "Personal",                    "images": 15},
    {"title": "Friend's home",      "year": 2002, "place": "Milan",           "publication": "Personal",                    "images": 2},
    {"title": "Napoli",             "year": 2002, "place": "Naples",          "publication": "Personal",                    "images": 7},
    {"title": "Milano Untitled",    "year": 2002, "place": "Milano",          "publication": "",                            "images": 8},
    {"title": "Varsaw",             "year": 2002, "place": "Poland",          "publication": "Personal",                    "images": 11},
    {"title": "China",              "year": 2003, "place": "Beijing/Shanghai","publication": "Amica Magazine",              "images": 56},
    {"title": "Naples",             "year": 2003, "place": "Italy",           "publication": "Personal",                    "images": 10},
    {"title": "New York",           "year": 2003, "place": "USA",             "publication": "Personal",                    "images": 22},
    {"title": "New York 35mm",      "year": 2003, "place": "New York",        "publication": "Personal",                    "images": 6},
    {"title": "New York Panoramics","year": 2003, "place": "USA",             "publication": "Personal",                    "images": 22},
    {"title": "Havana",             "year": 2004, "place": "Cuba",            "publication": "D La Repubblica delle Donne", "images": 87},
    {"title": "Istanbul",           "year": 2025, "place": "Turkey",          "publication": "Personal",                    "images": 51},
]

titles = [p["title"] for p in PROJECTS]
places = list({p["place"] for p in PROJECTS if p["place"]})
pubs   = list({p["publication"] for p in PROJECTS if p["publication"] and p["publication"] != "Personal"})
years  = sorted({str(p["year"]) for p in PROJECTS})
total_photos = sum(p["images"] for p in PROJECTS)

context = (
    f"Photographer: Alessandro Rizzi, Italian documentary and street photographer.\n"
    f"Archive spans: {years[0]}–{years[-1]} ({len(PROJECTS)} projects, {total_photos} photographs).\n"
    f"Projects: {', '.join(titles)}.\n"
    f"Places photographed: {', '.join(places)}.\n"
    f"Published in: {', '.join(pubs) if pubs else 'personal archive and editorial work'}.\n"
    f"Style: documentary, street photography, analog film, medium format, reportage.\n"
    f"Themes: urban life, travel, memory, identity, everyday life, cities."
)

print("Contesto costruito:")
print(context)
print()

# ── Chiama GPT per generare i meta tag ───────────────────────────────────────
client = openai.OpenAI()
resp = client.chat.completions.create(
    model='gemini-2.5-flash',
    max_tokens=400,
    messages=[{
        'role': 'user',
        'content': (
            f"Generate SEO meta tags for a photography portfolio website.\n"
            f"Context:\n{context}\n\n"
            f"Respond ONLY with a JSON object with these exact keys:\n"
            f"- title: page title (max 60 chars, Italian, include photographer name, evocative)\n"
            f"- description: meta description (max 155 chars, Italian, evocative, mentions key places and style)\n"
            f"- keywords: comma-separated keywords (Italian+English mix, max 25 keywords, include places, style, themes)\n"
            f"No explanations, no markdown, pure JSON."
        )
    }]
)
raw = resp.choices[0].message.content.strip()
raw = re.sub(r'^```(?:json)?\s*', '', raw)
raw = re.sub(r'\s*```$', '', raw)
seo = json.loads(raw)

title       = seo.get('title', 'Alessandro Rizzi — Fotografo')[:60]
description = seo.get('description', '')[:155]
keywords    = seo.get('keywords', '')

print(f"TITLE:       {title}")
print(f"DESCRIPTION: {description}")
print(f"KEYWORDS:    {keywords}")
print()

# ── Aggiorna il file index.html del sito pubblico ────────────────────────────
site_html = Path(__file__).parent / 'static' / 'site' / 'index.html'

new_seo_block = (
    f'  <!-- SEO:START -->\n'
    f'  <meta name="description" content="{description}" />\n'
    f'  <meta name="keywords" content="{keywords}" />\n'
    f'  <meta property="og:title" content="{title}" />\n'
    f'  <meta property="og:description" content="{description}" />\n'
    f'  <meta property="og:type" content="website" />\n'
    f'  <meta name="twitter:card" content="summary_large_image" />\n'
    f'  <meta name="twitter:title" content="{title}" />\n'
    f'  <meta name="twitter:description" content="{description}" />\n'
    f'  <!-- SEO:END -->'
)

with open(str(site_html), 'r', encoding='utf-8') as f:
    html = f.read()

# Sostituisce il titolo
html = re.sub(r'<title>[^<]*</title>', f'<title>{title}</title>', html)

# Sostituisce il blocco SEO
html = re.sub(
    r'  <!-- SEO:START -->.*?<!-- SEO:END -->',
    new_seo_block,
    html,
    flags=re.DOTALL
)

with open(str(site_html), 'w', encoding='utf-8') as f:
    f.write(html)

print(f"✓ Aggiornato: {site_html}")
print("Blocco SEO inserito nel sito pubblico.")
