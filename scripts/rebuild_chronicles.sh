#!/usr/bin/env bash
# Régénère toutes les chroniques de pays via l'API locale (serveur lancé sur le port 8000)
for C in $(curl -s localhost:8000/api/countries | python3 -c "import sys,json;print(' '.join(c['id'] for c in json.load(sys.stdin)))"); do
  ID=$(curl -s -X POST localhost:8000/api/countries/$C/chronicle | python3 -c "import sys,json;print(json.load(sys.stdin)['run_id'])")
  for i in $(seq 1 400); do S=$(curl -s localhost:8000/api/runs/$ID | python3 -c "import sys,json;print(json.load(sys.stdin)['status'])"); [ "$S" = done -o "$S" = error ] && break; sleep 3; done
  echo "$C $S"
done
echo FIN
