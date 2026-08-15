"""进厂水量水质超前预测：LightGBM 点预测 + P10/P90 分位数区间，
基线为 persistence / 季节朴素 / MLP，指标 MAE / RMSE / NSE / PICP / MPIW。

用法：
  python -m src.models.forecast --dataset koeln --horizons 4 8 12
  python -m src.models.forecast --dataset taihe --horizons 12 24 36
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path
from urllib.request import urlretrieve

import numpy as np
import pandas as pd
from lightgbm import LGBMRegressor
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import StandardScaler

LAGS = [1, 2, 3, 4, 6, 8, 12, 24]  # 以步为单位的滞后


def _metrics(y, yhat) -> dict:
    err = yhat - y
    mae = float(np.mean(np.abs(err)))
    rmse = float(np.sqrt(np.mean(err ** 2)))
    nse = float(1 - np.sum(err ** 2) / np.sum((y - y.mean()) ** 2))
    return {"MAE": round(mae, 2), "RMSE": round(rmse, 2), "NSE": round(nse, 4)}


def build_features(df: pd.DataFrame, target: str, exog: list[str], horizon: int):
    """滞后特征 + 时刻特征 → (X, y)，y 为 target 未来 horizon 步。"""
    feat = {}
    for c in [target] + exog:
        for l in LAGS:
            feat[f"{c}_lag{l}"] = df[c].shift(l - 1)
        feat[f"{c}_diff"] = df[c].diff()
        feat[f"{c}_roll6"] = df[c].rolling(6).mean()
    idx = df.index
    feat["hour"] = idx.hour + idx.minute / 60
    feat["dow"] = idx.dayofweek
    X = pd.DataFrame(feat, index=idx)
    y = df[target].shift(-horizon)
    valid = X.notna().all(axis=1) & y.notna()
    return X[valid], y[valid]


def _quantile_models(Xtr, ytr, Xte):
    bounds = {}
    for alpha in (0.1, 0.9):
        m = LGBMRegressor(objective="quantile", alpha=alpha, n_estimators=300,
                          learning_rate=0.05, num_leaves=63, verbose=-1)
        m.fit(Xtr, ytr)
        bounds[alpha] = m.predict(Xte)
    return bounds[0.1], bounds[0.9]


def run(name: str, df: pd.DataFrame, target: str, exog: list[str],
        horizons: list[int], step_min: int) -> list[dict]:
    steps_per_day = 24 * 60 // step_min
    results = []
    for h in horizons:
        X, y = build_features(df, target, exog, h)
        split = int(len(X) * 0.75)
        Xtr, Xte, ytr, yte = X[:split], X[split:], y[:split], y[split:]
        model = LGBMRegressor(n_estimators=400, learning_rate=0.05,
                              num_leaves=63, verbose=-1)
        model.fit(Xtr, ytr)
        pred = model.predict(Xte)
        # 基线 1：persistence；基线 2：季节朴素（昨日同刻）；基线 3：MLP
        persist = Xte[f"{target}_lag1"].to_numpy()
        seasonal = df[target].shift(steps_per_day - h).reindex(yte.index).to_numpy()
        scaler = StandardScaler().fit(Xtr)
        mlp = MLPRegressor(hidden_layer_sizes=(64, 32), max_iter=200,
                           early_stopping=True, random_state=7)
        mlp.fit(scaler.transform(Xtr), ytr)
        mlp_pred = mlp.predict(scaler.transform(Xte))
        # 分位数区间 P10–P90
        lo, hi = _quantile_models(Xtr, ytr, Xte)
        yv = yte.to_numpy()
        picp = float(np.mean((yv >= lo) & (yv <= hi)))
        mpiw = float(np.mean(hi - lo))
        r = {"dataset": name, "target": target,
             "horizon_min": h * step_min,
             "n_train": len(Xtr), "n_test": len(Xte),
             "model": _metrics(yv, pred),
             "mlp": _metrics(yv, mlp_pred),
             "seasonal_naive": _metrics(yv[~np.isnan(seasonal)],
                                        seasonal[~np.isnan(seasonal)]),
             "persistence": _metrics(yv, persist),
             "interval": {"PICP_80": round(picp, 3), "MPIW": round(mpiw, 1)}}
        if "rain" in df.columns:  # 雨天子集分层评估
            rain_mask = df["rain"].reindex(yte.index).to_numpy() > 0
            if rain_mask.sum() > 50:
                r["model_rainy"] = _metrics(yv[rain_mask], pred[rain_mask])
        results.append(r)
        print(f"[{name}] {target} +{h * step_min}min  "
              f"LGBM NSE={r['model']['NSE']} | MLP {r['mlp']['NSE']} | "
              f"seasonal {r['seasonal_naive']['NSE']} | "
              f"persist {r['persistence']['NSE']} | PICP80={picp:.2f}")
    return results


KOELN_CSV = "data/external/zenodo_6992694_koeln_wtp_network_rain/wtp_network_rain.csv"
KOELN_URL = ("https://zenodo.org/api/records/6992694/files/"
             "wtp_network_rain.csv/content")


def ensure_koeln():
    """Köln 数据集（Zenodo 6992694，CC-BY-4.0，约 10MB）缺失时自动下载。"""
    p = Path(KOELN_CSV)
    if p.exists():
        return
    p.parent.mkdir(parents=True, exist_ok=True)
    print(f"[koeln] 本地未找到数据集，正从 Zenodo 下载… -> {p}")
    urlretrieve(KOELN_URL, p)


def load_koeln() -> pd.DataFrame:
    ensure_koeln()
    df = pd.read_csv(
        KOELN_CSV,
        sep=";", parse_dates=["Timestamp"], index_col="Timestamp")
    df.columns = ["rain", "level1", "level2", "level3", "level_storage", "inflow"]
    return df.astype(float).interpolate(limit=4).dropna()


def ensure_taihe(sim_dir: str, days: int = 92):
    """模拟数据缺失时自动生成（优先实测降雨，否则合成降雨）。"""
    if Path(sim_dir, "plant_inflow_quality.csv").exists():
        return
    print(f"[taihe] {sim_dir} 不存在，自动生成 {days} 天模拟数据…")
    rain_csv = "data/processed/shanghai_rain_10min.csv"
    cmd = [sys.executable, "-m", "src.simulation.generate",
           "--days", str(days), "--out", sim_dir]
    if Path(rain_csv).exists():
        cmd += ["--rain-csv", rain_csv, "--rain-start", "2024-06-01"]
    else:
        print("[taihe] 未找到上海实测雨量，改用合成降雨驱动模拟")
    subprocess.run(cmd, check=True)


def load_taihe(sim_dir: str) -> pd.DataFrame:
    ensure_taihe(sim_dir)
    q = pd.read_csv(f"{sim_dir}/plant_inflow_quality.csv", parse_dates=["time"],
                    index_col="time")
    w = pd.read_csv(f"{sim_dir}/weather.csv", parse_dates=["time"], index_col="time")
    lv = pd.read_csv(f"{sim_dir}/node_levels.csv", parse_dates=["time"], index_col="time")
    up_nodes = lv.columns[:4]  # 上游代表节点
    df = pd.DataFrame({
        "inflow": q["inflow_m3h"], "cod": q["cod_mg_l"],
        "cod_load": q["cod_mg_l"] * q["inflow_m3h"] / 1000.0,  # kg/h
        "nh3n": q["nh3n_mg_l"],
        "nh3n_load": q["nh3n_mg_l"] * q["inflow_m3h"] / 1000.0,  # kg/h
        "ph": q["ph"], "ss": q["ss_mg_l"],
        "rain": w["rain_mm_h"],
        **{f"lvl_{c}": lv[c] for c in up_nodes},
    })
    return df.dropna()


def predict_series(horizon_min: int = 120,
                   sim_dir: str = "data/simulated_realrain"):
    """泰和场景在线预测输出：返回测试段 (P50, P90, 真值)，索引为发布时刻。

    预警链路以此为输入（发布时刻 t 的值 = 对 t+horizon 的预测）。
    """
    df = load_taihe(sim_dir)
    step = 5
    h = horizon_min // step
    exog = ["rain"] + [c for c in df.columns if c.startswith("lvl_")]
    X, y = build_features(df, "inflow", exog, h)
    split = int(len(X) * 0.75)
    model = LGBMRegressor(n_estimators=400, learning_rate=0.05,
                          num_leaves=63, verbose=-1)
    model.fit(X[:split], y[:split])
    p50 = pd.Series(model.predict(X[split:]), index=y[split:].index)
    q90 = LGBMRegressor(objective="quantile", alpha=0.9, n_estimators=300,
                        learning_rate=0.05, num_leaves=63, verbose=-1)
    q90.fit(X[:split], y[:split])
    p90 = pd.Series(q90.predict(X[split:]), index=y[split:].index)
    return p50, p90, y[split:]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", choices=["koeln", "taihe"], required=True)
    ap.add_argument("--horizons", type=int, nargs="+", default=None,
                    help="预测超前步数（koeln 15min/步，taihe 5min/步）")
    ap.add_argument("--sim-dir", default="data/simulated_realrain")
    ap.add_argument("--out", default="reports/forecast_metrics.json")
    args = ap.parse_args()

    if args.dataset == "koeln":
        df = load_koeln()
        horizons = args.horizons or [4, 8, 12]      # 1h/2h/3h @15min
        results = run("koeln", df, "inflow",
                      ["rain", "level1", "level2", "level3", "level_storage"],
                      horizons, 15)
    else:
        df = load_taihe(args.sim_dir)
        horizons = args.horizons or [12, 24, 36]    # 1h/2h/3h @5min
        exog = ["rain"] + [c for c in df.columns if c.startswith("lvl_")]
        results = run("taihe", df, "inflow", exog, horizons, 5)
        results += run("taihe", df, "cod", exog + ["inflow"], horizons, 5)
        results += run("taihe", df, "cod_load", exog + ["inflow"], horizons, 5)
        results += run("taihe", df, "nh3n_load", exog + ["inflow"], horizons, 5)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    existing = json.loads(out.read_text()) if out.exists() else []
    existing = [r for r in existing if r["dataset"] != args.dataset]
    out.write_text(json.dumps(existing + results, ensure_ascii=False, indent=1))
    print(f"-> {out}")


if __name__ == "__main__":
    main()
