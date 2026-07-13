"""
测试剧情互动模式，并把输出写入 logs/story_interaction.log。

流程尽量模拟真实场景：
1. 新游客出现，进入玩法选择。
2. 游客选择剧情互动，播放开场 0。
3. 开场选择 B 先听规则，再进入第一幕。
4. 三幕任务都先选错一次，再选对，验证“选错后重试直到选对”。
5. 剧情结束后回到玩法选择。
"""
import contextlib
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))

from agent import BearAgent


LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
LOG_PATH = os.path.join(LOG_DIR, "story_interaction.log")
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


def call(agent, name, perception_result):
    print("\n" + "=" * 60)
    print(f"【步骤】{name}")
    print("=" * 60)

    start_time = time.time()
    response = agent.process(perception_result)
    elapsed_ms = (time.time() - start_time) * 1000

    print(f"【响应时间】{elapsed_ms:.2f} ms")
    print("【响应JSON】")
    print(json.dumps(response, ensure_ascii=False, indent=2))
    return response


def run_retry_until_correct_branch():
    print("\n" + "#" * 70)
    print("剧情任务测试：先听规则，三幕均先答错一次，再答对")
    print("#" * 70)

    agent = BearAgent(rules_path=RULES_PATH)

    call(agent, "新游客出现，输出玩法选择clip", base_perception())
    call(agent, "等待玩法选择时，游客挥手，不应输出JSON", base_perception(
        gesture="wave_hand",
        gesture_confidence=0.9,
        emotion="happy",
    ))
    call(agent, "游客选择剧情互动，输出开场介绍 0", base_perception("剧情互动"))
    call(agent, "开场等待选择时，无关表情不应输出JSON", base_perception(
        emotion="surprised",
        emotion_confidence=0.9,
        hand_gesture="clapping",
        hand_gesture_confidence=0.8,
    ))

    call(agent, "游客选择 B：先听听规则，输出 0B 后进入第一幕 1", base_perception("先听听规则"))

    call(agent, "第一幕游客错选 B：往右走，输出 1B 并重播 1", base_perception("往右走"))
    call(agent, "第一幕游客答对 A：往左走，输出 1A 后进入第二幕 2", base_perception("往左走"))

    call(agent, "第二幕游客错选 A：路线A，输出 2A 并重播 2", base_perception("路线A"))
    call(agent, "第二幕游客答对 B：路线B，输出 2B 后进入第三幕 3", base_perception("路线B"))

    call(agent, "第三幕游客错选 C：触碰轨道，输出 3C 并重播 3", base_perception("触碰轨道"))
    call(agent, "第三幕游客答对 B：垃圾分类，输出 3B 和结尾 4", base_perception("垃圾分类"))

    call(agent, "剧情结束后回到玩法选择，游客选择地图查询", base_perception("地图查询"))
    call(agent, "已进入地图查询，问海螺湾怎么走", base_perception("海螺湾怎么走"))


def run_opening_a_branch():
    print("\n" + "#" * 70)
    print("剧情任务测试：开场直接选择 A，一路答对")
    print("#" * 70)

    agent = BearAgent(rules_path=RULES_PATH)

    call(agent, "新游客出现，输出玩法选择clip", base_perception())
    call(agent, "游客选择剧情互动，输出开场介绍 0", base_perception("剧情互动"))
    call(agent, "开场游客选择 A：好，一起完成任务，输出 0A 后进入第一幕 1", base_perception("好，一起完成任务"))
    call(agent, "第一幕答对 A：往左走，输出 1A 后进入第二幕 2", base_perception("A"))
    call(agent, "第二幕答对 B：路线B，输出 2B 后进入第三幕 3", base_perception("B"))
    call(agent, "第三幕答对 B：垃圾分类，输出 3B 和结尾 4", base_perception("B"))


def run():
    run_retry_until_correct_branch()
    run_opening_a_branch()


def main():
    os.makedirs(LOG_DIR, exist_ok=True)
    with open(LOG_PATH, "w", encoding="utf-8") as log_file:
        with contextlib.redirect_stdout(log_file), contextlib.redirect_stderr(log_file):
            run()
    print(f"剧情互动测试完成，日志已写入：{LOG_PATH}")


if __name__ == "__main__":
    main()
