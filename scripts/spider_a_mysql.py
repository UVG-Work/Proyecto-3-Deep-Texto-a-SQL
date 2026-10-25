"""Convierte Spider (SQLite) a MySQL 8.4.10.

1. Carga cada base SQLite de Spider en MySQL como `sp_<db_id>` (tipos inferidos de los datos, PK, FK).
2. Transpila cada consulta gold de SQLite a MySQL con sqlglot, corrigiendo mayúsculas de tablas.
3. Ejecuta la consulta en MySQL y la compara con el resultado en SQLite.
   Se descartan: error de transpilación, error en MySQL (p. ej. ONLY_FULL_GROUP_BY) y resultado distinto.

Uso: python scripts/spider_a_mysql.py C:/spider_dl/spider_data
Salida: datos/intermedio/spider_mysql.jsonl, datos/descartes_spider.csv
"""
import csv
import json
import re
import sqlite3
import sys
from collections import Counter
from pathlib import Path

import sqlglot
from sqlglot import exp

sys.path.insert(0, str(Path(__file__).parent))
from db import conectar, ejecutar
from evaluar import resultados_iguales

RAIZ = Path(sys.argv[1])
SALIDA = Path(__file__).parent.parent / "datos"
(SALIDA / "intermedio").mkdir(parents=True, exist_ok=True)

FECHA = re.compile(r"^\d{4}-\d{2}-\d{2}$")
FECHA_HORA = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")


def es_num(v):
    try:
        float(v)
        return True
    except (TypeError, ValueError):
        return False


def tipo_mysql(decl, valores):
    """Elige un tipo MySQL compatible con todos los valores no nulos de la columna."""
    decl = (decl or "").lower()
    vals = [v for v in valores if v is not None and v != ""]
    if not vals:
        if "int" in decl:
            return "INT"
        if any(k in decl for k in ("real", "float", "doub", "num", "dec")):
            return "DOUBLE"
        return "VARCHAR(255)"
    if all(isinstance(v, int) or (isinstance(v, str) and re.fullmatch(r"-?\d+", v.strip())) for v in vals):
        grande = max(abs(int(v)) for v in vals) > 2_000_000_000
        return "BIGINT" if grande else "INT"
    if all(isinstance(v, (int, float)) or (isinstance(v, str) and es_num(v)) for v in vals):
        return "DOUBLE"
    s = [str(v) for v in vals]
    if ("date" in decl or "time" in decl) and all(FECHA.match(x) for x in s):
        return "DATE"
    if ("date" in decl or "time" in decl) and all(FECHA_HORA.match(x) for x in s):
        return "DATETIME"
    return "VARCHAR(255)" if max(len(x.encode("utf8")) for x in s) <= 255 else "TEXT"


def convertir_valor(v, tipo):
    if v is None:
        return None
    if tipo in ("INT", "BIGINT", "DOUBLE") and (v == "" or (isinstance(v, str) and not es_num(v))):
        return None
    if isinstance(v, bytes):
        return v.decode("utf8", "replace")
    return v


