# Pose-640 AIPP validation and benchmark

## Test scope

- Device: Ascend 310B (`davinci-mini`)
- Reference model: `yolo11n_pose_640_source_ref.om`
- AIPP model: `yolo11n_pose_640_aipp.om`
- Reference input: float32 NCHW, `[1, 3, 640, 640]`
- AIPP input: uint8 packed BGR, `[1, 640, 640, 3]`
- Warm-up is excluded from all timing statistics.
- The timings below cover `InferSession.infer()` only. They do not include camera input, CPU letterbox, post-processing, drawing, or result transmission.

## Timing results

| Run | Model | Loops | Mean (ms) | P50 (ms) | P95 (ms) | Min (ms) | Max (ms) |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | Reference OM | 100 | 28.112 | 27.395 | 33.586 | 26.985 | 36.598 |
| 1 | AIPP OM | 100 | 18.500 | 18.160 | 19.184 | 17.978 | 26.987 |
| 2 | Reference OM | 200 | 28.080 | 27.165 | 35.498 | 26.880 | 37.036 |
| 2 | AIPP OM | 200 | 18.603 | 18.323 | 19.403 | 18.013 | 25.561 |

The 200-loop repeat reduced mean inference latency from `28.080 ms` to `18.603 ms`, a reduction of `33.75%` and a throughput speedup of about `1.51x`. The 100-loop run showed a similar `34.19%` reduction.

## Host input reduction

| Model | Host input bytes | Reduction |
| --- | ---: | ---: |
| Reference OM | 4,915,200 | - |
| AIPP OM | 1,228,800 | 75% |

AIPP accepts the letterboxed BGR image as packed `uint8`, performs BGR-to-RGB channel conversion and `1/255` normalization in the model input pipeline, and avoids constructing and transferring a float32 NCHW tensor on the host.

## Numerical validation

Both models were compared with the same ONNX golden output.

| Metric | Reference OM | AIPP OM |
| --- | ---: | ---: |
| Cosine similarity | 0.999999870 | 0.999999862 |
| MAE | 0.073207 | 0.074308 |
| RMSE | 0.151386 | 0.155769 |
| Top-10 index overlap | 10/10 | 10/10 |

The AIPP output is as close to the ONNX golden output as the reference OM for this test input. The current golden sample has very low detection confidence, so a real-camera comparison of boxes and keypoints is still required before replacing the production model.

## Conclusion

The static AIPP model passed the current numerical check and produced a repeatable inference-time improvement. It has now been integrated into `BoardPoseRuntime` and tested through the complete camera runtime. See `AIPP_POSE640_RUNTIME_RESULTS_20260716.md` for the scheduling-level results.

Raw results:

- `pose640_aipp_validation.json`
- `pose640_aipp_validation_repeat.json`
