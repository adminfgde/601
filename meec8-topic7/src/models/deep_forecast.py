"""深度时序模型对比：LSTM（PyTorch）vs LightGBM，
输入过去 3h 序列，时间顺序 75/25 切分，输出测试段 NSE/MAE/RMSE。

用法：
  python -m src.models.deep_forecast --horizon-min 120
"""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from torch import nn

from src.models.forecast import _metrics, load_taihe

WINDOW = 36  # 过去 3h @5min


class LSTMForecaster(nn.Module):
    def __init__(self, n_feat: int, hidden: int = 64):
        super().__init__()
        self.lstm = nn.LSTM(n_feat, hidden, num_layers=2, batch_first=True,
                            dropout=0.1)
        self.head = nn.Linear(hidden, 1)

    def forward(self, x):
        out, _ = self.lstm(x)
        return self.head(out[:, -1]).squeeze(-1)


def make_sequences(df: pd.DataFrame, cols: list[str], h: int):
    arr = df[cols].to_numpy(dtype=np.float32)
    y = df["inflow"].shift(-h).to_numpy(dtype=np.float32)
    xs, ys, idx = [], [], []
    for i in range(WINDOW, len(df) - h):
        xs.append(arr[i - WINDOW:i])
        ys.append(y[i])
        idx.append(df.index[i])
    return np.stack(xs), np.array(ys), pd.DatetimeIndex(idx)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sim-dir", default="data/simulated_realrain")
    ap.add_argument("--horizon-min", type=int, default=120)
    ap.add_argument("--epochs", type=int, default=15)
    ap.add_argument("--out", default="reports/deep_forecast.json")
    args = ap.parse_args()
    torch.manual_seed(7)
    np.random.seed(7)

    df = load_taihe(args.sim_dir)
    cols = ["inflow", "rain"] + [c for c in df.columns if c.startswith("lvl_")]
    X, y, idx = make_sequences(df, cols, args.horizon_min // 5)
    split = int(len(X) * 0.75)
    mu, sd = X[:split].mean((0, 1)), X[:split].std((0, 1)) + 1e-6
    ymu, ysd = y[:split].mean(), y[:split].std()
    Xn, yn = (X - mu) / sd, (y - ymu) / ysd

    val = int(split * 0.9)
    device = "cpu"
    model = LSTMForecaster(len(cols)).to(device)
    opt = torch.optim.Adam(model.parameters(), lr=1e-3)
    loss_fn = nn.MSELoss()
    tr = torch.utils.data.DataLoader(
        torch.utils.data.TensorDataset(torch.from_numpy(Xn[:val]),
                                       torch.from_numpy(yn[:val])),
        batch_size=256, shuffle=True)
    xva = torch.from_numpy(Xn[val:split])
    yva = torch.from_numpy(yn[val:split])

    best, best_state, patience = np.inf, None, 0
    for ep in range(args.epochs):
        model.train()
        for xb, yb in tr:
            opt.zero_grad()
            loss = loss_fn(model(xb), yb)
            loss.backward()
            opt.step()
        model.eval()
        with torch.no_grad():
            vloss = float(loss_fn(model(xva), yva))
        print(f"epoch {ep + 1} val_loss={vloss:.4f}")
        if vloss < best - 1e-4:
            best, best_state, patience = vloss, model.state_dict(), 0
        else:
            patience += 1
            if patience >= 3:
                break
    model.load_state_dict(best_state)

    model.eval()
    preds = []
    with torch.no_grad():
        for i in range(split, len(Xn), 4096):
            preds.append(model(torch.from_numpy(Xn[i:i + 4096])).numpy())
    pred = np.concatenate(preds) * ysd + ymu
    m = _metrics(y[split:], pred)
    report = {"model": "LSTM(2层×64, 窗口3h)", "horizon_min": args.horizon_min,
              "n_train": int(split), "n_test": int(len(X) - split), **m}
    print(json.dumps(report, ensure_ascii=False))
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"-> {args.out}")


if __name__ == "__main__":
    main()
