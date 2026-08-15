"""水量/水质/降雨/泵站运行时序生成：旱天双峰日变化、降雨入流入渗与
稀释/初期冲刷、按距离的输送延迟、工业冲击事件、前池液位启停泵逻辑。
"""
import numpy as np
import pandas as pd

from .config import SimConfig

FLOW_VELOCITY_MS = 0.8


def _diurnal(hours: np.ndarray) -> np.ndarray:
    """旱天日变化系数（均值≈1 的双峰曲线）。"""
    return (1.0
            + 0.35 * np.exp(-((hours % 24 - 9) ** 2) / 8)
            + 0.30 * np.exp(-((hours % 24 - 20) ** 2) / 10)
            - 0.35 * np.exp(-((hours % 24 - 3.5) ** 2) / 6))


def _gen_rain(t_hours: np.ndarray, cfg, rng) -> np.ndarray:
    """降雨强度 mm/h 时序：按日抽样降雨事件，三角形雨型。"""
    rain = np.zeros_like(t_hours)
    for d in range(int(t_hours[-1] // 24) + 1):
        if rng.random() < cfg.rain_prob_per_day:
            start = d * 24 + rng.uniform(0, 20)
            dur = rng.uniform(1, 8)
            peak = rng.uniform(3, 40)  # mm/h
            frac = np.clip((t_hours - start) / dur, 0, 1)
            mask = (frac > 0) & (frac < 1)
            r = rng.uniform(0.3, 0.5)  # 雨峰位置系数
            shape = np.where(frac < r, frac / r, (1 - frac) / (1 - r))
            rain[mask] += peak * shape[mask]
    return rain


def _gen_shocks(t_hours: np.ndarray, cfg, rng) -> np.ndarray:
    """工业冲击事件：返回 COD 突增倍率曲线（基线 1.0）。"""
    shock = np.ones_like(t_hours)
    for d in range(int(t_hours[-1] // 24) + 1):
        if rng.random() < cfg.shock_prob_per_day:
            start = d * 24 + rng.uniform(0, 22)
            dur = rng.uniform(0.5, 3)
            mag = rng.uniform(1.8, 4.0)
            mask = (t_hours >= start) & (t_hours < start + dur)
            shock[mask] = np.maximum(shock[mask], mag)
    return shock


def load_real_rain(path: str, start: str, n_steps: int, step_minutes: int,
                   column: str = "rain_citymean") -> tuple[np.ndarray, pd.DatetimeIndex]:
    """加载上海实测雨量（data/processed/shanghai_rain_10min.csv，mm/10min），
    返回 mm/h 序列与对应时间轴。"""
    df = pd.read_csv(path, index_col=0, parse_dates=True)
    s = df[column].fillna(0.0) * 6.0  # mm/10min -> mm/h
    s = s.resample(f"{step_minutes}min").interpolate(limit=6).fillna(0.0)
    t = pd.date_range(start, periods=n_steps, freq=f"{step_minutes}min")
    return s.reindex(t, fill_value=0.0).to_numpy(), t


def generate_timeseries(cfg: SimConfig, nodes: pd.DataFrame, pumps: pd.DataFrame,
                        rain_csv: str | None = None, rain_start: str = "2024-06-01"):
    """生成全部时序，返回 dict[str, DataFrame]。

    rain_csv 非空时用上海实测雨量（从 rain_start 起取 days 天）驱动雨天入流，
    时间轴同步为真实日期；否则用内置随机雨型。"""
    ts_cfg, q_cfg = cfg.timeseries, cfg.quality
    rng = np.random.default_rng(ts_cfg.seed)

    n_steps = ts_cfg.days * 24 * 60 // ts_cfg.step_minutes
    if rain_csv:
        rain, t = load_real_rain(rain_csv, rain_start, n_steps, ts_cfg.step_minutes)
    else:
        t = pd.date_range("2026-06-01", periods=n_steps, freq=f"{ts_cfg.step_minutes}min")
    t_hours = np.arange(n_steps) * ts_cfg.step_minutes / 60.0
    weekend = pd.Series(t).dt.dayofweek.values >= 5

    if not rain_csv:
        rain = _gen_rain(t_hours, ts_cfg, rng)
    shock = _gen_shocks(t_hours, ts_cfg, rng)

    weather = pd.DataFrame({
        "time": t, "rain_mm_h": np.round(rain, 2),
        "temp_c": np.round(26 + 5 * np.sin(2 * np.pi * (t_hours % 24 - 14) / 24)
                           + rng.normal(0, 0.5, n_steps), 1),
    })

    # 厂前旱天基础流量 (m3/h)
    base_q = ts_cfg.base_inflow_m3d / 24.0
    diurnal = _diurnal(t_hours) * np.where(weekend, 0.92, 1.0)

    # 各节点流量：按汇水面积比例分摊 + 降雨入流(RDII) + 输送延迟
    node_flows, node_levels = {}, {}
    total_catch = nodes["catchment_ha"].sum()
    for _, nd in nodes.iterrows():
        share = nd["catchment_ha"] / total_catch
        lag_steps = int(nd["dist_to_plant_km"] * 1000 / FLOW_VELOCITY_MS / 60
                        / ts_cfg.step_minutes)
        # 该节点上游沿线的旱天流量（简化为面积占比 × 上游位置系数）
        dry = base_q * share * 6 * diurnal
        rdii = nd["catchment_ha"] * 10 * rain * 0.35 / 6  # 入流入渗 m3/h（径流系数0.35）
        q = (dry + rdii) * (1 + rng.normal(0, 0.03, n_steps))
        q = np.roll(q, -lag_steps) if nd["kind"] != "plant_inlet" else q
        node_flows[nd["node_id"]] = np.round(np.maximum(q, 0), 1)
        # 液位：流量的非线性映射 + 噪声（近似曼宁关系）
        lvl = 0.15 + 1.2 * (q / (q.mean() * 2.5)) ** 0.6
        node_levels[nd["node_id"]] = np.round(lvl + rng.normal(0, 0.01, n_steps), 3)

    flows = pd.DataFrame({"time": t, **node_flows})
    levels = pd.DataFrame({"time": t, **node_levels})

    # 厂前进水 = 全网汇总（含延迟后的叠加），加雨天稀释水质
    q_in = flows[[c for c in flows.columns if c != "time"]].sum(axis=1).values / 6
    q_in = base_q * diurnal + nodes["catchment_ha"].sum() * 10 * rain * 0.35 / 8
    q_in *= (1 + rng.normal(0, 0.02, n_steps))

    dilution = base_q * diurnal / np.maximum(q_in, 1)  # 雨天稀释系数 <=1
    first_flush = 1 + 1.5 * np.clip(np.gradient(rain), 0, None) / 10  # 初期冲刷抬升SS/COD

    def q_series(mean, flush=1.0):
        s = mean * (0.9 + 0.2 * diurnal) * dilution * (1 + rng.normal(0, q_cfg.noise, n_steps))
        return np.round(np.maximum(s * (1 + (flush - 1)) if np.isscalar(flush) else s * flush, 0.1), 1)

    quality = pd.DataFrame({
        "time": t,
        "cod_mg_l": np.round(np.maximum(q_cfg.cod_mean * (0.9 + 0.2 * diurnal) * dilution
                                        * shock * first_flush
                                        * (1 + rng.normal(0, q_cfg.noise, n_steps)), 20), 1),
        "nh3n_mg_l": q_series(q_cfg.nh3n_mean),
        "tn_mg_l": q_series(q_cfg.tn_mean),
        "tp_mg_l": q_series(q_cfg.tp_mean),
        "ss_mg_l": np.round(np.maximum(q_cfg.ss_mean * (0.9 + 0.2 * diurnal)
                                       * first_flush * (1 + rng.normal(0, 0.1, n_steps)), 10), 1),
        "ph": np.round(q_cfg.ph_mean + rng.normal(0, 0.1, n_steps) - 0.3 * (shock > 1.5), 2),
        "toxicity_flag": (shock > 1.5).astype(int),
        "inflow_m3h": np.round(q_in, 1),
    })

    # 泵站运行：前池液位驱动的启停泵逻辑
    pump_frames = []
    for _, ps in pumps.iterrows():
        node_q = node_flows.get(ps["node_id"], q_in)
        ratio = np.asarray(node_q) / ps["total_capacity_m3h"]
        n_on = np.clip(np.ceil(ratio * ps["n_pumps"] + rng.normal(0, 0.2, n_steps)),
                       0, ps["n_pumps"]).astype(int)
        pump_frames.append(pd.DataFrame({
            "time": t, "pump_id": ps["pump_id"], "pumps_on": n_on,
            "flow_m3h": np.round(n_on * ps["unit_capacity_m3h"]
                                 * rng.uniform(0.85, 1.0, n_steps), 1),
            "wet_well_level_m": np.round(1.0 + 2.0 * ratio + rng.normal(0, 0.05, n_steps), 2),
        }))
    pump_ops = pd.concat(pump_frames, ignore_index=True)

    # 事件标签
    events = pd.DataFrame({
        "time": t,
        "rain_event": (rain > 0.5).astype(int),
        "shock_event": (shock > 1.5).astype(int),
    })

    return {"weather": weather, "node_flows": flows, "node_levels": levels,
            "plant_inflow_quality": quality, "pump_operations": pump_ops,
            "event_labels": events}
