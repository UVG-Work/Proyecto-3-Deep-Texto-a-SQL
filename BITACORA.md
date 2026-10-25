# Bitácora

| Fecha | Autor | Entrada |
|---|---|---|
| 2026-10-24 | June Herrera | Instalación de MySQL 8.4.10 (Docker `mysql:8.4.10`) y verificación de `ONLY_FULL_GROUP_BY` y `lower_case_table_names=0`. Entorno con torch CUDA 13 para la RTX 5070. Utilidades compartidas en `scripts/db.py`. |
| 2026-10-24 | Andrés Mazariegos | Descarga de Spider y conversión a MySQL (`spider_a_mysql.py`): 9 094 pares válidos; 599 descartados (408 con resultado distinto a SQLite, 191 con error en MySQL). |
| 2026-10-25 | Andrés Mazariegos | Traducción al español con opus-mt-en-es protegiendo los literales con marcadores. Se detectó un bug (marcadores pegados a palabras y siglas cortas dentro de palabras, p. ej. "departmENts"); se corrigió y se re-tradujo: quedaron solo 5 marcadores perdidos. |
| 2026-10-25 | June Herrera | 12 esquemas propios con COMMENT en español y nombres abreviados ES/EN; 844 pares generados con LLM, todos ejecutados sin error en MySQL 8.4.10. Validación propia: `taller_mecanico` y `conference_events`, 40 preguntas (12 fáciles, 16 medias, 12 difíciles), sin esquemas compartidos con el entrenamiento. |
| 2026-10-25 | June Herrera | Evaluador de exactitud por ejecución con las reglas del enunciado (orden, redondeo a 2 decimales, columna extra). Baseline: EX ponderada 0.325; 17 de 24 fallos se deben a columnas inventadas. |
| 2026-10-25 | Andrés Mazariegos | Primer intento de entrenamiento: 117 s/paso por desborde de VRAM (batch 4, logits de 152k de vocabulario). Solución: batch 1 × acumulación 16 y logits solo para la respuesta (`logits_to_keep`): 10.6 s/paso con 3.8 GB. |
| 2026-10-25 | June Herrera | Config A (LoRA en q,k,v,o): 77.7 min, 4.36 M parámetros, EX 0.388. Config B (atención + MLP): 92.7 min, 18.5 M parámetros, EX 0.450. Se confirma la hipótesis (B > A). |
| 2026-10-25 | Andrés Mazariegos | Experimento de inferencia: autocorrección con `ejecutar` (+0.05 en el baseline y en B). Análisis de errores: dominan las columnas inexistentes y los JOIN de 2–3 saltos. |
| 2026-10-25 | Andrés Mazariegos | 6 esquemas propios más (486 pares) dirigidos a los errores. Modelo final = B + datos v2 + 2 épocas (141 min): EX 0.55 en bf16 y 0.61 en fp16 (T4). Mejora sobre el modelo base: +0.175 / +0.30. |
| 2026-10-25 | June Herrera | Verificación de `solucion.py` en fp16 (T4): carga en 12 s, ≤ 18 s por pregunta, determinista. README, notebooks, presentación y predicción de la EX (≈ 0.55). |
