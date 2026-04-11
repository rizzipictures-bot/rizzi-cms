#!/usr/bin/env python3
"""
Social Generator — Genera hashtag stratificati, tag partner Instagram e meta SEO
per ogni progetto fotografico.

Sistema a 3 livelli di hashtag:
- Ultra-niche: community specifica, alta conversione
- Medio: genere fotografico, buona visibilità
- Ampio: fotografia in generale, massima reach

Tag partner a 3 livelli:
- Aspirazionale: account con 500k+ follower (bassa probabilità repost, alta visibilità)
- Realistico: account con 50-500k follower (media probabilità, pubblico qualificato)
- Certo: community attive con 10-50k follower (alta probabilità engagement)
"""

import os, json
from openai import OpenAI

client = OpenAI()

# ── Database partner Instagram per genere fotografico ─────────────────────────
PARTNER_DATABASE = {
    "documentary": {
        "aspirational": [
            {"name": "Magnum Photos", "handle": "@magnumphotos", "followers": "1.2M"},
            {"name": "National Geographic", "handle": "@natgeo", "followers": "280M"},
            {"name": "VII Photo Agency", "handle": "@viiphoto", "followers": "120k"},
        ],
        "realistic": [
            {"name": "Foam Fotografiemuseum", "handle": "@foam_fotografiemuseum", "followers": "180k"},
            {"name": "LensCulture", "handle": "@lensculture", "followers": "450k"},
            {"name": "Burn Magazine", "handle": "@burnmagazine", "followers": "85k"},
            {"name": "Aperture Foundation", "handle": "@aperturefoundation", "followers": "220k"},
            {"name": "World Press Photo", "handle": "@worldpressphoto", "followers": "1.1M"},
            {"name": "Reportage Festival", "handle": "@reportagefestival", "followers": "45k"},
        ],
        "certain": [
            {"name": "Documentary Photography", "handle": "@documentaryphotography", "followers": "35k"},
            {"name": "Analog Photography", "handle": "@analogphotography", "followers": "280k"},
            {"name": "Film Photography Project", "handle": "@filmphotographyproject", "followers": "120k"},
            {"name": "Leica Camera", "handle": "@leica_camera", "followers": "1.8M"},
        ]
    },
    "portrait": {
        "aspirational": [
            {"name": "Vogue Italia", "handle": "@vogueitalia", "followers": "3.2M"},
            {"name": "British Journal of Photography", "handle": "@bjponline", "followers": "180k"},
            {"name": "Portrait of Humanity", "handle": "@portraitofhumanity", "followers": "95k"},
        ],
        "realistic": [
            {"name": "Foam Fotografiemuseum", "handle": "@foam_fotografiemuseum", "followers": "180k"},
            {"name": "Portrait Awards", "handle": "@portraitawards", "followers": "65k"},
            {"name": "Sony World Photography", "handle": "@worldphoto", "followers": "820k"},
            {"name": "Taylor Wessing Prize", "handle": "@npg_london", "followers": "350k"},
        ],
        "certain": [
            {"name": "Portrait Photography", "handle": "@portraitphotography", "followers": "450k"},
            {"name": "Fine Art Photography", "handle": "@fineartphotography", "followers": "180k"},
        ]
    },
    "editorial": {
        "aspirational": [
            {"name": "Vogue Italia", "handle": "@vogueitalia", "followers": "3.2M"},
            {"name": "D La Repubblica", "handle": "@dlarepubblica", "followers": "450k"},
            {"name": "Condé Nast Italia", "handle": "@condenastita", "followers": "85k"},
        ],
        "realistic": [
            {"name": "Foam Magazine", "handle": "@foam_fotografiemuseum", "followers": "180k"},
            {"name": "Blow Magazine", "handle": "@blowmagazine", "followers": "45k"},
            {"name": "GUP Magazine", "handle": "@gupmagazine", "followers": "38k"},
            {"name": "Hotshoe Magazine", "handle": "@hotshoemagazine", "followers": "22k"},
        ],
        "certain": [
            {"name": "Editorial Photography", "handle": "@editorialphotography", "followers": "95k"},
            {"name": "Fashion Photography", "handle": "@fashionphotography", "followers": "380k"},
        ]
    },
    "landscape": {
        "aspirational": [
            {"name": "National Geographic", "handle": "@natgeo", "followers": "280M"},
            {"name": "500px", "handle": "@500px", "followers": "1.5M"},
        ],
        "realistic": [
            {"name": "Landscape Photography Magazine", "handle": "@landscapephotomag", "followers": "85k"},
            {"name": "Sony World Photography", "handle": "@worldphoto", "followers": "820k"},
        ],
        "certain": [
            {"name": "Landscape Photography", "handle": "@landscapephotography", "followers": "650k"},
            {"name": "Analog Photography", "handle": "@analogphotography", "followers": "280k"},
        ]
    },
    "street": {
        "aspirational": [
            {"name": "Magnum Photos", "handle": "@magnumphotos", "followers": "1.2M"},
            {"name": "Leica Camera", "handle": "@leica_camera", "followers": "1.8M"},
        ],
        "realistic": [
            {"name": "Street Photography International", "handle": "@streetphotographyintl", "followers": "180k"},
            {"name": "Burn Magazine", "handle": "@burnmagazine", "followers": "85k"},
            {"name": "LensCulture", "handle": "@lensculture", "followers": "450k"},
        ],
        "certain": [
            {"name": "Street Photography", "handle": "@streetphotography", "followers": "1.2M"},
            {"name": "Analog Photography", "handle": "@analogphotography", "followers": "280k"},
            {"name": "Film Photography", "handle": "@filmphotographic", "followers": "95k"},
        ]
    }
}

