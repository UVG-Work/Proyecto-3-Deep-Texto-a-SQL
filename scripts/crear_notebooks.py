"""Genera notebooks/01_datos.ipynb, 02_entrenamiento.ipynb y 03_evaluacion.ipynb.
Los pasos pesados (conversión, entrenamiento, inferencia) están detrás de PASOS_PESADOS=False;
las celdas de análisis leen los artefactos ya generados en datos/ y resultados/.
"""
import json
from pathlib import Path

NB = Path(__file__).resolve().parent.parent / "notebooks"


def nb(celdas):
    cells = []
    for tipo, src in celdas:
        c = {"cell_type": tipo, "metadata": {}, "source": src.strip("\n").splitlines(keepends=True)}
        if tipo == "code":
            c.update(outputs=[], execution_count=None)
        cells.append(c)
    return {"cells": cells, "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                                         "language_info": {"name": "python"}}, "nbformat": 4, "nbformat_minor": 5}


COMUN = """
import json, os, sys
from pathlib import Path
import pandas as pd
RAIZ = Path.cwd().parent if Path.cwd().name == "notebooks" else Path.cwd()
os.chdir(RAIZ); sys.path.insert(0, "scripts")
PASOS_PESADOS = False  # True para regenerar todo (requiere MySQL 8.4.10 en Docker y GPU)
pd.set_option("display.max_colwidth", 120)
"""

datos = nb([
    ("markdown", """
# 1. Dataset de entrenamiento y validación propia

**Fuentes**
1. **Spider** (train + others + dev), convertido de SQLite a MySQL 8.4.10 y con las preguntas traducidas al español
   (Helsinki-NLP/opus-mt-en-es, protegiendo los literales de la consulta con marcadores).
2. **12 esquemas propios** (5–8 tablas, nombres en español/inglés, completos o abreviados, con `COMMENT`),
   con pares pregunta–SQL generados con un LLM. Cubren lo que Spider no tiene: funciones de ventana, CTE, fechas de MySQL.

Solo se aceptan pares cuya consulta se ejecuta sin error en MySQL 8.4.10 (`ONLY_FULL_GROUP_BY` activo).
La validación propia usa 2 esquemas que **no** aparecen en entrenamiento (partición por esquema).
"""),
    ("code", COMUN),
    ("code", """
if PASOS_PESADOS:
    !python scripts/spider_a_mysql.py C:/spider_dl/spider_data
    !python scripts/traducir_spider.py C:/spider_dl/spider_data
    !python scripts/construir_dataset.py
resumen = json.loads(Path("datos/resumen_dataset.json").read_text(encoding="utf8"))
{k: v for k, v in resumen.items() if k != "tablas_validacion"}
"""),
    ("markdown", "## Descartes y motivo"),
    ("code", """
desc = pd.read_csv("datos/descartes.csv")
print(desc.motivo.value_counts().to_string())
desc.groupby("motivo").head(2)[["motivo", "question", "query_sqlite", "detalle"]]
"""),
    ("markdown", """
- **resultado_distinto_sqlite**: la consulta corre en MySQL pero devuelve otra cosa que en SQLite (división entera, comparación de
  cadenas sin distinguir mayúsculas, `LIMIT` con empates…). Se descarta para no enseñar consultas cuyo significado cambió.
- **error_mysql**: falla en MySQL 8.4.10, típicamente por `ONLY_FULL_GROUP_BY`, palabras reservadas o funciones de SQLite.
- **traduccion_perdio_valor**: el traductor alteró un literal que la consulta necesita (p. ej. un nombre propio).
- **esquema_demasiado_largo**: prompt + respuesta > 2048 tokens.
"""),
    ("markdown", "## Ejemplos de entrenamiento"),
    ("code", """
train = pd.read_json("datos/entrenamiento.jsonl", lines=True)
print(train.fuente.value_counts().to_string())
train.groupby("fuente").head(3)[["fuente", "db", "pregunta", "sql"]]
"""),
    ("code", """
propios = train[train.fuente == "propio"].drop_duplicates(["db", "pregunta"])
pd.crosstab(propios.db, propios.nivel, margins=True)
"""),
    ("code", """
print(train[train.fuente == "propio"].iloc[0].esquema[:1500])
"""),
    ("markdown", "## Validación propia (40 preguntas, 2 esquemas no vistos)"),
    ("code", """
val = pd.read_json("datos/validacion_propia.jsonl", lines=True)
display(pd.crosstab(val.db, val.nivel, margins=True))
assert not set(val.db.str.replace("val_", "own_")) & set(train.db), "esquema de validación presente en entrenamiento"
val[["db", "nivel", "pregunta", "sql"]]
"""),
])

entrenamiento = nb([
    ("markdown", """
# 2. Entrenamiento LoRA: dos configuraciones que difieren en un solo factor

Base: `Qwen/Qwen2.5-Coder-1.5B-Instruct`, bf16, gradient checkpointing, 1 época, lr 2e-4 coseno, batch efectivo 16,
r = 16, α = 32, dropout 0.05. Pérdida solo sobre los tokens de la SQL (el prompt se enmascara).

**Factor que cambia: los módulos donde se inserta LoRA.**

| | Config A `lora_attn` | Config B `lora_all` |
|---|---|---|
| Módulos | `q,k,v,o` (atención) | `q,k,v,o,gate,up,down` (atención + MLP) |

**Hipótesis (escrita antes de entrenar).** B tendrá menor loss de validación y mayor EX que A. En un modelo de 1.5B,
las capas MLP concentran la mayor parte de los parámetros y son donde se almacena el "conocimiento" de patrones
(dialecto MySQL, uso de `COMMENT`, estructura de CTE y ventanas); adaptar solo la atención cambia sobre todo *a qué
columnas mira* el modelo, pero no tanto *qué escribe*. Esperamos que A mejore sobre el baseline (copiar nombres de
columnas del esquema en lugar de inventarlos) y que B mejore además en preguntas medias/difíciles. Costo esperado
de B: ~4× parámetros entrenables y algo más de tiempo por paso.
"""),
    ("code", COMUN),
    ("code", """
if PASOS_PESADOS:
    !python scripts/entrenar.py --nombre lora_attn --modulos attn --batch 1 --acum 16 --max_spider 4000
    !python scripts/entrenar.py --nombre lora_all  --modulos all  --batch 1 --acum 16 --max_spider 4000
    # modelo final (entregado): config B + 6 esquemas propios más (datos v2) + 2 épocas
    !python scripts/entrenar.py --nombre lora_final --modulos all --batch 1 --acum 16 --max_spider 3000 --epocas 2
filas = []
for n in ["lora_attn", "lora_all", "lora_final"]:
    m = json.loads(Path(f"resultados/metricas_{n}.json").read_text(encoding="utf8"))
    ev = [x["eval_loss"] for x in m["historial"] if "eval_loss" in x]
    tr = [x["loss"] for x in m["historial"] if "loss" in x]
    filas.append({"config": n, "módulos": ",".join(m["modulos"]), "parámetros entrenables": f'{m["parametros_entrenables"]:,}',
                  "% del modelo": m["porcentaje_entrenable"], "ejemplos": m["ejemplos"], "minutos": m["minutos_entrenamiento"],
                  "VRAM máx (GB)": m["vram_max_gb"], "loss train final": round(tr[-1], 4), "loss dev final": round(ev[-1], 4)})
pd.DataFrame(filas)
"""),
    ("code", """
import matplotlib.pyplot as plt
fig, ax = plt.subplots(figsize=(9, 4.5))
for n, c in [("lora_attn", "#2a6fdb"), ("lora_all", "#e0572b")]:
    h = json.loads(Path(f"resultados/metricas_{n}.json").read_text(encoding="utf8"))["historial"]
    ax.plot([x["step"] for x in h if "loss" in x], [x["loss"] for x in h if "loss" in x], color=c, alpha=.4, label=f"{n} train")
    ax.plot([x["step"] for x in h if "eval_loss" in x], [x["eval_loss"] for x in h if "eval_loss" in x], color=c, lw=2, marker="o", label=f"{n} dev")
ax.set_xlabel("paso"); ax.set_ylabel("loss"); ax.grid(alpha=.3); ax.legend(); plt.show()
"""),
    ("markdown", """
**Resultado:** se confirma la hipótesis. B baja más la loss de dev (0.130 frente a 0.144) y sube la EX de 0.388 a 0.450
(ver notebook 03), sobre todo en las preguntas medias. A arregla las fáciles y reduce las columnas inventadas, pero no
mejora las medias.

**Modelo final:** config B con 6 esquemas más (datos v2) y 2 épocas. Su dev incluye ejemplos de los esquemas nuevos, así
que no se compara directamente con A/B. Mínimo al final de la época 1 y leve subida en la 2; aun así la EX mejora.
"""),
    ("code", """
from IPython.display import Image
Image("resultados/curva_final.png")
"""),
])

evaluacion = nb([
    ("markdown", """
# 3. Evaluación en la validación propia, experimento de inferencia y análisis de errores

Métrica: **EX ponderada** (fácil 1, media 2, difícil 3) con las reglas del enunciado: orden de filas solo si la
pregunta lo pide, números redondeados a 2 decimales, una columna adicional no penaliza (`scripts/evaluar.py`).
"""),
    ("code", COMUN),
    ("code", """
if PASOS_PESADOS:
    !python scripts/evaluar_modelo.py --nombre baseline --sin-adapter
    !python scripts/evaluar_modelo.py --nombre lora_attn --adapter checkpoints/lora_attn/adapter
    !python scripts/evaluar_modelo.py --nombre lora_all --adapter checkpoints/lora_all/adapter
    !python scripts/evaluar_modelo.py --nombre lora_all_autocorreccion --adapter checkpoints/lora_all/adapter --autocorreccion
    !python scripts/evaluar_modelo.py --nombre baseline_autocorreccion --sin-adapter --autocorreccion
    !python scripts/evaluar_modelo.py --nombre final --adapter checkpoints/lora_final/adapter
    !python scripts/evaluar_modelo.py --nombre final_autocorreccion --adapter checkpoints/lora_final/adapter --autocorreccion
    !python scripts/evaluar_modelo.py --nombre final_fp16_autocorreccion --adapter adapter/ --autocorreccion --fp16
    !python scripts/evaluar_modelo.py --nombre baseline_fp16_autocorreccion --sin-adapter --autocorreccion --fp16
r = json.loads(Path("resultados/resumen.json").read_text(encoding="utf8"))
tabla = pd.DataFrame(r).T[["EX_ponderada", "EX_simple", "por_nivel", "ejecutan", "segundos_promedio", "segundos_max", "dtype"]]
tabla["dtype"] = tabla["dtype"].fillna("bf16")
tabla
"""),
    ("markdown", """
**Experimento de inferencia (autocorrección con `ejecutar`):** si la consulta falla, se le muestra el error de MySQL al
modelo y se regenera (máx. 3 llamadas). Mejora +0.05 en baseline y en B, y +0.025 en el final. Arregla columnas
inexistentes, no errores semánticos. Mejora del adapter frente al base con autocorrección: +0.175 (bf16) / +0.30 (fp16).
"""),
    ("code", """
from IPython.display import Image
Image("resultados/ex_comparacion.png")
"""),
    ("markdown", "## Errores por categoría"),
    ("code", """
pd.DataFrame({k: v["errores_por_categoria"] for k, v in r.items()}).fillna(0).astype(int)
"""),
    ("code", """
final = pd.read_csv("resultados/validacion_propia.csv")
final[~final.correcta][["nivel", "categoria_error", "pregunta", "sql_generada", "sql_referencia", "error_mysql"]]
"""),
    ("markdown", "## Comparación por pregunta: baseline vs. modelo final"),
    ("code", """
base = pd.read_csv("resultados/baseline.csv")
comp = pd.DataFrame({"nivel": base.nivel, "pregunta": base.pregunta, "baseline": base.correcta, "final": final.correcta})
print("arregladas:", int((~comp.baseline & comp.final).sum()), "| empeoradas:", int((comp.baseline & ~comp.final).sum()))
comp[comp.baseline != comp.final]
"""),
    ("markdown", """
## Predicción para la evaluación oculta

EX ≈ 0.55 con adapter (intervalo 0.42–0.68) y ≈ 0.33 sin adapter. La justificación completa está en el README §8: por
nivel, fácil ≈ 92 %, media ≈ 75–80 %, difícil ≈ 25–33 %. El error estándar es ≈ 0.08 con 30–40 preguntas (la sola
diferencia bf16/fp16 mueve 6 puntos). Nuestras trampas pueden ser más duras que las del docente, pero el estilo de la
validación se parece al del entrenamiento.
"""),
])

for nombre, cuaderno in [("01_datos", datos), ("02_entrenamiento", entrenamiento), ("03_evaluacion", evaluacion)]:
    (NB / f"{nombre}.ipynb").write_text(json.dumps(cuaderno, ensure_ascii=False, indent=1), encoding="utf8")
print("ok")
