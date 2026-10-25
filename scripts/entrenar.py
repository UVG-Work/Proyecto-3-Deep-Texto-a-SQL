"""Fine-tuning LoRA de Qwen2.5-Coder-1.5B-Instruct para Text-to-SQL.

La pérdida se calcula solo sobre la respuesta (la SQL); el prompt (sistema + esquema + pregunta) se enmascara.
Uso:
  python scripts/entrenar.py --nombre lora_attn --modulos attn
  python scripts/entrenar.py --nombre lora_all  --modulos all
Salida: checkpoints/<nombre>/adapter, checkpoints/<nombre>/metricas.json (loss, tiempo, parámetros).
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

os.environ["TSQL_NO_CARGAR"] = "1"
BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
import torch
from datasets import Dataset
from peft import LoraConfig, get_peft_model
from transformers import (AutoModelForCausalLM, AutoTokenizer, DataCollatorForSeq2Seq, Trainer,
                          TrainingArguments, set_seed)
from solucion import CONFIG, mensajes

MODULOS = {
    "attn": ["q_proj", "k_proj", "v_proj", "o_proj"],
    "all": ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
}


class TrainerRespuesta(Trainer):
    """Calcula logits solo para los tokens de la respuesta (logits_to_keep): con 152k de vocabulario,
    los logits de todo el prompt no caben en 8 GB de VRAM. Requiere padding a la izquierda."""

    def compute_loss(self, model, inputs, return_outputs=False, num_items_in_batch=None):
        labels = inputs.pop("labels")
        k = int((labels != -100).sum(1).max()) + 1
        out = model(**inputs, logits_to_keep=k)
        logits = out.logits[:, :-1].float()
        objetivo = labels[:, -(k - 1):]
        suma = torch.nn.functional.cross_entropy(logits.reshape(-1, logits.size(-1)), objetivo.reshape(-1),
                                                 ignore_index=-100, reduction="sum")
        n = num_items_in_batch if num_items_in_batch is not None else (objetivo != -100).sum()
        loss = suma / n
        return (loss, out) if return_outputs else loss


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nombre", required=True)
    ap.add_argument("--modulos", choices=MODULOS, default="all")
    ap.add_argument("--rank", type=int, default=16)
    ap.add_argument("--alpha", type=int, default=32)
    ap.add_argument("--lr", type=float, default=2e-4)
    ap.add_argument("--epocas", type=float, default=1.0)
    ap.add_argument("--batch", type=int, default=4)
    ap.add_argument("--acum", type=int, default=4)
    ap.add_argument("--max_spider", type=int, default=5000)
    ap.add_argument("--max_len", type=int, default=2048)
    a = ap.parse_args()
    set_seed(CONFIG["semilla"])
    salida = BASE / "checkpoints" / a.nombre

    tok = AutoTokenizer.from_pretrained(CONFIG["modelo_base"])

    def tokenizar(e):
        prompt = tok.apply_chat_template(mensajes(e["esquema"], e["pregunta"]), tokenize=False, add_generation_prompt=True)
        p_ids = tok(prompt, add_special_tokens=False)["input_ids"]
        r_ids = tok(e["sql"] + "<|im_end|>\n", add_special_tokens=False)["input_ids"]
        return {"input_ids": p_ids + r_ids, "attention_mask": [1] * (len(p_ids) + len(r_ids)),
                "labels": [-100] * len(p_ids) + r_ids}

    leer = lambda f: [json.loads(l) for l in open(BASE / "datos" / f, encoding="utf8")]
    train = leer("entrenamiento.jsonl")
    if a.max_spider:  # todos los propios + los primeros N de Spider (el archivo ya viene barajado)
        spider = {id(e) for e in [e for e in train if e["fuente"] != "propio"][:a.max_spider]}
        train = [e for e in train if e["fuente"] == "propio" or id(e) in spider]
    cols = ["esquema", "pregunta", "sql"]
    ds_train = Dataset.from_list([{k: e[k] for k in cols} for e in train]).map(tokenizar, remove_columns=cols)
    ds_dev = Dataset.from_list([{k: e[k] for k in cols} for e in leer("dev_loss.jsonl")]).map(tokenizar, remove_columns=cols)
    corto = lambda e: len(e["input_ids"]) <= a.max_len
    n0 = len(ds_train)
    ds_train, ds_dev = ds_train.filter(corto), ds_dev.filter(corto)
    print(f"ejemplos de entrenamiento: {len(ds_train)} (omitidos por longitud > {a.max_len}: {n0 - len(ds_train)})")

    modelo = AutoModelForCausalLM.from_pretrained(CONFIG["modelo_base"], dtype=torch.bfloat16, device_map="cuda",
                                                  attn_implementation="sdpa")
    modelo.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
    modelo.enable_input_require_grads()
    lora = LoraConfig(r=a.rank, lora_alpha=a.alpha, lora_dropout=0.05, target_modules=MODULOS[a.modulos],
                      task_type="CAUSAL_LM")
    modelo = get_peft_model(modelo, lora)
    entrenables, total = modelo.get_nb_trainable_parameters()
    print(f"parámetros entrenables: {entrenables:,} de {total:,} ({100 * entrenables / total:.3f} %)")

    args = TrainingArguments(
        output_dir=str(salida / "tmp"), per_device_train_batch_size=a.batch, per_device_eval_batch_size=a.batch,
        gradient_accumulation_steps=a.acum, num_train_epochs=a.epocas, learning_rate=a.lr,
        lr_scheduler_type="cosine", warmup_steps=0.03, weight_decay=0.0, bf16=True, logging_steps=10,
        eval_strategy="steps", eval_steps=100, save_strategy="no", report_to=[], seed=CONFIG["semilla"],
        train_sampling_strategy="group_by_length", dataloader_num_workers=0,
    )
    tok.padding_side = "left"  # así la respuesta queda al final de todas las secuencias del lote
    trainer = TrainerRespuesta(model=modelo, args=args, train_dataset=ds_train, eval_dataset=ds_dev,
                      data_collator=DataCollatorForSeq2Seq(tok, padding=True, label_pad_token_id=-100))
    t0 = time.time()
    trainer.train()
    minutos = (time.time() - t0) / 60
    modelo.save_pretrained(salida / "adapter")
    tok.save_pretrained(salida / "adapter")
    metricas = {
        "nombre": a.nombre, "modulos": MODULOS[a.modulos], "rank": a.rank, "alpha": a.alpha, "lr": a.lr,
        "epocas": a.epocas, "batch_efectivo": a.batch * a.acum, "ejemplos": len(ds_train), "max_spider": a.max_spider, "max_len": a.max_len,
        "parametros_entrenables": entrenables, "parametros_totales": total,
        "porcentaje_entrenable": round(100 * entrenables / total, 4), "minutos_entrenamiento": round(minutos, 1),
        "gpu": torch.cuda.get_device_name(0), "vram_max_gb": round(torch.cuda.max_memory_allocated() / 1e9, 2),
        "historial": trainer.state.log_history,
    }
    (salida / "metricas.json").write_text(json.dumps(metricas, indent=2, ensure_ascii=False), encoding="utf8")
    print(f"listo en {minutos:.1f} min")


if __name__ == "__main__":
    main()
