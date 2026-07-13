"""
轻量 Temporal TCN（1D CNN 堆叠 + 时间维全局池化 + 分类头）。

结构说明（便于 ONNX / CANN / 昇腾 310B）：
- 主干算子：Conv1d, ReLU, Dropout,（可选）Add 残差, GlobalAveragePool(等价 ReduceMean), Flatten, Gemm
- 避免 Transformer / 复杂 RNN / 自定义算子
- forward 无数据依赖分支，导出 ONNX 稳定

张量形状（注释）：
- 输入 x: [B, T, D]
- 转置为 Conv1d 格式: [B, D, T]  （通道维 = 特征维 D）
- 经若干 Conv1d(kernel=k, padding=k//2) 保持时间长度 T
- AdaptiveAvgPool1d(1) -> [B, C, 1] -> Flatten [B, C]
- Linear(C, num_classes) -> [B, num_classes]
"""
from __future__ import annotations

import torch
import torch.nn as nn


class TemporalTCN(nn.Module):
    def __init__(
        self,
        t: int,
        d: int,
        num_classes: int,
        channels: int = 64,
        kernel_size: int = 3,
        dropout: float = 0.2,
        use_residual: bool = True,
    ):
        super().__init__()
        self.t = t
        self.d = d
        self.num_classes = num_classes
        pad = kernel_size // 2
        c = channels
        self.use_residual = use_residual
        self.stem = nn.Conv1d(d, c, kernel_size, padding=pad)
        self.act1 = nn.ReLU()
        self.drop1 = nn.Dropout(dropout)
        self.mid = nn.Conv1d(c, c, kernel_size, padding=pad)
        self.act2 = nn.ReLU()
        self.drop2 = nn.Dropout(dropout)
        self.proj = nn.Conv1d(d, c, kernel_size=1) if use_residual else None
        self.pool = nn.AdaptiveAvgPool1d(1)
        self.head = nn.Linear(c, num_classes)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: [B, T, D]
        x = x.transpose(1, 2)
        # [B, D, T]
        out = self.stem(x)
        out = self.act1(out)
        out = self.drop1(out)
        if self.use_residual and self.proj is not None:
            out = out + self.proj(x)
        out = self.mid(out)
        out = self.act2(out)
        out = self.drop2(out)
        out = self.pool(out).squeeze(-1)
        return self.head(out)
