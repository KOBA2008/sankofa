"""Construit le corpus d'archives des six lieux : python harvest.py [id_lieu ...]"""
import sys

from sankofa.investigate import build_corpus
from sankofa.places import PLACES

wanted = set(sys.argv[1:])
for place in PLACES:
    if wanted and place["id"] not in wanted:
        continue
    print(f"\n=== {place['city']} · {place['name']} ===", flush=True)
    m = build_corpus(place)
    print(f"→ {len(m['archives'])} archives, {len(m['currents'])} vues actuelles", flush=True)
