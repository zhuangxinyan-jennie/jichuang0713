"""
测试脚本 - 仅测试规则库（不调用LLM）
"""
import sys
import os
import json

sys.path.insert(0, os.path.dirname(__file__))

from agent import BearAgent


RULES_PATH = os.path.join(os.path.dirname(__file__), "rules.json")


def test_scenario(agent, name, perception_result):
    """测试一个场景"""
    print("\n" + "=" * 60)
    print(f"【场景】{name}")
    print("=" * 60)

    try:
        response = agent.process(perception_result)

        print("\n【响应JSON】")
        print(json.dumps(response, ensure_ascii=False, indent=2))
        print()
        return True
    except Exception as e:
        print(f"\n【错误】{e}")
        import traceback
        traceback.print_exc()
        return False


def base_perception(**overrides):
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
        "speech_text": "",
    }
    data.update(overrides)
    return data


def main():
    print("初始化Agent...")
    try:
        agent = BearAgent(rules_path=RULES_PATH)
    except Exception as e:
        print(f"初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return

    test_scenario(agent, "新游客出现 - 进入玩法选择", base_perception())
    test_scenario(agent, "游客选择随机互动", base_perception(speech_text="随机互动"))

    test_scenario(agent, "初次见面 - 规则库", base_perception())
    test_scenario(agent, "游客挥手-开心 - 规则库", base_perception(
        emotion="happy",
        emotion_confidence=0.92,
        gesture="wave_hand",
        gesture_confidence=0.88,
    ))
    test_scenario(agent, "游客挥手-平静 - 规则库", base_perception(
        gesture="wave_hand",
        gesture_confidence=0.88,
    ))
    test_scenario(agent, "游客鼓掌-开心 - 规则库", base_perception(
        emotion="happy",
        emotion_confidence=0.90,
        gesture="clapping",
        gesture_confidence=0.85,
    ))
    test_scenario(agent, "游客鼓掌-平静 - 规则库", base_perception(
        gesture="clapping",
        gesture_confidence=0.90,
    ))

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
