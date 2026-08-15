"""批量生成技术报告 / PPT / 看板所需图表。

输出目录：reports/figures/
用法：python -m src.viz.make_figures
前置：已按 README 快速开始跑完 ①~⑤（存在 data/processed 与 data/simulated_realrain）。
"""
import json
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from lightgbm import LGBMRegressor

from src.models.forecast import (_quantile_models, build_features, load_koeln,
                                 load_taihe)

matplotlib.rcParams["font.sans-serif"] = ["WenQuanYi Zen Hei", "Noto Sans CJK SC"]
matplotlib.rcParams["axes.unicode_minus"] = False

OUT = Path("reports/figures")
LEVEL_COLORS = {"正常": "#c8e6c9", "蓝色": "#90caf9", "黄色": "#fff176",
                "橙色": "#ffb74d", "红色": "#e57373"}


def _save(fig, name: str):
    fig.tight_layout()
    fig.savefig(OUT / name, dpi=150)
    plt.close(fig)
    print("->", OUT / name)


def fig_rain_overview():
    r = pd.read_csv("data/processed/shanghai_rain_10min.csv",
                    index_col=0, parse_dates=True)
    daily = r["rain_citymean"].resample("D").sum()
    fig, axes = plt.subplots(2, 1, figsize=(11, 6))
    axes[0].bar(daily.index, daily.values, width=1, color="#1976d2")
    axes[0].set_title("上海水务局「水情信息」全市日均雨量 2021–2025（52 站 10min 数据聚合）")
    axes[0].set_ylabel("日雨量 mm")
    z = r.loc["2024-06-01":"2024-08-31", "rain_citymean"]
    axes[1].plot(z.index, z.values, lw=0.5, color="#1976d2")
    axes[1].set_title("2024 汛期（6–8 月）10 分钟级雨量 —— 模拟场景驱动序列")
    axes[1].set_ylabel("10min 雨量 mm")
    _save(fig, "fig01_上海降雨概览.png")


def fig_pump_capacity():
    df = pd.read_csv("data/raw/Date1_泵站配泵能力.csv")
    df = df.sort_values("设计能力_m3s", ascending=False)
    fig, ax = plt.subplots(figsize=(11, 4.5))
    ax.bar(df["泵站"], df["设计能力_m3s"], color="#00796b")
    ax.set_title(f"Date1：泰和污水厂上游 {len(df)} 座泵站配泵能力（合计 "
                 f"{df['设计能力_m3s'].sum():.1f} m³/s）")
    ax.set_ylabel("设计能力 m³/s")
    ax.set_xlabel("泵站（A–Z）")
    _save(fig, "fig02_泵站配泵能力.png")


def fig_topology():
    nodes = pd.read_csv("data/simulated_realrain/topology_nodes.csv")
    links = pd.read_csv("data/simulated_realrain/topology_links.csv")
    # 干线沿 x 轴按距厂距离排布，支线错开 y
    pos = {}
    trunk = nodes[nodes.kind == "trunk"].sort_values("dist_to_plant_km",
                                                     ascending=False)
    for i, r in enumerate(trunk.itertuples()):
        pos[r.node_id] = (-r.dist_to_plant_km, 0)
    rng = np.random.default_rng(7)
    for r in nodes[nodes.kind != "trunk"].itertuples():
        pos[r.node_id] = (-r.dist_to_plant_km,
                          float(rng.uniform(0.6, 2.4)) * (1 if rng.random() > .5 else -1))
    fig, ax = plt.subplots(figsize=(11, 4.5))
    for r in links.itertuples():
        if r.from_node in pos and r.to_node in pos:
            x = [pos[r.from_node][0], pos[r.to_node][0]]
            y = [pos[r.from_node][1], pos[r.to_node][1]]
            ax.plot(x, y, color="#90a4ae", lw=max(r.diameter_mm / 1500, 0.4), zorder=1)
    kinds = {"trunk": ("#1565c0", "干线节点"), "branch": ("#26a69a", "支线节点"),
             "pump": ("#e53935", "泵站")}
    for k, (c, label) in kinds.items():
        sub = nodes[nodes.kind == k]
        xy = np.array([pos[n] for n in sub.node_id if n in pos])
        if len(xy):
            ax.scatter(xy[:, 0], xy[:, 1], s=60 if k == "pump" else 25,
                       color=c, label=label, zorder=2)
    ax.scatter([0], [0], marker="*", s=380, color="#6a1b9a", zorder=3, label="泰和污水厂")
    ax.legend(loc="upper left", ncol=4)
    ax.set_title("模拟管网骨架：43 节点 / 42 管段 / 6 泵站（按距厂距离概化布置）")
    ax.set_xlabel("距厂距离 km（负向为上游）")
    ax.set_yticks([])
    _save(fig, "fig03_管网拓扑骨架.png")


