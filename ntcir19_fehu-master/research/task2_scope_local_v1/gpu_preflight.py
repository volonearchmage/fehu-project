"""Future GPU-only acceptance, not executed during CPU preparation."""
import argparse
import datetime
import json
from pathlib import Path
import subprocess
import time

import torch

from .chunk_model import bag_targets
from .losses import scope_loss
from .prepare import write_json
from .train import load_model, load_training_data, parameter_digest, static_check


def run(args):
    binding = static_check(args.cache_dir, args.supervision_dir, args.model_dir)
    if binding["missing_model_files"]:
        raise RuntimeError("Pinned local weights are missing; no automatic download")
    if args.out.exists():
        raise FileExistsError(args.out)
    smi = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total,driver_version,uuid", "--format=csv,noheader"],
                         text=True, capture_output=True, timeout=20)
    if smi.returncode or "4090" not in smi.stdout:
        raise RuntimeError(f"RTX 4090 nvidia-smi check failed: {smi.stdout}\n{smi.stderr}")
    if not torch.cuda.is_available() or not torch.cuda.is_bf16_supported():
        raise RuntimeError("CUDA/BF16 unavailable; CPU fallback forbidden")
    properties = torch.cuda.get_device_properties(0)
    if "4090" not in properties.name:
        raise RuntimeError("Selected CUDA device is not the expected RTX 4090")
    x = torch.arange(12, device="cuda", dtype=torch.float32).reshape(3, 4)
    torch.testing.assert_close((x @ x.T).cpu(), torch.arange(12.).reshape(3,4) @ torch.arange(12.).reshape(3,4).T)
    torch.cuda.synchronize()
    data, supervision = load_training_data(args.cache_dir, args.supervision_dir)
    ordered = sorted(data["fit"], key=lambda p: (len(p.original.input_ids), p.key))
    chosen = [ordered[round(i * (len(ordered)-1)/19)] for i in range(20)]
    records, initial_hashes = [], []
    # Each condition starts from the same local checkpoint and seed. No updates.
    for method in ("J", "S"):
        model = load_model(args.model_dir); model.train(); initial_hashes.append(parameter_digest(model))
        for plan in chosen:
            model.zero_grad(set_to_none=True); torch.cuda.reset_peak_memory_stats(); torch.cuda.synchronize()
            start = time.monotonic()
            with torch.autocast("cuda", dtype=torch.bfloat16):
                a,c = model([plan])
                result = scope_loss(a,c,mode=method,**bag_targets([plan],supervision,device="cuda"))
            result["loss"].backward(); torch.cuda.synchronize()
            if not torch.isfinite(result["loss"]) or not all(p.grad is not None and torch.isfinite(p.grad).all() for p in model.parameters()):
                raise RuntimeError("Nonfinite/missing gradient in GPU acceptance")
            records.append(dict(method=method, key=plan.key, windows=len(plan.windows), tokens=len(plan.original.input_ids),
                                seconds=time.monotonic()-start, peak_bytes=torch.cuda.max_memory_allocated()))
        del a,c,result,model
        torch.cuda.empty_cache()
    if initial_hashes[0] != initial_hashes[1]:
        raise RuntimeError("J/S initial parameters differ")
    write_json(args.out, dict(schema="fehu-gpu-preflight-v1", passed=True, binding=binding,
        time=datetime.datetime.now().astimezone().isoformat(), boot_id=Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
        nvidia_smi=smi.stdout, gpu=properties.name, memory_bytes=properties.total_memory,
        pytorch=torch.__version__, cuda=torch.version.cuda, initial_weights_sha256=initial_hashes[0],
        records=records, formal_training=False, optimizer_updates=0))


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--supervision-dir", type=Path, required=True)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--execute", action="store_true", help="Requires future user authorization for GPU acceptance")
    args=parser.parse_args()
    if args.execute:
        run(args)
    else:
        print(json.dumps(dict(action="offline_static_check_only", **static_check(args.cache_dir,args.supervision_dir,args.model_dir)), indent=2))
