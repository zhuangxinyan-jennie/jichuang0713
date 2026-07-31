"""
乐园天气查询：和风天气 API + 本地缓存 + 规则话术（不占用 LLM）。

注册：https://dev.qweather.com/  → 控制台复制 API Key → 查 LocationID
"""
from __future__ import annotations

import gzip
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

WEATHER_KEYWORDS = (
    "天气",
    "气温",
    "温度",
    "几度",
    "下雨",
    "降雨",
    "下雪",
    "预报",
    "穿什么",
    "带伞",
    "热不热",
    "冷不冷",
    "会不会下雨",
    "要不要带伞",
)

# 雨天/恶劣天 → 优先室内（与 map_guide 地名一致）
INDOOR_PICKS = ["海螺湾", "电影科技大揭秘", "宇宙博览会", "生命之光", "聊斋", "童梦天地"]
# 晴好天 → 优先室外
OUTDOOR_PICKS = ["飞越极限", "火流星", "熊出没历险记", "逃出恐龙岛", "大摆锤", "飓风飞椅"]
# 高温 → 可遮阳的户外或室内交替
SHADE_PICKS = ["唐古拉雪山", "生命之光", "海螺湾"]

_CACHE: dict[str, Any] = {"mono": 0.0, "payload": None}


def _load_weather_config() -> dict[str, Any]:
    cfg: dict[str, Any] = {}
    try:
        from config import WEATHER_CONFIG  # type: ignore

        if isinstance(WEATHER_CONFIG, dict):
            cfg.update(WEATHER_CONFIG)
    except (ImportError, AttributeError):
        pass
    env_key = os.environ.get("QWEATHER_API_KEY") or os.environ.get("WEATHER_API_KEY")
    if env_key:
        cfg["api_key"] = env_key.strip()
    if os.environ.get("WEATHER_LOCATION_ID"):
        cfg["location_id"] = os.environ["WEATHER_LOCATION_ID"].strip()
    if os.environ.get("WEATHER_LOCATION_NAME"):
        cfg["location_name"] = os.environ["WEATHER_LOCATION_NAME"].strip()
    return cfg


def _normalize_question(text: str) -> str:
    return re.sub(r"\s+", "", (text or "").strip())


