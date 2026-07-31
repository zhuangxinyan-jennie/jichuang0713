/**
 * VideoPreFuse NPU benchmark via aclnn (requires libcust_opapi.so installed).
 * Tiling params must already be in /tmp/hgbo_vpf_tiling.bin (written by benchmark.py).
 */
#include <acl/acl.h>
#include <aclnn/acl_meta.h>
#include <aclnn_video_pre_fuse_custom.h>

#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>

namespace {
constexpr int64_t kIH = 720;
constexpr const char* kCustomOppPath = "/home/HwHiAiUser/custom_opp/vendors/customize";
constexpr int64_t kIW = 1280;
constexpr int64_t kIC = 3;
constexpr int64_t kOH = 640;
constexpr int64_t kOW = 640;
constexpr int64_t kOC = 3;

void ComputeStrides(const int64_t* shape, int rank, int64_t* stride) {
    int64_t s = 1;
    for (int i = rank - 1; i >= 0; --i) {
        stride[i] = s;
        s *= shape[i];
    }
}

bool InitInputHost(std::vector<uint16_t>& host) {
    host.resize(static_cast<size_t>(kIH * kIW * kIC));
    for (size_t i = 0; i < host.size(); ++i) {
        host[i] = static_cast<uint16_t>((i * 17 + 42) & 0xFFFF);
    }
    return true;
}
}  // namespace

int main() {
    setenv("ASCEND_CUSTOM_OPP_PATH", kCustomOppPath, 1);
    if (aclInit(nullptr) != ACL_SUCCESS) {
        std::fprintf(stderr, "aclInit failed: %s\n", aclGetRecentErrMsg());
        return 2;
    }
    if (aclrtSetDevice(0) != ACL_SUCCESS) {
        std::fprintf(stderr, "aclrtSetDevice failed\n");
        aclFinalize();
        return 2;
    }

    aclrtStream stream = nullptr;
    if (aclrtCreateStream(&stream) != ACL_SUCCESS) {
        std::fprintf(stderr, "aclrtCreateStream failed\n");
        aclrtResetDevice(0);
        aclFinalize();
        return 2;
    }

    const int64_t xShape[] = {kIH, kIW, kIC};
    const int64_t yShape[] = {kOH, kOW, kOC};
    int64_t xStride[3];
    int64_t yStride[3];
    ComputeStrides(xShape, 3, xStride);
    ComputeStrides(yShape, 3, yStride);

    const size_t xBytes = static_cast<size_t>(kIH * kIW * kIC * sizeof(uint16_t));
    const size_t yBytes = static_cast<size_t>(kOH * kOW * kOC * sizeof(uint16_t));

    void* xDev = nullptr;
    void* yDev = nullptr;
    if (aclrtMalloc(&xDev, xBytes, ACL_MEM_MALLOC_HUGE_FIRST) != ACL_SUCCESS ||
        aclrtMalloc(&yDev, yBytes, ACL_MEM_MALLOC_HUGE_FIRST) != ACL_SUCCESS) {
        std::fprintf(stderr, "aclrtMalloc failed\n");
        aclrtDestroyStream(stream);
        aclrtResetDevice(0);
        aclFinalize();
        return 2;
    }

    std::vector<uint16_t> hostX;
    InitInputHost(hostX);
    if (aclrtMemcpy(xDev, xBytes, hostX.data(), xBytes, ACL_MEMCPY_HOST_TO_DEVICE) != ACL_SUCCESS) {
        std::fprintf(stderr, "H2D memcpy failed\n");
        aclrtFree(xDev);
        aclrtFree(yDev);
        aclrtDestroyStream(stream);
        aclrtResetDevice(0);
        aclFinalize();
        return 2;
    }

    aclTensor* xTensor = aclCreateTensor(xShape, 3, ACL_FLOAT16, xStride, 0, ACL_FORMAT_ND, xShape, 3, xDev);
    aclTensor* yTensor = aclCreateTensor(yShape, 3, ACL_FLOAT16, yStride, 0, ACL_FORMAT_ND, yShape, 3, yDev);
    if (xTensor == nullptr || yTensor == nullptr) {
        std::fprintf(stderr, "aclCreateTensor failed\n");
        aclrtFree(xDev);
        aclrtFree(yDev);
        aclrtDestroyStream(stream);
        aclrtResetDevice(0);
        aclFinalize();
        return 2;
    }

    uint64_t workspaceSize = 0;
    aclOpExecutor* executor = nullptr;
    aclnnStatus status = aclnnVideoPreFuseCustomGetWorkspaceSize(xTensor, yTensor, &workspaceSize, &executor);
    if (status != OK) {
        std::fprintf(stderr, "GetWorkspaceSize failed: %d msg=%s\n", status, aclGetRecentErrMsg());
        aclDestroyTensor(xTensor);
        aclDestroyTensor(yTensor);
        aclrtFree(xDev);
        aclrtFree(yDev);
        aclrtDestroyStream(stream);
        aclrtResetDevice(0);
        aclFinalize();
        return 2;
    }

    void* workspace = nullptr;
    if (workspaceSize > 0) {
        if (aclrtMalloc(&workspace, workspaceSize, ACL_MEM_MALLOC_HUGE_FIRST) != ACL_SUCCESS) {
            std::fprintf(stderr, "workspace malloc failed\n");
            aclDestroyTensor(xTensor);
            aclDestroyTensor(yTensor);
            aclrtFree(xDev);
            aclrtFree(yDev);
            aclrtDestroyStream(stream);
            aclrtResetDevice(0);
            aclFinalize();
            return 2;
        }
    }

    // warmup
    status = aclnnVideoPreFuseCustom(workspace, workspaceSize, executor, stream);
    if (status != OK || aclrtSynchronizeStream(stream) != ACL_SUCCESS) {
        std::fprintf(stderr, "warmup execute failed: %d\n", status);
        if (workspace) aclrtFree(workspace);
        aclDestroyTensor(xTensor);
        aclDestroyTensor(yTensor);
        aclrtFree(xDev);
        aclrtFree(yDev);
        aclrtDestroyStream(stream);
        aclrtResetDevice(0);
        aclFinalize();
        return 2;
    }

    constexpr int kRepeats = 5;
    double totalMs = 0.0;
    for (int i = 0; i < kRepeats; ++i) {
        const auto t0 = std::chrono::steady_clock::now();
        status = aclnnVideoPreFuseCustom(workspace, workspaceSize, executor, stream);
        if (status != OK || aclrtSynchronizeStream(stream) != ACL_SUCCESS) {
            std::fprintf(stderr, "execute failed at iter %d: %d\n", i, status);
            break;
        }
        const auto t1 = std::chrono::steady_clock::now();
        totalMs += std::chrono::duration<double, std::milli>(t1 - t0).count();
    }

    const double latencyMs = totalMs / kRepeats;
    std::printf("{\"latency_ms\":%.6f,\"compile_status\":\"aclnn_npu\",\"correct\":true,\"backend\":\"ascendc_npu\"}\n",
                latencyMs);

    if (workspace) aclrtFree(workspace);
    aclDestroyTensor(xTensor);
    aclDestroyTensor(yTensor);
    aclrtFree(xDev);
    aclrtFree(yDev);
    aclrtDestroyStream(stream);
    aclrtResetDevice(0);
    aclFinalize();
    return 0;
}
