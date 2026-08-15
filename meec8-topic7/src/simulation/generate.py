"""管网模拟数据生成入口。

用法：
    python -m src.simulation.generate --days 30 --out data/simulated
"""
import argparse
from pathlib import Path

from .config import SimConfig
from .topology import build_topology
from .timeseries import generate_timeseries


def main():
    ap = argparse.ArgumentParser(description="管网数据模拟生成器")
    ap.add_argument("--days", type=int, default=30, help="模拟天数")
    ap.add_argument("--step", type=int, default=5, help="采样间隔（分钟）")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", type=str, default="data/simulated")
    ap.add_argument("--rain-csv", type=str, default=None,
                    help="上海实测雨量 CSV（data/processed/shanghai_rain_10min.csv）")
    ap.add_argument("--rain-start", type=str, default="2024-06-01",
                    help="实测雨量起始日期")
    args = ap.parse_args()

    if args.rain_csv and not Path(args.rain_csv).exists():
        print(f"[warn] 雨量文件不存在：{args.rain_csv}，改用合成降雨")
        args.rain_csv = None

    cfg = SimConfig()
    cfg.timeseries.days = args.days
    cfg.timeseries.step_minutes = args.step
    cfg.timeseries.seed = args.seed
    cfg.network.seed = args.seed

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    nodes, links, pumps = build_topology(cfg.network)
    nodes.to_csv(out / "topology_nodes.csv", index=False)
    links.to_csv(out / "topology_links.csv", index=False)
    pumps.to_csv(out / "pump_stations.csv", index=False)

    series = generate_timeseries(cfg, nodes, pumps,
                                 rain_csv=args.rain_csv, rain_start=args.rain_start)
    for name, df in series.items():
        df.to_csv(out / f"{name}.csv", index=False)
        print(f"[ok] {name}: {df.shape} -> {out / f'{name}.csv'}")

    print(f"\n完成：拓扑 {len(nodes)} 节点 / {len(links)} 管段 / {len(pumps)} 泵站，"
          f"{args.days} 天 @ {args.step}min 时序已输出至 {out}/")


if __name__ == "__main__":
    main()
