"""
测试地图查询模式，并把输出写入 logs/map_query.log。
"""
import contextlib
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))

from agent import BearAgent


LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
LOG_PATH = os.path.join(LOG_DIR, "map_query.log")
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


def run():
    print("初始化Agent...")
    agent = BearAgent(rules_path=RULES_PATH)
    print(f"【熊大当前位置】{agent.map_guide.current_location}")

    call(agent, "新游客出现，输出玩法选择clip", base_perception())
    call(agent, "游客选择地图查询模式", base_perception("地图查询"))
    call(agent, "游客问海螺湾怎么走", base_perception("海螺湾怎么走"))
    call(agent, "游客问飞越极限在哪里", base_perception("飞越极限在哪里"))
    call(agent, "游客问熊熊海盗船怎么走", base_perception("熊熊海盗船怎么走"))
    call(agent, "游客问德克士怎么走", base_perception("德克士怎么走"))
    call(agent, "游客问未知地点", base_perception("彩虹糖果屋怎么走"))

    print("\n" + "=" * 60)
    print("【固定原点核对：方特城堡 -> 海螺湾】")
    print("=" * 60)
    agent.map_guide.current_location = "方特城堡"
    call(agent, "固定原点后，游客问海螺湾怎么走", base_perception("海螺湾怎么走"))

    print("\n" + "=" * 60)
    print("地图查询测试完成")
    print("=" * 60)


def main():
    os.makedirs(LOG_DIR, exist_ok=True)
    with open(LOG_PATH, "w", encoding="utf-8") as log_file:
        with contextlib.redirect_stdout(log_file), contextlib.redirect_stderr(log_file):
            run()
    print(f"地图查询测试完成，日志已写入：{LOG_PATH}")


if __name__ == "__main__":
    main()
