"""Evaluador por exactitud de ejecución (EX ponderada), con las reglas del enunciado:
- el orden de filas solo cuenta si la pregunta lo pide;
- los números se redondean a 2 decimales;
- una columna adicional no penaliza.
También clasifica cada fallo en: sintaxis, columna/tabla inexistente, JOIN, agregación, filtro, resultado distinto.
`python scripts/evaluar.py` corre los autotests.
"""
import datetime
import decimal
import itertools
import re
from collections import Counter

PESOS = {"facil": 1, "media": 2, "dificil": 3}


def norm(v):
    if v is None:
        return None
    if isinstance(v, bool):
        return float(v)
    if isinstance(v, (int, float, decimal.Decimal)):
        return round(float(v), 2) + 0.0  # +0.0 evita -0.0
    if isinstance(v, (datetime.date, datetime.datetime, datetime.timedelta)):
        return str(v)
    if isinstance(v, bytes):
        return v.decode("utf8", "replace")
    s = str(v)
    try:  # números guardados como texto (p. ej. SQLite) se comparan como número
        return round(float(s), 2) + 0.0 if re.fullmatch(r"-?\d+(\.\d+)?", s.strip()) else s
    except ValueError:
        return s


def _iguales(pred, gold, ordenado):
    return pred == gold if ordenado else Counter(pred) == Counter(gold)


def resultados_iguales(pred, gold, ordenado=False, extra_ok=True):
    pred = [tuple(norm(v) for v in f) for f in pred]
    gold = [tuple(norm(v) for v in f) for f in gold]
    if len(pred) != len(gold):
        return False
    if not gold:
        return True
    ng, np_ = len(gold[0]), len(pred[0])
    if np_ == ng and _iguales(pred, gold, ordenado):
        return True
    if np_ < ng or (np_ > ng and not extra_ok):
        return False
    # Buscar qué columnas de la predicción corresponden a las de referencia (permite extras y otro orden).
    col = lambda filas, j: [f[j] for f in filas]
    firma = (lambda c: c) if ordenado else (lambda c: Counter(c))
    candidatos = [[k for k in range(np_) if firma(col(pred, k)) == firma(col(gold, j))] for j in range(ng)]
    if any(not c for c in candidatos):
        return False
    for combo in itertools.islice(itertools.product(*candidatos), 5000):
        if len(set(combo)) == ng and _iguales([tuple(f[k] for k in combo) for f in pred], gold, ordenado):
            return True
    return False


def categoria_error(sql_pred, sql_gold, res_pred):
    """Asigna una categoría de error a una predicción incorrecta."""
    if not sql_pred or not re.match(r"\s*(select|with)\b", sql_pred, re.I):
        return "sintaxis"
    if not res_pred["ok"]:
        e = res_pred["error"] or ""
        if "1054" in e or "1146" in e or "Unknown column" in e or "doesn't exist" in e:
            return "columna o tabla inexistente"
        return "sintaxis"
    try:
        import sqlglot
        from sqlglot import exp
        p, g = sqlglot.parse_one(sql_pred, read="mysql"), sqlglot.parse_one(sql_gold, read="mysql")
        tablas = lambda a: {t.name.lower() for t in a.find_all(exp.Table)}
        aggs = lambda a: sorted(type(x).__name__ for x in a.find_all(exp.AggFunc)) + (["GROUP"] if a.find(exp.Group) else [])
        filtro = lambda a: sorted(w.sql() for w in a.find_all(exp.Where, exp.Having))
        if tablas(p) != tablas(g) or len(list(p.find_all(exp.Join))) != len(list(g.find_all(exp.Join))):
            return "JOIN"
        if aggs(p) != aggs(g):
            return "agregacion"
        if filtro(p) != filtro(g):
            return "filtro"
    except Exception:
        pass
    return "resultado distinto"


def _demo():
    assert resultados_iguales([[1, "a"], [2, "b"]], [[2, "b"], [1, "a"]])
    assert not resultados_iguales([[1, "a"], [2, "b"]], [[2, "b"], [1, "a"]], ordenado=True)
    assert resultados_iguales([[3.14159]], [[decimal.Decimal("3.14")]])
    assert resultados_iguales([["x", 5, 7]], [[5, "x"]])  # columna extra y otro orden
    assert not resultados_iguales([[5]], [[5, "x"]])
    assert not resultados_iguales([["x", 5, 7]], [[5, "x"]], extra_ok=False)
    assert resultados_iguales([], [])
    print("evaluar: ok")


if __name__ == "__main__":
    _demo()
