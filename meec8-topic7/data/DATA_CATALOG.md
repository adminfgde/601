# 数据目录与来源清单（DATA CATALOG）

> 原则：取之尽锱铢，用之如泥沙。多渠道穷尽获取，逐项标记来源、许可、用途。
> 后端可直接下载的已入库（`data/external/`）；`data/raw/` 为组委会官方数据；大体量/需前端登录的在末尾登记为"待取清单"。

---

## 一、组委会官方数据（`data/raw/`，第一优先，完全合规）

| 文件 | 内容 | 用途 |
|---|---|---|
| `Date1_主题七任务书.doc` | 主题七完整任务书（背景/任务/成果/数据） | 需求基准 |
| `Date1_产业赛道评分表.xlsx` | 官方评分细则（规范性15+技术30+应用30+答辩20+加分5） | 交付对齐 |
| `Date1_泵站配泵能力与服务范围.xlsx` / `.csv` | **26 座泵站**（A–Z）设计能力(m³/s)、服务面积、四至服务范围 | 管网拓扑骨架、能力约束 |
| `Date1_泵站系统图.png` | 彭越浦泵站为汇入点的干线-重力接入-泵站系统拓扑图（含污水/雨水截流/合流/合建泵站图例、苏州河水系） | 拓扑还原 |
| `Date1_泵站分布地图.png` | 26 泵站在上海（普陀/长宁/静安/黄浦沿苏州河）的地理分布 | 空间校核 |

**关键事实（从 Date1 解构）**：泰和污水厂上游为**彭越浦泵站汇流的合流制系统**，26 座泵站沿苏州河分布，总设计能力约 **40.5 m³/s**；系统图明确干线（红）、重力接入（黑）、水系（蓝）三类连接及污水/雨水截流/合流/合建四类泵站——这就是主题七"厂站网一体化"的真实对象。

---

## 二、外部真实数据集（`data/external/`，已后端下载，含许可）

### 1. Graz-West R05 连续管网水力+污染物数据集（2008–2011）★最贴合
- 目录：`zenodo_15783832_graz_sewer/`（原始 zip + `extracted/`）
- 来源：Graz 大学城市水管理所 / Zenodo 15783832，**CC-BY-4.0**
- 内容：合流制管网出口的**连续液位/流量**（hydraulic data）、**在线光谱水质 COD/TSS**（pollutant data，calibrated+spectrometer）、**实验室化验**（lab data）、**多站降雨**（precipitation data）、**SWMM 模型文件**（sewer model/model.inp）、降雨事件表
- 场景：457 ha、19500 人、合流制、年降雨 800mm——与泰和合流制上游高度同构
- 用途：**方法验证/预训练主力**（水量水质+降雨+模型齐全，可直接跑"感知-预测"闭环）

### 2. Barcelona Poblenou 管网 s::can 在线水质
- 文件：`zenodo_8043771_barcelona_quality/scan_water_quality.csv`（48MB）
- 来源：Zenodo 8043771，CC-BY
- 内容：管网内在线水质仪时序——电导率、流量、pH、温度、NH3、CODeq、TSS、NH4
- 用途：**管网内在线水质**这一稀缺品类；水质预测特征参考、毒性/异常检测样本

### 3. 英国复杂内涝城区高分辨率水文+管网监测
- 目录：`zenodo_20699635_uk_sewer/`（网络 shapefile + 雨量 + 钻孔遥测 + 索引）
- 来源：Zenodo 20699635
- 内容：管网 GIS（`2_network_shape_files.zip`）、雨量遥测（`7_rain_gauge...zip`）、地下水位（`3_borehole...zip`）、测点索引
- 注：`5_sewer_telemetry_data.zip`(231MB)、`4_fluvial...zip`(106MB)、`1_catchment_shape...zip`(331MB) 体量大，登记于待取清单按需拉
- 用途：管网 GIS 结构参考、降雨-液位响应、入渗（地下水）耦合

