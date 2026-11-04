"""Authorized v2 pilot: fixed three epochs, fit/tune only, no score-based gate."""
import argparse
import json
from pathlib import Path
import time
import traceback

import numpy as np
import torch
import torch.nn.functional as F

from research.task2_scope_local_v1.chunking import digest
from research.task2_scope_local_v1.prepare import write_json
from .common import (append_log, arrays, bag_targets, cfg, epoch_order, accumulation_groups,
    load_model, loss_for, now, optimizer, parameter_digest, predict, read_guard, reset_seed,
    restore_checkpoint, save_checkpoint, setup)
from .metrics import better, evaluate


def train_group(model, opt, sched, plans, gold, method):
    model.train(); opt.zero_grad(set_to_none=True)
    t0 = time.perf_counter()
    stats = dict(bags=len(plans), microbatches=len(plans), windows=sum(len(p.windows) for p in plans),
        event_loss_sum=0., article_loss_sum=0., total_loss_sum=0., positive_bce_sum=0., negative_bce_sum=0.,
        positive_cells=0, negative_cells=0, forward_seconds=0., backward_seconds=0.)
    for plan in plans:
        targets = bag_targets([plan], gold, device="cuda")
        torch.cuda.synchronize(); t = time.perf_counter()
        with torch.autocast("cuda", dtype=torch.bfloat16):
            a, e = model([plan]); losses = loss_for(method, a, e, targets)
        torch.cuda.synchronize(); stats["forward_seconds"] += time.perf_counter()-t
        t = time.perf_counter()
        (losses["loss"] / len(plans)).backward()
        torch.cuda.synchronize(); stats["backward_seconds"] += time.perf_counter()-t
        with torch.no_grad():
            y = targets["child_targets"].bool()
            cells = F.binary_cross_entropy_with_logits(e.float(), y.float(), reduction="none")
            stats["positive_bce_sum"] += float(cells[y].sum())
            stats["negative_bce_sum"] += float(cells[~y].sum())
            stats["positive_cells"] += int(y.sum()); stats["negative_cells"] += int((~y).sum())
        for name in ("event", "article", "total"):
            stats[name + "_loss_sum"] += float(losses["loss" if name == "total" else name + "_loss"].detach())
    torch.cuda.synchronize(); t = time.perf_counter()
    norm = torch.nn.utils.clip_grad_norm_(model.parameters(), cfg()["max_grad_norm"], error_if_nonfinite=True)
    stats["gradient_norm_before_clip"] = float(norm)
    stats["lr_used"] = [g["lr"] for g in opt.param_groups]
    opt.step(); sched.step(); torch.cuda.synchronize()
    stats.update(optimizer_seconds=time.perf_counter()-t, group_seconds=time.perf_counter()-t0,
        lr_next=sched.get_last_lr(), gradients_finite=True,
        peak_allocated_bytes=torch.cuda.max_memory_allocated(), peak_reserved_bytes=torch.cuda.max_memory_reserved())
    return stats


