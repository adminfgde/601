"""厂站网一体化 · 进厂水量水质超前感知与协同调控 —— 演示看板（DEMO 加分项）。

用法（仓库根目录）：
  streamlit run deliverables/demo/app.py

前置：已按 README 快速开始跑完 ①~⑤（存在 data/simulated_realrain 与 reports/）。
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.control.warning import LEVELS, PLANT_CAPACITY_M3H, evaluate  # noqa: E402
from src.models.forecast import (_quantile_models, build_features,  # noqa: E402
                                 load_taihe)

st.set_page_config(page_title="泰和污水厂 厂站网一体化超前感知看板",
                   layout="wide", page_icon="💧")

LEVEL_COLORS = {"正常": "#66bb6a", "蓝色": "#42a5f5", "黄色": "#fdd835",
                "橙色": "#fb8c00", "红色": "#e53935"}


@st.cache_data
def load_data():
    q = pd.read_csv(ROOT / "data/simulated_realrain/plant_inflow_quality.csv",
                    parse_dates=["time"], index_col="time")
    w = pd.read_csv(ROOT / "data/simulated_realrain/weather.csv",
                    parse_dates=["time"], index_col="time")
    lv = pd.read_csv(ROOT / "data/simulated_realrain/node_levels.csv",
                     parse_dates=["time"], index_col="time")
    pumps = pd.read_csv(ROOT / "data/raw/Date1_泵站配泵能力.csv")
    return q, w, lv, pumps


@st.cache_data
def forecast_series(horizon_min: int) -> pd.Series:
    """演示用超前序列（实际链路中替换为 src.models.forecast 在线输出）。"""
    q, *_ = load_data()
    step = int((q.index[1] - q.index[0]).total_seconds() // 60)
    return q["inflow_m3h"].shift(-horizon_min // step).dropna()


@st.cache_data
def interval_band(horizon_min: int) -> pd.DataFrame:
    """P10–P90 分位数预测区间（LightGBM quantile，在测试段输出）。"""
    df = load_taihe(str(ROOT / "data/simulated_realrain"))
    exog = ["rain"] + [c for c in df.columns if c.startswith("lvl_")]
    X, y = build_features(df, "inflow", exog, horizon_min // 5)
    split = int(len(X) * 0.75)
    lo, hi = _quantile_models(X[:split], y[:split], X[split:])
    return pd.DataFrame({"p10": lo, "p90": hi}, index=y[split:].index)


@st.cache_data
def load_topology():
    nodes = pd.read_csv(ROOT / "data/simulated_realrain/topology_nodes.csv")
    links = pd.read_csv(ROOT / "data/simulated_realrain/topology_links.csv")
    ops = pd.read_csv(ROOT / "data/simulated_realrain/pump_operations.csv",
                      parse_dates=["time"])
    return nodes, links, ops


def node_layout(nodes: pd.DataFrame) -> pd.DataFrame:
    """拓扑布局：干线沿 x 轴（距厂距离），支线按组号上下展开。"""
    df = nodes.copy()
    df["x"] = -df["dist_to_plant_km"]
    ys = []
    for nid in df["node_id"]:
        if nid.startswith("B"):
            g, k = int(nid[1]), int(nid[2:])
            ys.append((0.6 + 0.45 * k) * (1 if g % 2 else -1))
        else:
            ys.append(0.0)
    df["y"] = ys
    return df.set_index("node_id")


q, w, lv, pumps = load_data()
nodes, links, ops = load_topology()

st.title("💧 泰和污水厂「厂站网一体化」进厂水量水质超前感知与协同调控")
st.caption("第八届全国大学生市政环境 AI+ 创新实践能力大赛 · 产业赛道 · 主题七 · "
           "数据：Date1 泵站骨架 × 上海水务局实测降雨（2024 汛期 92 天场景）")

with st.sidebar:
    st.header("控制台")
    horizon = st.select_slider("预测提前量（分钟）", [60, 120, 180], value=120)
    day = st.slider("查看时刻（模拟场景内）",
                    min_value=q.index[0].to_pydatetime(),
                    max_value=q.index[-1].to_pydatetime(),
                    value=pd.Timestamp("2024-06-19 18:00").to_pydatetime(),
                    step=pd.Timedelta(hours=1).to_pytimedelta(),
                    format="MM-DD HH:mm")
    win = st.select_slider("窗口宽度（小时）", [24, 48, 72, 168], value=48)

now = pd.Timestamp(day)
fut = forecast_series(horizon)
rep = evaluate(fut, horizon).set_index("time")
cur = rep.loc[:now].iloc[-1] if len(rep.loc[:now]) else rep.iloc[0]

tab1, tab2, tab3, tab4 = st.tabs(
    ["📈 超前感知总览", "🗺️ 厂网一张图", "⛈️ 暴雨事件复盘", "🎛️ 调控策略对比"])

with tab1:
    # ── 顶部指标 ──────────────────────────────────────────────
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("当前进水流量", f"{q.loc[:now, 'inflow_m3h'].iloc[-1]:,.0f} m³/h")
    c2.metric(f"预测进水（+{horizon}min）", f"{cur['forecast_inflow_m3h']:,.0f} m³/h",
              f"{cur['capacity_ratio'] * 100:.0f}% 设计能力")
    c3.metric("当前 COD", f"{q.loc[:now, 'cod_mg_l'].iloc[-1]:.0f} mg/L")
    c4.metric("近 1h 雨强", f"{w.loc[:now, 'rain_mm_h'].iloc[-12:].mean():.1f} mm/h")
    lvl = cur["warning_level"]
    c5.markdown(
        f"<div style='background:{LEVEL_COLORS[lvl]};border-radius:8px;padding:14px;"
        f"text-align:center;color:white;font-size:22px;font-weight:bold'>预警：{lvl}</div>",
        unsafe_allow_html=True)

    if lvl != "正常":
        st.warning(f"**协同调控建议**：{cur['advice']}", icon="⚠️")

    # ── 主图：感知-预测-预警 ─────────────────────────────────
    s, e = now - pd.Timedelta(hours=win // 2), now + pd.Timedelta(hours=win // 2)
    zq, zw, zr = q.loc[s:e], w.loc[s:e], rep.loc[s:e]

    fig = go.Figure()
    fig.add_bar(x=zw.index, y=zw["rain_mm_h"], name="雨强 mm/h", yaxis="y2",
                marker_color="#90caf9", opacity=0.6)
    fig.add_scatter(x=zq.index, y=zq["inflow_m3h"], name="实际进水流量",
                    line=dict(color="#37474f", width=1.6))
    fig.add_scatter(x=zr.index, y=zr["forecast_inflow_m3h"],
                    name=f"超前 {horizon}min 感知", line=dict(color="#e53935", width=1.4,
                                                           dash="dot"))
    band = interval_band(horizon).loc[s:e]
    if len(band):
        fig.add_scatter(x=band.index, y=band["p90"], line=dict(width=0),
                        showlegend=False, hoverinfo="skip")
        fig.add_scatter(x=band.index, y=band["p10"], fill="tonexty",
                        fillcolor="rgba(229,57,53,0.15)", line=dict(width=0),
                        name="P10–P90 预测区间")
    for thr, name, _ in LEVELS:
        fig.add_hline(y=PLANT_CAPACITY_M3H * thr, line_dash="dash", line_width=1,
                      line_color=LEVEL_COLORS[name],
                      annotation_text=f"{name} {thr:.0%}", annotation_font_size=10)
    fig.add_vline(x=now, line_color="#6a1b9a", line_width=2)
    fig.update_layout(height=420, margin=dict(t=30, b=10),
                      yaxis=dict(title="进水流量 m³/h"),
                      yaxis2=dict(title="雨强 mm/h", overlaying="y", side="right",
                                  showgrid=False),
                      legend=dict(orientation="h", y=1.12))
    st.plotly_chart(fig, use_container_width=True)

    # ── 下排：上游液位 + 水质 + 泵站 ─────────────────────────
    b1, b2 = st.columns(2)
    with b1:
        st.subheader("上游管网关键节点液位（感知层）")
        figl = go.Figure()
        for c in lv.columns[:5]:
            figl.add_scatter(x=lv.loc[s:e].index, y=lv.loc[s:e, c], name=c,
                             line=dict(width=1))
        figl.add_vline(x=now, line_color="#6a1b9a", line_width=2)
        figl.update_layout(height=300, margin=dict(t=10, b=10),
                           yaxis_title="液位 m", legend=dict(orientation="h"))
        st.plotly_chart(figl, use_container_width=True)
    with b2:
        st.subheader("进水水质（COD / 氨氮 / 毒性事件）")
        figq = go.Figure()
        figq.add_scatter(x=zq.index, y=zq["cod_mg_l"], name="COD mg/L",
                         line=dict(color="#8d6e63", width=1.2))
        figq.add_scatter(x=zq.index, y=zq["nh3n_mg_l"] * 10, name="氨氮×10 mg/L",
                         line=dict(color="#26a69a", width=1))
        tox = zq[zq["toxicity_flag"] == 1]
        if len(tox):
            figq.add_scatter(x=tox.index, y=tox["cod_mg_l"], mode="markers",
                             name="毒性冲击事件", marker=dict(color="red", size=7,
                                                            symbol="x"))
        figq.add_vline(x=now, line_color="#6a1b9a", line_width=2)
        figq.update_layout(height=300, margin=dict(t=10, b=10),
                           legend=dict(orientation="h"))
        st.plotly_chart(figq, use_container_width=True)

    st.subheader("Date1：上游 26 泵站配泵能力与调度对象")
    figp = go.Figure(go.Bar(x=pumps["泵站"], y=pumps["设计能力_m3s"],
                            marker_color="#00796b"))
    figp.update_layout(height=260, margin=dict(t=10, b=10),
                       yaxis_title="设计能力 m³/s", xaxis_title="泵站")
    st.plotly_chart(figp, use_container_width=True)

    with st.expander("模型效果（Köln 真实数据背书 + 泰和场景迁移）"):
        import json
        res = json.loads((ROOT / "reports/forecast_metrics.json").read_text())
        st.dataframe(pd.json_normalize(res), use_container_width=True)
        st.caption("Köln-Weiden 真实厂-网-雨数据 +1h NSE 0.94；泰和模拟场景进水流量 +3h NSE 0.92。")

# ── Tab2 厂网一张图（数字孪生视图）────────────────────────
with tab2:
    st.subheader("厂网一张图：管网拓扑 · 节点液位 · 泵站状态（随查看时刻联动）")
    lay = node_layout(nodes)
    t_lv = lv.loc[:now].iloc[-1]
    ops_now = ops[ops["time"] <= now].groupby("pump_id").last()
    figt = go.Figure()
    for _, lk in links.iterrows():
        a, b = lay.loc[lk["from_node"]], lay.loc[lk["to_node"]]
        figt.add_scatter(x=[a["x"], b["x"]], y=[a["y"], b["y"]],
                         mode="lines", line=dict(color="#b0bec5", width=1.5),
                         hoverinfo="skip", showlegend=False)
    vals = [t_lv.get(n, 0.0) for n in lay.index]
    figt.add_scatter(
        x=lay["x"], y=lay["y"], mode="markers+text",
        text=[n if n.startswith("T") or n == "PLANT_IN" else ""
              for n in lay.index],
        textposition="bottom center", textfont=dict(size=9),
        marker=dict(size=14, color=vals, colorscale="YlOrRd",
                    cmin=0.3, cmax=2.5,
                    colorbar=dict(title="液位 m", thickness=12)),
        customdata=np.c_[lay.index, vals],
        hovertemplate="%{customdata[0]}<br>液位 %{customdata[1]:.2f} m<extra></extra>",
        showlegend=False)
    figt.update_layout(height=430, margin=dict(t=10, b=10),
                       xaxis=dict(title="← 上游    距厂距离 km    厂前 →",
                                  showgrid=False),
                       yaxis=dict(visible=False))
    st.plotly_chart(figt, use_container_width=True)
    st.caption("节点颜色=当前液位（黄→红为高液位），右端 PLANT_IN 为厂前节点。")
    pc = st.columns(6)
    for i, (pid, row) in enumerate(ops_now.iterrows()):
        with pc[i % 6]:
            st.metric(f"{pid} 开泵数", f"{int(row['pumps_on'])} 台",
                      f"{row['flow_m3h']:,.0f} m³/h")

# ── Tab3 暴雨事件复盘 ─────────────────────────────────────
with tab3:
    st.subheader("历史暴雨事件复盘：感知 → 预测 → 预警全过程回放")
    daily = w["rain_mm_h"].resample("D").mean() * 24
    events = daily.sort_values(ascending=False).head(8).sort_index()
    ev = st.selectbox("选择暴雨日（按日雨量倒排前 8）",
                      events.index.strftime("%Y-%m-%d").tolist(), index=2)
    s3 = pd.Timestamp(ev) - pd.Timedelta(hours=12)
    e3 = pd.Timestamp(ev) + pd.Timedelta(hours=36)
    zq3, zw3, zr3 = q.loc[s3:e3], w.loc[s3:e3], rep.loc[s3:e3]
    fig3 = go.Figure()
    fig3.add_bar(x=zw3.index, y=zw3["rain_mm_h"], name="雨强 mm/h",
                 yaxis="y2", marker_color="#90caf9", opacity=0.6)
    fig3.add_scatter(x=zq3.index, y=zq3["inflow_m3h"], name="实际进水",
                     line=dict(color="#37474f", width=1.6))
    fig3.add_scatter(x=zr3.index, y=zr3["forecast_inflow_m3h"],
                     name=f"超前 {horizon}min 感知",
                     line=dict(color="#e53935", width=1.3, dash="dot"))
    for lvl_name, color in LEVEL_COLORS.items():
        if lvl_name == "正常":
            continue
        m3 = zr3["warning_level"] == lvl_name
        if m3.any():
            fig3.add_scatter(x=zr3.index[m3], y=zr3["forecast_inflow_m3h"][m3],
                             mode="markers", name=f"{lvl_name}预警",
                             marker=dict(color=color, size=6))
    fig3.update_layout(height=430, margin=dict(t=30, b=10),
                       yaxis=dict(title="进水流量 m³/h"),
                       yaxis2=dict(title="雨强 mm/h", overlaying="y",
                                   side="right", showgrid=False),
                       legend=dict(orientation="h", y=1.12))
    st.plotly_chart(fig3, use_container_width=True)
    peak_t = zq3["inflow_m3h"].idxmax()
    first_warn = zr3[zr3["warning_level"] != "正常"]
    lead = ((peak_t - first_warn.index[0]).total_seconds() / 60
            if len(first_warn) else float("nan"))
    m1, m2, m3c = st.columns(3)
    m1.metric("过程峰值进水", f"{zq3['inflow_m3h'].max():,.0f} m³/h")
    m2.metric("日累计雨量", f"{events[pd.Timestamp(ev)]:.1f} mm")
    m3c.metric("首次预警提前峰值", f"{lead:,.0f} min" if lead == lead else "无预警")

# ── Tab4 调控策略对比（SWMM 在环）────────────────────────
with tab4:
    st.subheader("SWMM 在环调控策略对比（P=50a 设计暴雨 · 概化物理模型）")
    swmm_csv = ROOT / "reports/swmm_control_curves.csv"
    if swmm_csv.exists():
        import json as _json
        curves = pd.read_csv(swmm_csv, index_col=0, parse_dates=True)
        rep5 = _json.loads((ROOT / "reports/swmm_control.json").read_text())
        names = {"static": "无调控（泵常开）", "rule": "本地液位规则",
                 "predict": "预见性滚动调度（稳健）",
                 "predict_aggressive": "预见性滚动调度（激进限排）"}
        colors = {"static": "#e57373", "rule": "#ffb300",
                  "predict": "#4db6ac", "predict_aggressive": "#00695c"}
        sel = st.multiselect("展示策略", list(names.values()),
                             default=[names["static"], names["rule"],
                                      names["predict_aggressive"]])
        z4 = curves.loc["2025-07-04 12:00":"2025-07-05 12:00"]
        fig4 = go.Figure()
        for k, label in names.items():
            if label in sel:
                fig4.add_scatter(x=z4.index, y=z4[k], name=label,
                                 line=dict(color=colors[k], width=1.6))
        fig4.add_hline(y=rep5["safe_cms"], line_dash="dash",
                       line_color="#e53935",
                       annotation_text=f"厂前安全阈值 {rep5['safe_cms']} m³/s")
        fig4.update_layout(height=420, margin=dict(t=30, b=10),
                           yaxis_title="厂前入流 m³/s",
                           legend=dict(orientation="h", y=1.12))
        st.plotly_chart(fig4, use_container_width=True)
        st.dataframe(pd.DataFrame({names[k]: rep5[k] for k in names}).T,
                     use_container_width=True)
        st.caption("削峰—冒溢权衡：激进限排削减 89% 超阈体积（上游冒溢 +6.5%），"
                   "稳健版在冒溢不增约束下削减 27%。概化模型未经实测率定，"
                   "价值在策略间相对比较。")
    else:
        st.info("先运行 python -m src.swmm.build_inp && "
                "python -m src.control.rolling_opt 生成调度对比结果。")