### 4. BSM2 国际标准污水厂进水基准数据
- 目录：`bsm2_influent/`
- 来源：`github.com/fau-evt/bsm2-python`（BSD 许可）
- 内容：`dryinfluent.csv`（旱天 14 天 15min）、`raininfluent.csv`（含降雨事件）、`dyninfluent_bsm2.csv`（609 天动态进水，流量+ASM 组分）、`constinfluent_bsm2.csv`
- 用途：**厂前进水（流量+COD/N/P 组分）国际基准**；预测模型标签范式、工艺冲击响应对照

### 5. 上海气象站逐日观测（GHCN-Daily）
- 文件：`noaa_ghcnd_shanghai/CHM00058362_shanghai_daily.csv`（12925 行，站号 58362 上海宝山/虹桥区域）
- 来源：NOAA NCEI GHCN-Daily，公共领域
- 内容：逐日降水 PRCP、气温 TMAX/TMIN 等，覆盖多年
- 用途：**降雨/气象驱动项**的正规公开来源；模拟器降雨参数标定

### 6. SWMM 示例管网模型
- 目录：`swmm_examples/`
- 来源：`github.com/pyswmm/pyswmm`（tests/data），MIT
- 内容：含泵/堰/污染物的 SWMM `.inp` 示例（`model_full_features/pollutants/pump_setting/weir_setting`）
- 用途：SWMM 建模范式参考、pyswmm 驱动生成物理一致数据

### 7. Köln-Weiden 厂-网-雨一体化时序（2017 全年）★★ 结构最对口
- 文件：`zenodo_6992694_koeln_wtp_network_rain/wtp_network_rain.csv`（105120 行，15min，CC-BY-4.0）
- 来源：Zenodo 6992694（德国科隆 Weiden 污水厂）
- 内容：**同一张表内含** 降雨强度 `rain_rate`、3 个管网节点液位 `Level_1/2/3`、调蓄管道液位 `level_storage_sewer`、**污水厂进水流量 `wtp_inflow`**
- 用途：**主题七"厂站网一体化"的最佳真值样本**——一张表就复现"上游管网液位 + 降雨 → 厂前进水流量"的完整因果链，直接用于建模、验证提前量与雨天入流响应

### 8. WWTP 进水量观测与处理数据（多站）
- 目录：`zenodo_15301164_wwtp_inflow/`（observations/wwtp.csv、dmi.csv 气象、processed/data.csv；CC-BY-NC-4.0，仅学术非商用）
- 来源：Zenodo 15301164
- 用途：厂前进水流量真值 + 配套气象；进水预测标签

### 9. Milan 污水厂进出水多参数在线监测（2019–2022）
- 目录：`zenodo_7116995_milan_wwtp_quality/`（CC-BY-4.0）
- 内容：进水 TSS/电导率/P-PO4、出水 NH4/NNOx/PPO4/pH/ORP、流量、TOC 等多条长时序在线数据
- 用途：**厂前进水水质真值**（TSS、电导率、磷）；水质预测标签与特征

### 10. Athens Psyttalia / 荷兰 mWWTP 化验数据
- 目录：`zenodo_18431689_athens_wwtp/`、`zenodo_14826489_wwtp_setpoint/`（均 CC-BY-4.0）
- 内容：进水化验成分（COD/N/P 等）与建模 set-point 实验室数据
- 用途：进水组分范围校核、报告行业调研素材

### 11. UCI 城市污水厂日运行数据（经典 ML 基准）
- 目录：`uci_water_treatment/`（UCI ML Repository，公开）
- 内容：527 天逐日进水/出水 38 项指标（流量、pH、COD、BOD、SS、导电度等）+ 故障标注
- 用途：进水-出水关系与异常检测的经典基准数据集，方法对照

### 12. 上海逐小时气象观测（NOAA ISD，2022–2025）
- 目录：`noaa_isd_shanghai_hourly/`（宝山 58362 + 虹桥 58367，逐小时，含降水 AA1/气温/湿度/气压；公共领域）
- 来源：NOAA NCEI Global Hourly (ISD)，免登录官方渠道
- 用途：替代被地理封锁的 CMA，作为**上海小时级降雨/气象驱动项**