def fig_scenario():
    q = pd.read_csv("data/simulated_realrain/plant_inflow_quality.csv",
                    parse_dates=["time"], index_col="time")
    w = pd.read_csv("data/simulated_realrain/weather.csv",
                    parse_dates=["time"], index_col="time")
    s, e = "2024-06-16", "2024-06-30"
    fig, axes = plt.subplots(3, 1, figsize=(11, 7), sharex=True)
    axes[0].plot(w.loc[s:e].index, w.loc[s:e, "rain_mm_h"], color="#1976d2", lw=0.8)
    axes[0].set_ylabel("雨强 mm/h")
    axes[0].set_title("实测降雨驱动的泰和模拟场景（2024-06 梅雨期两周）")
    axes[1].plot(q.loc[s:e].index, q.loc[s:e, "inflow_m3h"], color="#00796b", lw=0.8)
    axes[1].set_ylabel("进水流量 m³/h")
    axes[2].plot(q.loc[s:e].index, q.loc[s:e, "cod_mg_l"], color="#8d6e63", lw=0.8)
    axes[2].set_ylabel("COD mg/L")
    _save(fig, "fig04_实测降雨驱动模拟场景.png")


def _fit_predict(df, target, exog, horizon):
    X, y = build_features(df, target, exog, horizon)
    split = int(len(X) * 0.75)
    model = LGBMRegressor(n_estimators=400, learning_rate=0.05,
                          num_leaves=63, verbose=-1)
    model.fit(X[:split], y[:split])
    pred = pd.Series(model.predict(X[split:]), index=y[split:].index)
    return y[split:], pred, model, X.columns


def fig_koeln_forecast():
    df = load_koeln()
    exog = ["rain", "level1", "level2", "level3", "level_storage"]
    y, pred, model, cols = _fit_predict(df, "inflow", exog, 4)  # +1h
    z = slice(-96 * 7, None)  # 测试集最后 7 天
    fig, ax = plt.subplots(figsize=(11, 4.2))
    ax.plot(y.index[z], y.values[z], label="实测进水流量", color="#37474f", lw=1)
    ax.plot(pred.index[z], pred.values[z], label="模型预测（+1h）",
            color="#e53935", lw=1)
    ax.set_title("Köln-Weiden 真实厂-网-雨数据：+1h 进水流量预测（测试集末 7 天，NSE 0.94）")
    ax.set_ylabel("进水流量 L/s")
    ax.legend()
    _save(fig, "fig05_Koeln超前预测.png")

    imp = pd.Series(model.feature_importances_, index=cols).nlargest(15)[::-1]
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.barh(imp.index, imp.values, color="#5e35b1")
    ax.set_title("Köln +1h 预测模型特征重要性 Top15（管网液位/降雨滞后主导）")
    _save(fig, "fig06_特征重要性.png")


def fig_taihe_forecast():
    df = load_taihe("data/simulated_realrain")
    exog = ["rain"] + [c for c in df.columns if c.startswith("lvl_")]
    y, pred, *_ = _fit_predict(df, "inflow", exog, 24)  # +2h
    z = slice(-288 * 7, None)
    fig, ax = plt.subplots(figsize=(11, 4.2))
    ax.plot(y.index[z], y.values[z], label="场景真值", color="#37474f", lw=0.9)
    ax.plot(pred.index[z], pred.values[z], label="模型预测（+2h）",
            color="#e53935", lw=0.9)
    ax.set_title("泰和模拟场景（26 泵站骨架 × 上海实测降雨）：+2h 进水流量预测（NSE 0.92）")
    ax.set_ylabel("进水流量 m³/h")
    ax.legend()
    _save(fig, "fig07_泰和场景预测.png")


