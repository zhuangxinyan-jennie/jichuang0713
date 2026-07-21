const WEATHER_KEYS = ["天气", "气温", "温度", "几度", "下雨", "降雨", "下雪", "预报", "穿什么", "带伞", "热不热", "冷不冷"] as const;

export function guestInputMatchesWeatherQuery(text: string): boolean {
  const t = text.trim().replace(/\s+/g, "");
  if (!t) return false;
  return WEATHER_KEYS.some((k) => t.includes(k));
}
