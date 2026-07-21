import { bridgeHttpBase } from "./asrBridge.js";

function requestJson(url) {
  return new Promise((resolve, reject) => {
    uni.request({
      url,
      method: "GET",
      timeout: 5000,
      success(response) {
        const status = Number(response.statusCode || 0);
        if (status >= 200 && status < 300) {
          resolve(response.data || {});
          return;
        }
        reject(new Error(`地图请求失败 (${status})`));
      },
      fail(error) {
        reject(new Error((error && error.errMsg) || "无法读取地图数据"));
      },
    });
  });
}

export function fetchMapManifest() {
  return requestJson(`${bridgeHttpBase()}/api/v1/map/manifest`);
}

export function loadBundledPlaces() {
  return requestJson("/static/map/places_2d.json");
}

export function mapBundleUrl(version) {
  return `${bridgeHttpBase()}/api/v1/map/bundle/${encodeURIComponent(version)}`;
}

export function downloadMapBundle(version) {
  return new Promise((resolve, reject) => {
    uni.downloadFile({
      url: mapBundleUrl(version),
      timeout: 30000,
      success(response) {
        if (Number(response.statusCode || 0) !== 200 || !response.tempFilePath) {
          reject(new Error(`地图包下载失败 (${response.statusCode || 0})`));
          return;
        }
        resolve(response.tempFilePath);
      },
      fail(error) {
        reject(new Error((error && error.errMsg) || "地图包下载失败"));
      },
    });
  });
}

export function findPlace(places, name) {
  const query = String(name || "").trim().toLowerCase();
  if (!query) return null;
  return (
    (places || []).find((place) => String(place.name || "").toLowerCase() === query) ||
    (places || []).find((place) => String(place.name || "").toLowerCase().includes(query)) ||
    null
  );
}