def fig_metrics_bar():
    import json
    res = json.loads(Path("reports/forecast_metrics.json").read_text())
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    for ax, ds, title in [(axes[0], "koeln", "Köln 真实数据（inflow）"),
                          (axes[1], "taihe", "泰和模拟场景（inflow）")]:
        rows = [r for r in res if r["dataset"] == ds and r["target"] == "inflow"]
        hs = [r["horizon_min"] for r in rows]
        x = np.arange(len(hs))
        ax.bar(x - 0.18, [r["model"]["NSE"] for r in rows], 0.36,
               label="LightGBM", color="#00796b")
        ax.bar(x + 0.18, [r["persistence"]["NSE"] for r in rows], 0.36,
               label="Persistence 基线", color="#b0bec5")
        ax.set_xticks(x, [f"+{h}min" for h in hs])
        ax.set_ylim(-0.7, 1.05)
        ax.axhline(0, color="k", lw=0.5)
        ax.set_title(title)
        ax.set_ylabel("NSE")
        ax.legend()
    _save(fig, "fig08_预测指标对比.png")


def fig_koeln_interval():
    df = load_koeln()
    exog = ["rain", "level1", "level2", "level3", "level_storage"]
    X, y = build_features(df, "inflow", exog, 4)
    split = int(len(X) * 0.75)
    lo, hi = _quantile_models(X[:split], y[:split], X[split:])
    yte = y[split:]
    picp = float(np.mean((yte.to_numpy() >= lo) & (yte.to_numpy() <= hi)))
    z = slice(-96 * 7, None)
    fig, ax = plt.subplots(figsize=(11, 4.2))
    ax.fill_between(yte.index[z], lo[z], hi[z], color="#ef9a9a", alpha=0.5,
                    label="P10–P90 预测区间")
    ax.plot(yte.index[z], yte.values[z], color="#37474f", lw=1, label="实测进水流量")
    ax.set_title(f"概率预测：Köln +1h 分位数区间（全测试集覆盖率 PICP={picp:.0%}，名义 80%）")
    ax.set_ylabel("进水流量 L/s")
    ax.legend()
    _save(fig, "fig10_概率预测区间.png")


def fig_model_comparison():
    import json
    res = json.loads(Path("reports/forecast_metrics.json").read_text())
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    keys = [("model", "LightGBM", "#00796b"), ("mlp", "MLP 神经网络", "#5e35b1"),
            ("seasonal_naive", "季节朴素", "#8d6e63"),
            ("persistence", "Persistence", "#b0bec5")]
    for ax, ds, title in [(axes[0], "koeln", "Köln 真实数据（inflow）"),
                          (axes[1], "taihe", "泰和模拟场景（inflow）")]:
        rows = [r for r in res if r["dataset"] == ds and r["target"] == "inflow"
                and "mlp" in r]
        hs = [r["horizon_min"] for r in rows]
        x = np.arange(len(hs))
        w = 0.2
        for i, (k, label, c) in enumerate(keys):
            ax.bar(x + (i - 1.5) * w, [r[k]["NSE"] for r in rows], w,
                   label=label, color=c)
        ax.set_xticks(x, [f"+{h}min" for h in hs])
        ax.set_ylim(-1.1, 1.05)
        ax.axhline(0, color="k", lw=0.5)
        ax.set_title(title)
        ax.set_ylabel("NSE")
        ax.legend(fontsize=8)
    _save(fig, "fig11_多模型对比.png")


def fig_cod_load():
    import json
    res = json.loads(Path("reports/forecast_metrics.json").read_text())
    rows = {t: [r for r in res if r["dataset"] == "taihe" and r["target"] == t
                and "mlp" in r] for t in ("cod", "cod_load")}
    hs = [r["horizon_min"] for r in rows["cod"]]
    x = np.arange(len(hs))
    fig, ax = plt.subplots(figsize=(8, 4.2))
    ax.bar(x - 0.18, [r["model"]["NSE"] for r in rows["cod"]], 0.36,
           label="COD 浓度 mg/L", color="#8d6e63")
    ax.bar(x + 0.18, [r["model"]["NSE"] for r in rows["cod_load"]], 0.36,
           label="COD 负荷 kg/h（浓度×流量）", color="#00796b")
    ax.set_xticks(x, [f"+{h}min" for h in hs])
    ax.axhline(0, color="k", lw=0.5)
    ax.set_ylim(-0.3, 1.0)
    ax.set_ylabel("NSE")
    ax.set_title("水质预测口径优化：预测 COD 负荷显著优于预测浓度（泰和场景）")
    ax.legend()
    _save(fig, "fig12_COD负荷口径.png")


