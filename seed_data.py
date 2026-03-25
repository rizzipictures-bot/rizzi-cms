"""
Aggiorna anni (2003-2012) e pubblicazioni per i 15 progetti città.
Eseguire con: python3 seed_data.py
Richiede il server attivo su localhost:5151
"""
import json, random, requests

BASE = 'http://localhost:5151'

magazines = [
    'Amica Magazine', 'D Repubblica', 'Time', 'Newsweek',
    'National Geographic', 'Vogue Italia', 'L\'Uomo Vogue',
    'Stern', 'Paris Match', 'Der Spiegel', 'Le Monde Magazine',
    'GEO', 'Io Donna', 'Grazia', 'The Sunday Times Magazine',
]

cities = [
    'Tokyo', 'Londra', 'Berlino', 'Città del Messico', 'Mumbai',
    'Lagos', 'Buenos Aires', 'Shanghai', 'Istanbul', 'Cairo',
    'Los Angeles', 'Amsterdam', 'Nairobi', 'Seoul', 'Lisbona'
]

projects = requests.get(f'{BASE}/api/projects').json()

random.seed(42)
updated = 0
for p in projects:
    if p['title'] in cities:
        year = str(random.randint(2003, 2012))
        pub = random.choice(magazines)
        r = requests.put(f'{BASE}/api/projects/{p["id"]}', json={
            'year': year,
            'publication': pub
        })
        if r.status_code == 200:
            print(f"  ✓ {p['title']} → {year} | {pub}")
            updated += 1
        else:
            print(f"  ✗ {p['title']} → errore {r.status_code}")

print(f"\nAggiornati {updated} progetti.")
