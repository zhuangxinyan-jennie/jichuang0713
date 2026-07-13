pre_on_board minimal deployment workspace for multimodal realtime pipeline

Current status
- This directory now contains the runtime subset actually used by the current multimodal system.
- It also includes the first-stage board deployment skeleton under `board_deploy/`.

Local PC start command
- `python3 run_realtime_yolo_asr.py`

Board deployment entry files
- `board_deploy/README_BOARD_DEPLOY.md`
- `board_deploy/model_manifest.json`
- `board_deploy/convert_models_on_board.sh`
- `board_deploy/STREAMING_PLAN.md`
