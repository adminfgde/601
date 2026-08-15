"""污染冲击异常分类预警：以在线水质/流量的滞后、差分特征训练
LightGBM 分类器识别 shock_event，输出步级与事件级指标。

用法：
  python -m src.models.anomaly
"""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier

from src.models.forecast import LAGS, load_taihe

OBS = ["cod", "nh3n", "ph", "ss", "inflow"]


def build_clf_features(df: pd.DataFrame) -> pd.DataFrame:
    feat = {}
    for c in OBS:
        for l in LAGS[:6]:
            feat[f"{c}_lag{l}"] = df[c].shift(l - 1)
        feat[f"{c}_diff"] = df[c].diff()
        feat[f"{c}_z3h"] = ((df[c] - df[c].rolling(36).mean())
                            / df[c].rolling(36).std())
    X = pd.DataFrame(feat, index=df.index)
    return X.dropna()


def _episodes(mask: np.ndarray) -> list[tuple[int, int]]:
    idx = np.flatnonzero(np.diff(np.r_[0, mask.astype(int), 0]))
    return list(zip(idx[::2], idx[1::2]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sim-dir", default="data/simulated_realrain")
    ap.add_argument("--out", default="reports/anomaly_metrics.json")
    args = ap.parse_args()

    df = load_taihe(args.sim_dir)
    labels = pd.read_csv(f"{args.sim_dir}/event_labels.csv",
                         parse_dates=["time"], index_col="time")["shock_event"]
    X = build_clf_features(df)
    y = labels.reindex(X.index).fillna(0).astype(int)

    split = int(len(X) * 0.75)
    Xtr, Xte, ytr, yte = X[:split], X[split:], y[:split], y[split:]
    clf = LGBMClassifier(n_estimators=300, learning_rate=0.05, num_leaves=63,
                         class_weight="balanced", verbose=-1)
    clf.fit(Xtr, ytr)
    prob = clf.predict_proba(Xte)[:, 1]
    pred = (prob >= 0.5).astype(int)

    tp = int(((pred == 1) & (yte == 1)).sum())
    fp = int(((pred == 1) & (yte == 0)).sum())
    fn = int(((pred == 0) & (yte == 1)).sum())
    prec = tp / (tp + fp) if tp + fp else None
    rec = tp / (tp + fn) if tp + fn else None
    f1 = (2 * prec * rec / (prec + rec)) if prec and rec else None

    # 事件级：真值事件段内首次报警延迟
    t_mask, p_mask = yte.to_numpy() == 1, pred == 1
    delays, hits = [], 0
    events = _episodes(t_mask)
    for s, e in events:
        alarm = np.flatnonzero(p_mask[s:e])
        if len(alarm):
            hits += 1
            delays.append(int(alarm[0]) * 5)
    false_ep = sum(1 for s, e in _episodes(p_mask) if not t_mask[s:e].any())

    report = {
        "note": "模拟场景毒性冲击标签，非泰和实测",
        "n_test": len(yte), "positives_test": int(yte.sum()),
        "step_level": {"precision": round(prec, 3) if prec else None,
                       "recall": round(rec, 3) if rec else None,
                       "F1": round(f1, 3) if f1 else None},
        "event_level": {"events": len(events), "hits": hits,
                        "recall": round(hits / len(events), 3) if events else None,
                        "mean_delay_min": round(float(np.mean(delays)), 1) if delays else None,
                        "false_alarm_episodes": false_ep},
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"-> {args.out}")


if __name__ == "__main__":
    main()
