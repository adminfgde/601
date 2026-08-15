"""降雨预报输入实验：在特征中加入未来 0~horizon 累计雨量，
对比 无预报 / noisy（σ=0.3 乘性噪声 + 0.5mm 起报阈值）/ perfect 三种配置
的 NSE 与黄/橙预警事件召回。

用法：
  python -m src.models.rain_forecast_exp --horizon-min 120
"""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from lightgbm import LGBMRegressor

from src.control.benefits import event_detection
from src.models.forecast import build_features, load_taihe


def future_rain(rain: pd.Series, h: int) -> pd.Series:
    """未来 1~h 步累计雨量（发布时刻可得的"预报量"真值）。"""
    return rain[::-1].rolling(h, min_periods=1).sum()[::-1].shift(-1)


def add_forecast_features(X: pd.DataFrame, rain: pd.Series, h: int,
                          mode: str, rng: np.random.Generator) -> pd.DataFrame:
    fut = future_rain(rain, h).reindex(X.index)
    if mode == "noisy":
        fut = fut * rng.lognormal(0.0, 0.3, len(fut))
        fut = fut.where(fut >= 0.5, 0.0)  # 起报阈值：小雨漏报
    X = X.copy()
    X["rain_fut_sum"] = fut
    X["rain_fut_half"] = future_rain(rain, h // 2).reindex(X.index)
    if mode == "noisy":
        X["rain_fut_half"] = X["rain_fut_half"] * rng.lognormal(0.0, 0.3, len(X))
    return X


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sim-dir", default="data/simulated_realrain")
    ap.add_argument("--horizon-min", type=int, default=120)
    ap.add_argument("--out", default="reports/rain_forecast_exp.json")
    args = ap.parse_args()
    h = args.horizon_min // 5
    rng = np.random.default_rng(7)

    df = load_taihe(args.sim_dir)
    exog = ["rain"] + [c for c in df.columns if c.startswith("lvl_")]
    X0, y = build_features(df, "inflow", exog, h)
    split = int(len(X0) * 0.75)
    report = {"horizon_min": args.horizon_min, "note": "理想/含噪雨预报对照实验"}

    for mode in ("none", "noisy", "perfect"):
        X = X0 if mode == "none" else add_forecast_features(
            X0, df["rain"], h, mode, rng)
        Xtr, Xte, ytr, yte = X[:split], X[split:], y[:split], y[split:]
        m = LGBMRegressor(n_estimators=400, learning_rate=0.05,
                          num_leaves=63, verbose=-1)
        m.fit(Xtr, ytr)
        pred = pd.Series(m.predict(Xte), index=yte.index)
        q90 = LGBMRegressor(objective="quantile", alpha=0.9, n_estimators=300,
                            learning_rate=0.05, num_leaves=63, verbose=-1)
        q90.fit(Xtr, ytr)
        p90 = pd.Series(q90.predict(Xte), index=yte.index)
        err = pred - yte
        nse = float(1 - np.sum(err ** 2) / np.sum((yte - yte.mean()) ** 2))
        det = {lvl: event_detection(yte, p90, thr, alert_factor=0.85,
                                    tol_steps=12)
               for thr, lvl in [(0.80, "黄色"), (0.95, "橙色")]}
        report[mode] = {"NSE": round(nse, 4), "detection_P90_运行口径": det}
        print(f"[{mode}] NSE={nse:.4f} 黄recall={det['黄色']['recall']} "
              f"橙recall={det['橙色']['recall']}")

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"-> {args.out}")


if __name__ == "__main__":
    main()
