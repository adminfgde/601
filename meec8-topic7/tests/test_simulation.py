"""模拟器与设计暴雨的单元测试。"""
import subprocess
import sys

import numpy as np
import pandas as pd
import pytest

from src.simulation.design_storm import R_PEAK, chicago_hyetograph, intensity_mm_min


@pytest.fixture(scope="session")
def sim_dir(tmp_path_factory):
    out = tmp_path_factory.mktemp("sim")
    subprocess.run([sys.executable, "-m", "src.simulation.generate",
                    "--days", "3", "--seed", "1", "--out", str(out)],
                   check=True)
    return out


def test_sim_outputs(sim_dir):
    q = pd.read_csv(sim_dir / "plant_inflow_quality.csv",
                    parse_dates=["time"], index_col="time")
    for col in ["inflow_m3h", "cod_mg_l", "nh3n_mg_l", "ph", "ss_mg_l"]:
        assert col in q.columns
        assert q[col].notna().all()
    assert (q["inflow_m3h"] > 0).all()
    assert q["ph"].between(4, 10).all()
    lv = pd.read_csv(sim_dir / "node_levels.csv",
                     parse_dates=["time"], index_col="time")
    assert lv.shape[1] >= 40  # 43 节点
    labels = pd.read_csv(sim_dir / "event_labels.csv",
                         parse_dates=["time"], index_col="time")
    assert set(labels["shock_event"].unique()) <= {0, 1}


def test_chicago_hyetograph_mass_balance():
    step, dur = 10, 120
    h = chicago_hyetograph(100, duration_min=dur, step_min=step)
    # 芝加哥过程线总量应等于暴雨强度公式给出的历时平均强度×历时
    total_formula = dur * float(intensity_mm_min(np.array([float(dur)]), 100)[0])
    assert h.sum() == pytest.approx(total_formula, rel=0.05)
    peak_pos = int(np.argmax(h)) * step
    assert abs(peak_pos - R_PEAK * dur) <= 2 * step


def test_intensity_monotonic():
    t = np.array([5.0, 30.0, 120.0])
    i5, i100 = intensity_mm_min(t, 5), intensity_mm_min(t, 100)
    assert (i100 > i5).all()          # 重现期越大越强
    assert (np.diff(i5) < 0).all()    # 历时越长强度越低
