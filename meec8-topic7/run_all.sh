#!/usr/bin/env bash
# 一键复现全流程：依赖 → 数据 → 预测 → 预警
# 用法：bash run_all.sh
set -e
cd "$(dirname "$0")"

echo "== 1/4 安装依赖 =="
pip install -r requirements.txt

echo "== 2/4 生成泰和模拟场景（有上海实测雨量则自动使用，否则合成降雨）=="
if [ -f data/processed/shanghai_rain_10min.csv ]; then
  python -m src.simulation.generate --days 92 \
    --rain-csv data/processed/shanghai_rain_10min.csv \
    --rain-start 2024-06-01 --out data/simulated_realrain
else
  python -m src.simulation.generate --days 92 --out data/simulated_realrain
fi

echo "== 3/4 超前预测（Köln 真实数据自动从 Zenodo 下载 + 泰和场景迁移）=="
python -m src.models.forecast --dataset koeln
python -m src.models.forecast --dataset taihe

echo "== 4/4 四级预警调控演示 =="
python -m src.control.warning

echo "全部完成：指标见 reports/forecast_metrics.json，预警见 reports/warning_demo.csv"
