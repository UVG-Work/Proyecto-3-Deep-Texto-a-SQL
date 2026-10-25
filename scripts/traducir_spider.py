"""Traduce al español las preguntas de Spider (ya convertidas a MySQL) con Helsinki-NLP/opus-mt-en-es.

Los literales de la SQL que aparecen en la pregunta se protegen con marcadores (XV0, XV1...) para que
no se traduzcan ('Switzerland' debe seguir siendo 'Switzerland', porque así está en los datos).
También traduce los nombres "naturales" de columnas de tables.json, usados como COMMENT en la mitad
de las bases (ver construir_dataset.py).

Uso: python scripts/traducir_spider.py C:/spider_dl/spider_data
"""
import hashlib
import json
import re
import sys
from pathlib import Path

import torch
from transformers import MarianMTModel, MarianTokenizer

RAIZ = Path(sys.argv[1])
INTER = Path(__file__).parent.parent / "datos" / "intermedio"
MODELO = "Helsinki-NLP/opus-mt-en-es"

tok = MarianTokenizer.from_pretrained(MODELO)
mt = MarianMTModel.from_pretrained(MODELO).cuda().eval().half()


def traducir(textos, lote=64):
    out = []
    for i in range(0, len(textos), lote):
        b = tok(textos[i:i + lote], return_tensors="pt", padding=True, truncation=True, max_length=256).to("cuda")
        with torch.no_grad():
            g = mt.generate(**b, num_beams=4, max_new_tokens=160)
        out += tok.batch_decode(g, skip_special_tokens=True)
        print(f"  {len(out)}/{len(textos)}", end="\r", flush=True)
    print()
    return out


def proteger(pregunta, sql):
    literales = sorted(set(re.findall(r"'((?:[^']|'')+)'", sql)), key=len, reverse=True)
    mapa = {}
    for lit in literales:
        lit_limpio = lit.replace("%", "").strip()
        if len(lit_limpio) < 2:
            continue
        # Límites de palabra; siglas cortas (<=3) solo coinciden respetando mayúsculas.
        patron = re.compile(r"[\"']?(?<!\w)" + re.escape(lit_limpio) + r"(?!\w)[\"']?", 0 if len(lit_limpio) <= 3 else re.I)
        if patron.search(pregunta):
            marca = f"XV{len(mapa)}"
            pregunta = patron.sub(marca, pregunta, count=1)
            mapa[marca] = lit_limpio
    return pregunta, mapa


def main():
    ej = [json.loads(l) for l in open(INTER / "spider_mysql.jsonl", encoding="utf8")]
    protegidas = [proteger(re.sub(r"\s+", " ", e["question"]).strip(), e["sql"]) for e in ej]
    trad = traducir([p for p, _ in protegidas])
    perdidos = 0
    with open(INTER / "spider_es.jsonl", "w", encoding="utf8") as f:
        for e, (_, mapa), t in zip(ej, protegidas, trad):
            for marca, lit in sorted(mapa.items(), key=lambda x: -len(x[0])):
                if marca not in t:
                    perdidos += 1
                t = t.replace(marca, lit)
            e["pregunta"] = t
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    print("marcadores perdidos:", perdidos)

    # Comentarios de columnas en español para la mitad de las bases (elegidas por hash, reproducible).
    tablas = json.load(open(RAIZ / "tables.json", encoding="utf8"))
    pendientes = []
    for t in tablas:
        if int(hashlib.md5(t["db_id"].encode()).hexdigest(), 16) % 2:
            continue
        for (ti, orig), (_, nat) in zip(t["column_names_original"][1:], t["column_names"][1:]):
            pendientes.append((t["db_id"], t["table_names_original"][ti], orig, nat))
        for orig, nat in zip(t["table_names_original"], t["table_names"]):
            pendientes.append((t["db_id"], orig, None, nat))
    frases = sorted({p[3] for p in pendientes})
    trad = dict(zip(frases, traducir(frases, lote=128)))
    com = {}
    for db, tabla, col, nat in pendientes:
        com.setdefault(db, {}).setdefault(tabla, {})[col or "__tabla__"] = trad[nat].strip(" .")
    json.dump(com, open(INTER / "spider_comentarios.json", "w", encoding="utf8"), ensure_ascii=False, indent=0)
    print("bases con comentarios:", len(com))


if __name__ == "__main__":
    main()
