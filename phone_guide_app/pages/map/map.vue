<template>
  <view class="page">
    <view class="page-head">
      <view>
        <text class="title">园区地图</text>
        <text class="version">版本 {{ mapVersion }}</text>
      </view>
      <text :class="['sync-state', remoteAvailable ? 'update' : 'ready']">{{ syncText }}</text>
    </view>

    <view class="map-panel">
      <view id="mapStage" class="map-stage">
        <image class="map-image" src="/static/map/park-map.png" mode="aspectFill" />
        <canvas canvas-id="routeCanvas" class="route-canvas" />
        <view
          v-for="place in places"
          :key="place.name"
          :class="['marker', markerClass(place)]"
          :style="markerStyle(place)"
          @click="selectPlace(place)"
        >
          <view class="marker-dot" />
          <text v-if="selectedName === place.name" class="marker-label">{{ place.name }}</text>
        </view>
      </view>
    </view>

    <view class="card location-card">
      <text class="label">当前位置</text>
      <picker mode="selector" :range="placeNames" :value="currentLocationIndex" @change="onLocationChange">
        <view class="picker-value">{{ currentLocation || "选择当前位置" }}</view>
      </picker>
      <text class="tip">可手动选择；园区位置二维码后续可直接更新此项。</text>
    </view>

    <view class="card search-card">
      <text class="label">查找地点</text>
      <input class="search-input" v-model="searchText" placeholder="输入地点名称" confirm-type="search" />
      <view v-if="selectedPlace" class="selected-place">
        <view>
          <text class="selected-name">{{ selectedPlace.name }}</text>
          <text class="selected-coord">
            地图 {{ selectedPlace.leftPct.toFixed(1) }}%, {{ selectedPlace.topPct.toFixed(1) }}%
          </text>
        </view>
        <button class="location-btn" @click="useSelectedAsLocation">设为当前位置</button>
      </view>
    </view>

    <view v-if="routeNames.length" class="card route-card">
      <text class="label">导航路线</text>
      <text class="route-text">{{ routeNames.join(" → ") }}</text>
      <button class="clear-route" @click="clearRoute">清除路线</button>
    </view>

    <view class="poi-section">
      <view class="poi-head">
        <text class="label">地点列表</text>
        <text class="count">{{ filteredPlaces.length }} 个</text>
      </view>
      <view
        v-for="place in filteredPlaces"
        :key="place.name"
        :class="['poi-item', { selected: selectedName === place.name }]"
        @click="selectPlace(place)"
      >
        <text class="poi-name">{{ place.name }}</text>
        <text class="poi-location">{{ place.leftPct.toFixed(0) }}%, {{ place.topPct.toFixed(0) }}%</text>
      </view>
      <text v-if="!filteredPlaces.length" class="empty">没有匹配地点</text>
    </view>
  </view>
</template>

<script>
import bundledManifest from "../../static/map/manifest.json";
import placesDocument from "../../static/map/places_2d.json";
import { fetchMapManifest, findPlace } from "../../utils/mapClient.js";

export default {
  data() {
    return {
      places: Array.isArray(placesDocument.places) ? placesDocument.places : [],
      mapVersion: bundledManifest.version || "内置",
      syncText: "使用内置地图",
      remoteAvailable: false,
      searchText: "",
      selectedName: "",
      currentLocation: uni.getStorageSync("map_current_location") || "方特城堡",
      routeNames: [],
      routeHandler: null,
    };
  },
  computed: {
    placeNames() {
      return this.places.map((place) => place.name);
    },
    currentLocationIndex() {
      const index = this.placeNames.indexOf(this.currentLocation);
      return index >= 0 ? index : 0;
    },
    selectedPlace() {
      return findPlace(this.places, this.selectedName);
    },
    filteredPlaces() {
      const query = this.searchText.trim().toLowerCase();
      if (!query) return this.places;
      return this.places.filter((place) => String(place.name || "").toLowerCase().includes(query));
    },
  },
  onLoad() {
    this.routeHandler = (payload) => this.applyRoute(payload);
    uni.$on("map-route", this.routeHandler);
    this.refreshManifest();
  },
  onReady() {
    this.drawRoute();
  },
  onUnload() {
    if (this.routeHandler) uni.$off("map-route", this.routeHandler);
  },
  methods: {
    async refreshManifest() {
      try {
        const remote = await fetchMapManifest();
        if (!remote.version || remote.version === this.mapVersion) {
          this.syncText = "地图已同步";
          this.remoteAvailable = false;
          return;
        }
        this.syncText = `板端版本 ${remote.version}`;
        this.remoteAvailable = true;
      } catch (_) {
        this.syncText = "离线地图可用";
        this.remoteAvailable = false;
      }
    },
    markerStyle(place) {
      return { left: `${place.leftPct}%`, top: `${place.topPct}%` };
    },
    markerClass(place) {
      return {
        current: place.name === this.currentLocation,
        selected: place.name === this.selectedName,
        route: this.routeNames.includes(place.name),
      };
    },
    selectPlace(place) {
      this.selectedName = place.name;
    },
    useSelectedAsLocation() {
      if (!this.selectedPlace) return;
      this.currentLocation = this.selectedPlace.name;
      uni.setStorageSync("map_current_location", this.currentLocation);
    },
    onLocationChange(event) {
      const index = Number(event && event.detail && event.detail.value);
      if (!Number.isInteger(index) || !this.places[index]) return;
      this.currentLocation = this.places[index].name;
      uni.setStorageSync("map_current_location", this.currentLocation);
    },
    applyRoute(payload) {
      const names = payload && Array.isArray(payload.path) ? payload.path : [];
      this.routeNames = names.filter((name) => findPlace(this.places, name));
      if (payload && payload.destination) this.selectedName = payload.destination;
      this.$nextTick(() => this.drawRoute());
    },
    clearRoute() {
      this.routeNames = [];
      this.drawRoute();
    },
    drawRoute() {
      const query = uni.createSelectorQuery().in(this);
      query
        .select("#mapStage")
        .boundingClientRect((rect) => {
          if (!rect) return;
          const context = uni.createCanvasContext("routeCanvas", this);
          context.clearRect(0, 0, rect.width, rect.height);
          const points = this.routeNames
            .map((name) => findPlace(this.places, name))
            .filter(Boolean)
            .map((place) => ({
              x: (place.leftPct / 100) * rect.width,
              y: (place.topPct / 100) * rect.height,
            }));
          if (points.length >= 2) {
            context.setStrokeStyle("#f0c36e");
            context.setLineWidth(3);
            context.setLineCap("round");
            context.beginPath();
            context.moveTo(points[0].x, points[0].y);
            points.slice(1).forEach((point) => context.lineTo(point.x, point.y));
            context.stroke();
          }
          context.draw();
        })
        .exec();
    },
  },
};
</script>

