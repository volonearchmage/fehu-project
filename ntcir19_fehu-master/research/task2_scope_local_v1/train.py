"""Explicit CUDA-only future entry point. Default action is offline validation.

No paid API, environment installation, automatic download, or CPU fallback.
The current user authorization does not permit invoking --execute.
"""
import argparse
import datetime
import hashlib
import json
import math
from pathlib import Path
import random
import time

import torch

from .build_chunk_cache import PACKAGE, read_cache
from .chunking import digest, validate_windows
from .chunk_model import ChunkedScopeModel, bag_targets, final_probabilities
from .data import load_json, sha256
from .losses import scope_loss
from .prepare import write_json


def configuration():
    return load_json(PACKAGE / "training_v1.json")


def static_check(cache_dir, supervision_dir, model_dir):
    manifest = load_json(cache_dir / "manifest.json")
    config = configuration()
    if manifest["config_sha256"] != sha256(PACKAGE / "chunking_v1.json") or manifest["tokenizer_lock_sha256"] != sha256(PACKAGE / "tokenizer_lock.json"):
        raise ValueError("Frozen cache configuration mismatch")
    for name, expected in manifest["implementation_sha256"].items():
        if sha256(PACKAGE / name) != expected:
            raise ValueError("Input implementation changed; rebuild cache")
    provenance = load_json(supervision_dir / "audit.json")
    if provenance["split_sha256"] != manifest["source_sha256"]["docs/2026-11-03_Task2_组会准备/evidence/grouped_train_split.json"]:
        raise ValueError("Input/supervision split differs")
    for part in ("fit", "tune"):
        row = manifest["partitions"][part]
        if sha256(cache_dir / row["cache"]) != row["sha256"]:
            raise ValueError("Input cache changed")
        name = f"{part}.supervision.jsonl"
        if sha256(supervision_dir / name) != provenance["artifact_sha256"][name]:
            raise ValueError("Supervision cache changed")
    model_lock = load_json(PACKAGE / "model_lock.json")
    if config["revision"] != model_lock["revision"]:
        raise ValueError("Model revision differs")
    missing = []
    for name, record in model_lock["files"].items():
        if not (model_dir / name).is_file():
            missing.append(str(model_dir / name))
        elif sha256(model_dir / name) != record["sha256"]:
            raise ValueError(f"Pretrained model file hash mismatch: {name}")
    return dict(schema="fehu-preflight-binding-v1", cache_manifest_sha256=sha256(cache_dir / "manifest.json"),
        training_config_sha256=sha256(PACKAGE / "training_v1.json"), model_lock_sha256=sha256(PACKAGE / "model_lock.json"),
        implementation_sha256={n: sha256(PACKAGE / n) for n in ("train.py", "chunk_model.py", "losses.py", "gpu_preflight.py")},
        missing_model_files=missing, config=config, gpu_checked=False)


def load_training_data(cache_dir, supervision_dir):
    manifest = load_json(cache_dir / "manifest.json")
    datasets, supervision = {}, {}
    for part in ("fit", "tune"):
        info = manifest["partitions"][part]
        datasets[part] = read_cache(cache_dir / info["cache"], info["sha256"])
        for p in datasets[part]: validate_windows(p)
        labels = {}
        with (supervision_dir / f"{part}.supervision.jsonl").open() as f:
            for line in f:
                row = json.loads(line); key = (row["guid"], row["actor_id"])
                if key in labels: raise ValueError("Duplicate supervision bag")
                labels[key] = row
        if set(labels) != {p.key for p in datasets[part]}:
            raise ValueError("Supervision coverage differs")
        for p in datasets[part]: bag_targets([p], labels)
        supervision.update(labels)
    return datasets, supervision


