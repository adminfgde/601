"""管网拓扑生成：干线 + 支线 + 泵站，输出节点表/管段表/泵站表。"""
import numpy as np
import pandas as pd

from .config import NetworkConfig


def build_topology(cfg: NetworkConfig):
    """生成树状排水管网拓扑。

    返回 (nodes, links, pumps) 三张 DataFrame：
    - nodes: 节点（检查井/监测点），含地面高程、埋深、汇水面积
    - links: 管段，含上下游节点、管径、管长、坡度
    - pumps: 泵站，含所在节点、配泵台数、单泵能力、前池容积
    """
    rng = np.random.default_rng(cfg.seed)
    nodes, links = [], []

    def add_node(nid, kind, dist_to_plant_km):
        nodes.append({
            "node_id": nid,
            "kind": kind,  # trunk / branch / plant_inlet
            "dist_to_plant_km": round(dist_to_plant_km, 2),
            "ground_elev_m": round(4.0 + rng.uniform(-0.5, 1.5), 2),
            "invert_depth_m": round(rng.uniform(3.0, 7.0), 2),
            "catchment_ha": round(rng.uniform(20, 80), 1),
        })

    # 干线：从最远端到厂前，编号 T01..Tnn，厂前节点 PLANT_IN
    trunk_ids = [f"T{i+1:02d}" for i in range(cfg.n_trunk_nodes)]
    total_len_km = cfg.n_trunk_nodes * 0.8
    for i, nid in enumerate(trunk_ids):
        add_node(nid, "trunk", total_len_km - i * 0.8)
    add_node("PLANT_IN", "plant_inlet", 0.0)

    chain = trunk_ids + ["PLANT_IN"]
    for up, dn in zip(chain[:-1], chain[1:]):
        links.append({
            "link_id": f"L_{up}_{dn}", "from_node": up, "to_node": dn,
            "diameter_mm": int(rng.choice([1200, 1350, 1500, 1650, 1800])),
            "length_m": int(rng.uniform(600, 1000)),
            "slope": round(rng.uniform(0.0008, 0.002), 4),
        })

    # 支线：每条支线接入一个干线节点
    join_points = rng.choice(trunk_ids, size=cfg.n_branches, replace=False)
    for b in range(cfg.n_branches):
        prev = None
        for j in range(cfg.nodes_per_branch):
            nid = f"B{b+1}{j+1:02d}"
            join = nodes[trunk_ids.index(join_points[b])]
            add_node(nid, "branch",
                     join["dist_to_plant_km"] + (cfg.nodes_per_branch - j) * 0.5)
            dn = prev if prev else None
            prev = nid
            target = dn or join_points[b]
            # 支线内从末端向接入点排序：这里直接由当前节点连向下游
            links.append({
                "link_id": f"L_{nid}_{target}", "from_node": nid, "to_node": target,
                "diameter_mm": int(rng.choice([400, 500, 600, 800])),
                "length_m": int(rng.uniform(300, 600)),
                "slope": round(rng.uniform(0.001, 0.003), 4),
            })

    # 泵站：厂前总泵站 + 若干支线/干线中途泵站
    pump_nodes = ["PLANT_IN"] + list(rng.choice(trunk_ids, size=cfg.n_pump_stations - 1, replace=False))
    pumps = []
    for k, pn in enumerate(pump_nodes):
        n_pumps = int(rng.choice([3, 4, 5]))
        unit = float(rng.choice([600, 900, 1200, 1500]))  # 单泵能力 m3/h
        pumps.append({
            "pump_id": f"PS{k+1:02d}", "node_id": pn,
            "n_pumps": n_pumps, "unit_capacity_m3h": unit,
            "total_capacity_m3h": n_pumps * unit,
            "wet_well_volume_m3": int(rng.uniform(400, 1500)),
        })

    return pd.DataFrame(nodes), pd.DataFrame(links), pd.DataFrame(pumps)
