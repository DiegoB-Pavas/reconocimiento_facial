import json
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
cache_path = os.path.join(BASE_DIR, 'modelos', 'rostros_cache.json')
MAX_FOTOS = 30

if not os.path.exists(cache_path):
    print(f"No se encuentra: {cache_path}")
    exit(1)

with open(cache_path, 'r') as f:
    cache = json.load(f)

total_original = 0
for emp_id, data in cache.items():
    rostros = data.get('rostros_base64', [])
    total_original += len(rostros)

for emp_id, data in cache.items():
    rostros = data.get('rostros_base64', [])
    if len(rostros) > MAX_FOTOS:
        cache[emp_id]['rostros_base64'] = rostros[:MAX_FOTOS]
        print(f"{emp_id}: {len(rostros)} -> {MAX_FOTOS} fotos")

total_final = sum(len(d.get('rostros_base64', [])) for d in cache.values())
print(f"\nTotal: {total_original} -> {total_final} fotos")

with open(cache_path, 'w') as f:
    json.dump(cache, f, indent=2)

print("Cache truncado. Ahora ve a la interfaz y ejecuta 'Entrenar Global'")
