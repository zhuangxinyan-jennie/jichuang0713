"""
简单记忆模块
保存最近3轮互动历史
"""
import time

class SimpleMemory:
    def __init__(self, max_history=3, reset_timeout=5.0):
        """
        Args:
            max_history: 最多保留几轮对话
            reset_timeout: 多少秒无人则清空记忆
        """
        self.max_history = max_history
        self.reset_timeout = reset_timeout
        self.interactions = []  # [{saw, said, time}, ...]
        self.last_seen_time = 0
        self.is_first_interaction = True

    def add(self, saw_description, said_text):
        """
        添加一轮互动记录

        Args:
            saw_description: 看到了什么（自然语言）
            said_text: 熊大说了什么
        """
        self.interactions.append({
            "saw": saw_description,
            "said": said_text,
            "time": time.time()
        })

        # 只保留最近N轮
        if len(self.interactions) > self.max_history:
            self.interactions.pop(0)

        self.is_first_interaction = False

    def check_reset(self, person_detected):
        """
        检查是否需要重置记忆

        Args:
            person_detected: 当前是否检测到人
        """
        current_time = time.time()

        if person_detected:
            self.last_seen_time = current_time
        else:
            # 无人超过timeout秒，清空记忆
            if current_time - self.last_seen_time > self.reset_timeout:
                self.clear()

    def clear(self):
        """清空所有记忆"""
        self.interactions.clear()
        self.is_first_interaction = True

    def to_prompt(self):
        """
        转换为给LLM的prompt文本

        Returns:
            str: 格式化的历史记录
        """
        if not self.interactions:
            return ""

        lines = [
            "【最近互动历史】",
            "你给出动作和回应时，可以选择参考这些互动历史，保持上下文连贯。"
        ]
        for i, interaction in enumerate(self.interactions[-self.max_history:], 1):
            lines.append(f"{i}. 你看到游客：{interaction['saw']}")
            lines.append(f"   你说了：{interaction['said']}")

        return "\n".join(lines)

    def get_context(self):
        """
        获取记忆上下文（用于规则匹配）

        Returns:
            dict: {is_first_interaction, last_saw, last_said}
        """
        if not self.interactions:
            return {
                "is_first_interaction": self.is_first_interaction,
                "last_saw": None,
                "last_said": None
            }

        last = self.interactions[-1]
        return {
            "is_first_interaction": self.is_first_interaction,
            "last_saw": last["saw"],
            "last_said": last["said"]
        }
