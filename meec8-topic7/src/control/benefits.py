"""预警命中评估与效益量化（模拟场景推算）：事件级召回
（严格/运行两套口径）与预抽空容积、削峰、调蓄拦截效益推算。

用法：
  python -m src.control.benefits --horizon-min 120
"""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.control.warning import LEVELS, PLANT_CAPACITY_M3H
from src.models.forecast import predict_series

PUMP_TOTAL_M3S = 40.5      # Date1：26 站合计设计能力
DRAWDOWN_ALPHA = 0.15      # 预降前池/管段可动用的调蓄比例（保守取值）
STEP_MIN = 5


def _episodes(mask: np.ndarray) -> list[tuple[int, int]]:
    """连续 True 段 [start, end) 列表。"""
    idx = np.flatnonzero(np.diff(np.r_[0, mask.astype(int), 0]))
    return list(zip(idx[::2], idx[1::2]))


def event_detection(truth: pd.Series, pred: pd.Series, threshold: float,
                    alert_factor: float = 1.0, tol_steps: int = 0) -> dict:
    """事件级命中：真值事件段（±容差窗）内预测达触发线即命中。"""
    t_mask = (truth / PLANT_CAPACITY_M3H >= threshold).to_numpy()
    p_mask = (pred / PLANT_CAPACITY_M3H >= threshold * alert_factor).to_numpy()
    events = _episodes(t_mask)
    n = len(t_mask)
    hits = sum(1 for s, e in events
               if p_mask[max(0, s - tol_steps):min(n, e + tol_steps)].any())
    false_alarms = sum(
        1 for s, e in _episodes(p_mask)
        if not t_mask[max(0, s - tol_steps):min(n, e + tol_steps)].any())
    return {"events": len(events), "hits": hits,
            "recall": round(hits / len(events), 3) if events else None,
            "false_alarm_episodes": false_alarms}


def benefits(truth: pd.Series, lead_min: int) -> dict:
    """效益推算（体积单位：万 m³）。"""
    step_h = STEP_MIN / 60
    v_storage = DRAWDOWN_ALPHA * PUMP_TOTAL_M3S * 3600 * (lead_min / 60) / 1e4
    out = {"预抽空可腾容积_万m3": round(v_storage, 2)}
    for name, thr in [("削峰(橙0.95)", 0.95), ("超越(红1.10)", 1.10)]:
        excess = (truth - thr * PLANT_CAPACITY_M3H).clip(lower=0)
        ep = _episodes((excess > 0).to_numpy())
        vols = [excess.iloc[s:e].sum() * step_h / 1e4 for s, e in ep]
        total = float(np.sum(vols))
        intercepted = float(np.sum([min(v, v_storage) for v in vols]))
        out[name] = {
            "事件数": len(ep), "超阈体积_万m3": round(total, 2),
            "可拦截体积_万m3": round(intercepted, 2),
            "拦截率": round(intercepted / total, 3) if total else None}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sim-dir", default="data/simulated_realrain")
    ap.add_argument("--horizon-min", type=int, default=120)
    ap.add_argument("--out", default="reports/benefit_summary.json")
    args = ap.parse_args()

    p50, p90, truth = predict_series(args.horizon_min, args.sim_dir)
    summary = {"horizon_min": args.horizon_min,
               "test_days": round(len(truth) * STEP_MIN / 1440, 1),
               "note": "模拟场景推算，非泰和实测",
               "detection": {}}
    tol = 60 // STEP_MIN  # ±60min 容差
    for thr, lvl, _ in LEVELS[:3]:  # 红/橙/黄
        summary["detection"][lvl] = {
            "P90严格": event_detection(truth, p90, thr),
            "P90运行(触发0.85±60min)": event_detection(
                truth, p90, thr, alert_factor=0.85, tol_steps=tol)}
    summary["benefits"] = benefits(truth, args.horizon_min)

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"-> {args.out}")


if __name__ == "__main__":
    main()
