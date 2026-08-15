"""四级预警（蓝/黄/橙/红，按厂设计能力占比）与泵站协同调控建议。
预警输入默认为模型 P90 预测，--oracle 切换为未来真值（上限对照）。

用法：
  python -m src.control.warning --sim-dir data/simulated_realrain
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from src.models.forecast import ensure_taihe, predict_series

# 泰和厂设计规模（Date1：日均 40 万 m3/d 量级按 26 站 40.5 m3/s 汇流概化）
PLANT_CAPACITY_M3H = 8000.0

LEVELS = [  # (占设计能力比例阈值, 预警级, 建议)
    (1.10, "红色", "全网限流：上游泵站按能力 70% 限排，启用调蓄，厂内超越预案待命"),
    (0.95, "橙色", "彭越浦总站错峰：上游支线泵站延迟 30~60min 开泵，削峰错时进厂"),
    (0.80, "黄色", "雨前预抽空：预降各泵站前池液位，腾出调蓄容积"),
    (0.60, "蓝色", "加强监视：关注上游液位与雨量变化趋势"),
]


def evaluate(forecast_inflow: pd.Series, horizon_min: int) -> pd.DataFrame:
    ratio = forecast_inflow / PLANT_CAPACITY_M3H
    level = np.select([ratio >= t for t, _, _ in LEVELS],
                      [l for _, l, _ in LEVELS], default="正常")
    advice = np.select([ratio >= t for t, _, _ in LEVELS],
                       [a for _, _, a in LEVELS], default="常规运行")
    return pd.DataFrame({"time": forecast_inflow.index,
                         "forecast_inflow_m3h": forecast_inflow.round(1).values,
                         "capacity_ratio": ratio.round(3).values,
                         "warning_level": level, "advice": advice,
                         "lead_time_min": horizon_min})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sim-dir", default="data/simulated_realrain")
    ap.add_argument("--horizon-min", type=int, default=120)
    ap.add_argument("--out", default="reports/warning_demo.csv")
    ap.add_argument("--oracle", action="store_true",
                    help="用未来真值作输入（预警能力上限对照）")
    args = ap.parse_args()

    if args.oracle:
        ensure_taihe(args.sim_dir)
        q = pd.read_csv(f"{args.sim_dir}/plant_inflow_quality.csv",
                        parse_dates=["time"], index_col="time")
        step = int((q.index[1] - q.index[0]).total_seconds() // 60)
        fut = q["inflow_m3h"].shift(-args.horizon_min // step).dropna()
    else:
        _, fut, _ = predict_series(args.horizon_min, args.sim_dir)
    report = evaluate(fut, args.horizon_min)

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    report.to_csv(args.out, index=False, encoding="utf-8-sig")
    counts = report["warning_level"].value_counts()
    print(counts.to_string())
    print(f"-> {args.out}")


if __name__ == "__main__":
    main()