### 13. 上海逐小时降水再分析（Open-Meteo/ERA5，2020–2025）
- 文件：`openmeteo_shanghai_hourly/shanghai_2020_2025_hourly.csv`（52612 行，逐小时降水/降雨/气温/湿度，北京时区）
- 来源：Open-Meteo Historical API（ERA5 再分析，CC-BY-4.0，免登录）
- 用途：无缺口连续降雨序列，与 ISD 实测互校；模拟器降雨参数标定与雨天入流建模

### 14. 上海市水务局「水情信息」全市水文站 10~15 分钟级时序（2021–2025.09）★★ 官方驱动项主力
- 目录：`shgov_water_regime/`（shuiqing_001/002.zip，解压后 10 个 CSV 共约 1150 万行；详见目录内 README）
- 来源：上海市公共数据开放平台 data.sh.gov.cn（上海市水务局，**无条件开放**），2026-07-22 经国内网络（DAO Bridge 笔记本通道）从官方下载入口获取
- 内容：全市 52 个水文站的 `rain(雨量)/waterlevel(水位)/sealevel(潮位)` 10~15 分钟级时序，含吴淞口、崇明南门等苏州河/黄浦江沿线站点，覆盖 2021-01-01 ~ 2025-09-23
- 用途：**上海本地官方分钟级降雨与河道水位**——雨天入流建模的最优驱动项，直接替代 CMA 分钟级降雨需求；河道水位/潮位作系统边界条件

### 15. CNEMC 国家地表水水质自动监测实时快照（上海 17 断面）
- 目录：`cnemc_shanghai_realtime/realtime_20260722T0501.json`
- 来源：中国环境监测总站 szzdjc.cnemc.cn 实时发布系统，2026-07-22 经国内网络获取
- 内容：上海市 17 个断面某一时刻的水温/pH/溶解氧/电导率/浊度/高锰酸盐指数/氨氮/总磷/总氮（含苏州河水系断面）
- 定位：**实时快照而非历史序列**；用作苏州河边界水质量级校核。如需时序可定期抓取累积

---

## 三、自建模拟数据（`data/simulated/`，见 `src/simulation/`）
以 Date1 的 26 泵站拓扑与配泵能力为骨架，批量生成旱天/雨天/冲击全场景的节点液位流量、泵站运行、厂前进水水量水质、降雨、事件标签，任意天数可复现。定位：**规模训练集/场景库**。

---

## 四、待取清单（体量大或需前端登录，按需获取）

| 来源 | 内容 | 获取方式 | 状态 |
|---|---|---|---|
| Zenodo 20699635 剩余 zip | UK 管网遥测(231M)/河道(106M)/汇水shp(331M) | 后端 curl，按需 | 未取（省空间） |
| Bellinge 数据集（丹麦 Odense） | 完整城区排水系统多年时序+SWMM/MIKE | DTU ERDA / ESSD 论文附录 | 待取 |
| Eawag UWO（瑞士 Fehraltorf） | 密集传感网多年管网数据 | ERIC / opendata.eawag.ch | 待取 |
| 中国气象数据网 data.cma.cn | 上海分钟级降雨 | 海外 IP 被 403 地理封锁 | **已由水务局「水情信息」10~15min 雨量替代（第 14 项）**，CMA 不再必需 |
| 中国环境监测总站 cnemc.cn | 苏州河等断面水质 4h 级 | 国内网络实时接口 | 已取实时快照（第 15 项）；历史序列无公开下载口 |
| 上海市政务数据 data.sh.gov.cn | 水情信息（已取）；泵站信息表（黄浦/徐汇/浦东等区）、排水系统基本信息 | 国内网络前端 | 「水情信息」已入库；各区泵站表/排水系统信息多为**有条件开放**（需实名认证+申请），如需可发起申请 |
| 天池 tianchi.aliyun.com | 水务相关数据集 | 已用手机号登录并逐关键词检索（污水/水质/降雨/供水/排水） | **已核实无相关数据**（仅藻类检测/养殖水质/国外降雨等，与厂站网无关） |
| Kaggle/DataFountain 水务赛题 | 进水预测/漏损等结构相近数据 | 前端账号 | 需登录 |

> 国内官方渠道已通过 DAO Bridge 笔记本国内网络打通：无条件开放的均已获取；余下均为需实名认证/申请的有条件开放资源，按需可继续发起。
