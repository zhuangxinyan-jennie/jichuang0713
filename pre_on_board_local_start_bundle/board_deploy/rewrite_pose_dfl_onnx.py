from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import onnx
from onnx import helper, numpy_helper

CHAIN_NAMES = (
    "/model.23/dfl/Constant",
    "/model.23/dfl/Reshape",
    "/model.23/dfl/Transpose",
    "/model.23/dfl/Softmax",
    "/model.23/dfl/conv/Conv",
    "/model.23/dfl/Constant_1",
    "/model.23/dfl/Reshape_1",
)
CHAIN_TYPES = ("Constant", "Reshape", "Transpose", "Softmax", "Conv", "Constant", "Reshape")


def rewrite_dfl(model: onnx.ModelProto) -> None:
    nodes = list(model.graph.node)
    by_name = {node.name: (index, node) for index, node in enumerate(nodes)}
    missing = [name for name in CHAIN_NAMES if name not in by_name]
    if missing:
        raise RuntimeError(f"DFL chain nodes not found: {missing}")

    chain = [by_name[name] for name in CHAIN_NAMES]
    indices = [index for index, _ in chain]
    actual_types = tuple(node.op_type for _, node in chain)
    if actual_types != CHAIN_TYPES:
        raise RuntimeError(f"unexpected DFL chain types: {actual_types}")
    if indices != list(range(indices[0], indices[0] + len(indices))):
        raise RuntimeError(f"DFL chain is not contiguous: {indices}")

    _, reshape = chain[1]
    _, dfl_conv = chain[4]
    _, final_reshape = chain[-1]
    dfl_input = reshape.input[0]
    dfl_output = final_reshape.output[0]
    removed_weight = dfl_conv.input[1]

    shape_name = "pose_dfl_shape_1x4x16x8400"
    weights_name = "pose_dfl_weights_0_to_15"
    axes_name = "pose_dfl_reduce_axis_2"
    existing_initializers = {item.name for item in model.graph.initializer}
    collisions = existing_initializers & {shape_name, weights_name, axes_name}
    if collisions:
        raise RuntimeError(f"initializer names already exist: {sorted(collisions)}")

    model.graph.initializer.extend(
        [
            numpy_helper.from_array(np.asarray([1, 4, 16, 8400], dtype=np.int64), shape_name),
            numpy_helper.from_array(np.arange(16, dtype=np.float32).reshape(1, 1, 16, 1), weights_name),
            numpy_helper.from_array(np.asarray([2], dtype=np.int64), axes_name),
        ]
    )
    retained_initializers = [item for item in model.graph.initializer if item.name != removed_weight]
    del model.graph.initializer[:]
    model.graph.initializer.extend(retained_initializers)

    replacement = [
        helper.make_node(
            "Reshape",
            [dfl_input, shape_name],
            ["pose_dfl_reshape_output"],
            name="/model.23/dfl_rewrite/Reshape",
        ),
        helper.make_node(
            "Softmax",
            ["pose_dfl_reshape_output"],
            ["pose_dfl_softmax_output"],
            name="/model.23/dfl_rewrite/Softmax",
            axis=2,
        ),
        helper.make_node(
            "Mul",
            ["pose_dfl_softmax_output", weights_name],
            ["pose_dfl_weighted_output"],
            name="/model.23/dfl_rewrite/Mul",
        ),
        helper.make_node(
            "ReduceSum",
            ["pose_dfl_weighted_output", axes_name],
            [dfl_output],
            name="/model.23/dfl_rewrite/ReduceSum",
            keepdims=0,
        ),
    ]

    start = indices[0]
    del model.graph.node[:]
    model.graph.node.extend(nodes[:start] + replacement + nodes[start + len(indices) :])


def main() -> None:
    parser = argparse.ArgumentParser(description="Rewrite YOLO11 pose DFL as Softmax + Mul + ReduceSum.")
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    if args.input.resolve() == args.output.resolve():
        parser.error("input and output must be different files")

    model = onnx.load(args.input)
    rewrite_dfl(model)
    onnx.checker.check_model(model, full_check=True)
    inferred = onnx.shape_inference.infer_shapes(model, strict_mode=True)
    onnx.checker.check_model(inferred, full_check=True)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    onnx.save(model, args.output)
    print(f"[DONE] wrote {args.output}")
    print("[DFL] [1,64,8400] -> Reshape[1,4,16,8400] -> Softmax(axis=2) -> Mul -> ReduceSum(axis=2)")


if __name__ == "__main__":
    main()
