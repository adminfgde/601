"""特征工程 / 预测 / 预警 / SWMM 构建的单元测试。"""
import numpy as np
import pandas as pd

from src.control.benefits import event_detection
from src.control.warning import LEVELS, PLANT_CAPACITY_M3H, evaluate
from src.models.forecast import build_features
from src.swmm.build_inp import UNITS, build_inp


def _toy_df(n=500):
    idx = pd.date_range("2024-06-01", periods=n, freq="5min")
    rng = np.random.default_rng(0)
    return pd.DataFrame({
        "inflow": 4000 + 800 * np.sin(np.arange(n) / 50) + rng.normal(0, 30, n),
        "rain": rng.exponential(0.1, n),
    }, index=idx)


def test_build_features_no_leakage():
    df = _toy_df()
    h = 12
    X, y = build_features(df, "inflow", ["rain"], h)
    assert len(X) == len(y) > 0
    assert X.notna().all().all()
    # y 是未来 h 步：与原序列对齐检查
    t0 = X.index[0]
    assert y.loc[t0] == df["inflow"].loc[t0 + pd.Timedelta(minutes=5 * h)]


def test_warning_levels():
    s = pd.Series([0.5, 0.7, 0.85, 1.0, 1.2]) * PLANT_CAPACITY_M3H
    s.index = pd.date_range("2024-06-01", periods=5, freq="5min")
    rep = evaluate(s, 60)
    assert list(rep["warning_level"]) == ["正常", "蓝色", "黄色", "橙色", "红色"]
    assert len(LEVELS) == 4


def test_event_detection_tolerance():
    idx = pd.date_range("2024-06-01", periods=100, freq="5min")
    truth = pd.Series(0.5 * PLANT_CAPACITY_M3H, index=idx)
    truth.iloc[40:50] = 1.2 * PLANT_CAPACITY_M3H  # 一次超阈事件
    pred = truth.shift(6, fill_value=0.5 * PLANT_CAPACITY_M3H)  # 预测滞后 30min
    strict = event_detection(truth, pred, 1.0, tol_steps=0)
    loose = event_detection(truth, pred, 1.0, tol_steps=12)
    assert strict["events"] == loose["events"] == 1
    assert loose["hits"] >= strict["hits"]
    assert loose["recall"] == 1.0


def test_swmm_inp_sections(tmp_path):
    rain = pd.Series(
        [0.0] * 100 + [5.0] * 12 + [0.0] * 32,
        index=pd.date_range("2025-07-01", periods=144, freq="10min"))
    csv = tmp_path / "rain.csv"
    rain.to_frame("rain_mm").to_csv(csv)
    inp = build_inp(str(csv), "2025-07-01", 1)
    for sec in ["[SUBCATCHMENTS]", "[STORAGE]", "[PUMPS]", "[XSECTIONS]",
                "[CURVES]", "[TIMESERIES]"]:
        assert sec in inp
    for n, *_ in UNITS:
        assert f"ST_{n}" in inp and f"P_{n}" in inp
