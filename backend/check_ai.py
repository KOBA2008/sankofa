"""Vérifie les clés d'IA : python check_ai.py"""
from sankofa import config
from sankofa.meta import meta

print("Meta Model API :", "clé présente" if config.META_API_KEY else "pas de clé")
print("Baseten        :", "clé présente" if config.BASETEN_API_KEY else "pas de clé")
if meta.baseten:
    try:
        ids = [m.id for m in meta.baseten.models.list().data]
        print(f"Modèles Baseten ({len(ids)}) :")
        for i in ids:
            print("   ", i)
    except Exception as exc:
        print("Liste des modèles impossible :", exc)
print("Moteur texte retenu :", meta.text_engine)
if meta.text_live:
    answer = meta.chat("Réponds en une phrase, en français.", "Qui était le roi Béhanzin ?", max_tokens=80)
    print("Test :", answer or f"échec ({meta.last_error})")
