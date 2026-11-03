"""Construit la bibliothèque musicale libre de droits : python build_music.py"""
from sankofa.sources.music import build_library

tracks = build_library()
print(f"{len(tracks)} morceaux")
for t in tracks:
    print(f"  {t['instrument']:<11} {t['mood']:<9} {t['duration']:>4}s  {t['license']:<14} {t['title'][:60]}")
