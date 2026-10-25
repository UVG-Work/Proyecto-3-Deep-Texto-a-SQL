"""Text-to-SQL (español -> MySQL 8.4) con Qwen2.5-Coder-1.5B-Instruct + adapter LoRA.

Contrato: generar_sql(esquema, pregunta, ejecutar=None) -> str
El modelo se carga al importar el módulo (límite: 5 min). Generación determinista (greedy).
Si el evaluador entrega `ejecutar`, la consulta se prueba y, si falla, se pide al modelo que la corrija
(máximo 3 llamadas a `ejecutar` por pregunta).
"""
import json
import os
import re
import time
from pathlib import Path

DIR = Path(__file__).resolve().parent
CONFIG = json.loads((DIR / "config.json").read_text(encoding="utf8"))

SISTEMA = (
    "Eres un experto en bases de datos MySQL 8.4. Recibes el esquema de una base de datos "
    "(sentencias CREATE TABLE, con comentarios que explican tablas y columnas) y una pregunta en español. "
    "Responde únicamente con una consulta SQL de MySQL (SELECT o WITH ... SELECT) que responda la pregunta, "
    "devolviendo las columnas que se piden. Respeta ONLY_FULL_GROUP_BY. No expliques nada."
)

MAX_NUEVOS = 320
MAX_CORRECCIONES = 2  # 1 ejecución inicial + 2 correcciones = 3 llamadas a `ejecutar`
TIEMPO_MAX = 22.0  # segundos; deja margen bajo el límite de 30 s
AUTOCORRECCION = os.environ.get("TSQL_AUTOCORRECCION", "1") == "1"


def compactar_esquema(esquema: str) -> str:
    """Quita del SHOW CREATE TABLE lo que no aporta (motor, charset, índices simples) para ahorrar tokens."""
    lineas = []
    for l in esquema.splitlines():
        s = l.strip()
        if re.match(r"^(UNIQUE )?KEY `", s) and not s.startswith("UNIQUE"):
            continue  # índices secundarios
        l = re.sub(r"\) ENGINE=.*?(COMMENT='.*')?;?$", lambda m: ")" + (" " + m.group(1) if m.group(1) else "") + ";", l)
        l = re.sub(r" (CHARACTER SET|COLLATE) \w+", "", l)
        l = re.sub(r" CONSTRAINT `[^`]+`", "", l)
        lineas.append(l)
    texto = "\n".join(lineas)
    texto = re.sub(r",\n\)", "\n)", texto)  # coma colgante tras quitar índices
    return re.sub(r"\n{3,}", "\n\n", texto).strip()


def mensajes(esquema: str, pregunta: str):
    return [
        {"role": "system", "content": SISTEMA},
        {"role": "user", "content": f"Esquema:\n{compactar_esquema(esquema)}\n\nPregunta: {pregunta.strip()}"},
    ]


def extraer_sql(texto: str) -> str:
    """Toma la primera consulta SELECT/WITH del texto generado."""
    m = re.search(r"```(?:sql|mysql)?\s*(.*?)```", texto, re.S | re.I)
    if m:
        texto = m.group(1)
    m = re.search(r"\b(WITH|SELECT)\b", texto, re.I)
    if not m:
        return texto.strip()
    sql = texto[m.start():]
    sql = sql.split(";")[0]  # una sola sentencia
    return re.sub(r"\s+", " ", sql).strip()


# ---------------------------------------------------------------- modelo
_modelo = _tok = None


def cargar():
    global _modelo, _tok
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    torch.manual_seed(CONFIG.get("semilla", 2026))
    cuda = torch.cuda.is_available()
    dtype = torch.bfloat16 if cuda and torch.cuda.get_device_capability()[0] >= 8 else torch.float16
    if not cuda:
        dtype = torch.float32
    _tok = AutoTokenizer.from_pretrained(CONFIG["modelo_base"])
    _modelo = AutoModelForCausalLM.from_pretrained(CONFIG["modelo_base"], dtype=dtype,
                                                   device_map="cuda" if cuda else None)
    if CONFIG.get("usar_adapter", True):
        from peft import PeftModel
        _modelo = PeftModel.from_pretrained(_modelo, str(DIR / CONFIG["adapter"])).merge_and_unload()
    _modelo.eval()


def _generar(msgs) -> str:
    import torch
    prompt = _tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
    ids = _tok(prompt, return_tensors="pt").to(_modelo.device)
    with torch.no_grad():
        out = _modelo.generate(**ids, max_new_tokens=MAX_NUEVOS, do_sample=False, temperature=None,
                               top_p=None, top_k=None, pad_token_id=_tok.eos_token_id)
    return _tok.decode(out[0, ids["input_ids"].shape[1]:], skip_special_tokens=True)


def es_lectura(sql: str) -> bool:
    return bool(re.match(r"^\s*(SELECT|WITH)\b", sql, re.I))


def generar_sql(esquema: str, pregunta: str, ejecutar=None) -> str:
    t0 = time.time()
    msgs = mensajes(esquema, pregunta)
    sql = extraer_sql(_generar(msgs))
    if ejecutar is None or not AUTOCORRECCION:
        return sql
    for _ in range(MAX_CORRECCIONES + 1):
        if not es_lectura(sql):
            error = "La respuesta debe ser una única consulta SELECT o WITH ... SELECT."
        else:
            try:
                r = ejecutar(sql)
            except Exception as e:  # el evaluador no debe tumbar la generación
                return sql
            if r.get("ok"):
                return sql
            error = r.get("error") or "error desconocido"
        if time.time() - t0 > TIEMPO_MAX:
            break
        msgs = msgs + [
            {"role": "assistant", "content": sql},
            {"role": "user", "content": f"La consulta falló en MySQL con este error:\n{error}\n"
                                        "Corrígela. Responde solo con la consulta SQL corregida."},
        ]
        sql = extraer_sql(_generar(msgs))
    return sql


if os.environ.get("TSQL_NO_CARGAR") != "1":
    cargar()
