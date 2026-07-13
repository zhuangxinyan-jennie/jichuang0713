"""
测试脚本 - 测试规则库 + LLM，并统计响应时间
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from agent import BearAgent
import json
import time

RULES_PATH = os.path.join(os.path.dirname(__file__), "rules.json")

def test_scenario(agent, name, perception_result):
    """测试一个场景"""
    print("\n" + "="*60)
    print(f"【场景】{name}")
    print("="*60)

    try:
        start_time = time.time()
        response = agent.process(perception_result)
        end_time = time.time()

        elapsed_ms = (end_time - start_time) * 1000

        print(f"\n【响应时间】{elapsed_ms:.2f} ms")
        print("\n【响应JSON】")
        print(json.dumps(response, ensure_ascii=False, indent=2))
        print()
        return True, elapsed_ms
    except Exception as e:
        print(f"\n【错误】{e}")
        import traceback
        traceback.print_exc()
        return False, 0

def main():
    print("初始化Agent...")
    try:
        agent = BearAgent(rules_path=RULES_PATH)
    except Exception as e:
        print(f"初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return

    times = []

    # 进入随机互动模式
    test_scenario(
        agent,
        "新游客出现 - 进入玩法选择",
        perception_result={
            "emotion": "neutral",
            "emotion_confidence": 0.85,
            "gesture": "none",
            "gesture_confidence": 0.0,
            "hand_gesture": "none",
            "hand_gesture_confidence": 0.0,
            "person_detected": True,
            "person_count": 1,
            "face_bbox": [120, 80, 280, 300],
            "speech_text": ""
        }
    )
    test_scenario(
        agent,
        "游客选择随机互动",
        perception_result={
            "emotion": "neutral",
            "emotion_confidence": 0.85,
            "gesture": "none",
            "gesture_confidence": 0.0,
            "hand_gesture": "none",
            "hand_gesture_confidence": 0.0,
            "person_detected": True,
            "person_count": 1,
            "face_bbox": [120, 80, 280, 300],
            "speech_text": "随机互动"
        }
    )

    # 场景1：初次见面（规则库命中）
    success, elapsed = test_scenario(
        agent,
        "初次见面 - 规则库",
        perception_result={
            "emotion": "neutral",
            "emotion_confidence": 0.85,
            "gesture": "none",
            "gesture_confidence": 0.0,
            "hand_gesture": "none",
            "hand_gesture_confidence": 0.0,
            "person_detected": True,
            "person_count": 1,
            "face_bbox": [120, 80, 280, 300],
            "speech_text": ""
        }
    )
    if success:
        times.append(("初次见面-规则库", elapsed))

    llm_scenarios = [
        (
            "游客挥手并说话 - LLM",
            {
                "emotion": "happy",
                "emotion_confidence": 0.92,
                "gesture": "wave_hand",
                "gesture_confidence": 0.88,
                "hand_gesture": "none",
                "hand_gesture_confidence": 0.0,
                "person_detected": True,
                "person_count": 1,
                "face_bbox": [120, 80, 280, 300],
                "speech_text": "熊大你好呀"
            }
        ),
        (
            "挥手+点赞复合手势 - LLM",
            {
                "emotion": "happy",
                "emotion_confidence": 0.92,
                "gesture": "wave_hand",
                "gesture_confidence": 0.88,
                "hand_gesture": "like",
                "hand_gesture_confidence": 0.85,
                "person_detected": True,
                "person_count": 1,
                "face_bbox": [120, 80, 280, 300],
                "speech_text": ""
            }
        ),
        (
            "请求转圈表演 - LLM",
            {
                "emotion": "happy",
                "emotion_confidence": 0.88,
                "gesture": "none",
                "gesture_confidence": 0.0,
                "hand_gesture": "none",
                "hand_gesture_confidence": 0.0,
                "person_detected": True,
                "person_count": 1,
                "face_bbox": [120, 80, 280, 300],
                "speech_text": "熊大，你能给我表演一个转圈吗？"
            }
        ),
        (
            "游客害怕想合影 - LLM",
            {
                "emotion": "scared",
                "emotion_confidence": 0.86,
                "gesture": "none",
                "gesture_confidence": 0.0,
                "hand_gesture": "none",
                "hand_gesture_confidence": 0.0,
                "person_detected": True,
                "person_count": 1,
                "face_bbox": [130, 90, 285, 310],
                "speech_text": "熊大，可以和你拍张照吗？"
            }
        ),
        (
            "游客难过求安慰 - LLM",
            {
                "emotion": "sad",
                "emotion_confidence": 0.90,
                "gesture": "none",
                "gesture_confidence": 0.0,
                "hand_gesture": "none",
                "hand_gesture_confidence": 0.0,
                "person_detected": True,
                "person_count": 1,
                "face_bbox": [118, 82, 275, 302],
                "speech_text": "熊大，我今天有点不开心。"
            }
        ),
        (
            "游客惊讶请求跳舞 - LLM",
            {
                "emotion": "surprised",
                "emotion_confidence": 0.84,
                "gesture": "none",
                "gesture_confidence": 0.0,
                "hand_gesture": "none",
                "hand_gesture_confidence": 0.0,
                "person_detected": True,
                "person_count": 1,
                "face_bbox": [110, 76, 268, 298],
                "speech_text": "哇你真的是熊大吗？能跳个舞吗？"
            }
        ),
        (
            "游客要求危险后空翻 - LLM",
            {
                "emotion": "happy",
                "emotion_confidence": 0.83,
                "gesture": "none",
                "gesture_confidence": 0.0,
                "hand_gesture": "none",
                "hand_gesture_confidence": 0.0,
                "person_detected": True,
                "person_count": 1,
                "face_bbox": [125, 86, 280, 305],
                "speech_text": "熊大，给我来个特别夸张的后空翻吧！"
            }
        ),
        (
            "多人围观打招呼 - LLM",
            {
                "emotion": "happy",
                "emotion_confidence": 0.80,
                "gesture": "wave_hand",
                "gesture_confidence": 0.82,
                "hand_gesture": "none",
                "hand_gesture_confidence": 0.0,
                "person_detected": True,
                "person_count": 4,
                "face_bbox": [95, 70, 315, 320],
                "speech_text": "熊大，我们一家人都来看你啦！"
            }
        ),
        (
            "游客想让熊大摆姿势 - LLM",
            {
                "emotion": "neutral",
                "emotion_confidence": 0.78,
                "gesture": "none",
                "gesture_confidence": 0.0,
                "hand_gesture": "ok",
                "hand_gesture_confidence": 0.80,
                "person_detected": True,
                "person_count": 1,
                "face_bbox": [122, 84, 278, 304],
                "speech_text": "熊大，摆个帅气一点的姿势！"
            }
        ),
        (
            "游客接着追问刚才表演 - LLM",
            {
                "emotion": "happy",
                "emotion_confidence": 0.87,
                "gesture": "clapping",
                "gesture_confidence": 0.86,
                "hand_gesture": "none",
                "hand_gesture_confidence": 0.0,
                "person_detected": True,
                "person_count": 1,
                "face_bbox": [120, 80, 280, 300],
                "speech_text": "刚才那个不错，能再来一个不一样的吗？"
            }
        ),
    ]

    for index, (name, perception_result) in enumerate(llm_scenarios, start=2):
        success, elapsed = test_scenario(agent, f"场景{index}：{name}", perception_result)
        if success:
            times.append((name.replace(" - ", "-"), elapsed))

    # 统计结果
    print("\n" + "="*60)
    print("【响应时间统计】")
    print("="*60)

    rule_times = [t for name, t in times if "规则库" in name]
    llm_times = [t for name, t in times if "LLM" in name]

    print("\n规则库响应时间：")
    for name, t in times:
        if "规则库" in name:
            print(f"  {name}: {t:.2f} ms")

    if rule_times:
        print(f"\n  平均: {sum(rule_times)/len(rule_times):.2f} ms")
        print(f"  最小: {min(rule_times):.2f} ms")
        print(f"  最大: {max(rule_times):.2f} ms")

    print("\nLLM响应时间：")
    for name, t in times:
        if "LLM" in name:
            print(f"  {name}: {t:.2f} ms")

    if llm_times:
        print(f"\n  平均: {sum(llm_times)/len(llm_times):.2f} ms")
        print(f"  最小: {min(llm_times):.2f} ms")
        print(f"  最大: {max(llm_times):.2f} ms")

    print("\n" + "="*60)
    print("测试完成")
    print("="*60)

if __name__ == "__main__":
    main()
