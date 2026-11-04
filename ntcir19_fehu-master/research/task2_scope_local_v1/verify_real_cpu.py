"""One real pretrained ModernBERT CPU update on two complete short fit bags.

This bounded integration check reuses the existing input/model/loss pipeline.
It is not a trainer, benchmark, model-quality evaluation, or CUDA fallback.
"""
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import resource
import sys
import time

import torch
from transformers import AutoModel

from .chunk_model import ChunkedScopeModel, bag_targets
from .chunking import make_windows, validate_windows
from .data import bags, load_articles, load_json, sha256, validate_split
from .losses import scope_loss
from .prepare import PROJECT, SOURCE, write_json
from .tokenization import BagTokenizer

PACKAGE = Path(__file__).resolve().parent


def parameter_hashes(model):
    return {name: hashlib.sha256(p.detach().contiguous().numpy().tobytes()).hexdigest()
            for name, p in model.named_parameters()}


def run(args):
    total_started = time.perf_counter()
    if sys.prefix == sys.base_prefix or Path(sys.prefix).resolve() != (PROJECT / ".venv").resolve():
        raise RuntimeError("Run this check only inside the project's isolated .venv")
    if torch.version.cuda is not None:
        raise RuntimeError("This integration check requires the isolated CPU-only torch build")
    args.out.mkdir(parents=True, exist_ok=False)
    torch.set_num_threads(2)
    torch.set_num_interop_threads(1)
    torch.manual_seed(11)
    timing = {}
    model_lock = load_json(PACKAGE / "model_lock.json")
    tokenizer_lock = load_json(PACKAGE / "tokenizer_lock.json")
    protocol = load_json(PACKAGE / "protocol.json")
    chunk_config = load_json(PACKAGE / "chunking_v1.json")
    for name, record in model_lock["files"].items():
        if sha256(args.model_dir / name) != record["sha256"]:
            raise ValueError(f"Pinned model file hash mismatch: {name}")
    for path in [PROJECT / "dataset/train/train_event_base.json", SOURCE / "grouped_train_split.json"]:
        if sha256(path) != protocol["source_sha256"][str(path.relative_to(PROJECT))]:
            raise ValueError("Input/split bytes changed")

    started = time.perf_counter()
    fit_articles = validate_split(load_articles(PROJECT / "dataset/train/train_event_base.json"),
                                  load_json(SOURCE / "grouped_train_split.json"))["fit"]
    input_bags = {b.key: b for b in bags(fit_articles)}
    cache_manifest = load_json(PACKAGE / "review/input_cache_manifest.json")
    coverage_path = PACKAGE / "review/fit.coverage.json"
    if sha256(coverage_path) != cache_manifest["partitions"]["fit"]["coverage_sha256"]:
        raise ValueError("Input-only length manifest changed")
    # Stable input-only choice. Gold is not opened until selection is complete.
    selected = []
    for row in sorted(load_json(coverage_path), key=lambda r: (r["original_tokens"], r["guid"], r["actor_id"])):
        if row["guid"] not in {b.guid for b in selected}:
            selected.append(input_bags[(row["guid"], row["actor_id"])])
        if len(selected) == 2:
            break
    tokenizer = BagTokenizer(args.tokenizer_dir, tokenizer_lock)
    encoded = [tokenizer.encode(b) for b in selected]
    if len(encoded) != 2 or any(len(e.input_ids) > 256 for e in encoded):
        raise ValueError("Bounded CPU check requires two complete fit bags of at most 256 tokens")
    plans = [make_windows(e, max_length=chunk_config["max_length"], overlap=chunk_config["body_overlap_tokens"]) for e in encoded]
    for plan, bag in zip(plans, selected):
        validate_windows(plan)
        if plan.event_ids != tuple(e.id for e in bag.events):
            raise ValueError("Subevent coverage mismatch")

    audit = load_json(args.supervision_dir / "audit.json")
    supervision_file = args.supervision_dir / "fit.supervision.jsonl"
    if sha256(supervision_file) != audit["artifact_sha256"][supervision_file.name]:
        raise ValueError("Fit supervision cache changed")
    if audit["split_sha256"] != protocol["source_sha256"][str((SOURCE / "grouped_train_split.json").relative_to(PROJECT))]:
        raise ValueError("Fit supervision split differs")
    keys = {b.key for b in selected}
    gold = {}
    with supervision_file.open() as f:
        for line in f:
            row = json.loads(line)
            if (row["guid"], row["actor_id"]) in keys:
                gold[(row["guid"], row["actor_id"])] = row
    targets = bag_targets(plans, gold, device="cpu")
    timing["input_and_tokenizer_seconds"] = time.perf_counter() - started

    started = time.perf_counter()
    encoder, loading = AutoModel.from_pretrained(str(args.model_dir), local_files_only=True,
        token=False, trust_remote_code=False, dtype=torch.float32, attn_implementation="sdpa",
        output_loading_info=True)
    # Transformers 5 returns sets for some key lists. Check serialization before
    # the bounded update so a reporting error cannot discard its measurements.
    loading = {key: sorted(value) if isinstance(value, set) else value
               for key, value in loading.items()}
    json.dumps(loading)
    if loading.get("missing_keys") or loading.get("mismatched_keys") or loading.get("error_msgs"):
        raise RuntimeError(f"Encoder was not fully initialized from pretrained weights: {loading}")
    if encoder.config.num_hidden_layers != 22 or encoder.config.hidden_size != 768:
        raise RuntimeError("Expected the full 22-layer pretrained ModernBERT-base encoder")
    model = ChunkedScopeModel(encoder, encoder.config.hidden_size, checkpoint_windows=False).cpu()
    model.train()
    timing["pretrained_load_seconds"] = time.perf_counter() - started
    before = parameter_hashes(model)
    shapes = []
    def record_encoder(module, inputs, output):
        shapes.append(list(output.last_hidden_state.shape))
    hook = model.encoder.register_forward_hook(record_encoder)
    optimizer = torch.optim.AdamW([dict(params=model.encoder.parameters(), lr=2e-5),
                                   dict(params=model.head.parameters(), lr=1e-4)], weight_decay=.01, foreach=False)
    optimizer.zero_grad(set_to_none=True)
    started = time.perf_counter()
    article_logits, event_logits = model(plans)
    losses = scope_loss(article_logits, event_logits, mode="S", article_weight=1., **targets)
    if not all(torch.isfinite(t).all() for t in (article_logits, event_logits, *losses.values())):
        raise RuntimeError("Nonfinite model output/loss")
    timing["forward_and_loss_seconds"] = time.perf_counter() - started
    started = time.perf_counter()
    losses["loss"].backward()
    timing["backward_seconds"] = time.perf_counter() - started
    grad_records = {}
    for name, p in model.named_parameters():
        if p.requires_grad and (p.grad is None or not torch.isfinite(p.grad).all()):
            raise RuntimeError(f"Missing/nonfinite gradient: {name}")
        if p.grad is not None:
            grad_records[name] = float(p.grad.norm())
    encoder_norm = sum(v*v for n,v in grad_records.items() if n.startswith("encoder.")) ** .5
    head_norm = sum(v*v for n,v in grad_records.items() if n.startswith("head.")) ** .5
    if encoder_norm <= 0 or head_norm <= 0:
        raise RuntimeError("Expected nonzero pretrained encoder and head gradients")
    started = time.perf_counter()
    optimizer.step()  # Exactly one update; no epoch/batch loop or fit evaluation.
    timing["optimizer_step_seconds"] = time.perf_counter() - started
    hook.remove()
    after = parameter_hashes(model)
    changed = [name for name in before if before[name] != after[name]]
    if not any(n.startswith("encoder.") for n in changed) or not any(n.startswith("head.") for n in changed):
        raise RuntimeError("Both pretrained encoder and classification head must update")
    if not all(torch.isfinite(p).all() for p in model.parameters()):
        raise RuntimeError("Nonfinite parameter after optimizer update")
    timing["compute_step_seconds"] = sum(timing[k] for k in ("forward_and_loss_seconds","backward_seconds","optimizer_step_seconds"))
    timing["total_validation_seconds"] = time.perf_counter() - total_started
    result = dict(passed=True, scope="One CPU AdamW update on two complete real fit bags; integration evidence only, not model quality",
        model=model_lock["model"], revision=model_lock["revision"], pretrained_file_sha256=model_lock["files"]["model.safetensors"]["sha256"],
        loading_info=loading, encoder_class=type(encoder).__name__, encoder_layers=encoder.config.num_hidden_layers,
        hidden_size=encoder.config.hidden_size, encoder_parameters=sum(p.numel() for p in encoder.parameters()),
        head_parameters=sum(p.numel() for p in model.head.parameters()), device="cpu", dtype="float32", attention="sdpa",
        tokenizer=dict(model=tokenizer_lock["model"],revision=tokenizer_lock["revision"],implementation="tokenizers.Tokenizer"),
        selected=[dict(guid=b.guid,actor_id=b.actor_id,events=len(b.events),tokens=len(e.input_ids),windows=len(p.windows),
                       all_events_retained=True,partition="fit") for b,e,p in zip(selected,encoded,plans)],
        shapes=dict(encoder=shapes,article_logits=list(article_logits.shape),event_logits=list(event_logits.shape),
                    child_mask=list(targets["child_mask"].shape),valid_events=targets["child_mask"].sum(1).tolist()),
        loss={k:float(v.detach()) for k,v in losses.items()},loss_mode="S",loss_is_not_effectiveness_metric=True,
        finite_gradients=True,gradient_parameter_tensors=len(grad_records),encoder_gradient_norm=encoder_norm,head_gradient_norm=head_norm,
        optimizer="AdamW",optimizer_steps=1,changed_parameter_tensors=len(changed),
        changed_encoder_tensors=sum(n.startswith("encoder.") for n in changed),changed_head_tensors=sum(n.startswith("head.") for n in changed),
        parameter_hashes_before=before,parameter_hashes_after=after,timing=timing,
        peak_process_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        environment=dict(python=sys.version.split()[0],isolated_venv=True,system_site_packages=False,
            versions={n:importlib.metadata.version(n) for n in ("torch","transformers","tokenizers","numpy","safetensors","huggingface-hub")},
            cpu_threads=torch.get_num_threads(),interop_threads=torch.get_num_interop_threads(),torch_cuda_build=torch.version.cuda),
        source_sha256={"script":sha256(Path(__file__)),"chunk_config":sha256(PACKAGE/"chunking_v1.json"),"fit_supervision":sha256(supervision_file)},
        evaluation_labels_read=False,gpu_experiment=False,full_training=False,weights_saved=False,paid_api_calls=0)
    write_json(args.out / "result.json", result)
    print(json.dumps({k:result[k] for k in ("passed","model","revision","encoder_parameters","selected","shapes","finite_gradients","encoder_gradient_norm","head_gradient_norm","optimizer_steps","changed_encoder_tensors","changed_head_tensors","timing")},indent=2),flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir",type=Path,required=True)
    parser.add_argument("--tokenizer-dir",type=Path,required=True)
    parser.add_argument("--supervision-dir",type=Path,required=True)
    parser.add_argument("--out",type=Path,required=True)
    run(parser.parse_args())
