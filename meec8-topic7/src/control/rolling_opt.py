"""SWMM 在环调度策略对比：static（泵常开）/ rule（本地液位规则）/
predict（预见性滚动调度：雨前预抽空→峰中错峰→峰后恢复），
pyswmm 逐步仿真、每 5min 下发泵指令。

用法：
  python -m src.control.rolling_opt --inp data/swmm/taihe_p50.inp
"""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from pyswmm import Links, Nodes, Simulation

from src.swmm.build_inp import UNITS

SAFE_CMS = 4.5          # 厂前安全输送阈值（超过则冲击工艺）
PRE_RAIN_MM = 10.0      # 未来 2h 累计雨量预抽空触发阈值
CTRL_STEP_S = 300


def rain_lookahead(rain: pd.Series, t, hours: float = 2.0) -> float:
    seg = rain.loc[t:t + pd.Timedelta(hours=hours)]
    return float(seg.sum())


def run_strategy(inp: str, strategy: str, rain: pd.Series,
                 guard: float = 0.85) -> pd.DataFrame:
    rows = []
    with Simulation(inp) as sim:
        nodes, links = Nodes(sim), Links(sim)
        plant = nodes["PLANT"]
        sts = [nodes[f"ST_{n}"] for n, *_ in UNITS]
        pumps = [links[f"P_{n}"] for n, *_ in UNITS]
        depths = [u[5] for u in UNITS]
        sim.step_advance(CTRL_STEP_S)
        for _ in sim:
            t = pd.Timestamp(sim.current_time)
            q_plant = plant.total_inflow
            if strategy == "static":
                settings = [1.0] * 6
            elif strategy == "rule":
                settings = [1.0 if st.depth > 0.6 * d else
                            (0.2 if st.depth < 0.1 * d else None)
                            for st, d in zip(sts, depths)]
            else:  # predict
                fut = rain_lookahead(rain, t)
                if fut >= PRE_RAIN_MM:          # 雨前预抽空
                    settings = [1.0] * 6
                elif q_plant > SAFE_CMS:        # 峰中错峰：上游限排
                    settings = [0.4, 0.4, 0.6, 1.0, 1.0, 1.0]
                    # 防冒溢保护：前池接近满时强制全开（guard>=1 即关闭保护）
                    settings = [1.0 if st.depth > guard * d else s
                                for st, d, s in zip(sts, depths, settings)]
                else:                           # 常态/峰后恢复
                    settings = [1.0 if st.depth > 0.3 * d else 0.7
                                for st, d in zip(sts, depths)]
            for p, s in zip(pumps, settings):
                if s is not None:
                    p.target_setting = s
            rows.append({"time": t, "plant_cms": q_plant,
                         "flood_cms": sum(st.flooding for st in sts),
                         "depth_mean": float(np.mean([st.depth for st in sts]))})
    df = pd.DataFrame(rows).set_index("time")
    return df


def metrics(df: pd.DataFrame) -> dict:
    dt_h = CTRL_STEP_S / 3600
    over = (df["plant_cms"] - SAFE_CMS).clip(lower=0)
    return {"峰值入流_cms": round(float(df["plant_cms"].max()), 2),
            "超阈历时_h": round(float((over > 0).sum() * dt_h), 1),
            "超阈体积_万m3": round(float(over.sum() * 3600 * dt_h / 1e4), 2),
            "前池冒溢体积_万m3": round(
                float(df["flood_cms"].sum() * 3600 * dt_h / 1e4), 2)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inp", default="data/swmm/taihe_p50.inp")
    ap.add_argument("--rain-csv",
                    default="data/processed/design_storm_p50_10min.csv")
    ap.add_argument("--out", default="reports/swmm_control.json")
    args = ap.parse_args()

    rain = pd.read_csv(args.rain_csv, index_col=0, parse_dates=True).iloc[:, 0]
    report, curves = {"inp": args.inp, "safe_cms": SAFE_CMS}, {}
    runs = [("static", {}), ("rule", {}),
            ("predict", {"guard": 0.85}),
            ("predict_aggressive", {"guard": 1.1})]
    for name, kw in runs:
        strat = "predict" if name.startswith("predict") else name
        df = run_strategy(args.inp, strat, rain, **kw)
        report[name] = metrics(df)
        curves[name] = df["plant_cms"]
        print(f"[{name}] {report[name]}")

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=2))
    pd.DataFrame(curves).to_csv("reports/swmm_control_curves.csv")
    print(f"-> {args.out}")


if __name__ == "__main__":
    main()
