"""
测试随机互动模式，并把输出写入 logs/random_interaction.log。

流程：
1. 新游客出现，Agent输出玩法选择clip。
2. 游客说“随机互动”，Agent进入随机互动模式。
3. 复用原 test_agent.py 的随机互动场景。
"""
import contextlib
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))

from agent import BearAgent


LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
LOG_PATH = os.path.join(LOG_DIR, "random_interaction.log")
RULES_PATH = os.path.join(os.path.dirname(__file__), "rules.json")


def base_perception(speech_text="", **overrides):
    data = {
        "emotion": "neutral",
        "emotion_confidence": 0.85,
        "gesture": "none",
        "gesture_confidence": 0.0,
        "hand_gesture": "none",
        "hand_gesture_confidence": 0.0,
        "person_detected": True,
        "person_count": 1,
        "face_bbox": [120, 80, 280, 300],
        "speech_text": speech_text,
    }
    data.update(overrides)
    return data


def test_scenario(agent, name, perception_result):
    print("\n" + "=" * 60)
    print(f"【场景】{name}")
    print("=" * 60)

    try:
        start_time = time.time()
        response = agent.process(perception_result)
        elapsed_ms = (time.time() - start_time) * 1000

        print(f"\n【响应时间】{elapsed_ms:.2f} ms")
        print("\n【响应JSON】")
        print(json.dumps(response, ensure_ascii=False, indent=2))
        return True, elapsed_ms
    except Exception as exc:
        print(f"\n【错误】{exc}")
        import traceback
        traceback.print_exc()
        return False, 0


def run():
    print("初始化Agent...")
    agent = BearAgent(rules_path=RULES_PATH)

    times = []

    test_scenario(agent, "新游客出现 - 进入玩法选择", base_perception())
    test_scenario(agent, "游客选择随机互动", base_perception("随机互动"))

    scenarios = [
        (
            "初次见面 - 规则库",
            base_perception(),
        ),
        (
            "游客挥手并说话 - LLM",
            base_perception(
                "熊大你好呀",
                emotion="happy",
                emotion_confidence=0.92,
                gesture="wave_hand",
                gesture_confidence=0.88,
            ),
        ),
        (
            "挥手+点赞复合手势 - LLM",
            base_perception(
                emotion="happy",
                emotion_confidence=0.92,
                gesture="wave_hand",
                gesture_confidence=0.88,
                hand_gesture="like",
                hand_gesture_confidence=0.85,
            ),
        ),
        (
            "请求转圈表演 - LLM",
            base_perception(
                "熊大，你能给我表演一个转圈吗？",
                emotion="happy",
                emotion_confidence=0.88,
            ),
        ),
        (
            "游客害怕想合影 - LLM",
            base_perception(
                "熊大，可以和你拍张照吗？",
                emotion="scared",
                emotion_confidence=0.86,
                face_bbox=[130, 90, 285, 310],
            ),
        ),
        (
            "游客难过求安慰 - LLM",
            base_perception(
                "熊大，我今天有点不开心。",
                emotion="sad",
                emotion_confidence=0.90,
                face_bbox=[118, 82, 275, 302],
            ),
        ),
        (
            "游客惊讶请求跳舞 - LLM",
            base_perception(
                "哇你真的是熊大吗？能跳个舞吗？",
                emotion="surprised",
                emotion_confidence=0.84,
                face_bbox=[110, 76, 268, 298],
            ),
        ),
        (
            "游客要求危险后空翻 - LLM",
            base_perception(
                "熊大，给我来个特别夸张的后空翻吧！",
                emotion="happy",
                emotion_confidence=0.83,
                face_bbox=[125, 86, 280, 305],
            ),
        ),
        (
            "多人围观打招呼 - LLM",
            base_perception(
                "熊大，我们一家人都来看你啦！",
                emotion="happy",
                emotion_confidence=0.80,
                gesture="wave_hand",
                gesture_confidence=0.82,
                person_count=4,
                face_bbox=[95, 70, 315, 320],
            ),
        ),
        (
            "游客想让熊大摆姿势 - LLM",
            base_perception(
                "熊大，摆个帅气一点的姿势！",
                emotion="neutral",
                emotion_confidence=0.78,
                hand_gesture="ok",
                hand_gesture_confidence=0.80,
                face_bbox=[122, 84, 278, 304],
            ),
        ),
        (
            "游客接着追问刚才表演 - LLM",
            base_perception(
                "刚才那个不错，能再来一个不一样的吗？",
                emotion="happy",
                emotion_confidence=0.87,
                gesture="clapping",
                gesture_confidence=0.86,
            ),
        ),
    ]

    for name, perception_result in scenarios:
        success, elapsed = test_scenario(agent, name, perception_result)
        if success:
            times.append((name, elapsed))

    print("\n" + "=" * 60)
    print("【响应时间统计】")
    print("=" * 60)
    for name, elapsed in times:
        print(f"  {name}: {elapsed:.2f} ms")
    if times:
        values = [elapsed for _, elapsed in times]
        print(f"\n  平均: {sum(values) / len(values):.2f} ms")
        print(f"  最小: {min(values):.2f} ms")
        print(f"  最大: {max(values):.2f} ms")


def main():
    os.makedirs(LOG_DIR, exist_ok=True)
    with open(LOG_PATH, "w", encoding="utf-8") as log_file:
        with contextlib.redirect_stdout(log_file), contextlib.redirect_stderr(log_file):
            run()
    print(f"随机互动测试完成，日志已写入：{LOG_PATH}")


if __name__ == "__main__":
    main()
