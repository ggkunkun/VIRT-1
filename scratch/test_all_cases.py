import sys
sys.path.insert(0, ".")
import json
from virtu_omni.engine.step_reverse_engine import StepReverseEngine

engine = StepReverseEngine()
with open('data/benchmark/reverse_engineering_eval_dataset.json', 'r', encoding='utf-8') as f:
    bench = json.load(f)

for case in bench['cases']:
    cid = case['id']
    fpath = case['source_file']
    res = engine.analyze_step(fpath)
    gt = case['ground_truth']
    target_vol = gt['theoretical_volume_cm3']
    calc_vol = res.theoretical_volume_mm3 / 1000.0
    vol_err = abs(calc_vol - target_vol) / target_vol * 100.0
    fam_ok = (res.part_family == case.get('family'))
    print(f'[{cid}] family={res.part_family:16} (match={fam_ok}) vol={calc_vol:7.2f}cm3 gt={target_vol:7.2f}cm3 err={vol_err:.2f}%')
