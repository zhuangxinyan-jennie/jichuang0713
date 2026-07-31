#include "kernel_operator.h"
#define __NPU_TILING__
#include "video_pre_fuse_custom_tiling_data.h"
#undef __NPU_TILING__

using namespace AscendC;

class KernelVideoPreFuse {
public:
    __aicore__ inline void Init(GM_ADDR x, GM_ADDR y, uint32_t ih, uint32_t iw, uint32_t ic, uint32_t oh,
                                uint32_t ow, uint32_t oc, uint32_t tileLength, uint32_t totalOut) {
        xPtr = reinterpret_cast<__gm__ half*>(x);
        yPtr = reinterpret_cast<__gm__ half*>(y);
        inputH = ih;
        inputW = iw;
        inputC = ic;
        outputH = oh;
        outputW = ow;
        outputC = oc;
        this->tileLength = tileLength > 0 ? tileLength : 1024;
        this->totalOut = totalOut;
    }

    __aicore__ inline void Process() {
        const half scale = static_cast<half>(255.0f);
        for (uint32_t start = 0; start < totalOut; start += tileLength) {
            const uint32_t end = start + tileLength > totalOut ? totalOut : start + tileLength;
            for (uint32_t idx = start; idx < end; ++idx) {
                const uint32_t oy = idx / (outputW * outputC);
                const uint32_t rem = idx % (outputW * outputC);
                const uint32_t ox = rem / outputC;
                const uint32_t c = rem % outputC;
                const uint32_t sy = oy * inputH / outputH;
                const uint32_t sx = ox * inputW / outputW;
                const uint32_t inIdx = (sy * inputW + sx) * inputC + c;
                const half val = xPtr[inIdx];
                yPtr[idx] = static_cast<half>(static_cast<float>(val) / static_cast<float>(scale));
            }
        }
    }

private:
    __gm__ half* xPtr;
    __gm__ half* yPtr;
    uint32_t inputH;
    uint32_t inputW;
    uint32_t inputC;
    uint32_t outputH;
    uint32_t outputW;
    uint32_t outputC;
    uint32_t tileLength;
    uint32_t totalOut;
};

extern "C" __global__ __aicore__ void video_pre_fuse_custom(GM_ADDR x, GM_ADDR y, GM_ADDR workspace, GM_ADDR tiling) {
    GET_TILING_DATA(tilingData, tiling);
    KernelVideoPreFuse op;
    op.Init(x, y, tilingData.inputH, tilingData.inputW, tilingData.inputC, tilingData.outputH, tilingData.outputW,
            tilingData.outputC, tilingData.tileLength, tilingData.totalOut);
    op.Process();
}