# ── Hashtag base per genere fotografico ───────────────────────────────────────
HASHTAG_BASE = {
    "documentary": {
        "niche": ["#documentaryphotography", "#photojournalism", "#humanstories", "#socialissues", "#reallife", "#documentaryfilm"],
        "medium": ["#documentaryphoto", "#streetdocumentary", "#photoessay", "#reportage", "#analogdocumentary"],
        "broad": ["#photography", "#photographer", "#photooftheday", "#blackandwhitephotography"]
    },
    "editorial": {
        "niche": ["#editorialphotography", "#fashioneditorial", "#magazinephotography", "#commercialphotography"],
        "medium": ["#editorialphoto", "#fashionphotographer", "#magazineshoot", "#italianphotography"],
        "broad": ["#photography", "#fashion", "#photooftheday", "#portrait"]
    },
    "portrait": {
        "niche": ["#portraitphotography", "#fineartportrait", "#environmentalportrait", "#humanportrait"],
        "medium": ["#portraitphoto", "#faceoftheday", "#portraitmood", "#analogportrait"],
        "broad": ["#photography", "#portrait", "#photooftheday", "#people"]
    },
    "landscape": {
        "niche": ["#landscapephotography", "#naturephotography", "#wildernessculture", "#earthpix"],
        "medium": ["#landscapephoto", "#naturephoto", "#outdoorphotography", "#analoglandscape"],
        "broad": ["#photography", "#nature", "#photooftheday", "#travel"]
    },
    "street": {
        "niche": ["#streetphotography", "#urbanphotography", "#streetphoto", "#decisivemoment"],
        "medium": ["#streetlife", "#urbanlife", "#cityphotography", "#analogstreet"],
        "broad": ["#photography", "#street", "#photooftheday", "#city"]
    }
}

def _detect_genre(project):
    """Rileva il genere fotografico dal progetto."""
    subtitle = (project.get('subtitle', '') or '').lower()
    description = (project.get('description', '') or '').lower()
    keywords = project.get('keywords', [])
    text = f"{subtitle} {description} {' '.join(keywords)}"
    
    if any(w in text for w in ['documentary', 'documentario', 'reportage', 'giornalismo']):
        return 'documentary'
    if any(w in text for w in ['editorial', 'editoriale', 'magazine', 'vogue', 'fashion', 'moda']):
        return 'editorial'
    if any(w in text for w in ['portrait', 'ritratto', 'face', 'volto']):
        return 'portrait'
    if any(w in text for w in ['landscape', 'paesaggio', 'nature', 'natura', 'mountain', 'montagna']):
        return 'landscape'
    if any(w in text for w in ['street', 'strada', 'urban', 'city', 'città']):
        return 'street'
    return 'documentary'  # default

