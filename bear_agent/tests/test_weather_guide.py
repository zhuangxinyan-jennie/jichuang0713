from __future__ import annotations

import unittest
from unittest.mock import patch

from weather_guide import WeatherGuide


class WeatherGuideTests(unittest.TestCase):
    def test_is_weather_question(self) -> None:
        self.assertTrue(WeatherGuide.is_weather_question("今天天气怎么样"))
        self.assertTrue(WeatherGuide.is_weather_question("会不会下雨"))
        self.assertFalse(WeatherGuide.is_weather_question("海螺湾怎么走"))

    def test_demo_snapshot_without_key(self) -> None:
        guide = WeatherGuide()
        with patch.object(guide, "_cfg", {"location_name": "测试园"}):
            snap = guide._fetch_or_demo()
        self.assertEqual(snap["source"], "demo")
        self.assertIn("temp_c", snap)

    def test_answer_rain_tip(self) -> None:
        guide = WeatherGuide()
        snap = {
            "source": "qweather",
            "location_name": "沈阳",
            "text": "小雨",
            "temp_c": 22,
            "feels_like_c": 22,
            "wind_dir": "北风",
            "tip": "带伞。",
            "indoor_picks": ["海螺湾"],
        }
        speech = guide._speech_from_snapshot(snap, "今天天气怎么样")
        self.assertIn("小雨", speech)
        self.assertIn("22", speech)

    def test_tomorrow_branch(self) -> None:
        guide = WeatherGuide()
        snap = {
            "source": "qweather",
            "location_name": "沈阳",
            "text": "多云",
            "temp_c": 20,
            "tomorrow_text": "阵雨",
            "tomorrow_temp_max": 24,
            "tomorrow_temp_min": 18,
            "tip": "记得带伞。",
        }
        speech = guide._speech_from_snapshot(snap, "明天天气怎么样")
        self.assertIn("明天", speech)
        self.assertIn("阵雨", speech)


if __name__ == "__main__":
    unittest.main()