<style scoped>
.page {
  min-height: 100vh;
  padding: 24rpx 28rpx 40rpx;
  box-sizing: border-box;
  background: #0a0a0a;
}
.page-head,
.poi-head,
.selected-place {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.page-head {
  margin-bottom: 20rpx;
}
.title {
  display: block;
  font-size: 36rpx;
  font-weight: 650;
}
.version {
  display: block;
  margin-top: 4rpx;
  color: #818181;
  font-size: 20rpx;
  font-family: ui-monospace, monospace;
}
.sync-state {
  padding: 8rpx 14rpx;
  border: 1px solid #353535;
  border-radius: 10rpx;
  font-size: 21rpx;
}
.sync-state.ready {
  color: #7fd99a;
}
.sync-state.update {
  color: #e6c07b;
}
.map-panel {
  margin-bottom: 20rpx;
  padding: 10rpx;
  border: 1px solid #2a2a2a;
  border-radius: 12rpx;
  background: #141414;
}
.map-stage {
  position: relative;
  width: 100%;
  aspect-ratio: 1024 / 686;
  overflow: hidden;
  background: #0d0d0d;
}
.map-image,
.route-canvas {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
}
.route-canvas {
  pointer-events: none;
}
.marker {
  position: absolute;
  z-index: 3;
  width: 28rpx;
  height: 28rpx;
  transform: translate(-50%, -50%);
}
.marker-dot {
  width: 14rpx;
  height: 14rpx;
  margin: 7rpx;
  border: 3rpx solid #fff;
  border-radius: 50%;
  box-sizing: border-box;
  background: #46678f;
}
.marker.current .marker-dot {
  background: #3f9761;
}
.marker.route .marker-dot {
  background: #c48b32;
}
.marker.selected .marker-dot {
  width: 20rpx;
  height: 20rpx;
  margin: 4rpx;
  background: #b94b4b;
}
.marker-label {
  position: absolute;
  left: 22rpx;
  top: -4rpx;
  min-width: 120rpx;
  padding: 5rpx 8rpx;
  background: rgba(10, 10, 10, 0.9);
  color: #fff;
  font-size: 19rpx;
  white-space: nowrap;
}
.card {
  margin-bottom: 20rpx;
  padding: 24rpx;
  border: 1px solid #2a2a2a;
  border-radius: 12rpx;
  background: #141414;
}
.label {
  display: block;
  color: #858585;
  font-size: 21rpx;
}
.picker-value,
.search-input {
  box-sizing: border-box;
  width: 100%;
  margin-top: 14rpx;
  padding: 18rpx 20rpx;
  border: 1px solid #333;
  border-radius: 10rpx;
  background: #0a0a0a;
  color: #e8e8e8;
  font-size: 25rpx;
}
.tip {
  display: block;
  margin-top: 12rpx;
  color: #777;
  font-size: 20rpx;
}
.selected-place {
  gap: 20rpx;
  margin-top: 18rpx;
  padding-top: 18rpx;
  border-top: 1px solid #2a2a2a;
}
.selected-name,
.selected-coord {
  display: block;
}
.selected-name {
  font-size: 27rpx;
}
.selected-coord {
  margin-top: 5rpx;
  color: #808080;
  font-size: 20rpx;
}
.location-btn,
.clear-route {
  margin: 0;
  padding: 0 18rpx;
  border: 1px solid #3a4a60;
  border-radius: 9rpx;
  background: #1b2635;
  color: #dce8ff;
  font-size: 21rpx;
  line-height: 58rpx;
}
.route-text {
  display: block;
  margin: 14rpx 0 18rpx;
  color: #f0c36e;
  font-size: 24rpx;
  line-height: 1.6;
}
.poi-section {
  padding: 8rpx 0;
}
.poi-head {
  margin-bottom: 10rpx;
}
.count {
  color: #777;
  font-size: 20rpx;
}
.poi-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 72rpx;
  padding: 0 20rpx;
  border-bottom: 1px solid #252525;
}
.poi-item.selected {
  border-left: 5rpx solid #82aaff;
  background: #151b24;
}
.poi-name {
  font-size: 24rpx;
}
.poi-location,
.empty {
  color: #777;
  font-size: 20rpx;
}
.empty {
  display: block;
  padding: 40rpx 0;
  text-align: center;
}
</style>
