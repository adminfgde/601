# 第八届全国大学生市政环境 AI+ 创新实践能力大赛 · 产业赛道 · 主题七

> **基于厂站网一体化的污水厂进厂水量水质超前感知与协同调控模型**

## 项目定位

在厂站网一体化运行管理背景下，构建以污水厂为调控核心的"厂前"水量水质超前感知与协同预警框架：

- 融合"管网—泵站—污水厂"多节点数据（管网关键节点液位/流量、泵站运行状态、在线水质仪表、气象预报等）
- 开发进水水量与关键水质指标（浓度、毒性等）的**短时预测模型**
- 形成"感知 → 预测 → 预警 → 预控"闭环决策支持系统
- 增强污水厂应对水力与污染负荷突变的准备时间与调控能力

## 关键时间节点（2026）

| 时间 | 事项 |
|---|---|
| 6.15 – 7.15 | 团队报名（官网 http://meevexp.oberyun.com） |
| **9.15 24:00 前** | **初赛作品在线提交截止** |
| 另行通知 | 决赛（初审–网评–决赛） |

## 成果清单（提交要求）

1. **技术报告**：PDF，≥15 页，含行业/背景调研、问题定义、技术路线、实验验证及结果分析 → `deliverables/report/`
2. **演示 PPT**：PPTX，15–20 页 → `deliverables/ppt/`
3. **演示视频**：MP4，3–5 分钟，16:9，展示模型动态运行 → `deliverables/video/`
4. **源代码**：ZIP/RAR，含核心代码、依赖配置、数据样本、中文注释与 README，保证可复现 → 本仓库
5. **加分项**：可交互原型（软件 DEMO/网页）或实物模型 → `deliverables/demo/`

## 评分参考（产业赛道）

- 成果规范性与完整性 15%（材料齐全、格式规范、**代码可复现**）
- 技术深度与 AI+ 创新 30%（算法模型、数据处理）
- 实践能力与应用价值 30%（系统演示、实用价值、工具与平台）
- 现场答辩表现 20%
- 加分项 5%（实物/硬件、额外创新）

## 数据现状（重要）

- 组委会提供数据（Date1，见 `data/raw/`）：泰和污水厂服务范围干线及支线泵站服务范围、主要泵站配泵能力等静态资料。组委会未提供时序运行数据，任务书允许使用超出范围的公开数据与自行模拟
- 真实数据：上海市水务局「水情信息」10min 雨量/水位、NOAA/Open-Meteo 气象、Köln/Graz/BSM2 等公开厂网数据集，已下载入库并逐项标注来源与许可（见 `data/DATA_CATALOG.md`、`data/external/`）
- 模拟数据：泰和场景的管网/泵站/进水时序由 `src/simulation/` 生成，生成方式与参数设定见技术报告第 2 章与 `docs/数据说明.md`，所有泰和场景结果均标注为模拟性质

## 仓库结构

```
docs/            比赛文件（PDF 原件 + 文本提取版）、数据说明、任务书
data/raw/        组委会原始数据（泰和污水厂/泵站资料）
data/simulated/  自行模拟生成的管网数据（脚本输出）
data/external/   外部公开真实数据集（Köln/Graz/BSM2 等，来源见 data/DATA_CATALOG.md）
src/data/        数据融合层（上海水务局雨量/水位清洗对齐 → data/processed/）
src/simulation/  管网数据模拟框架（拓扑 + 旱天/雨天时序，支持 --rain-csv 实测降雨驱动）
src/models/      预测模型（LightGBM 超前 1~3h 预测，Köln 真实数据验证 + 泰和场景迁移）
src/control/     四级预警与泵站协同调控建议
src/viz/         报告/PPT 图表批量生成
src/utils/       公共工具
notebooks/       探索分析
reports/         过程性分析报告
deliverables/    最终提交物（报告 MD+PDF / PPT 生成脚本 / 视频脚本分镜 / Streamlit DEMO / 源码打包脚本）
```

## 快速开始

一键复现（推荐，自动处理缺失数据）：

```bash
bash run_all.sh
```

- Köln 真实数据集缺失时会自动从 Zenodo（记录 6992694，CC-BY-4.0，约 10MB）下载
- 上海实测雨量缺失时自动改用合成降雨驱动泰和模拟场景（`src.data.shanghai_rain` 需要
  自行下载上海水务局原始数据到 `data/external/shgov_water_regime/`，非必需）
- 泰和模拟数据缺失时预测/预警脚本会自动生成

分步执行：

```bash
pip install -r requirements.txt        # 锁定版本见 requirements-lock.txt；深度模型另需 requirements-optional.txt
python -m pytest tests -q              # 单元测试（CI：.github/workflows/ci.yml 每次 push 自动运行）
python -m src.data.shanghai_rain          # ① 数据融合：上海官方雨量/水位 → data/processed/
python -m src.simulation.generate --days 92 \
  --rain-csv data/processed/shanghai_rain_10min.csv \
  --rain-start 2024-06-01 --out data/simulated_realrain   # ② 实测降雨驱动的泰和汛期场景
python -m src.models.forecast --dataset koeln             # ③ 真实数据方法验证
python -m src.models.forecast --dataset taihe             # ④ 泰和场景迁移
python -m src.control.warning                             # ⑤ 预警调控演示
python -m src.viz.make_figures                            # ⑥ 报告/PPT 全部图表 → reports/figures/
streamlit run deliverables/demo/app.py                    # ⑦ 交互式演示看板（DEMO 加分项）
```

## 交付物构建

```bash
python deliverables/report/build_pdf.py    # 技术报告 MD → PDF（15 页，headless Chrome）
python deliverables/ppt/build_ppt.py       # 演示 PPT（18 页 PPTX）
bash deliverables/package_source.sh        # 源码提交包 ZIP（含数据样本，可复现）
```

视频录制脚本与分镜见 `deliverables/video/视频脚本_分镜.md`。

实验结果见 `docs/实验结果.md`（Köln 真实数据 +1h 预测 NSE 0.942），报告大纲见 `docs/技术报告大纲.md`。
