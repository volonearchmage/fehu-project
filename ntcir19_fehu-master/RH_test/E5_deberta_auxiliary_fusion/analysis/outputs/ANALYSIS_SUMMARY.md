# E5 complementarity analysis (E1 vs augmented DeBERTa v2)

- gold (guid,actor) keys: 456; E1 pred keys: 447; v2 prob rows: 459
- **E1**: 1b micro 0.5480 (P 0.5405 / R 0.5556), macro 0.3719, DRR 0.0347
- **v2@0.30**: 1b micro 0.3306 (P 0.2381 / R 0.5406), macro 0.1303, DRR 0.2880

## Gold-cell coverage (2390 cells)
- all:     {'both': 864, 'e1_only': 464, 'v2_only': 428, 'neither': 634}
- target18: {'both': 3, 'e1_only': 35, 'v2_only': 9, 'neither': 93}

## Recovery sweep (see recovery_sweep.csv)
- tau=0.30 gate=False: +4132 cells, prec 0.104 (t18: +151, prec 0.060)
- tau=0.30 gate=True: +746 cells, prec 0.189 (t18: +0, prec 0.000)
- tau=0.35 gate=False: +2516 cells, prec 0.116 (t18: +94, prec 0.064)
- tau=0.35 gate=True: +672 cells, prec 0.191 (t18: +0, prec 0.000)
- tau=0.40 gate=False: +1580 cells, prec 0.135 (t18: +48, prec 0.042)
- tau=0.40 gate=True: +545 cells, prec 0.207 (t18: +0, prec 0.000)
- tau=0.45 gate=False: +1056 cells, prec 0.152 (t18: +8, prec 0.125)
- tau=0.45 gate=True: +424 cells, prec 0.207 (t18: +0, prec 0.000)
- tau=0.50 gate=False: +694 cells, prec 0.166 (t18: +0, prec 0.000)
- tau=0.50 gate=True: +294 cells, prec 0.211 (t18: +0, prec 0.000)
- tau=0.55 gate=False: +404 cells, prec 0.171 (t18: +0, prec 0.000)
- tau=0.55 gate=True: +164 cells, prec 0.171 (t18: +0, prec 0.000)
- tau=0.60 gate=False: +165 cells, prec 0.164 (t18: +0, prec 0.000)
- tau=0.60 gate=True: +51 cells, prec 0.137 (t18: +0, prec 0.000)
- tau=0.65 gate=False: +80 cells, prec 0.200 (t18: +0, prec 0.000)
- tau=0.65 gate=True: +0 cells, prec 0.000 (t18: +0, prec 0.000)
- tau=0.70 gate=False: +59 cells, prec 0.220 (t18: +0, prec 0.000)
- tau=0.70 gate=True: +0 cells, prec 0.000 (t18: +0, prec 0.000)
- tau=0.80 gate=False: +0 cells, prec 0.000 (t18: +0, prec 0.000)
- tau=0.80 gate=True: +0 cells, prec 0.000 (t18: +0, prec 0.000)
- tau=0.90 gate=False: +0 cells, prec 0.000 (t18: +0, prec 0.000)
- tau=0.90 gate=True: +0 cells, prec 0.000 (t18: +0, prec 0.000)

E1 micro-precision reference: 0.5405 — additions above this precision raise micro-F1.

## Filter (E1 TP vs FP separation by v2 prob)
- AUC exact label: 0.6809; AUC value-max: 0.6635
- TP dist {'n': 1328, 'p10': 0.1617, 'p25': 0.2579, 'median': 0.3601, 'p75': 0.5045, 'mean': 0.376}
- FP dist {'n': 1129, 'p10': 0.0757, 'p25': 0.1554, 'median': 0.2681, 'p75': 0.3558, 'mean': 0.2705}
- tau_low=0.01: -7 FP / -2 TP (ratio 3.5)
- tau_low=0.02: -20 FP / -2 TP (ratio 10.0)
- tau_low=0.05: -74 FP / -13 TP (ratio 5.692)
- tau_low=0.1: -156 FP / -41 TP (ratio 3.805)
- tau_low=0.15: -271 FP / -106 TP (ratio 2.557)
- tau_low=0.2: -379 FP / -215 TP (ratio 1.763)

## Direction (E1 value-correct cells, unique gold direction)
- counts: {'e1_ok_v2_ok': 937, 'e1_ok_v2_rev': 312, 'e1_rev_v2_ok': 42, 'e1_rev_v2_rev': 23}
- flip if v2 margin>=0.0: 42 fixes / 312 breaks (net -270)
- flip if v2 margin>=0.05: 35 fixes / 206 breaks (net -171)
- flip if v2 margin>=0.1: 23 fixes / 122 breaks (net -99)
- flip if v2 margin>=0.2: 10 fixes / 44 breaks (net -34)
- flip if v2 margin>=0.3: 2 fixes / 12 breaks (net -10)
- flip if v2 margin>=0.5: 0 fixes / 0 breaks (net +0)