def cargar_base(db_id):
    ruta = RAIZ / "database" / db_id / f"{db_id}.sqlite"
    src = sqlite3.connect(ruta)
    src.text_factory = lambda b: b.decode("utf8", "replace")
    tablas = [r[0] for r in src.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
    my = "sp_" + db_id.lower()
    with conectar() as c, c.cursor() as cur:
        cur.execute(f"DROP DATABASE IF EXISTS `{my}`")
        cur.execute(f"CREATE DATABASE `{my}` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci")
    c = conectar(my, autocommit=True)
    cur = c.cursor()
    cur.execute("SET FOREIGN_KEY_CHECKS=0")
    tipos = {}
    for t in tablas:
        info = src.execute(f'PRAGMA table_info("{t}")').fetchall()
        filas = src.execute(f'SELECT * FROM "{t}"').fetchall()
        cols, defs, pks = [], [], []
        for i, (_, nombre, decl, notnull, _, pk) in enumerate(info):
            tp = tipo_mysql(decl, [f[i] for f in filas])
            if pk and tp == "TEXT":
                tp = "VARCHAR(255)"
            tipos[(t.lower(), nombre.lower())] = tp
            cols.append(tp)
            defs.append(f"`{nombre}` {tp}")
            if pk:
                pks.append((pk, nombre))
        if pks:
            defs.append("PRIMARY KEY (" + ", ".join(f"`{n}`" for _, n in sorted(pks)) + ")")
        cur.execute(f"CREATE TABLE `{t}` (" + ", ".join(defs) + ")")
        if filas:
            ph = ", ".join(["%s"] * len(info))
            datos = [[convertir_valor(v, cols[i]) for i, v in enumerate(f)] for f in filas]
            cur.executemany(f"INSERT IGNORE INTO `{t}` VALUES ({ph})", datos)
    # Claves foráneas: se agregan una a una; las incompatibles se omiten.
    for t in tablas:
        for fk in src.execute(f'PRAGMA foreign_key_list("{t}")').fetchall():
            ref_t, col, ref_c = fk[2], fk[3], fk[4]
            real_ref = next((x for x in tablas if x.lower() == (ref_t or "").lower()), None)
            if not real_ref or not ref_c:
                continue
            try:
                cur.execute(f"ALTER TABLE `{real_ref}` ADD INDEX (`{ref_c}`)")
            except Exception:
                pass
            try:
                cur.execute(f"ALTER TABLE `{t}` ADD FOREIGN KEY (`{col}`) REFERENCES `{real_ref}` (`{ref_c}`)")
            except Exception:
                pass
    c.close()
    return src, my, tablas


def transpilar(sql, tablas):
    sql = re.sub(r'"([^"\']*)"', r"'\1'", sql)  # Spider usa comillas dobles para cadenas
    arbol = sqlglot.parse_one(sql, read="sqlite")
    canon = {t.lower(): t for t in tablas}
    for tb in arbol.find_all(exp.Table):
        if tb.name.lower() in canon:
            tb.set("this", exp.to_identifier(canon[tb.name.lower()]))
    return arbol.sql(dialect="mysql")


def main():
    ejemplos = []
    for archivo, fuente in [("train_spider.json", "spider_train"), ("train_others.json", "spider_others"),
                            ("dev.json", "spider_dev")]:
        for e in json.load(open(RAIZ / archivo, encoding="utf8")):
            ejemplos.append({"db_id": e["db_id"], "question": e["question"], "query_sqlite": e["query"], "fuente": fuente})
    salida, descartes = [], []
    motivos = Counter()
    por_db = {}
    for e in ejemplos:
        por_db.setdefault(e["db_id"], []).append(e)
    for n, (db_id, lista) in enumerate(sorted(por_db.items())):
        try:
            src, my, tablas = cargar_base(db_id)
        except Exception as ex:
            for e in lista:
                descartes.append({**e, "motivo": "carga_base", "detalle": str(ex)[:200]})
            motivos["carga_base"] += len(lista)
            continue
        for e in lista:
            try:
                sql = transpilar(e["query_sqlite"], tablas)
            except Exception as ex:
                motivo, det = "transpilacion", str(ex)[:200]
            else:
                r = ejecutar(my, sql)
                if not r["ok"]:
                    motivo, det = "error_mysql", r["error"][:200]
                else:
                    try:
                        ref = [list(f) for f in src.execute(e["query_sqlite"]).fetchall()]
                    except Exception as ex:
                        ref = None
                    orden = "order by" in e["query_sqlite"].lower()
                    if ref is not None and not resultados_iguales(r["filas"], ref, orden, extra_ok=False):
                        motivo, det = "resultado_distinto_sqlite", ""
                    else:
                        salida.append({**e, "db": my, "sql": sql})
                        continue
            motivos[motivo] += 1
            descartes.append({**e, "motivo": motivo, "detalle": det})
        print(f"[{n + 1}/{len(por_db)}] {db_id}: acumulado {len(salida)} ok, {len(descartes)} descartes", flush=True)
    with open(SALIDA / "intermedio" / "spider_mysql.jsonl", "w", encoding="utf8") as f:
        for s in salida:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")
    with open(SALIDA / "descartes_spider.csv", "w", encoding="utf8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["fuente", "db_id", "question", "query_sqlite", "motivo", "detalle"], extrasaction="ignore")
        w.writeheader()
        w.writerows(descartes)
    print("OK:", len(salida), "Descartes:", dict(motivos))


if __name__ == "__main__":
    main()