def generate_hashtags_and_tags(project):
    """
    Genera hashtag stratificati e tag partner per un progetto.
    
    Returns:
        dict con:
        - hashtags: {niche, medium, broad, location, project_specific}
        - partner_tags: {aspirational, realistic, certain}
        - instagram_caption: caption completa pronta per Instagram
        - meta_keywords: lista di keyword per SEO
    """
    genre = _detect_genre(project)
    title = project.get('title', '')
    place = project.get('place', '')
    year  = str(project.get('year', ''))
    subtitle = project.get('subtitle', '')
    description = project.get('description', '')
    
    # Hashtag base dal database
    base_hashtags = HASHTAG_BASE.get(genre, HASHTAG_BASE['documentary'])
    
    # Hashtag di location
    location_tags = []
    if place:
        place_clean = place.lower().replace(' ', '').replace(',', '')
        location_tags = [
            f'#{place_clean}',
            f'#{place_clean}photography',
            f'#visitin{place_clean}',
        ]
    
    # Usa AI per generare hashtag specifici del progetto
    prompt = f"""Sei un esperto di social media per fotografi professionisti.
    
Progetto fotografico:
- Titolo: {title}
- Sottotitolo: {subtitle}
- Anno: {year}
- Luogo: {place}
- Descrizione: {description}
- Genere: {genre}

Genera ESATTAMENTE 8 hashtag ultra-specifici per questo progetto (non generici).
Devono essere hashtag che usano curatori, gallerie e fotografi professionisti su Instagram.
Formato: restituisci SOLO una lista JSON di stringhe, es: ["#tag1", "#tag2", ...]
Niente altro testo."""

    project_specific_tags = []
    try:
        resp = client.chat.completions.create(
            model='gpt-4.1-mini',
            messages=[{'role': 'user', 'content': prompt}],
            temperature=0.7,
            max_tokens=200
        )
        raw = resp.choices[0].message.content.strip()
        # Pulisci il JSON
        if raw.startswith('['):
            project_specific_tags = json.loads(raw)
        else:
            import re
            match = re.search(r'\[.*?\]', raw, re.DOTALL)
            if match:
                project_specific_tags = json.loads(match.group())
    except Exception as e:
        project_specific_tags = [f'#{title.lower().replace(" ", "")}', f'#{genre}photography']
    
    # Partner tags dal database
    partners = PARTNER_DATABASE.get(genre, PARTNER_DATABASE['documentary'])
    
    # Costruisci la caption Instagram
    caption_lines = []
    
    # Titolo e descrizione
    if description:
        caption_lines.append(description)
    else:
        caption_lines.append(f'{title} — {subtitle}' if subtitle else title)
    
    if year and place:
        caption_lines.append(f'{place}, {year}')
    
    caption_lines.append('')
    
    # Tag partner (max 3 per non sembrare spam)
    partner_tags_str = ' '.join([p['handle'] for p in partners['realistic'][:2]] + 
                                  [p['handle'] for p in partners['aspirational'][:1]])
    caption_lines.append(partner_tags_str)
    caption_lines.append('')
    
    # Hashtag
    all_hashtags = (
        project_specific_tags[:4] +
        base_hashtags['niche'][:3] +
        location_tags[:2] +
        base_hashtags['medium'][:3] +
        base_hashtags['broad'][:3]
    )
    caption_lines.append(' '.join(all_hashtags))
    
    # Meta keywords per SEO
    meta_keywords = [
        title, subtitle, place, year, genre,
        'photography', 'fotografia', 'photographer', 'fotografo',
        'Alessandro Rizzi'
    ] + [t.lstrip('#') for t in project_specific_tags[:5]]
    meta_keywords = [k for k in meta_keywords if k]
    
    return {
        'genre': genre,
        'hashtags': {
            'niche': base_hashtags['niche'],
            'medium': base_hashtags['medium'],
            'broad': base_hashtags['broad'],
            'location': location_tags,
            'project_specific': project_specific_tags
        },
        'partner_tags': {
            'aspirational': partners.get('aspirational', []),
            'realistic': partners.get('realistic', []),
            'certain': partners.get('certain', [])
        },
        'instagram_caption': '\n'.join(caption_lines),
        'meta_keywords': meta_keywords
    }


def generate_meta_seo(project, social_data):
    """
    Genera i meta tag HTML per SEO del progetto.
    
    Returns:
        dict con title, description, keywords, og_title, og_description
    """
    title = project.get('title', '')
    subtitle = project.get('subtitle', '')
    place = project.get('place', '')
    year = str(project.get('year', ''))
    description = project.get('description', '')
    
    og_title = f'{title} — Alessandro Rizzi Photography'
    og_description = description if description else f'{subtitle} — {place}, {year}'
    
    return {
        'title': og_title,
        'description': og_description[:160],  # max 160 char per SEO
        'keywords': ', '.join(social_data['meta_keywords'][:15]),
        'og_title': og_title,
        'og_description': og_description[:200],
        'og_type': 'article',
        'twitter_card': 'summary_large_image'
    }


if __name__ == '__main__':
    # Test
    test_project = {
        'title': 'Havana',
        'subtitle': 'Editorial',
        'year': '2004',
        'place': 'Cuba',
        'description': 'Un viaggio fotografico attraverso le strade di Havana.',
        'keywords': ['cuba', 'havana', 'street', 'editorial']
    }
    result = generate_hashtags_and_tags(test_project)
    print(json.dumps(result, indent=2, ensure_ascii=False))
