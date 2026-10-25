"""Genera las figuras del reporte a partir de checkpoints/*/metricas.json y resultados/resumen.json."""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

BASE = Path(__file__).resolve().parent.parent
RES = BASE / "resultados"
COLORES = {"lora_attn": "#2a6fdb", "lora_all": "#e0572b"}
ORDEN = ["baseline", "baseline_autocorreccion", "baseline_fp16_autocorreccion", "lora_attn", "lora_all",
         "lora_all_autocorreccion", "final", "final_autocorreccion", "final_fp16_autocorreccion"]
ERRORES = ["baseline", "lora_attn", "lora_all", "final", "final_fp16_autocorreccion"]


def curvas_loss(colores=COLORES, archivo="curvas_loss.png", titulo="Curvas de loss: config A (atención) vs config B (atención + MLP)"):
    fig, ax = plt.subplots(figsize=(8, 4.5))
    for nombre, color in colores.items():
        ruta = RES / f"metricas_{nombre}.json"
        if not ruta.exists():
            continue
        h = json.loads(ruta.read_text(encoding="utf8"))["historial"]
        tr = [(x["step"], x["loss"]) for x in h if "loss" in x]
        ev = [(x["step"], x["eval_loss"]) for x in h if "eval_loss" in x]
        ax.plot(*zip(*tr), color=color, alpha=0.45, lw=1, label=f"{nombre} train")
        ax.plot(*zip(*ev), color=color, lw=2.2, marker="o", ms=3, label=f"{nombre} dev")
    ax.set_xlabel("paso de optimización")
    ax.set_ylabel("loss (solo tokens de la SQL)")
    ax.set_ylim(0, None)
    ax.grid(alpha=0.25)
    ax.legend()
    ax.set_title(titulo)
    fig.tight_layout()
    fig.savefig(RES / archivo, dpi=150)


def comparacion_ex():
    r = json.loads((RES / "resumen.json").read_text(encoding="utf8"))
    nombres = [n for n in ORDEN if n in r]
    vals = [r[n]["EX_ponderada"] for n in nombres]
    fig, ax = plt.subplots(figsize=(8, 4.6))
    b = ax.barh(nombres, vals, color="#2a6fdb")
    ax.bar_label(b, fmt="%.3f", padding=3)
    ax.axvline(0.70, color="#999", ls="--", lw=1)
    ax.text(0.70, -0.6, " meta 0.70", color="#777", fontsize=9)
    ax.set_xlim(0, 1)
    ax.invert_yaxis()
    ax.set_xlabel("EX ponderada (validación propia, 40 preguntas)")
    ax.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(RES / "ex_comparacion.png", dpi=150)


def errores():
    r = json.loads((RES / "resumen.json").read_text(encoding="utf8"))
    cats = ["sintaxis", "columna o tabla inexistente", "JOIN", "agregacion", "filtro", "resultado distinto"]
    nombres = [n for n in ERRORES if n in r]
    fig, ax = plt.subplots(figsize=(9, 4.5))
    ancho = 0.8 / len(nombres)
    for i, n in enumerate(nombres):
        ax.bar([j + i * ancho for j in range(len(cats))], [r[n]["errores_por_categoria"].get(c, 0) for c in cats],
               width=ancho, label=n)
    ax.set_xticks([j + 0.4 - ancho / 2 for j in range(len(cats))], cats, rotation=15)
    ax.set_ylabel("preguntas falladas")
    ax.legend(fontsize=8)
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(RES / "errores_categoria.png", dpi=150)


if __name__ == "__main__":
    curvas_loss()
    curvas_loss({"lora_final": "#2e9e5b"}, "curva_final.png", "Modelo final: config B, 18 esquemas propios, 2 épocas")
    comparacion_ex()
    errores()
    print("figuras en", RES)
