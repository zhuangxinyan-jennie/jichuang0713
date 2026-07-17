#include "video_pre_fuse_custom_tiling.h"
#include "register/op_def_registry.h"

#include <cstdint>
#include <cstdio>
#include <cstring>

namespace {
constexpr const char* kTilingBin = "/tmp/hgbo_vpf_tiling.bin";

#pragma pack(push, 1)
struct HgboTilingBin {
    uint32_t inputH;
    uint32_t inputW;
    uint32_t inputC;
    uint32_t outputH;
    uint32_t outputW;
    uint32_t outputC;
    uint32_t splitAxis;
    uint32_t tileH;
    uint32_t tileW;
    uint32_t tileLen;
    uint32_t bufferNum;
};
#pragma pack(pop)

bool LoadHgboTiling(HgboTilingBin* out) {
    if (out == nullptr) {
        return false;
    }
    FILE* fp = fopen(kTilingBin, "rb");
    if (fp == nullptr) {
        return false;
    }
    const size_t n = fread(out, 1, sizeof(HgboTilingBin), fp);
    fclose(fp);
    return n == sizeof(HgboTilingBin);
}

uint32_t ComputeTileLength(const HgboTilingBin& cfg) {
    if (cfg.splitAxis == 0) {
        return cfg.tileH * cfg.inputW * cfg.inputC;
    }
    if (cfg.splitAxis == 1) {
        return cfg.inputH * cfg.tileW * cfg.inputC;
    }
    return cfg.tileLen;
}
}  // namespace

namespace optiling {
static ge::graphStatus TilingFunc(gert::TilingContext* context) {
    HgboTilingBin cfg{};
    if (!LoadHgboTiling(&cfg)) {
        cfg.inputH = 720;
        cfg.inputW = 1280;
        cfg.inputC = 3;
        cfg.outputH = 640;
        cfg.outputW = 640;
        cfg.outputC = 3;
        cfg.splitAxis = 0;
        cfg.tileH = 8;
        cfg.tileW = 128;
        cfg.tileLen = 4096;
        cfg.bufferNum = 1;
    }

    VideoPreFuseCustomTilingData tiling;
    tiling.set_inputH(cfg.inputH);
    tiling.set_inputW(cfg.inputW);
    tiling.set_inputC(cfg.inputC);
    tiling.set_outputH(cfg.outputH);
    tiling.set_outputW(cfg.outputW);
    tiling.set_outputC(cfg.outputC);
    tiling.set_splitAxis(cfg.splitAxis);
    tiling.set_tileH(cfg.tileH);
    tiling.set_tileW(cfg.tileW);
    tiling.set_tileLen(cfg.tileLen);
    tiling.set_bufferNum(cfg.bufferNum);

    const uint32_t tileLength = ComputeTileLength(cfg);
    const uint32_t totalOut = cfg.outputH * cfg.outputW * cfg.outputC;
    tiling.set_tileLength(tileLength > 0 ? tileLength : 1024);
    tiling.set_totalOut(totalOut);

    context->SetBlockDim(1);
    tiling.SaveToBuffer(context->GetRawTilingData()->GetData(), context->GetRawTilingData()->GetCapacity());
    context->GetRawTilingData()->SetDataSize(tiling.GetDataSize());
    return ge::GRAPH_SUCCESS;
}
}  // namespace optiling

namespace ge {
static ge::graphStatus InferShape(gert::InferShapeContext* context) {
    gert::Shape* y_shape = context->GetOutputShape(0);
    y_shape->SetDimNum(3);
    y_shape->SetDim(0, 640);
    y_shape->SetDim(1, 640);
    y_shape->SetDim(2, 3);
    return GRAPH_SUCCESS;
}
}  // namespace ge

namespace ops {
class VideoPreFuseCustom : public OpDef {
public:
    explicit VideoPreFuseCustom(const char* name) : OpDef(name) {
        this->Input("x")
            .ParamType(REQUIRED)
            .DataType({ge::DT_FLOAT16})
            .Format({ge::FORMAT_ND})
            .UnknownShapeFormat({ge::FORMAT_ND});
        this->Output("y")
            .ParamType(REQUIRED)
            .DataType({ge::DT_FLOAT16})
            .Format({ge::FORMAT_ND})
            .UnknownShapeFormat({ge::FORMAT_ND});

        this->SetInferShape(ge::InferShape);
        this->AICore().SetTiling(optiling::TilingFunc);
        this->AICore().AddConfig("ascend310b");
    }
};

OP_ADD(VideoPreFuseCustom);
}  // namespace ops
