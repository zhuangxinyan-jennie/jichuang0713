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
            "play_recommendation": WeatherGuide._build_play_recommendation("小雨", 22, None),
            "tip": WeatherGuide._build_play_recommendation("小雨", 22, None)["summary"],
            "indoor_picks": ["海螺湾"],
        }
        speech = guide._speech_from_snapshot(snap, "今天天气怎么样")
        self.assertIn("小雨", speech)
        self.assertIn("22", speech)
        self.assertIn("室内", speech)

    def test_answer_actions(self) -> None:
        guide = WeatherGuide()
        out = guide.answer("今天天气怎么样")
        self.assertEqual(out["actions"], ["捂耳倾听", "叉腰昂首"])

    def test_outdoor_recommendation(self) -> None:
        rec = WeatherGuide._build_play_recommendation("晴", 26, None)
        self.assertEqual(rec["priority"], "室外")
        self.assertIn("飞越极限", rec["picks"][0])

    def test_indoor_recommendation(self) -> None:
        rec = WeatherGuide._build_play_recommendation("小雨", 20, None)
        self.assertEqual(rec["priority"], "室内")
        self.assertIn("海螺湾", rec["picks"])

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
