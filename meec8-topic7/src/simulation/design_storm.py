"""设计暴雨生成：上海市暴雨强度公式 + 芝加哥雨型。

上海市暴雨强度公式（DB31/T 1043）：
    q = 1600·(1+0.846·lgP) / (t+7.0)^0.656   [L/(s·ha)]
换算 1 L/(s·ha) = 0.006 mm/min。

生成指定重现期 P（年）、历时 duration 的芝加哥过程线（雨峰系数 r），
嵌入 7 天干燥背景（第 4 天 18:00 起爆发），输出与
data/processed/shanghai_rain_10min.csv 相同格式（mm/10min，rain_citymean 列），
可直接被 src.simulation.generate --rain-csv 消费。

用法：
  python -m src.simulation.design_storm --return-periods 5 50 100
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

R_PEAK = 0.405  # 上海常用雨峰位置系数


def intensity_mm_min(t_min: np.ndarray, p_year: float) -> np.ndarray:
    """暴雨强度公式：历时 t（min）内平均强度 mm/min。"""
    q = 1600.0 * (1 + 0.846 * np.log10(p_year)) / (t_min + 7.0) ** 0.656
    return q * 0.006


def chicago_hyetograph(p_year: float, duration_min: int = 120,
                       step_min: int = 10, r: float = R_PEAK) -> np.ndarray:
    """芝加哥过程线：返回每步雨量 mm（长度 duration/step）。

    瞬时强度由 i_avg=A/(t+b)^n 微分得到（标准 Keifer-Chu 公式）：
      峰前 i(τ)=A[(1-n)τ/r + b] / (τ/r + b)^(n+1)，τ 为距峰时间；
      峰后同式以 (1-r) 替换 r。峰值位于 r·duration 处。
    """
    a_coef = 1600.0 * (1 + 0.846 * np.log10(p_year)) * 0.006
    b, n = 7.0, 0.656
    tp = duration_min * r
    t_fine = np.arange(0.0, duration_min, 0.1)
    tau = np.where(t_fine < tp, (tp - t_fine) / r, (t_fine - tp) / (1 - r))
    i_fine = a_coef * ((1 - n) * tau + b) / (tau + b) ** (n + 1)  # mm/min
    depth_fine = i_fine * 0.1
    n_steps = duration_min // step_min
    return depth_fine.reshape(n_steps, -1).sum(axis=1)


def build_scenario(p_year: float, days: int = 7, step_min: int = 10,
                   start: str = "2025-07-01") -> pd.Series:
    n = days * 24 * 60 // step_min
    t = pd.date_range(start, periods=n, freq=f"{step_min}min")
    rain = np.zeros(n)
    storm = chicago_hyetograph(p_year, step_min=step_min)
    i0 = (3 * 24 + 18) * 60 // step_min  # 第 4 天 18:00
    rain[i0:i0 + len(storm)] = storm
    return pd.Series(rain, index=t, name="rain_citymean")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--return-periods", type=float, nargs="+",
                    default=[5, 50, 100])
    ap.add_argument("--out-dir", default="data/processed")
    args = ap.parse_args()
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for p in args.return_periods:
        s = build_scenario(p)
        path = out / f"design_storm_p{int(p)}_10min.csv"
        s.to_frame().to_csv(path)
        print(f"P={int(p)}a 2h 总雨量 {s.sum():.1f} mm，峰值 "
              f"{s.max():.1f} mm/10min -> {path}")


if __name__ == "__main__":
    main()
