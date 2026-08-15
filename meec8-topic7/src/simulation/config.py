"""管网模拟全局配置。"""
from dataclasses import dataclass, field


@dataclass
class NetworkConfig:
    """管网拓扑规模（参照泰和污水厂服务范围的干线+支线泵站结构）。"""
    n_trunk_nodes: int = 12          # 干线关键节点（检查井/监测点）数
    n_branches: int = 6              # 支线数
    nodes_per_branch: int = 5        # 每条支线节点数
    n_pump_stations: int = 6         # 泵站数（干线末端 1 座总泵站 + 支线泵站）
    seed: int = 42


@dataclass
class TimeseriesConfig:
    """时序生成参数。"""
    days: int = 30
    step_minutes: int = 5            # 采样分辨率
    base_inflow_m3d: float = 100000  # 污水厂旱天日均进水量 m3/d
    rain_prob_per_day: float = 0.25  # 单日降雨概率
    shock_prob_per_day: float = 0.05 # 工业冲击/毒性事件概率
    seed: int = 42


@dataclass
class QualityConfig:
    """旱天进水水质基准（mg/L，pH 无量纲），日内随流量同相波动。"""
    cod_mean: float = 320.0
    nh3n_mean: float = 28.0
    tn_mean: float = 42.0
    tp_mean: float = 4.5
    ss_mean: float = 180.0
    ph_mean: float = 7.3
    noise: float = 0.06              # 相对噪声水平


@dataclass
class SimConfig:
    network: NetworkConfig = field(default_factory=NetworkConfig)
    timeseries: TimeseriesConfig = field(default_factory=TimeseriesConfig)
    quality: QualityConfig = field(default_factory=QualityConfig)
