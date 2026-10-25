"""Carga un esquema propio en MySQL y ejecuta cada par pregunta-SQL.

Uso: python scripts/validar_pares.py datos/esquemas_propios/tienda.sql datos/esquemas_propios/tienda.jsonl
Reporta errores y consultas con resultado vacío. Código de salida 1 si hay errores.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from db import cargar_sql, ejecutar

ruta_sql, ruta_jsonl = sys.argv[1], sys.argv[2]
db = "own_" + Path(ruta_sql).stem
cargar_sql(db, ruta_sql)
pares = [json.loads(l) for l in open(ruta_jsonl, encoding="utf8") if l.strip()]
errores = vacios = 0
niveles = {}
for i, p in enumerate(pares):
    niveles[p["nivel"]] = niveles.get(p["nivel"], 0) + 1
    r = ejecutar(db, p["sql"])
    if not r["ok"]:
        errores += 1
        print(f"[ERROR] #{i} {p['pregunta']}\n   {p['sql']}\n   -> {r['error']}")
    elif not r["filas"]:
        vacios += 1
        print(f"[VACIO] #{i} {p['pregunta']}\n   {p['sql']}")
print(f"\n{db}: {len(pares)} pares, {errores} errores, {vacios} vacios, niveles={niveles}")
sys.exit(1 if errores else 0)
