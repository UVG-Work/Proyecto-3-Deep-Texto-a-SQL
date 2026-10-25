"""Evalúa solucion.generar_sql sobre la validación propia (40 preguntas) con EX ponderada.

Uso:
  python scripts/evaluar_modelo.py --nombre baseline --sin-adapter
  python scripts/evaluar_modelo.py --nombre lora_all --adapter checkpoints/lora_all/adapter
  python scripts/evaluar_modelo.py --nombre final_fp16_autocorreccion --adapter adapter/ --autocorreccion --fp16
Escribe resultados/<nombre>.csv y agrega el resumen a resultados/resumen.json.
"""
import argparse
import csv
import json
import os
import sys
import time
from collections import Counter
from pathlib import Path

os.environ["TSQL_NO_CARGAR"] = "1"
BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / "scripts"))
sys.path.insert(0, str(BASE))
import solucion
from db import ejecutar
from evaluar import PESOS, categoria_error, resultados_iguales


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nombre", required=True)
    ap.add_argument("--adapter", default="adapter/")
    ap.add_argument("--sin-adapter", action="store_true")
    ap.add_argument("--autocorreccion", action="store_true")
    ap.add_argument("--datos", default="datos/validacion_propia.jsonl")
    ap.add_argument("--fp16", action="store_true", help="simula la T4 de Colab (cómputo en fp16)")
    a = ap.parse_args()
    if a.fp16:
        import torch
        torch.cuda.get_device_capability = lambda *_: (7, 5)  # solucion.cargar elige fp16 con capacidad < 8

    solucion.CONFIG["usar_adapter"] = not a.sin_adapter
    solucion.CONFIG["adapter"] = a.adapter
    solucion.AUTOCORRECCION = a.autocorreccion
    t0 = time.time()
    solucion.cargar()
    t_carga = time.time() - t0

    items = [json.loads(l) for l in open(BASE / a.datos, encoding="utf8")]
    filas, puntos, total = [], 0, 0
    por_nivel = Counter()
    for it in items:
        llamadas = []

        def ejecutar_eval(sql, db=it["db"]):
            if len(llamadas) >= 3:
                return {"ok": False, "columnas": [], "filas": [], "error": "límite de 3 llamadas alcanzado"}
            llamadas.append(sql)
            return ejecutar(db, sql, max_filas=10)

        t = time.time()
        pred = solucion.generar_sql(it["esquema"], it["pregunta"], ejecutar_eval if a.autocorreccion else None)
        dt = time.time() - t
        gold = ejecutar(it["db"], it["sql"])
        rp = ejecutar(it["db"], pred) if solucion.es_lectura(pred) else {"ok": False, "error": "no es SELECT", "filas": []}
        ok = rp["ok"] and resultados_iguales(rp["filas"], gold["filas"], it.get("ordenado", False))
        peso = PESOS[it["nivel"]]
        total += peso
        puntos += peso * ok
        por_nivel[(it["nivel"], ok)] += 1
        filas.append({"db": it["db"], "nivel": it["nivel"], "ordenado": it.get("ordenado", False), "pregunta": it["pregunta"],
                      "sql_referencia": it["sql"], "sql_generada": pred, "ejecuta": rp["ok"], "correcta": ok,
                      "categoria_error": "" if ok else categoria_error(pred, it["sql"], rp),
                      "error_mysql": "" if rp["ok"] else rp.get("error", ""), "segundos": round(dt, 2),
                      "llamadas_ejecutar": len(llamadas)})
        print(f"{'OK ' if ok else 'XX '} [{it['nivel']}] {dt:5.1f}s {pred[:110]}", flush=True)

    (BASE / "resultados").mkdir(exist_ok=True)
    with open(BASE / "resultados" / f"{a.nombre}.csv", "w", encoding="utf8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(filas[0]))
        w.writeheader()
        w.writerows(filas)
    resumen = {
        "EX_ponderada": round(puntos / total, 4),
        "EX_simple": round(sum(f["correcta"] for f in filas) / len(filas), 4),
        "por_nivel": {n: f"{por_nivel[(n, True)]}/{por_nivel[(n, True)] + por_nivel[(n, False)]}" for n in PESOS},
        "ejecutan": sum(f["ejecuta"] for f in filas),
        "errores_por_categoria": dict(Counter(f["categoria_error"] for f in filas if not f["correcta"])),
        "segundos_promedio": round(sum(f["segundos"] for f in filas) / len(filas), 2),
        "segundos_max": max(f["segundos"] for f in filas),
        "segundos_carga": round(t_carga, 1),
        "adapter": None if a.sin_adapter else a.adapter,
        "autocorreccion": a.autocorreccion,
        "dtype": "fp16" if a.fp16 else "bf16",
    }
    ruta = BASE / "resultados" / "resumen.json"
    todo = json.loads(ruta.read_text(encoding="utf8")) if ruta.exists() else {}
    todo[a.nombre] = resumen
    ruta.write_text(json.dumps(todo, ensure_ascii=False, indent=2), encoding="utf8")
    print(json.dumps({a.nombre: resumen}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
