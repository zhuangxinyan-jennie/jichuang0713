from __future__ import annotations

import unittest

from greeting_guide import greeting_response, is_greeting_speech


class GreetingGuideTests(unittest.TestCase):
    def test_greeting_phrases(self) -> None:
        self.assertTrue(is_greeting_speech("熊大你好呀"))
        self.assertTrue(is_greeting_speech("你好熊大"))
        self.assertTrue(is_greeting_speech("嗨，熊大"))

    def test_not_greeting(self) -> None:
        self.assertFalse(is_greeting_speech("海螺湾怎么走"))
        self.assertFalse(is_greeting_speech("今天天气怎么样"))
        self.assertFalse(is_greeting_speech(""))

    def test_actions(self) -> None:
        out = greeting_response("熊大你好呀")
        self.assertEqual(out["actions"], ["挥手致意", "双手欢呼"])


if __name__ == "__main__":
    unittest.main()
