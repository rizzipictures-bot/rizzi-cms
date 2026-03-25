"""
Aggiorna anni (2003-2012) e pubblicazioni per i 15 progetti città.
Usa solo librerie standard Python — nessuna installazione necessaria.
Eseguire con: python3 seed_data.py
"""
import json, random, urllib.request, urllib.error

BASE = 'http://localhost:5151'

magazines = [
    'Amica Magazine', 'D Repubblica', 'Time', 'Newsweek',
    'National Geographic', 'Vogue Italia', "L'Uomo Vogue",
    'Stern', 'Paris Match', 'Der Spiegel', 'Le Monde Magazine',
    'GEO', 'Io Donna', 'Grazia', 'The Sunday Times Magazine',
]

cities = [
    'Tokyo', 'Londra', 'Berlino', 'Città del Messico', 'Mumbai',
    'Lagos', 'Buenos Aires', 'Shanghai', 'Istanbul', 'Cairo',
    'Los Angeles', 'Amsterdam', 'Nairobi', 'Seoul', 'Lisbona'
]

def api_get(path):
    with urllib.request.urlopen(BASE + path) as r:
        return json.loads(r.read())

def api_put(path, data):
    body = json.dumps(data).encode()
    req = urllib.request.Request(BASE + path, data=body, method='PUT',
                                  headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())

projects = api_get('/api/projects')

random.seed(42)
updated = 0
for p in projects:
    if p['title'] in cities:
        year = str(random.randint(2003, 2012))
        pub  = random.choice(magazines)
        try:
            api_put(f'/api/projects/{p["id"]}', {'year': year, 'publication': pub})
            print(f"  ✓ {p['title']:<22} {year}  |  {pub}")
            updated += 1
        except Exception as e:
            print(f"  ✗ {p['title']} → {e}")

print(f"\nAggiornati {updated} progetti su {len(cities)} città.")
