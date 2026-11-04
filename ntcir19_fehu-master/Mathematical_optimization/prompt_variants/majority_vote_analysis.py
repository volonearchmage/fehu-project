"""3-way majority vote + Flash direction verification."""
import json, os
from collections import defaultdict, Counter

BASE = '..'
VAR = 'prompt_variants'

def load_preds(path):
    data = json.load(open(path))
    preds = set()
    for art in data:
        guid = art['guid']
        for hv in art.get('article_human_values', []):
            preds.add((guid, str(hv['actor']), str(hv['l1_value']), str(hv.get('direction','1'))))
    return preds

S_base = load_preds(f'{VAR}/baseline/pred_task1b.json')
S_tmb  = load_preds(f'{VAR}/targeted_more_shot_balanced/pred_task1b.json')
S_cs   = load_preds(f'{VAR}/compact_strict/pred_task1b.json')

print(f'baseline:   {len(S_base)} predictions')
print(f'targeted:   {len(S_tmb)} predictions')
print(f'compact_strict: {len(S_cs)} predictions')

# Majority vote: >=2/3
all_preds = list(S_base) + list(S_tmb) + list(S_cs)
counts = Counter(all_preds)
S_majority = {p for p, c in counts.items() if c >= 2}

print(f'\n3-way majority (>=2/3): {len(S_majority)} predictions')
print(f'  3/3 agree: {sum(1 for p,c in counts.items() if c==3)}')
print(f'  2/3 agree: {sum(1 for p,c in counts.items() if c==2)}')

base_tmb = S_base & S_tmb
base_cs = S_base & S_cs
tmb_cs = S_tmb & S_cs
all3 = S_base & S_tmb & S_cs
print(f'\nIntersections:')
print(f'  baseline & targeted: {len(base_tmb)}')
print(f'  baseline & compact_strict: {len(base_cs)}')
print(f'  targeted & compact_strict: {len(tmb_cs)}')
print(f'  all 3: {len(all3)}')

# Flash direction verification
flash_data = json.load(open('runs/20260724_160254/pred_task1b.json'))
flash_map = {}
flash_set = set()
for art in flash_data:
    guid = art['guid']
    for hv in art.get('article_human_values', []):
        aid = str(hv['actor'])
        l1 = str(hv['l1_value'])
        d = str(hv.get('direction','1'))
        flash_map[(guid, aid, l1)] = d
        flash_set.add((guid, aid, l1, d))

S_final = set()
flipped = 0
for (guid, aid, l1, d_maj) in S_majority:
    flash_d = flash_map.get((guid, aid, l1))
    if flash_d is None or flash_d == d_maj:
        S_final.add((guid, aid, l1, d_maj))
    else:
        S_final.add((guid, aid, l1, flash_d))
        flipped += 1

flash_only = flash_set - S_majority
S_final |= flash_only

print(f'\nFlash direction verification:')
print(f'  Flipped directions: {flipped}')
print(f'  Added Flash-only: {len(flash_only)}')
print(f'  S_final: {len(S_final)} predictions')

# Gold analysis
gold_data = json.load(open(f'{BASE}/dataset/gold_labels/dev/dev_human_values.json'))
gold_set = set()
for item in gold_data:
    guid = item['guid']
    for hv in item.get('article_human_values', []):
        gold_set.add((guid, str(hv['actor']), str(hv['l1_value']), str(hv['direction'])))

for name, s in [('S_base', S_base), ('S_majority', S_majority), ('S_final', S_final)]:
    tp = len(s & gold_set)
    fp = len(s - gold_set)
    fn = len(gold_set - s)
    p = tp/(tp+fp) if tp+fp>0 else 0
    r = tp/(tp+fn) if tp+fn>0 else 0
    f1 = 2*p*r/(p+r) if p+r>0 else 0
    print(f'\n{name}: TP={tp} FP={fp} FN={fn} P={p:.4f} R={r:.4f} F1={f1:.4f}')

# Build JSON output
pred_by_guid = defaultdict(list)
for (guid, aid, l1, direction) in S_final:
    pred_by_guid[guid].append({'actor': aid, 'l1_value': l1, 'direction': direction})

output = [{'guid': g, 'article_human_values': h} for g, h in pred_by_guid.items()]
os.makedirs(f'{VAR}/majority_vote', exist_ok=True)
json.dump(output, open(f'{VAR}/majority_vote/pred_task1b.json','w'), indent=2, ensure_ascii=False)

# Derive 1a
l1_to_l2_data = json.load(open(f'{BASE}/dataset/hv_categories/level_1_to_level_2.json'))
l1n = json.load(open(f'{BASE}/dataset/hv_categories/human_value_level1_values.json'))
l2n = json.load(open(f'{BASE}/dataset/hv_categories/human_value_level2_values.json'))
l1_to_l2 = {l1n[k]: l2n[v] for k, v in l1_to_l2_data['level_1_to_level_2'].items()}

output_1a = []
for art in output:
    seen = set()
    vals = []
    for hv in art['article_human_values']:
        l2 = l1_to_l2.get(str(hv['l1_value']))
        if l2:
            k = (str(hv['actor']), l2)
            if k not in seen:
                seen.add(k)
                vals.append({'actor': hv['actor'], 'l2_value': l2})
    output_1a.append({'guid': art['guid'], 'article_human_values': vals})

json.dump(output_1a, open(f'{VAR}/majority_vote/pred_task1a.json','w'), indent=2, ensure_ascii=False)
n1a = sum(len(a['article_human_values']) for a in output_1a)
print(f'\n1a predictions: {n1a}')
print(f'Saved to {VAR}/majority_vote/')
