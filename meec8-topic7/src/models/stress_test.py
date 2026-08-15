"""极端场景压力测试：基准场景训练的模型在设计暴雨（P=5/50/100a）
与台风"烟花"实况回放场景上做跨场景泛化测试，输出事件级洪峰/峰现误差。

用法：
  python -m src.models.stress_test --horizon-min 120
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from lightgbm import LGBMRegressor

from src.models.forecast import build_features, load_taihe

BASE_SIM = "data/simulated_realrain"
SCENARIOS = {  # name -> (rain_csv, rain_start)
    "design_p5": ("data/processed/design_storm_p5_10min.csv", "2025-07-01"),
    "design_p50": ("data/processed/design_storm_p50_10min.csv", "2025-07-01"),
    "design_p100": ("data/processed/design_storm_p100_10min.csv", "2025-07-01"),
    "typhoon_infa": ("data/processed/shanghai_rain_10min.csv", "2021-07-21"),
}


def ensure_scenario(name: str, rain_csv: str, rain_start: str) -> str:
    out = f"data/stress/{name}"
    if not Path(f"{out}/plant_inflow_quality.csv").exists():
        subprocess.run([sys.executable, "-m", "src.simulation.generate",
                        "--days", "7", "--rain-csv", rain_csv,
                        "--rain-start", rain_start, "--out", out], check=True)
    return out


def event_metrics(truth: pd.Series, pred: pd.Series, rain: pd.Series,
                  step_min: int = 5) -> list[dict]:
    """按降雨事件（间隔<2h 合并）统计洪峰误差与峰现时间误差。"""
    wet = (rain.rolling(int(120 / step_min), min_periods=1).max() > 0).to_numpy()
    idx = np.flatnonzero(np.diff(np.r_[0, wet.astype(int), 0]))
    out = []
    for s, e in zip(idx[::2], idx[1::2]):
        if (e - s) * step_min < 60:
            continue
        t_seg, p_seg = truth.iloc[s:e], pred.iloc[s:e]
        if t_seg.max() < truth.median() * 1.1:  # 无明显涨水过程
            continue
        peak_err = float((p_seg.max() - t_seg.max()) / t_seg.max())
        lag_min = float((p_seg.idxmax() - t_seg.idxmax()).total_seconds() / 60)
        out.append({"start": str(t_seg.index[0]), "dur_h": round((e - s) * step_min / 60, 1),
                    "peak_true_m3h": round(float(t_seg.max()), 0),
                    "peak_rel_err": round(peak_err, 3),
                    "peak_lag_min": lag_min})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--horizon-min", type=int, default=120)
    ap.add_argument("--out", default="reports/stress_test.json")
    args = ap.parse_args()
    h = args.horizon_min // 5

    base = load_taihe(BASE_SIM)
    exog = ["rain"] + [c for c in base.columns if c.startswith("lvl_")]
    Xb, yb = build_features(base, "inflow", exog, h)
    model = LGBMRegressor(n_estimators=400, learning_rate=0.05,
                          num_leaves=63, verbose=-1)
    model.fit(Xb, yb)

    curves = {}
    report = {"horizon_min": args.horizon_min,
              "train": "2024 汛期基准场景（92 天）全量",
              "note": "跨场景泛化测试：模型未见过任何极端场景样本"}
    for name, (rain_csv, rain_start) in SCENARIOS.items():
        sim_dir = ensure_scenario(name, rain_csv, rain_start)
        df = load_taihe(sim_dir)
        X, y = build_features(df, "inflow", exog, h)
        pred = pd.Series(model.predict(X), index=y.index)
        if name == "design_p100":
            curves["truth"], curves["base_model"] = y, pred
        err = pred - y
        nse = float(1 - np.sum(err ** 2) / np.sum((y - y.mean()) ** 2))
        ev = event_metrics(y, pred, df["rain"].shift(-h).reindex(y.index))
        report[name] = {
            "rain_total_mm": round(float(df["rain"].sum() * 5 / 60), 1),
            "peak_inflow_m3h": round(float(y.max()), 0),
            "NSE": round(nse, 3),
            "events": ev}
        print(f"[{name}] NSE={nse:.3f} 峰值={y.max():.0f} m3/h "
              f"事件峰值误差={[e['peak_rel_err'] for e in ev]}")

    # 增广对照：训练集混入 P5+P50 设计暴雨场景后，重测 P100 与台风
    Xas, yas = [], []
    for aug_name in ("design_p5", "design_p50"):
        aug = load_taihe(f"data/stress/{aug_name}")
        Xa, ya = build_features(aug, "inflow", exog, h)
        Xas.append(Xa)
        yas.append(ya)
    model_aug = LGBMRegressor(n_estimators=400, learning_rate=0.05,
                              num_leaves=63, verbose=-1)
    model_aug.fit(pd.concat([Xb, *Xas]), pd.concat([yb, *yas]))
    report["augmented"] = {"train": "基准 + P5/P50 设计暴雨增广"}
    for name in ("design_p100", "typhoon_infa"):
        df = load_taihe(f"data/stress/{name}")
        X, y = build_features(df, "inflow", exog, h)
        pred = pd.Series(model_aug.predict(X), index=y.index)
        if name == "design_p100":
            curves["aug_model"] = pred
        err = pred - y
        nse = float(1 - np.sum(err ** 2) / np.sum((y - y.mean()) ** 2))
        ev = event_metrics(y, pred, df["rain"].shift(-h).reindex(y.index))
        report["augmented"][name] = {
            "NSE": round(nse, 3),
            "peak_rel_err": [e["peak_rel_err"] for e in ev]}
        print(f"[增广后 {name}] NSE={nse:.3f} "
              f"峰值误差={[e['peak_rel_err'] for e in ev]}")

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=2))
    pd.DataFrame(curves).to_csv("reports/stress_p100_curves.csv")
    print(f"-> {args.out}")


if __name__ == "__main__":
    main()
