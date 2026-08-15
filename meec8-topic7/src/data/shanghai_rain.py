"""上海市水务局「水情信息」清洗与驱动序列构建。

输入：data/external/shgov_water_regime/shuiqing_001/002.zip
      （全市 52 站 10~15 分钟级 rain/waterlevel/sealevel，2021-01 ~ 2025-09）
输出：data/processed/
  - shanghai_rain_10min.csv    全市平均雨量 + 代表站雨量（10min 栅格）
  - shanghai_waterlevel_10min.csv  代表站水位
  - station_summary.csv        各站覆盖统计

用法：
  python -m src.data.shanghai_rain
"""
from pathlib import Path
import zipfile

import numpy as np
import pandas as pd

RAW_DIR = Path("data/external/shgov_water_regime")
OUT_DIR = Path("data/processed")

# 苏州河/黄浦江沿线与市区代表站（覆盖泰和系统上游区域的空间代表）
KEY_STATIONS = ["吴淞口", "黄浦公园", "米市渡", "青浦南门", "嘉定南门", "崇明南门"]


def load_raw() -> pd.DataFrame:
    frames = []
    for z in sorted(RAW_DIR.glob("shuiqing_*.zip")):
        with zipfile.ZipFile(z) as zf:
            for name in zf.namelist():
                with zf.open(name) as f:
                    frames.append(pd.read_csv(
                        f, usecols=["datatime", "rain", "stationname", "waterlevel"],
                        dtype={"rain": "float32", "waterlevel": "float32"}))
    df = pd.concat(frames, ignore_index=True)
    df["datatime"] = pd.to_datetime(df["datatime"])
    return df


def build(df: pd.DataFrame) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    summary = (df.groupby("stationname")
                 .agg(n=("rain", "size"),
                      start=("datatime", "min"), end=("datatime", "max"),
                      rain_nonzero=("rain", lambda s: int((s > 0).sum())),
                      rain_max=("rain", "max"))
                 .sort_values("n", ascending=False))
    summary.to_csv(OUT_DIR / "station_summary.csv", encoding="utf-8-sig")

    grid = df.set_index("datatime").sort_index()
    rain_wide = (grid.pivot_table(index="datatime", columns="stationname",
                                  values="rain", aggfunc="mean")
                     .resample("10min").mean())
    out = pd.DataFrame(index=rain_wide.index)
    out["rain_citymean"] = rain_wide.mean(axis=1)
    for s in KEY_STATIONS:
        if s in rain_wide.columns:
            out[f"rain_{s}"] = rain_wide[s]
    out.to_csv(OUT_DIR / "shanghai_rain_10min.csv", encoding="utf-8-sig")

    wl_wide = (grid.pivot_table(index="datatime", columns="stationname",
                                values="waterlevel", aggfunc="mean")
                   .resample("10min").mean())
    cols = [s for s in KEY_STATIONS if s in wl_wide.columns]
    wl_wide[cols].to_csv(OUT_DIR / "shanghai_waterlevel_10min.csv", encoding="utf-8-sig")


def main():
    df = load_raw()
    build(df)
    print(f"rows={len(df)}, stations={df['stationname'].nunique()}, "
          f"span={df['datatime'].min()} -> {df['datatime'].max()}")


if __name__ == "__main__":
    main()