def execute(args):
    read_guard(); run = args.run.resolve()
    frozen, data, gold = setup(run)
    receipt = json.loads((run / "preflight/receipt.json").read_text())
    if not receipt["passed"] or receipt["binding"] != frozen["binding"]:
        raise RuntimeError("Matching new input/trainer GPU receipt required")
    out = args.out.resolve() if args.out else run / args.method
    out.mkdir(parents=True, exist_ok=False)
    reset_seed(); model = load_model(Path(frozen["model_dir"]))
    initial = parameter_digest(model)
    if initial != receipt["initial_weights_sha256"]:
        raise RuntimeError("Initial parameters differ")
    opt, sched = optimizer(model, len(data["fit"]))
    best = None; step = 0; start_epoch = 1; history = []; epoch_sources = {}
    if args.resume:
        state = restore_checkpoint(args.resume, model, opt, sched, frozen["binding"], args.method)
        start_epoch = state["epoch"]+1; step = state["optimizer_steps"]; best = state["best_selection"]
        history = state["history"]
        epoch_sources = state["epoch_sources"]
        if state["initial_weights_sha256"] != initial or not 1 <= state["epoch"] < 3:
            raise RuntimeError("Invalid epoch resume point")
    write_json(out / "run_manifest.json", dict(method=args.method, frozen=frozen,
        effective_config=dict(cfg(), **cfg()["methods"][args.method]), initial_weights_sha256=initial,
        resume_from=str(args.resume) if args.resume else None, started=now(),
        expected_bags_per_epoch=2650, expected_updates_per_epoch=166, expected_total_updates=498))
    all_started = time.perf_counter()
    measured = []; completed_bags = (start_epoch-1)*len(data["fit"])
    first_update_checked = bool(args.resume)
    for epoch in range(start_epoch, 4):
        torch.cuda.reset_peak_memory_stats()
        epoch_started = time.perf_counter()
        order = epoch_order(len(data["fit"]), epoch)
        groups = accumulation_groups(order, 16); rows = []
        for gi, indices in enumerate(groups, 1):
            before = parameter_digest(model) if step == 1 and not first_update_checked else None
            stats = train_group(model, opt, sched, [data["fit"][i] for i in indices], gold, args.method)
            step += 1; completed_bags += len(indices)
            if before:
                after = parameter_digest(model)
                if before == after: raise RuntimeError("No real parameter change at first nonzero-LR update")
                write_json(out / "actual_update.json", dict(optimizer_step=step, lr=stats["lr_used"],
                    before_sha256=before, after_sha256=after, changed=True))
                first_update_checked = True
            row = dict(time=now(), method=args.method, epoch=epoch, group=gi, optimizer_step=step,
                epoch_bags=sum(len(x) for x in groups[:gi]), total_bags=completed_bags, **stats)
            rows.append(row)
            # Exclude all 50 LR warmup groups too; every later sample follows the
            # actual training distribution, including optimizer update cost.
            if step > 50: measured.append(stats)
            if sum(x["bags"] for x in measured) >= 100:
                n = sum(x["bags"] for x in measured); seconds = sum(x["group_seconds"] for x in measured)
                overhead = np.mean([h["tune_and_metrics_seconds"]+h.get("checkpoint_seconds", 0.) for h in history]) if history else None
                row["throughput"] = dict(post_warmup_bags=n, bags_per_second=n/seconds,
                    measured_seconds=seconds, remaining_training_seconds=(7950-completed_bags)*seconds/n,
                    validation_checkpoint_seconds_per_epoch=overhead,
                    remaining_total_seconds=(7950-completed_bags)*seconds/n+(4-epoch)*overhead if overhead is not None else None)
            append_log(out / "training.jsonl", row)
        train_seconds = time.perf_counter()-epoch_started
        tune_started = time.perf_counter(); predictions = predict(model, data["tune"])
        scores, targets, keys, _ = arrays(predictions, gold)
        metrics, curve = evaluate(scores, targets)
        write_json(out / f"tune_scores_epoch_{epoch}.json", predictions)
        np.savez_compressed(out / f"pr_curve_epoch_{epoch}.npz", **curve)
        selection = dict(epoch=epoch, **metrics["selected"])
        epoch_sources[str(epoch)] = str(out)
        if better(selection, best): best = selection
        epoch_row = dict(method=args.method, epoch=epoch, optimizer_steps=step, epoch_updates=len(groups),
            bags=sum(r["bags"] for r in rows), microbatches=sum(r["microbatches"] for r in rows),
            windows=sum(r["windows"] for r in rows), order_sha256=digest(order),
            ordered_bag_keys_sha256=digest([data["fit"][i].key for i in order]),
            fit_event_loss=sum(r["event_loss_sum"] for r in rows)/2650,
            fit_article_loss=sum(r["article_loss_sum"] for r in rows)/2650,
            fit_total_loss=sum(r["total_loss_sum"] for r in rows)/2650,
            fit_positive_bce=sum(r["positive_bce_sum"] for r in rows)/sum(r["positive_cells"] for r in rows),
            fit_negative_bce=sum(r["negative_bce_sum"] for r in rows)/sum(r["negative_cells"] for r in rows),
            fit_positive_cells=sum(r["positive_cells"] for r in rows),
            fit_loss_interpretation="training-mode aggregate over changing parameters; bag-mean event/article, cell-mean positive/negative BCE; T article BCE logged but weight zero",
            tune=metrics, best_selection=best, lr_next=sched.get_last_lr(),
            forward_seconds=sum(r["forward_seconds"] for r in rows), backward_seconds=sum(r["backward_seconds"] for r in rows),
            optimizer_seconds=sum(r["optimizer_seconds"] for r in rows), train_seconds=train_seconds,
            tune_and_metrics_seconds=time.perf_counter()-tune_started,
            peak_allocated_bytes=torch.cuda.max_memory_allocated(), peak_reserved_bytes=torch.cuda.max_memory_reserved(), gradients_finite=True)
        if epoch_row["bags"] != 2650 or epoch_row["fit_positive_cells"] != 14624 or step != 166*epoch:
            raise RuntimeError("Training coverage or update counts differ")
        t = time.perf_counter()
        save_checkpoint(out / f"epoch_{epoch}.pt", model, opt, sched, binding=frozen["binding"],
            method=args.method, epoch=epoch, optimizer_steps=step, best_selection=best,
            history=history+[epoch_row], epoch_boundary=True, initial_weights_sha256=initial,
            epoch_sources=epoch_sources,
            source_run=str(out), original_pilot=str(run), acceptance_only=False)
        epoch_row["checkpoint_seconds"] = time.perf_counter()-t
        epoch_row["elapsed_seconds"] = time.perf_counter()-epoch_started
        history.append(epoch_row)
        write_json(out / f"epoch_{epoch}.json", epoch_row)
        append_log(out / "epochs.jsonl", epoch_row)
    write_json(out / "selection.json", dict(method=args.method, selected=best,
        initial_weights_sha256=initial, completed_epochs=3, optimizer_steps=step,
        processed_bags=7950, elapsed_seconds=time.perf_counter()-all_started,
        epoch_sources=epoch_sources,
        holdout_dev_test_evaluated=False, history=history))
    print(json.dumps(dict(completed=args.method, selection=best, time=now())), flush=True)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--run", type=Path, required=True)
    p.add_argument("--method", choices=["T", "J", "S"], required=True)
    p.add_argument("--resume", type=Path)
    p.add_argument("--out", type=Path)
    a = p.parse_args()
    if a.resume and not a.out: p.error("Resume requires a NEW --out directory; history is never overwritten")
    try:
        execute(a)
    except Exception:
        failure = a.run / f"failure_{a.method}_{time.time_ns()}.json"
        write_json(failure, dict(time=now(), traceback=traceback.format_exc(),
            resume="Use last complete epoch checkpoint with --resume PATH --out NEW_DIR; no mid-accumulation resume"))
        raise


if __name__ == "__main__": main()
