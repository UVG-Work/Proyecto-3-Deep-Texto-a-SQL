"""Arma los conjuntos finales:
- datos/entrenamiento.jsonl: Spider traducido (MySQL) + 12 esquemas propios (repetidos x3).
- datos/validacion_propia.jsonl: 2 esquemas propios no vistos, 40 preguntas.
- datos/descartes.csv: todos los pares descartados y el motivo.
Cada ejemplo lleva el esquema tal como lo devuelve SHOW CREATE TABLE en MySQL 8.4.10.
"""
import csv
import json
import os
import random
import re
import sys
from collections import Counter
from pathlib import Path

os.environ["TSQL_NO_CARGAR"] = "1"
BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / "scripts"))
sys.path.insert(0, str(BASE))
from db import cargar_sql, esquema, ejecutar
from solucion import mensajes
from transformers import AutoTokenizer

DATOS = BASE / "datos"
MAX_TOKENS = 2048
REPETIR_PROPIOS = 3
random.seed(2026)
tok = AutoTokenizer.from_pretrained("Qwen/Qwen2.5-Coder-1.5B-Instruct")


def con_comentarios(texto, com):
    """Agrega COMMENT en español a columnas/tablas de un SHOW CREATE TABLE de Spider."""
    out, tabla = [], None
    for l in texto.splitlines():
        m = re.match(r"CREATE TABLE `([^`]+)`", l)
        if m:
            tabla = com.get(m.group(1), {})
        m = re.match(r"(\s+`([^`]+)` .*?)(,?)$", l)
        if m and tabla and m.group(2) in tabla and "COMMENT" not in l:
            l = f"{m.group(1)} COMMENT '{tabla[m.group(2)].replace(chr(39), chr(39) * 2)}'{m.group(3)}"
        if l.startswith(") ENGINE") and tabla and "__tabla__" in tabla:
            l = l.rstrip(";") + f" COMMENT='{tabla['__tabla__'].replace(chr(39), chr(39) * 2)}';"
        out.append(l)
    return "\n".join(out)


def n_tokens(esq, preg, sql):
    m = mensajes(esq, preg) + [{"role": "assistant", "content": sql}]
    return len(tok.apply_chat_template(m, tokenize=True, return_dict=False))


def main():
    descartes = list(csv.DictReader(open(DATOS / "descartes_spider.csv", encoding="utf8")))
    entrenamiento, motivos = [], Counter(d["motivo"] for d in descartes)

    # --- Spider traducido
    com = json.load(open(DATOS / "intermedio" / "spider_comentarios.json", encoding="utf8"))
    cache = {}
    for l in open(DATOS / "intermedio" / "spider_es.jsonl", encoding="utf8"):
        e = json.loads(l)
        if e["db"] not in cache:
            esq = esquema(e["db"])
            cache[e["db"]] = con_comentarios(esq, com[e["db_id"]]) if e["db_id"] in com else esq
        esq = cache[e["db"]]
        literales = [x for x in re.findall(r"'((?:[^']|'')+)'", e["sql"]) if len(x.strip("%")) >= 2]
        perdido = any(x.strip("%").lower() in e["question"].lower() and x.strip("%").lower() not in e["pregunta"].lower()
                      for x in literales)
        motivo = "traduccion_perdio_valor" if perdido else (
            "esquema_demasiado_largo" if n_tokens(esq, e["pregunta"], e["sql"]) > MAX_TOKENS else None)
        if motivo:
            motivos[motivo] += 1
            descartes.append({"fuente": e["fuente"], "db_id": e["db_id"], "question": e["question"],
                              "query_sqlite": e["query_sqlite"], "motivo": motivo, "detalle": e["pregunta"]})
            continue
        entrenamiento.append({"fuente": e["fuente"], "db": e["db"], "esquema": esq, "pregunta": e["pregunta"],
                              "sql": e["sql"], "nivel": None})

    # --- Esquemas propios (generados con LLM, validados en MySQL)
    propios = []
    for sqlf in sorted((DATOS / "esquemas_propios").glob("*.sql")):
        db = "own_" + sqlf.stem
        cargar_sql(db, sqlf)
        esq = esquema(db)
        for l in open(sqlf.with_suffix(".jsonl"), encoding="utf8"):
            if not l.strip():
                continue
            p = json.loads(l)
            r = ejecutar(db, p["sql"])
            if not r["ok"]:
                motivos["error_mysql"] += 1
                descartes.append({"fuente": "propio", "db_id": db, "question": p["pregunta"], "query_sqlite": p["sql"],
                                  "motivo": "error_mysql", "detalle": r["error"][:200]})
                continue
            propios.append({"fuente": "propio", "db": db, "esquema": esq, "pregunta": p["pregunta"],
                            "sql": p["sql"], "nivel": p["nivel"]})
    print("propios:", len(propios), "esquemas:", len({p['db'] for p in propios}))

    # --- Validación propia (no debe compartir esquemas con entrenamiento)
    validacion = []
    for sqlf in sorted((DATOS / "validacion").glob("*.sql")):
        db = "val_" + sqlf.stem
        cargar_sql(db, sqlf)
        esq = esquema(db)
        for l in open(sqlf.with_suffix(".jsonl"), encoding="utf8"):
            if l.strip():
                p = json.loads(l)
                validacion.append({"db": db, "esquema": esq, **p})
    tablas_val = {t for v in validacion for t in re.findall(r"CREATE TABLE `([^`]+)`", v["esquema"])}
    assert not {p["db"] for p in propios} & {v["db"].replace("val_", "own_") for v in validacion}

    # Separar 3 % de Spider por base (no por pregunta) para la curva de loss de validación interna.
    dbs_spider = sorted({e["db"] for e in entrenamiento})
    dev_dbs = set(random.sample(dbs_spider, 5))
    train = [e for e in entrenamiento if e["db"] not in dev_dbs] + propios * REPETIR_PROPIOS
    dev = [e for e in entrenamiento if e["db"] in dev_dbs] + random.sample(propios, 40)
    random.shuffle(train)

    def volcar(nombre, filas):
        with open(DATOS / nombre, "w", encoding="utf8") as f:
            for r in filas:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

    volcar("entrenamiento.jsonl", train)
    volcar("dev_loss.jsonl", dev)
    volcar("validacion_propia.jsonl", validacion)
    with open(DATOS / "descartes.csv", "w", encoding="utf8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["fuente", "db_id", "question", "query_sqlite", "motivo", "detalle"])
        w.writeheader()
        w.writerows(descartes)
    resumen = {
        "pares_spider_validos": len(entrenamiento),
        "pares_propios_unicos": len(propios),
        "esquemas_propios": len({p["db"] for p in propios}),
        "ejemplos_entrenamiento_con_repeticion": len(train),
        "ejemplos_dev_loss": len(dev),
        "preguntas_validacion": len(validacion),
        "descartes_por_motivo": dict(motivos),
        "total_descartes": sum(motivos.values()),
        "fuentes": dict(Counter(e["fuente"] for e in train)),
        "tablas_validacion": sorted(tablas_val),
    }
    json.dump(resumen, open(DATOS / "resumen_dataset.json", "w", encoding="utf8"), ensure_ascii=False, indent=2)
    print(json.dumps(resumen, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