def load_model(model_dir, *, device="cuda"):
    from transformers import AutoModel
    cfg = configuration()
    torch.manual_seed(cfg["seed"])
    # Local path and token=False prevent authentication/cache credential lookup.
    encoder, info = AutoModel.from_pretrained(str(model_dir), local_files_only=True,
        token=False, trust_remote_code=False, attn_implementation=cfg["attention"], dtype=torch.float32,
        output_loading_info=True)
    if info.get("missing_keys") or info.get("mismatched_keys") or info.get("error_msgs"):
        raise RuntimeError(f"Pretrained encoder did not load completely: {info}")
    model = ChunkedScopeModel(encoder, encoder.config.hidden_size, checkpoint_windows=cfg["checkpoint_windows"])
    return model.to(device)


def parameter_digest(model):
    h = hashlib.sha256()
    for name, tensor in sorted(model.state_dict().items()):
        h.update(name.encode()); h.update(tensor.detach().cpu().contiguous().numpy().tobytes())
    return h.hexdigest()


def epoch_order(count, epoch, seed=11):
    return torch.randperm(count, generator=torch.Generator().manual_seed(seed + epoch)).tolist()


def accumulation_groups(order, effective_batch):
    return [order[i:i+effective_batch] for i in range(0, len(order), effective_batch)]


def choose_threshold(probabilities, targets):
    if probabilities.shape != targets.shape or not torch.isfinite(probabilities).all():
        raise ValueError("Invalid tune scores")
    best = None
    grid = configuration()["threshold_grid"]
    for percent in range(grid["start_percent"], grid["end_percent"] + 1, grid["step_percent"]):
        threshold = percent / 100
        pred, gold = probabilities >= threshold, targets.bool()
        tp = int((pred & gold).sum()); fp = int((pred & ~gold).sum()); fn = int((~pred & gold).sum())
        f1 = 2 * tp / (2 * tp + fp + fn) if tp + fp + fn else 0.
        row = dict(threshold=threshold, micro_f1=f1, tp=tp, fp=fp, fn=fn)
        if best is None or (f1, threshold) > (best["micro_f1"], best["threshold"]): best = row
    return best


def better_checkpoint(candidate, current):
    if current is None: return True
    return (candidate["micro_f1"], candidate["threshold"], -candidate["epoch"]) > (current["micro_f1"], current["threshold"], -current["epoch"])


def cuda_gate(receipt, binding):
    if binding["missing_model_files"]:
        raise RuntimeError("Pinned model weights/config are missing; automatic download is disabled")
    if not receipt or not receipt.is_file():
        raise RuntimeError("Completed GPU preflight receipt is required before training")
    evidence = load_json(receipt)
    if not evidence.get("passed") or evidence.get("binding") != binding:
        raise RuntimeError("GPU preflight failed or does not match these exact inputs/code/config")
    if evidence.get("boot_id") != Path("/proc/sys/kernel/random/boot_id").read_text().strip():
        raise RuntimeError("GPU receipt is from another boot")
    if not torch.cuda.is_available() or not torch.cuda.is_bf16_supported():
        raise RuntimeError("CUDA/BF16 unavailable; CPU fallback is forbidden")


