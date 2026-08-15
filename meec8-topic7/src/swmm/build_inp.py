"""概化 SWMM 模型构建：6 泵站汇流单元（子汇水区 + DWF + 前池调蓄 +
可控泵 → 干线级联 → 厂前节点），产物 INP 供 src.control.rolling_opt 使用。

用法：
  python -m src.swmm.build_inp --rain-csv data/processed/design_storm_p50_10min.csv --out data/swmm/taihe_p50.inp
"""
import argparse
from pathlib import Path

import pandas as pd

# 6 概化泵站单元：面积 ha、不透水率 %、旱天污水 m3/s、前池容积概化
UNITS = [  # (name, area_ha, imperv, dwf_cms, storage_area_m2, max_depth_m)
    ("U1", 80, 55, 0.30, 2500, 5.0),
    ("U2", 65, 60, 0.25, 2000, 5.0),
    ("U3", 50, 65, 0.20, 1600, 4.5),
    ("U4", 40, 60, 0.15, 1200, 4.5),
    ("U5", 30, 70, 0.12, 1000, 4.0),
    ("U6", 25, 65, 0.10, 800, 4.0),
]
PUMP_CAP_CMS = [1.6, 1.3, 1.0, 0.8, 0.6, 0.5]  # 合计 5.8 m3/s（÷7 概化 40.5）


def rain_timeseries(rain_csv: str, start: str, days: int) -> str:
    df = pd.read_csv(rain_csv, index_col=0, parse_dates=True)
    col = df.columns[0]
    s = df[col].loc[start:].iloc[:days * 144].fillna(0.0)  # mm/10min
    lines = [f"RG1 {t.strftime('%m/%d/%Y %H:%M')} {v:.3f}"
             for t, v in s.items()]  # VOLUME 雨量计：每记录间隔的雨深 mm
    return "\n".join(lines), s.index[0]


def build_inp(rain_csv: str, start: str, days: int) -> str:
    ts, t0 = rain_timeseries(rain_csv, start, days)
    t_end = t0 + pd.Timedelta(days=days)
    sub, jn, st, pu, co, dwf = [], [], [], [], [], []
    for i, (n, area, imp, q_dwf, s_area, s_depth) in enumerate(UNITS):
        sub.append(f"S_{n} RG1 ST_{n} {area} {imp} 500 0.5 0")
        st.append(f"ST_{n} 0 {s_depth} 0 FUNCTIONAL 0 0 {s_area}")
        jn.append(f"J_{n} 0 3")
        pu.append(f"P_{n} ST_{n} J_{n} PC_{n} ON 0.3 0.1")
        dwf.append(f"ST_{n} FLOW {q_dwf}")
        nxt = f"J_{UNITS[i + 1][0]}" if i + 1 < len(UNITS) else "PLANT"
        co.append(f"C_{n} J_{n} {nxt} 1200 0.013 0 0 0 0")
    curves = "\n".join(f"PC_{n} Pump1 0 {c}" for (n, *_), c
                       in zip(UNITS, PUMP_CAP_CMS))
    return f"""[TITLE]
泰和概化厂站网 SWMM 模型（6 泵站单元级联）

[OPTIONS]
FLOW_UNITS CMS
INFILTRATION HORTON
FLOW_ROUTING DYNWAVE
START_DATE {t0.strftime('%m/%d/%Y')}
START_TIME {t0.strftime('%H:%M')}
REPORT_START_DATE {t0.strftime('%m/%d/%Y')}
REPORT_START_TIME {t0.strftime('%H:%M')}
END_DATE {t_end.strftime('%m/%d/%Y')}
END_TIME {t_end.strftime('%H:%M')}
ROUTING_STEP 30
REPORT_STEP 00:05:00
WET_STEP 00:05:00
DRY_STEP 00:05:00

[RAINGAGES]
RG1 VOLUME 0:10 1.0 TIMESERIES RAIN

[SUBCATCHMENTS]
;;Name Gage Outlet Area %Imperv Width Slope CurbLen
{chr(10).join(sub)}

[SUBAREAS]
;;Sub N-Imperv N-Perv S-Imperv S-Perv %Zero
{chr(10).join(f'S_{n} 0.013 0.15 1.5 5 25 OUTLET' for n, *_ in UNITS)}

[INFILTRATION]
{chr(10).join(f'S_{n} 3.0 0.5 4 7 0' for n, *_ in UNITS)}

[JUNCTIONS]
;;Name Elev MaxDepth
{chr(10).join(jn)}

[OUTFALLS]
PLANT -1 FREE NO

[STORAGE]
;;Name Elev MaxDepth InitDepth Shape A B C
{chr(10).join(st)}

[CONDUITS]
;;Name From To Length Roughness InOff OutOff InitFlow MaxFlow
{chr(10).join(co)}

[XSECTIONS]
;;Link Shape Geom1 Geom2 Geom3 Geom4 Barrels
{chr(10).join(f'C_{n} CIRCULAR 2.5 0 0 0 1' for n, *_ in UNITS)}

[PUMPS]
;;Name From To Curve Status Startup Shutoff
{chr(10).join(pu)}

[CURVES]
;;Name Type X Y
{curves}

[DWF]
;;Node Type Avg
{chr(10).join(dwf)}

[TIMESERIES]
;;Name Date Time Value
{chr(10).join('RAIN ' + l.split(' ', 1)[1] for l in ts.splitlines())}

[REPORT]
CONTROLS NO
INPUT NO
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rain-csv",
                    default="data/processed/design_storm_p50_10min.csv")
    ap.add_argument("--start", default="2025-07-01")
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--out", default="data/swmm/taihe_p50.inp")
    args = ap.parse_args()
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(build_inp(args.rain_csv, args.start, args.days))
    print(f"-> {args.out}")


if __name__ == "__main__":
    main()