def fig_stress_test():
    rep = json.loads(Path("reports/stress_test.json").read_text())
    curves = pd.read_csv("reports/stress_p100_curves.csv",
                         index_col=0, parse_dates=True)
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.2),
                             gridspec_kw={"width_ratios": [3, 2]})
    z = curves.loc["2025-07-04 12:00":"2025-07-05 12:00"]
    axes[0].plot(z.index, z["truth"], color="#37474f", lw=1.4, label="真值")
    axes[0].plot(z.index, z["base_model"], color="#e57373", lw=1.1,
                 label="基准训练模型（峰值低估 47%）")
    axes[0].plot(z.index, z["aug_model"], color="#00796b", lw=1.1,
                 label="+P50 设计暴雨增广（低估 13%）")
    axes[0].set_title("P=100a 设计暴雨压力测试（+2h 预测，芝加哥雨型 2h）")
    axes[0].set_ylabel("进水流量 m³/h")
    axes[0].legend(fontsize=9)
    names = ["design_p5", "design_p50", "design_p100", "typhoon_infa"]
    labels = ["P=5a", "P=50a", "P=100a", "台风烟花\n(2021实况)"]
    base_nse = [rep[n]["NSE"] for n in names]
    aug_nse = [rep["augmented"].get(n, {}).get("NSE") for n in names]
    x = np.arange(len(names))
    axes[1].bar(x - 0.18, base_nse, 0.36, color="#e57373", label="基准训练")
    axes[1].bar([i + 0.18 for i, v in enumerate(aug_nse) if v is not None],
                [v for v in aug_nse if v is not None], 0.36,
                color="#00796b", label="暴雨增广后")
    axes[1].set_xticks(x, labels, fontsize=9)
    axes[1].set_ylabel("NSE")
    axes[1].set_ylim(0, 1)
    axes[1].set_title("跨场景泛化 NSE")
    axes[1].legend(fontsize=9)
    _save(fig, "fig13_极端场景压力测试.png")


def fig_swmm_control():
    curves = pd.read_csv("reports/swmm_control_curves.csv",
                         index_col=0, parse_dates=True)
    z = curves.loc["2025-07-04 18:00":"2025-07-05 12:00"]
    fig, ax = plt.subplots(figsize=(11, 4.2))
    ax.plot(z.index, z["static"], color="#e57373", lw=1.2, label="无调控（泵常开）")
    ax.plot(z.index, z["rule"], color="#ffb300", lw=1.2, label="本地液位规则")
    ax.plot(z.index, z["predict_aggressive"], color="#00796b", lw=1.4,
            label="预见性滚动调度（超阈体积降89%）")
    ax.axhline(4.5, color="#e53935", ls="--", lw=1, label="厂前安全输送阈值 4.5 m³/s")
    ax.set_title("SWMM 在环三策略调度对比（P=50a 设计暴雨，6 泵站概化级联）")
    ax.set_ylabel("厂前入流 m³/s")
    ax.legend(fontsize=9)
    _save(fig, "fig14_SWMM调度对比.png")


def fig_warning_timeline():
    rep = pd.read_csv("reports/warning_demo.csv", parse_dates=["time"],
                      index_col="time")
    s, e = "2024-08-13", "2024-08-23"  # 测试段（预测模型在线输出）内的强降雨窗口
    z = rep.loc[s:e]
    fig, ax = plt.subplots(figsize=(11, 4.2))
    ax.plot(z.index, z["forecast_inflow_m3h"], color="#37474f", lw=0.9,
            label="预测进厂流量（提前 120min）")
    for lv, c in LEVEL_COLORS.items():
        if lv == "正常":
            continue
        m = z["warning_level"] == lv
        ax.fill_between(z.index, 0, z["forecast_inflow_m3h"].max() * 1.05,
                        where=m, color=c, alpha=0.55, label=f"{lv}预警")
    ax.axhline(8000, color="#e53935", ls="--", lw=1, label="厂设计能力 8000 m³/h")
    ax.set_title("四级预警时间线（模型 P90 预测驱动，2024-08 测试段，提前量 120min）")
    ax.set_ylabel("m³/h")
    ax.legend(ncol=3, fontsize=8)
    _save(fig, "fig09_预警时间线.png")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    fig_rain_overview()
    fig_pump_capacity()
    fig_topology()
    fig_scenario()
    fig_koeln_forecast()
    fig_taihe_forecast()
    fig_metrics_bar()
    fig_warning_timeline()
    fig_koeln_interval()
    fig_model_comparison()
    fig_cod_load()
    if Path("reports/stress_test.json").exists():
        fig_stress_test()
    if Path("reports/swmm_control_curves.csv").exists():
        fig_swmm_control()
    print("全部图表生成完毕")


if __name__ == "__main__":
    main()
