"""Shared binding, data, optimization and explicit epoch checkpoint state."""
import importlib.metadata
from functools import lru_cache
import json
import math
import os
from pathlib import Path
import random
import sys
import time

import numpy as np
import torch

from research.task2_scope_local_v1.data import load_json, sha256
from research.task2_scope_local_v1.prepare import PROJECT, write_json
from research.task2_scope_local_v1.train import load_model, load_training_data, parameter_digest, epoch_order, accumulation_groups
from research.task2_scope_local_v1.chunk_model import bag_targets
from research.task2_scope_local_v1.losses import scope_loss
from .inputs import PACKAGE, V1


def read_guard():
    """Deny raw gold and any held-out cache reads in pilot entry points."""
    def hook(event, args):
        if event != "open" or not isinstance(args[0], (str, bytes, os.PathLike)):
            return
        p = os.fsdecode(args[0]).replace("\\", "/")
        if "/dataset/gold_labels/" in p or any(x in p for x in (
                "holdout.supervision", "dev.supervision", "test.supervision", "holdout.chunks", "dev.chunks", "test2.chunks")):
            raise RuntimeError("Pilot forbidden gold/cache read: " + p)
    sys.addaudithook(hook)


def now():
    import datetime
    return datetime.datetime.now().astimezone().isoformat()


@lru_cache(maxsize=1)
def cfg():
    return load_json(PACKAGE / "config.json")


def make_binding(run, supervision_dir, model_dir):
    manifest = load_json(run / "input_cache/manifest.json")
    config = cfg()
    audit = load_json(supervision_dir / "audit.json")
    if audit["split_sha256"] != manifest["source_sha256"]["docs/2026-11-03_Task2_组会准备/evidence/grouped_train_split.json"]:
        raise ValueError("Input and supervision split mismatch")
    files = [PACKAGE / n for n in ("config.json", "inputs.py", "common.py", "metrics.py", "train.py", "preflight.py", "score.py")]
    files += [V1 / n for n in ("data.py", "tokenization.py", "chunking.py", "chunk_model.py", "model.py", "losses.py", "train.py", "build_chunk_cache.py", "prepare.py", "model_lock.json", "tokenizer_lock.json", "training_v1.json")]
    files += [PROJECT / "research/task2_prompt_baseline_v1/evaluator/official_cli.py"]
    for part in ("fit", "tune"):
        p = supervision_dir / f"{part}.supervision.jsonl"
        if sha256(p) != audit["artifact_sha256"][p.name]:
            raise ValueError("Supervision changed")
        files.append(p)
        p = run / "input_cache" / manifest["partitions"][part]["cache"]
        if sha256(p) != manifest["partitions"][part]["sha256"]:
            raise ValueError("Input cache changed")
        files.append(p)
    for n, h in manifest["source_sha256"].items():
        if sha256(PROJECT / n) != h:
            raise ValueError("Source input or split changed")
    if manifest["config_sha256"] != sha256(PACKAGE / "config.json") or manifest["input_implementation_sha256"] != sha256(PACKAGE / "inputs.py"):
        raise ValueError("V2 input config/code changed")
    lock = load_json(V1 / "model_lock.json")
    if lock["revision"] != config["revision"]:
        raise ValueError("Pinned revision differs")
    for n, r in lock["files"].items():
        if sha256(model_dir / n) != r["sha256"]:
            raise ValueError("Pinned pretrained model changed")
    return dict(schema="pilot-v2-binding", protocol_commit=config["protocol_commit"], config=config,
        input_manifest_sha256=sha256(run / "input_cache/manifest.json"),
        files_sha256={str(p.relative_to(PROJECT)): sha256(p) for p in files},
        model_files_sha256={n: r["sha256"] for n, r in lock["files"].items()},
        python=sys.executable, versions={n: importlib.metadata.version(n) for n in ("torch", "transformers", "tokenizers", "numpy", "scikit-learn")},
        cuda_build=torch.version.cuda, boot_id=Path("/proc/sys/kernel/random/boot_id").read_text().strip())


def setup(run):
    # Process-local numerical reproducibility, not an environment installation
    # or system setting. Set before any CUDA context/work is created.
    os.environ["CUBLAS_WORKSPACE_CONFIG"] = cfg()["cublas_workspace_config"]
    torch.use_deterministic_algorithms(cfg()["deterministic_algorithms"])
    f = load_json(run / "frozen.json")
    current = make_binding(run, Path(f["supervision_dir"]), Path(f["model_dir"]))
    if current != f["binding"]:
        raise RuntimeError("Frozen code/config/input/model/environment binding changed")
    if not torch.cuda.is_available() or not torch.cuda.is_bf16_supported():
        raise RuntimeError("CUDA/BF16 unavailable; no CPU fallback")
    data, gold = load_training_data(run / "input_cache", Path(f["supervision_dir"]))
    if (len(data["fit"]), len(data["tune"])) != (2650, 398):
        raise ValueError("Unexpected complete partition bag counts")
    return f, data, gold


