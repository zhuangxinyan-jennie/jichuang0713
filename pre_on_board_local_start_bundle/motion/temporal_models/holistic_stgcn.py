"""
Lightweight ST-GCN for pose+hands landmarks.

Board inference uses NPU pose + hand landmark OMs; training may use MediaPipe offline.
Input: [B, C, T, V] with C=10, T=48, V=75.
"""
from __future__ import annotations

from typing import Iterable, List, Sequence, Tuple

import numpy as np
import torch
import torch.nn as nn

NUM_NODES = 75
LEFT_HAND_OFFSET = 33
RIGHT_HAND_OFFSET = 54

POSE_EDGES: List[Tuple[int, int]] = [
    (0, 1), (1, 2), (2, 3), (3, 7), (0, 4), (4, 5), (5, 6), (6, 8),
    (9, 10), (11, 12), (11, 13), (13, 15), (15, 17), (15, 19), (15, 21),
    (17, 19), (12, 14), (14, 16), (16, 18), (16, 20), (16, 22), (18, 20),
    (11, 23), (12, 24), (23, 24), (23, 25), (25, 27), (27, 29), (29, 31),
    (27, 31), (24, 26), (26, 28), (28, 30), (30, 32), (28, 32),
]

HAND_EDGES_BASE: List[Tuple[int, int]] = [
    (0, 1), (1, 2), (2, 3), (3, 4), (0, 5), (5, 6), (6, 7), (7, 8),
    (0, 9), (9, 10), (10, 11), (11, 12), (0, 13), (13, 14), (14, 15),
    (15, 16), (0, 17), (17, 18), (18, 19), (19, 20), (5, 9), (9, 13),
    (13, 17),
]


def _offset_edges(edges: Iterable[Tuple[int, int]], offset: int) -> List[Tuple[int, int]]:
    return [(a + offset, b + offset) for a, b in edges]


GRAPH_EDGES: List[Tuple[int, int]] = (
    POSE_EDGES
    + _offset_edges(HAND_EDGES_BASE, LEFT_HAND_OFFSET)
    + _offset_edges(HAND_EDGES_BASE, RIGHT_HAND_OFFSET)
    + [(15, LEFT_HAND_OFFSET), (16, RIGHT_HAND_OFFSET)]
)


def bone_parent_indices(num_nodes: int = NUM_NODES) -> np.ndarray:
    parent = np.full((num_nodes,), -1, dtype=np.int64)
    for src, dst in GRAPH_EDGES:
        if 0 <= dst < num_nodes and parent[dst] < 0:
            parent[dst] = src
    return parent


def _normalize_adjacency(a: np.ndarray) -> np.ndarray:
    degree = a.sum(axis=1, keepdims=True)
    degree[degree <= 1e-6] = 1.0
    return a / degree


def build_adjacency(num_nodes: int = NUM_NODES) -> np.ndarray:
    self_link = np.eye(num_nodes, dtype=np.float32)
    toward_child = np.zeros((num_nodes, num_nodes), dtype=np.float32)
    toward_parent = np.zeros((num_nodes, num_nodes), dtype=np.float32)
    for src, dst in GRAPH_EDGES:
        if 0 <= src < num_nodes and 0 <= dst < num_nodes:
            toward_child[src, dst] = 1.0
            toward_parent[dst, src] = 1.0
    return np.stack(
        [
            self_link,
            _normalize_adjacency(toward_parent),
            _normalize_adjacency(toward_child),
        ],
        axis=0,
    ).astype(np.float32)


class GraphConv(nn.Module):
    def __init__(self, in_channels: int, out_channels: int, adjacency: np.ndarray):
        super().__init__()
        if adjacency.ndim != 3:
            raise ValueError("adjacency must be [K,V,V]")
        self.num_subsets = int(adjacency.shape[0])
        self.register_buffer("adjacency", torch.tensor(adjacency, dtype=torch.float32))
        self.proj = nn.Conv2d(in_channels, out_channels * self.num_subsets, kernel_size=1)
        self.out_channels = out_channels

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        n, _, t, v = x.shape
        x = self.proj(x)
        x = x.view(n, self.num_subsets, self.out_channels, t, v)
        parts = []
        for k in range(self.num_subsets):
            parts.append(torch.matmul(x[:, k], self.adjacency[k]))
        return torch.stack(parts, dim=0).sum(dim=0)


class STGCNBlock(nn.Module):
    def __init__(
        self,
        in_channels: int,
        out_channels: int,
        adjacency: np.ndarray,
        temporal_kernel: int = 9,
        dropout: float = 0.2,
    ):
        super().__init__()
        padding = (temporal_kernel // 2, 0)
        self.gcn = GraphConv(in_channels, out_channels, adjacency)
        self.tcn = nn.Sequential(
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True),
            nn.Conv2d(
                out_channels,
                out_channels,
                kernel_size=(temporal_kernel, 1),
                padding=padding,
            ),
            nn.BatchNorm2d(out_channels),
            nn.Dropout(dropout),
        )
        if in_channels == out_channels:
            self.residual: nn.Module = nn.Identity()
        else:
            self.residual = nn.Sequential(
                nn.Conv2d(in_channels, out_channels, kernel_size=1),
                nn.BatchNorm2d(out_channels),
            )
        self.relu = nn.ReLU(inplace=True)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.relu(self.tcn(self.gcn(x)) + self.residual(x))


class HolisticLiteSTGCN(nn.Module):
    def __init__(
        self,
        in_channels: int = 10,
        num_classes: int = 8,
        channels: Sequence[int] = (32, 64, 64, 128),
        num_nodes: int = NUM_NODES,
        temporal_kernel: int = 9,
        dropout: float = 0.2,
    ):
        super().__init__()
        adjacency = build_adjacency(num_nodes)
        self.in_channels = in_channels
        self.num_classes = num_classes
        self.num_nodes = num_nodes
        self.channels = tuple(int(c) for c in channels)
        self.data_bn = nn.BatchNorm1d(in_channels * num_nodes)

        blocks = []
        c_in = in_channels
        for c_out in self.channels:
            blocks.append(
                STGCNBlock(
                    c_in,
                    int(c_out),
                    adjacency,
                    temporal_kernel=temporal_kernel,
                    dropout=dropout,
                )
            )
            c_in = int(c_out)
        self.blocks = nn.Sequential(*blocks)
        self.head = nn.Linear(c_in, num_classes)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        n, c, t, v = x.shape
        x = x.permute(0, 3, 1, 2).contiguous().view(n, v * c, t)
        x = self.data_bn(x)
        x = x.view(n, v, c, t).permute(0, 2, 3, 1).contiguous()
        x = self.blocks(x)
        x = x.mean(dim=(2, 3))
        return self.head(x)