def execute(args, binding):
    cuda_gate(args.gpu_ready_report, binding)
    cfg = binding["config"]
    args.out.mkdir(parents=True, exist_ok=False)
    data, gold = load_training_data(args.cache_dir, args.supervision_dir)
    random.seed(cfg["seed"]); torch.manual_seed(cfg["seed"])
    model = load_model(args.model_dir)
    initial_hash = parameter_digest(model)
    if initial_hash != load_json(args.gpu_ready_report)["initial_weights_sha256"]:
        raise RuntimeError("Initial parameters differ from the verified GPU preflight")
    write_json(args.out / "run_manifest.json", dict(method=args.method, binding=binding,
        initial_weights_sha256=initial_hash, started=datetime.datetime.now().astimezone().isoformat()))
    optim = torch.optim.AdamW([dict(params=model.encoder.parameters(), lr=cfg["encoder_lr"]),
                              dict(params=model.head.parameters(), lr=cfg["head_lr"])], weight_decay=cfg["weight_decay"])
    steps = math.ceil(len(data["fit"]) / cfg["effective_batch_bags"]) * cfg["epochs"]
    warmup = math.ceil(steps * cfg["warmup_fraction"])
    def factor(step):
        return step / max(1, warmup) if step < warmup else max(0., (steps-step) / max(1, steps-warmup))
    scheduler = torch.optim.lr_scheduler.LambdaLR(optim, factor)
    best = None; optimizer_steps = 0
    for epoch in range(1, cfg["epochs"] + 1):
        model.train(); started = time.monotonic(); total_loss = 0.
        order = epoch_order(len(data["fit"]), epoch, cfg["seed"])
        for group in accumulation_groups(order, cfg["effective_batch_bags"]):
            optim.zero_grad(set_to_none=True)
            for index in group:
                plan = data["fit"][index]
                with torch.autocast("cuda", dtype=torch.bfloat16):
                    a, c = model([plan])
                    result = scope_loss(a, c, mode=args.method, article_weight=cfg["article_weight"],
                                        **bag_targets([plan], gold, device="cuda"))
                # Tail group uses its actual original-bag count, not always 16.
                (result["loss"] / len(group)).backward()
                total_loss += float(result["loss"].detach())
            torch.nn.utils.clip_grad_norm_(model.parameters(), cfg["max_grad_norm"], error_if_nonfinite=True)
            optim.step(); scheduler.step(); optimizer_steps += 1
        model.eval(); scores = []; p_scores = []; targets = []; keyed_scores = []
        with torch.no_grad():
            for plan in data["tune"]:
                with torch.autocast("cuda", dtype=torch.bfloat16): a, c = model([plan])
                event_prob = final_probabilities(a, c, args.method)[0].cpu()
                scores.append(event_prob)
                p_scores.append(final_probabilities(a, c, "P")[0].cpu())
                targets.append(bag_targets([plan], gold)["child_targets"][0])
                keyed_scores.append(dict(guid=plan.key[0], actor_id=plan.key[1], event_ids=plan.event_ids,
                    article_probability=a.float().sigmoid()[0].cpu().tolist(), event_probability=event_prob.tolist()))
        chosen = dict(epoch=epoch, **choose_threshold(torch.cat(scores), torch.cat(targets)))
        row = dict(epoch=epoch, method=args.method, fit_loss=total_loss/len(data["fit"]), tune=chosen,
            optimizer_steps=optimizer_steps, order_sha256=digest(order), elapsed_seconds=time.monotonic()-started,
            peak_cuda_bytes=torch.cuda.max_memory_allocated())
        write_json(args.out / f"epoch_{epoch}.json", row)
        write_json(args.out / f"tune_scores_epoch_{epoch}.json", keyed_scores)
        # Epoch checkpoints are immutable; interruption restarts from a preserved
        # run in a future resume implementation, never silently overwrites it.
        torch.save(dict(model=model.state_dict(), optimizer=optim.state_dict(), scheduler=scheduler.state_dict(),
            epoch=epoch, optimizer_steps=optimizer_steps, torch_rng=torch.get_rng_state(),
            cuda_rng=torch.cuda.get_rng_state_all(), selection=chosen, binding=binding), args.out / f"epoch_{epoch}.pt")
        if better_checkpoint(chosen, best):
            best = chosen
            if args.method == "J":
                best = dict(best, P_tune=choose_threshold(torch.cat(p_scores), torch.cat(targets)))
    write_json(args.out / "selection.json", dict(method=args.method, selected=best,
        initial_weights_sha256=initial_hash, holdout_dev_test_evaluated=False, automatic_extension=False))


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--method", choices=["J", "S"], required=True)
    p.add_argument("--cache-dir", type=Path, required=True)
    p.add_argument("--supervision-dir", type=Path, required=True)
    p.add_argument("--model-dir", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--gpu-ready-report", type=Path)
    p.add_argument("--execute", action="store_true", help="Future authorized GPU training; requires matching GPU preflight receipt")
    return p


if __name__ == "__main__":
    args = parser().parse_args()
    binding = static_check(args.cache_dir, args.supervision_dir, args.model_dir)
    if not args.execute:
        print(json.dumps(dict(action="offline_static_check_only", **binding), indent=2))
    else:
        execute(args, binding)