class WeatherGuide:
    """根据实时天气生成熊大口语回复；API 失败时给出明确提示。"""

    @staticmethod
    def is_weather_question(text: str) -> bool:
        compact = _normalize_question(text)
        if not compact:
            return False
        return any(k in compact for k in WEATHER_KEYWORDS)

    def __init__(self) -> None:
        self._cfg = _load_weather_config()

    def refresh_config(self) -> None:
        self._cfg = _load_weather_config()

    def get_snapshot(self, *, force: bool = False) -> dict[str, Any]:
        """返回结构化天气；带内存缓存（默认 10 分钟）。"""
        self.refresh_config()
        ttl = float(self._cfg.get("cache_ttl_sec") or 600)
        now = time.monotonic()
        if (
            not force
            and _CACHE.get("payload") is not None
            and now - float(_CACHE.get("mono") or 0) < ttl
        ):
            return dict(_CACHE["payload"])

        payload = self._fetch_or_demo()
        _CACHE["mono"] = now
        _CACHE["payload"] = payload
        return dict(payload)

    def answer(self, speech_text: str = "") -> dict[str, Any]:
        snap = self.get_snapshot()
        speech = self._speech_from_snapshot(snap, speech_text)
        return {
            "interaction_type": "weather_query",
            "speech": speech,
            "motion_type": "sequential",
            "actions": ["捂耳倾听", "叉腰昂首"],
            "motion_description": None,
            "emotion": "smile",
            "weather": snap,
        }

    def _fetch_or_demo(self) -> dict[str, Any]:
        api_key = str(self._cfg.get("api_key") or "").strip()
        location_id = str(self._cfg.get("location_id") or "").strip()
        location_name = str(self._cfg.get("location_name") or "乐园").strip()
        api_host = str(self._cfg.get("api_host") or "https://devapi.qweather.com").rstrip("/")

        if not api_key or not location_id:
            return {
                "source": "demo",
                "location_name": location_name,
                "text": "多云",
                "temp_c": 26,
                "feels_like_c": 27,
                "humidity": 55,
                "wind_dir": "东南风",
                "wind_scale": "2",
                "tip": "示例数据：请在 bear_agent/config.py 配置 WEATHER_CONFIG 或设置环境变量 QWEATHER_API_KEY。",
                "indoor_picks": INDOOR_PICKS,
                "outdoor_picks": OUTDOOR_PICKS,
                "play_recommendation": WeatherGuide._build_play_recommendation("多云", 26, None),
                "updated_at": time.strftime("%Y-%m-%d %H:%M"),
            }

        try:
            now = self._http_json(
                f"{api_host}/v7/weather/now",
                {"location": location_id},
                api_key,
            )
            daily = self._http_json(
                f"{api_host}/v7/weather/3d",
                {"location": location_id},
                api_key,
            )
        except urllib.error.URLError as exc:
            reason = exc.reason if hasattr(exc, "reason") else str(exc)
            hint = ""
            if "403" in str(exc) or "401" in str(exc):
                hint = " 请检查 WEATHER_CONFIG.api_host 是否为控制台「设置」里的专属 API Host。"
            return {
                "source": "error",
                "location_name": location_name,
                "text": "暂不可用",
                "temp_c": None,
                "tip": f"天气服务暂时连不上：{reason}.{hint}",
                "updated_at": time.strftime("%Y-%m-%d %H:%M"),
            }

        now_row = ((now.get("now") or {}) if now.get("code") == "200" else {}) or {}
        daily_rows = daily.get("daily") if daily.get("code") == "200" else None
        tomorrow = (daily_rows or [{}])[1] if daily_rows and len(daily_rows) > 1 else {}

        text = str(now_row.get("text") or "未知")
        temp = _safe_int(now_row.get("temp"))
        payload: dict[str, Any] = {
            "source": "qweather",
            "location_name": location_name,
            "text": text,
            "temp_c": temp,
            "feels_like_c": _safe_int(now_row.get("feelsLike")),
            "humidity": _safe_int(now_row.get("humidity")),
            "wind_dir": str(now_row.get("windDir") or ""),
            "wind_scale": str(now_row.get("windScale") or ""),
            "icon": str(now_row.get("icon") or ""),
            "updated_at": time.strftime("%Y-%m-%d %H:%M"),
        }
        if tomorrow:
            payload["tomorrow_text"] = str(tomorrow.get("textDay") or "")
            payload["tomorrow_temp_max"] = _safe_int(tomorrow.get("tempMax"))
            payload["tomorrow_temp_min"] = _safe_int(tomorrow.get("tempMin"))

        payload["tip"] = self._build_tip(text, temp, payload.get("tomorrow_text"))
        payload["indoor_picks"] = self._indoor_picks_for(text)
        payload["outdoor_picks"] = self._outdoor_picks_for(text, temp)
        payload["play_recommendation"] = self._build_play_recommendation(
            text, temp, payload.get("tomorrow_text")
        )
        return payload

    def _http_json(self, url: str, params: dict[str, str], api_key: str) -> dict[str, Any]:
        qs = urllib.parse.urlencode(params)
        full_url = f"{url}?{qs}" if qs else url
        headers = {
            "User-Agent": "xiongda-weather-guide/1.0",
            "X-QW-Api-Key": api_key,
            "Accept-Encoding": "gzip",
        }
        req = urllib.request.Request(full_url, headers=headers)
        # 默认直连；若设置了 https_proxy/http_proxy（板上经 PC 代理出网）则走代理
        proxy = (os.environ.get("https_proxy") or os.environ.get("HTTPS_PROXY")
                 or os.environ.get("http_proxy") or os.environ.get("HTTP_PROXY") or "").strip()
        if proxy:
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({
                "http": proxy,
                "https": proxy,
            }))
        else:
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(req, timeout=8) as resp:
            raw = resp.read()
            if resp.headers.get("Content-Encoding") == "gzip" or raw[:2] == b"\x1f\x8b":
                raw = gzip.decompress(raw)
            text = raw.decode("utf-8", errors="replace")
        data = json.loads(text)
        if not isinstance(data, dict):
            raise urllib.error.URLError("invalid json")
        if str(data.get("code")) not in ("200", "204"):
            raise urllib.error.URLError(f"api code {data.get('code')}")
        return data

    def _build_tip(self, text: str, temp: int | None, tomorrow_text: str | None) -> str:
        rec = self._build_play_recommendation(text, temp, tomorrow_text)
        return str(rec.get("summary") or "")

    @staticmethod
    def _build_play_recommendation(
        text: str,
        temp: int | None,
        tomorrow_text: str | None,
    ) -> dict[str, Any]:
        """根据天气生成「优先室内 / 室外」游玩建议。"""
        t = text or ""
        mode = "outdoor"
        priority = "室外"
        picks: list[str] = []

        if any(k in t for k in ("雨", "雷", "雪", "雾", "霾")):
            mode = "indoor"
            priority = "室内"
            picks = list(INDOOR_PICKS[:4])
        elif temp is not None and temp >= 32:
            mode = "mixed"
            priority = "室内或遮阳"
            picks = list(SHADE_PICKS[:3]) + list(INDOOR_PICKS[:2])
        elif temp is not None and temp <= 5:
            mode = "indoor"
            priority = "室内"
            picks = list(INDOOR_PICKS[:3])
        elif tomorrow_text and any(k in tomorrow_text for k in ("雨", "雪", "雷")):
            mode = "outdoor"
            priority = "室外"
            picks = list(OUTDOOR_PICKS[:3])
            summary = (
                f"游玩建议：今天天气还行，优先玩室外项目，像{'、'.join(picks)}；"
                f"明天可能{tomorrow_text}，记得安排室内备选。"
            )
            return {
                "mode": mode,
                "priority": priority,
                "picks": picks,
                "summary": summary,
            }
        else:
            mode = "outdoor"
            priority = "室外"
            picks = list(OUTDOOR_PICKS[:4])

        joined = "、".join(picks[:4])
        if mode == "indoor":
            summary = f"游玩建议：这种天气优先玩室内项目，推荐{joined}"
        elif mode == "mixed":
            summary = f"游玩建议：有点热，优先室内或遮阳项目，像{joined}，记得补水防晒"
        else:
            summary = f"游玩建议：天气不错，优先玩室外项目，像{joined}"

        return {
            "mode": mode,
            "priority": priority,
            "picks": picks,
            "summary": summary,
        }

    @staticmethod
    def _indoor_picks_for(text: str) -> list[str]:
        if any(k in text for k in ("雨", "雷", "雪", "雾", "霾")):
            return list(INDOOR_PICKS)
        return []

    @staticmethod
    def _outdoor_picks_for(text: str, temp: int | None) -> list[str]:
        if any(k in text for k in ("雨", "雷", "雪", "雾", "霾")):
            return []
        if temp is not None and temp <= 5:
            return []
        if temp is not None and temp >= 32:
            return list(SHADE_PICKS)
        return list(OUTDOOR_PICKS)

    def _speech_from_snapshot(self, snap: dict[str, Any], question: str) -> str:
        loc = snap.get("location_name") or "这边"
        text = snap.get("text") or "未知"
        temp = snap.get("temp_c")
        play_rec = snap.get("play_recommendation") or {}
        play_line = str(play_rec.get("summary") or snap.get("tip") or "").strip().rstrip("。.!！")
        source = snap.get("source")

        if source == "demo":
            base = f"（演示）{loc}现在{text}"
            if temp is not None:
                base += f"，大约{temp}度"
            if play_line:
                base += f"。{play_line}"
            return base + "。"

        if source == "error":
            return f"俺这会儿查不到{loc}天气，稍后再试试哈。"

        q = _normalize_question(question)
        want_tomorrow = any(k in q for k in ("明天", "后天", "预报"))
        if want_tomorrow and snap.get("tomorrow_text"):
            tmax = snap.get("tomorrow_temp_max")
            tmin = snap.get("tomorrow_temp_min")
            base = f"明天{loc}大概{snap.get('tomorrow_text')}"
            if tmin is not None and tmax is not None:
                base += f"，大约{tmin}到{tmax}度"
            if play_line:
                base += f"。{play_line}"
            return base + "。"

        base = f"{loc}现在{text}"
        if temp is not None:
            base += f"，大约{temp}度"
        if play_line:
            base += f"。{play_line}"
        return base + "。"


def _safe_int(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(float(value))
    except (TypeError, ValueError):
        return None
