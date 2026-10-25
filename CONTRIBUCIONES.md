# Contribuciones

Áreas: **Andrés Mazariegos** es responsable de los **datos** (Spider → MySQL, traducción, armado del dataset, esquemas
extra) y del **análisis de errores**. **June Herrera** es responsable del **entrenamiento** y de la **validación** (validación
propia, evaluador, baseline, solución y verificación en T4). Las evidencias son los commits de `historial_git.txt`.

| Tarea | Responsable | Evidencia |
|---|---|---|
| Entorno, MySQL 8.4.10, utilidades (`scripts/db.py`, `config.json`, `requirements.txt`) | June Herrera | commit "Estructura inicial…" |
| Conversión de Spider a MySQL 8.4.10 (`scripts/spider_a_mysql.py`) | Andrés Mazariegos | `datos/descartes_spider.csv` |
| Traducción al español de Spider (`scripts/traducir_spider.py`) | Andrés Mazariegos | `datos/intermedio/` |
| 12 esquemas propios + pares generados con LLM (`datos/esquemas_propios/`) | June Herrera | commit "Esquemas propios…" |
| Validación propia: 2 esquemas, 40 preguntas (`datos/validacion/`) | June Herrera | commit "Validación propia…" |
| Evaluador EX ponderada (`scripts/evaluar.py`, `scripts/evaluar_modelo.py`) | June Herrera | autotests en `python scripts/evaluar.py` |
| Armado del dataset y descartes (`scripts/construir_dataset.py`) | Andrés Mazariegos | `datos/resumen_dataset*.json`, `datos/descartes.csv` |
| `solucion.py` (prompt, compactación del esquema, autocorrección) | June Herrera | commit "Solución…" |
| Entrenamiento LoRA config A y B (`scripts/entrenar.py`) | Andrés Mazariegos y June Herrera | `resultados/metricas_lora_attn.json`, `resultados/metricas_lora_all.json` |
| Baseline y evaluación de A/B | June Herrera | `resultados/baseline.csv`, `resultados/lora_*.csv` |
| Experimento de inferencia (autocorrección con `ejecutar`) | Andrés Mazariegos | `resultados/*_autocorreccion.csv` |
| Análisis de errores por categoría y gráficas (`scripts/graficas.py`) | Andrés Mazariegos | `resultados/errores_categoria.png` |
| 6 esquemas extra y modelo final (datos v2, 2 épocas) | Andrés Mazariegos | `resultados/metricas_lora_final.json` |
| Verificación fp16/T4 y `resultados/validacion_propia.csv` | June Herrera | `resultados/final_fp16_autocorreccion.csv` |
| Notebooks (`notebooks/`) | Andrés Mazariegos | `notebooks/0*.ipynb` |
| README, presentación y predicción justificada | June Herrera | `README.md`, `presentacion.pdf` |
