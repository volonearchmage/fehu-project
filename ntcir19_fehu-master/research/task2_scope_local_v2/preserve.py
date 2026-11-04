"""Final read-only preservation audit; hashes, never uploads file contents."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def audit(run):
    root=Path.cwd(); project=root/'ntcir19_fehu-master'
    before=json.loads((run.parent/'provenance_before.json').read_text())
    historic=json.loads((project/'output/linux_handoff/archive_hashes_before.json').read_text())
    old_env=json.loads((project/'output/task2_scope_local_v1/real_model_20261104-220202/old_environment_before.json').read_text())
    checks={};skipped=[]
    for category,entries in [('task_start_preserved',before['preserved_sha256']),('historical_archive',historic),('old_environment_key_files',old_env['file_sha256'])]:
        bad=[];count=0
        for name,expected in entries.items():
            p=Path(name.replace('\\','/'))
            if any(part=='.env' or part.startswith('.env.') or part in {'credentials','auth.json'} for part in p.parts):
                skipped.append(name);continue
            if not p.is_absolute():p=root/p
            count+=1
            if not p.is_file() or sha(p)!=expected:bad.append(name)
        checks[category]=dict(checked=count,mismatches=bad,passed=not bad)
    old_cache=project/'output/task2_scope_local_v1/pretraining_20261104-214022/input_cache_v1'
    manifest=json.loads((old_cache/'manifest.json').read_text())
    cache_checks={part:sha(old_cache/r['cache'])==r['sha256'] for part,r in manifest['partitions'].items()}
    current_head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
    current_branch=subprocess.check_output(['git','branch','--show-current'],text=True).strip()
    current_boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    result=dict(checks=checks,old_input_caches_unchanged=cache_checks,skipped_sensitive_paths=skipped,
        boot_unchanged=current_boot==before['boot_id'],head_unchanged=current_head==before['head'],
        branch_unchanged=current_branch==before['branch'],
        user_stop_sha256=sha(project/'research/task2_prompt_baseline_v1/USER_STOP.json'))
    result['passed']=all(c['passed'] for c in checks.values()) and all(cache_checks.values()) and all(result[k] for k in ('boot_unchanged','head_unchanged','branch_unchanged')) and not skipped
    with (run/'preservation_final.json').open('x') as f:json.dump(result,f,indent=2);f.write('\n')
    print(json.dumps(result,indent=2))
    if not result['passed']:raise RuntimeError('Preservation mismatch; inspect evidence before reporting completion')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True)
    audit(p.parse_args().run.resolve())