def reset_seed():
    random.seed(11); np.random.seed(11); torch.manual_seed(11); torch.cuda.manual_seed_all(11)


def optimizer(model, fit_count):
    c = cfg()
    opt = torch.optim.AdamW([dict(params=model.encoder.parameters(), lr=c["encoder_lr"]),
                            dict(params=model.head.parameters(), lr=c["head_lr"])], weight_decay=c["weight_decay"])
    total = math.ceil(fit_count / c["effective_batch_bags"]) * c["epochs"]
    warmup = math.ceil(total * c["warmup_fraction"])
    def factor(step):
        return step/max(1, warmup) if step < warmup else max(0., (total-step)/max(1, total-warmup))
    sched = torch.optim.lr_scheduler.LambdaLR(opt, factor)
    return opt, sched


def loss_for(method, article, events, targets):
    return scope_loss(article, events, **targets, **cfg()["methods"][method])


def rng():
    return dict(python=random.getstate(), numpy=np.random.get_state(), torch=torch.get_rng_state(), cuda=torch.cuda.get_rng_state_all())


def restore_rng(state):
    random.setstate(state["python"]); np.random.set_state(state["numpy"])
    torch.set_rng_state(state["torch"]); torch.cuda.set_rng_state_all(state["cuda"])


def save_checkpoint(path, model, opt, sched, **metadata):
    state = dict(model=model.state_dict(), optimizer=opt.state_dict(), scheduler=sched.state_dict(), rng=rng(), **metadata)
    with path.open("xb") as f:
        torch.save(state, f); f.flush(); os.fsync(f.fileno())


def restore_checkpoint(path, model, opt, sched, binding, method, *, acceptance=False):
    state = torch.load(path, map_location="cpu", weights_only=False)
    if state["binding"] != binding or state["method"] != method or state.get("acceptance_only", False) != acceptance:
        raise ValueError("Checkpoint binding/method/purpose differs")
    if not state.get("epoch_boundary"):
        raise ValueError("Only explicit complete-epoch boundary restore is supported")
    if not acceptance and state["optimizer_steps"] != state["epoch"] * 166:
        raise ValueError("Checkpoint is not a complete 2650-bag epoch")
    model.load_state_dict(state["model"], strict=True); opt.load_state_dict(state["optimizer"])
    sched.load_state_dict(state["scheduler"]); restore_rng(state["rng"])
    return {k: v for k, v in state.items() if k not in {"model", "optimizer", "scheduler", "rng"}}


@torch.no_grad()
def predict(model, plans):
    """Input-only prediction; no supervision parameter and no gold access."""
    model.eval(); rows = []
    for plan in plans:
        with torch.autocast("cuda", dtype=torch.bfloat16):
            a, e = model([plan])
        ap = a[0].float().sigmoid().cpu().numpy()
        ep = e[0].float().sigmoid().cpu().numpy()
        if not np.isfinite(ap).all() or not np.isfinite(ep).all() or ep.shape != (len(plan.event_ids), 108):
            raise RuntimeError("Inference failed: never export as empty")
        rows.append(dict(guid=plan.key[0], actor_id=plan.key[1], event_ids=list(plan.event_ids),
                         article_probability=ap.tolist(), event_probability=ep.tolist()))
    torch.cuda.synchronize()
    return rows


def arrays(rows, gold, *, product=False):
    scores, targets, keys, articles = [], [], [], []
    for r in rows:
        key = r["guid"], r["actor_id"]
        g = gold[key]
        if r["event_ids"] != g["event_ids"]:
            raise ValueError("Score/gold candidate order differs")
        a = np.asarray(r["article_probability"], dtype=np.float32)
        e = np.asarray(r["event_probability"], dtype=np.float32)
        scores.append(e*a[None, :] if product else e)
        y = np.zeros_like(e, dtype=bool)
        for i, indices in enumerate(g["children"]): y[i, indices] = True
        targets.append(y)
        keys.extend((key[0], key[1], event) for event in r["event_ids"])
        articles.extend([a] * len(e))
    if len(keys) != len(set(keys)):
        raise ValueError("Duplicate candidate scores")
    return np.concatenate(scores), np.concatenate(targets), keys, np.asarray(articles)


def append_log(path, record):
    with path.open("a") as f:
        f.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n"); f.flush()
    print(json.dumps(record, ensure_ascii=False, allow_nan=False), flush=True)
