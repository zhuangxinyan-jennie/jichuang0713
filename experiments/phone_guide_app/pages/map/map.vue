<template>
  <view class="page">
    <view class="card">
      <text class="label">2D 乐园导览图（预览）</text>
      <image class="map" src="/static/map/park-map.png" mode="widthFix" />
      <text class="tip">
        后续：大屏展示互动时，游客扫码进入本页，可看目的地星星与步行指引。\n
        本期以「语音 → 板端识别 → PC 终端」为主。
      </text>
    </view>
  </view>
</template>

<script>
export default {};
</script>

<style scoped>
.page {
  padding: 28rpx;
}
.card {
  background: #141414;
  border: 1px solid #2a2a2a;
  border-radius: 24rpx;
  padding: 24rpx;
}
.label {
  display: block;
  color: #8b8b8b;
  font-size: 22rpx;
  margin-bottom: 16rpx;
}
.map {
  width: 100%;
  border-radius: 12rpx;
  background: #0a0a0a;
}
.tip {
  display: block;
  margin-top: 16rpx;
  color: #8b8b8b;
  font-size: 22rpx;
  white-space: pre-line;
  line-height: 1.5;
}
</style>
