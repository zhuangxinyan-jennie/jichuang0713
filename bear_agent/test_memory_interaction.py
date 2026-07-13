"""
专项测试随机互动里的记忆功能，并把输出写入 logs/memory_interaction.log。

默认调用真实Qwen API。运行时会打开 planner.debug_prompt，把真实发给LLM的
user prompt 打印到日志，便于查看【最近互动历史】是否进入调用。

如需离线测试状态机，可加 --fake 使用 FakeLLMClient。
"""
import argparse
import contextlib
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))

from agent import BearAgent


LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
LOG_PATH = os.path.join(LOG_DIR, "memory_interaction.log")
RULES_PATH = os.path.join(os.path.dirname(__file__), "rules.json")


class FakeMessage:
    def __init__(self, content):
        self.content = content


class FakeChoice:
    def __init__(self, content):
        self.message = FakeMessage(content)


class FakeResponse:
    def __init__(self, content):
        self.choices = [FakeChoice(content)]


class FakeCompletions:
    def __init__(self):
        self.call_count = 0

    def create(self, model, messages, temperature, max_tokens, extra_body=None):
        self.call_count += 1
        user_prompt = messages[-1]["content"]

        print("\n" + "-" * 60)
        print(f"【FakeLLM 第 {self.call_count} 次收到的 user prompt】")
        print("-" * 60)
        print(user_prompt)

        has_memory = "【最近互动历史】" in user_prompt
        if has_memory and "刚才" in user_prompt:
            content = """说话：俺记得刚才那下不错，这回换个新花样！
方式：sequential
动作：张臂欢迎 -> 双手欢呼
表情：confident"""
        elif has_memory:
            content = """说话：俺记得你刚才来过，咱接着玩！
方式：sequential
动作：挥手致意
表情：smile"""
        else:
            content = """说话：嘿！俺还没记住啥，先打个招呼！
方式：sequential
动作：挥手致意
表情：smile"""

        print("\n【FakeLLM 返回】")
        print(content)
        return FakeResponse(content)


class FakeChat:
    def __init__(self):
        self.completions = FakeCompletions()


class FakeLLMClient:
    def __init__(self):
        self.chat = FakeChat()


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

    print(f"\n【响应时间】{elapsed_ms:.2f} ms")
    print("【响应JSON】")
    print(json.dumps(response, ensure_ascii=False, indent=2))
    print_memory(agent)
    return response


def print_memory(agent):
    print("\n【当前记忆】")
    context = agent.memory.get_context()
    print(json.dumps(context, ensure_ascii=False, indent=2))
    prompt = agent.memory.to_prompt()
    print(prompt if prompt else "（空）")


def run(use_fake=False):
    print("初始化Agent...")
    agent = BearAgent(rules_path=RULES_PATH)
    agent.planner.debug_prompt = True

    if use_fake:
        print("使用FakeLLMClient，不调用真实Qwen API。")
        agent.planner.llm_client = FakeLLMClient()
    else:
        print("使用真实Qwen API。")

    call(agent, "新游客出现，进入玩法选择", base_perception())
    call(agent, "游客选择随机互动", base_perception("随机互动"))

    call(agent, "第1轮：初次见面走规则库，写入第一条记忆", base_perception())

    call(agent, "第2轮：游客请求跳舞，触发真实Qwen API并携带第1轮记忆", base_perception(
        "熊大，你能跳个舞吗？",
        emotion="happy",
    ))

    call(agent, "第3轮：游客说刚才不错，触发真实Qwen API并测试上下文追问", base_perception(
        "刚才那个不错，能再来一个不一样的吗？",
        emotion="happy",
        gesture="clapping",
        gesture_confidence=0.86,
    ))

    call(agent, "第4轮：再来一轮，让记忆达到max_history=3", base_perception(
        "熊大，再摆一个帅气姿势！",
        emotion="happy",
    ))

    call(agent, "第5轮：继续互动，验证最旧记忆会被挤出", base_perception(
        "你还记得刚才我们玩了什么吗？",
        emotion="surprised",
    ))

    print("\n" + "=" * 60)
    print("【测试重点】")
    print("=" * 60)
    print("1. 查看【Planner 发给LLM的 user prompt】是否包含【最近互动历史】。")
    print("2. 查看每轮响应后【当前记忆】是否追加 saw/said。")
    print("3. 第5轮后 max_history=3，应只保留最近3条互动。")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--fake",
        action="store_true",
        help="使用FakeLLMClient离线测试，不调用真实Qwen API。"
    )
    args = parser.parse_args()

    os.makedirs(LOG_DIR, exist_ok=True)
    with open(LOG_PATH, "w", encoding="utf-8") as log_file:
        with contextlib.redirect_stdout(log_file), contextlib.redirect_stderr(log_file):
            run(use_fake=args.fake)
    print(f"记忆专项测试完成，日志已写入：{LOG_PATH}")


if __name__ == "__main__":
    main()
