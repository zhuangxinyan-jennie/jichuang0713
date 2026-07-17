
#include "register/tilingdata_base.h"

namespace optiling {
BEGIN_TILING_DATA_DEF(VideoPreFuseCustomTilingData)
  TILING_DATA_FIELD_DEF(uint32_t, inputH);
  TILING_DATA_FIELD_DEF(uint32_t, inputW);
  TILING_DATA_FIELD_DEF(uint32_t, inputC);
  TILING_DATA_FIELD_DEF(uint32_t, outputH);
  TILING_DATA_FIELD_DEF(uint32_t, outputW);
  TILING_DATA_FIELD_DEF(uint32_t, outputC);
  TILING_DATA_FIELD_DEF(uint32_t, splitAxis);
  TILING_DATA_FIELD_DEF(uint32_t, tileH);
  TILING_DATA_FIELD_DEF(uint32_t, tileW);
  TILING_DATA_FIELD_DEF(uint32_t, tileLen);
  TILING_DATA_FIELD_DEF(uint32_t, bufferNum);
  TILING_DATA_FIELD_DEF(uint32_t, tileLength);
  TILING_DATA_FIELD_DEF(uint32_t, totalOut);
END_TILING_DATA_DEF;

REGISTER_TILING_DATA_CLASS(VideoPreFuseCustom, VideoPreFuseCustomTilingData)
}
