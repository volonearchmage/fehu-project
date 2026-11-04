"""Targeted real-model evidence for changed v2 input and epoch-state restore."""
import argparse
import gc
import hashlib
import json
from pathlib import Path
import time

import numpy as np
import torch

from research.task2_scope_local_v1.prepare import write_json
from .common import (arrays, bag_targets, epoch_order, load_model, loss_for, now, optimizer,
    parameter_digest, predict, read_guard, reset_seed, restore_checkpoint, rng, save_checkpoint, setup)
from .metrics import evaluate
from .train import train_group


def state_digest(value):
    h = hashlib.sha256()
    def visit(v):
        if isinstance(v, torch.Tensor):
            h.update(str((v.dtype, tuple(v.shape))).encode()); h.update(v.detach().cpu().contiguous().numpy().tobytes())
        elif isinstance(v, np.ndarray):
            h.update(str((v.dtype, v.shape)).encode()); h.update(v.tobytes())
        elif isinstance(v, dict):
            for k in sorted(v, key=str): h.update(str(k).encode()); visit(v[k])
        elif isinstance(v, (tuple, list)):
            for x in v: visit(x)
        else: h.update(repr(v).encode())
    visit(value)
    return h.hexdigest()


def execute(run):
    read_guard(); frozen, data, gold = setup(run)
    out = run / "preflight"; out.mkdir(exist_ok=False)
    started = time.perf_counter()
    by_length = sorted(data["fit"], key=lambda p: (len(p.original.input_ids), p.key))
    selected = [by_length[0], by_length[len(by_length)//2], by_length[-1]]
    initial_hashes = {}; forward_checks = {}
    for method in ("T", "J", "S"):
        reset_seed(); model = load_model(Path(frozen["model_dir"]))
        initial_hashes[method] = parameter_digest(model)
        checks = []
        for plan in selected:
            model.train(); model.zero_grad(set_to_none=True)
            with torch.autocast("cuda", dtype=torch.bfloat16):
                a, e = model([plan]); losses = loss_for(method, a, e, bag_targets([plan], gold, device="cuda"))
            losses["loss"].backward()
            norm = torch.nn.utils.clip_grad_norm_(model.parameters(), 1., error_if_nonfinite=True)
            checks.append(dict(key=plan.key, window_tokens=[len(w.input_ids) for w in plan.windows],
                article_shape=list(a.shape), event_shape=list(e.shape), gradient_norm=float(norm),
                gradients_finite=True, event_loss=float(losses["event_loss"].detach()), article_loss=float(losses["article_loss"].detach())))
        forward_checks[method] = checks
        if method != "S":
            del model; gc.collect(); torch.cuda.empty_cache()
    if len(set(initial_hashes.values())) != 1: raise AssertionError("Initial weights differ across methods")
    # Start the acceptance update from original parameters, not the previous
    # diagnostic gradients. Exactly the formal 498-step scheduler is exercised.
    del model; gc.collect(); torch.cuda.empty_cache()
    reset_seed(); model = load_model(Path(frozen["model_dir"]))
    opt, sched = optimizer(model, len(data["fit"]))
    order = epoch_order(len(data["fit"]), 1)
    group = [data["fit"][i] for i in order[:16]]
    first = train_group(model, opt, sched, group, gold, "S")
    before = parameter_digest(model)
    second = train_group(model, opt, sched, group, gold, "S")
    after = parameter_digest(model)
    if before == after or not second["lr_used"][0] > 0:
        raise AssertionError("No actual AdamW update")
    if not all(torch.isfinite(p).all() for p in model.parameters()):
        raise AssertionError("Nonfinite updated parameters")
    # New longest semantic-only input, after real Adam state allocation.
    torch.cuda.reset_peak_memory_stats(); model.zero_grad(set_to_none=True)
    longest = by_length[-1]; t = time.perf_counter()
    with torch.autocast("cuda", dtype=torch.bfloat16):
        a, e = model([longest]); losses = loss_for("S", a, e, bag_targets([longest], gold, device="cuda"))
    losses["loss"].backward(); torch.nn.utils.clip_grad_norm_(model.parameters(), 1., error_if_nonfinite=True)
    torch.cuda.synchronize()
    longest_check = dict(key=longest.key, windows=[len(w.input_ids) for w in longest.windows],
        elapsed_seconds=time.perf_counter()-t, peak_allocated_bytes=torch.cuda.max_memory_allocated(),
        peak_reserved_bytes=torch.cuda.max_memory_reserved())
    model.zero_grad(set_to_none=True)
    checkpoint = out / "acceptance_boundary.pt"
    t = time.perf_counter()
    save_checkpoint(checkpoint, model, opt, sched, binding=frozen["binding"], method="S", epoch=0,
        optimizer_steps=2, best_selection=None, history=[], epoch_boundary=True, acceptance_only=True,
        note="Synthetic boundary after two complete optimizer groups; tests epoch-state serialization mechanics, not a completed training epoch")
    save_seconds = time.perf_counter()-t
    next_group = [data["fit"][i] for i in order[16:32]]
    continuous = train_group(model, opt, sched, next_group, gold, "S")
    hashes = dict(model=parameter_digest(model), optimizer=state_digest(opt.state_dict()),
                  scheduler=state_digest(sched.state_dict()), rng=state_digest(rng()))
    t = time.perf_counter()
    restored = restore_checkpoint(checkpoint, model, opt, sched, frozen["binding"], "S", acceptance=True)
    restore_seconds = time.perf_counter()-t
    resumed = train_group(model, opt, sched, next_group, gold, "S")
    restored_hashes = dict(model=parameter_digest(model), optimizer=state_digest(opt.state_dict()),
                          scheduler=state_digest(sched.state_dict()), rng=state_digest(rng()))
    write_json(out / "next_step_comparison.json", dict(continuous=hashes, resumed=restored_hashes, equal=hashes == restored_hashes))
    if hashes != restored_hashes: raise AssertionError("Continuous/resumed next update differs")
    write_json(out / "resume_consistency.json", dict(passed=True, continuous=hashes, resumed=restored_hashes,
        continuous_loss=continuous["total_loss_sum"], resumed_loss=resumed["total_loss_sum"],
        save_seconds=save_seconds, restore_seconds=restore_seconds, restored_metadata=restored,
        limitation="Explicit complete-epoch restore only; no automatic/mid-microbatch resume"))
    # Common original-model tune baseline, never eligible for epoch selection.
    del opt, sched, model; gc.collect(); torch.cuda.empty_cache()
    reset_seed(); model = load_model(Path(frozen["model_dir"]))
    rows = predict(model, data["tune"])
    scores, labels, _, _ = arrays(rows, gold)
    metrics, curve = evaluate(scores, labels)
    write_json(out / "initial_tune_scores.json", rows)
    write_json(out / "initial_tune_metrics.json", dict(metrics=metrics, epoch=0, eligible_for_selection=False))
    np.savez_compressed(out / "initial_tune_pr_curve.npz", **curve)
    write_json(out / "receipt.json", dict(passed=True, time=now(), binding=frozen["binding"],
        initial_weights_sha256=initial_hashes["T"], method_initial_hashes=initial_hashes,
        forward_backward=forward_checks, adamw=dict(first_lr=first["lr_used"], second_lr=second["lr_used"],
            before_sha256=before, after_sha256=after, actual_parameters_updated=True), updated_longest=longest_check,
        resume_next_step_exact=True, gpu=torch.cuda.get_device_name(0),
        total_memory=torch.cuda.get_device_properties(0).total_memory, elapsed_seconds=time.perf_counter()-started,
        no_learning_score_gate=True))
    print(json.dumps(dict(passed=True, elapsed_seconds=time.perf_counter()-started, updated_longest=longest_check)), flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser(); p.add_argument("--run", type=Path, required=True)
    execute(p.parse_args().run.resolve())
