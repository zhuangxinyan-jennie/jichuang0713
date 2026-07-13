"""
输出解析模块
将LLM的4行文本输出解析为JSON格式
"""
import re

from config import ACTION_NAME_ALIASES


class OutputParser:
    def flatten_action_list(self, action_list):
        """兼容扁平动作列表和按层级分类的动作库。"""
        if isinstance(action_list, dict):
            return [action for actions in action_list.values() for action in actions]
        return list(action_list)

    def get_action_categories(self, action_list):
        """返回动作名到层级分类的映射。"""
        if not isinstance(action_list, dict):
            return {}

        categories = {}
        for category, actions in action_list.items():
            for action in actions:
                categories[action] = category
        return categories

    def _extract_value(self, line):
        """提取中文字段冒号后的内容。"""
        if "：" in line:
            return line.split("：", 1)[1].strip()
        if ":" in line:
            return line.split(":", 1)[1].strip()
        return ""

    def parse(self, llm_output):
        """
        解析LLM输出为JSON格式

        期望输入格式：
        说话：嘿！你好呀！来跟熊大挥挥手！
        方式：sequential
        动作：挥手致意 -> 双手欢呼
        表情：smile

        或者新动作格式：
        说话：让我给你表演一个后空翻！
        方式：generated
        动作：熊大向后跳起，在空中翻转一圈，稳稳落地
        表情：smile

        Returns:
            {
                "speech": "...",
                "motion_type": "sequential/generated",
                "actions": [...],  # 叠加/顺序时的动作列表
                "motion_description": "...",  # 新动作时的描述
                "emotion": "..."
            }
        """
        try:
            lines = llm_output.strip().split('\n')
            fields = {
                "speech": "",
                "motion_type": "sequential",
                "action_text": "",
                "emotion": "smile"
            }
            result = {
                "speech": "",
                "motion_type": "sequential",
                "actions": [],
                "motion_description": None,
                "emotion": "smile"
            }

            for line in lines:
                line = line.strip()
                if not line:
                    continue

                if line.startswith("说话：") or line.startswith("说话:"):
                    fields["speech"] = self._extract_value(line)
                elif line.startswith("方式：") or line.startswith("方式:"):
                    motion_type = self._extract_value(line)
                    if motion_type in {"sequential", "generated"}:
                        fields["motion_type"] = motion_type
                elif line.startswith("动作：") or line.startswith("动作:"):
                    fields["action_text"] = self._extract_value(line)
                elif line.startswith("表情：") or line.startswith("表情:"):
                    fields["emotion"] = self._extract_value(line)

            result["speech"] = fields["speech"]
            result["motion_type"] = fields["motion_type"]
            result["emotion"] = fields["emotion"]

            action_text = fields["action_text"]
            if result["motion_type"] == "generated":
                result["motion_description"] = action_text
                result["actions"] = []
            else:
                action_text = action_text.replace('→', '->').replace('+', '->')
                actions = [a.strip() for a in action_text.split('->')]
                result["actions"] = [a for a in actions if a]

            return result

        except Exception as e:
            # 解析失败，返回默认响应
            print(f"[OutputParser] 解析失败: {e}")
            return {
                "speech": "嗯...熊大没听清楚，你能再说一遍吗？",
                "motion_type": "sequential",
                "actions": ["挠头歪身"],
                "motion_description": None,
                "emotion": "confused"
            }

    def repair(self, parsed_output, action_list, emotion_list):
        """
        自动修正常见的LLM串字段错误。

        - 动作列表里混入表情名：从动作列表移除
        - 表情字段里填了动作名或非法值：改成默认 smile
        """
        repaired = parsed_output.copy()
        valid_actions = self.flatten_action_list(action_list)

        emotion_raw = repaired["emotion"]
        emotion_parts = [p for p in re.split(r"\s*(?:\+|->|→|,|，|、|\s)\s*", emotion_raw) if p]
        valid_emotions = [p for p in emotion_parts if p in emotion_list]
        misplaced_actions = [p for p in emotion_parts if p in valid_actions]

        if misplaced_actions:
            print(f"[OutputParser] 修正：表情里包含动作 {misplaced_actions}，已移除")

        if valid_emotions:
            repaired["emotion"] = valid_emotions[0]
        elif emotion_raw not in emotion_list:
            default_emotion = "smile" if "smile" in emotion_list else emotion_list[0]
            print(f"[OutputParser] 修正：表情 '{emotion_raw}' 不在表情库中，已改为 {default_emotion}")
            repaired["emotion"] = default_emotion

        if repaired["motion_type"] == "generated":
            return repaired

        clean_actions = []
        for action in repaired["actions"]:
            if action in emotion_list:
                print(f"[OutputParser] 修正：动作 '{action}' 是表情名，已从动作列表移除")
                continue
            canon = ACTION_NAME_ALIASES.get(action, action)
            if canon != action:
                print(f"[OutputParser] 修正：废弃动作名 '{action}' → '{canon}'")
                action = canon
            clean_actions.append(action)

        repaired["actions"] = clean_actions

        return repaired

    def validate(self, parsed_output, action_list, emotion_list=None):
        """
        验证解析结果的合法性

        Args:
            parsed_output: parse()的返回结果
            action_list: 合法的动作列表
            emotion_list: 合法的表情列表

        Returns:
            bool: 是否合法
        """
        valid_actions = self.flatten_action_list(action_list)
        action_categories = self.get_action_categories(action_list)

        if parsed_output["motion_type"] not in {"sequential", "generated"}:
            print(f"[OutputParser] 警告：方式 '{parsed_output['motion_type']}' 不合法")
            return False

        if emotion_list is not None and parsed_output["emotion"] not in emotion_list:
            print(f"[OutputParser] 警告：表情 '{parsed_output['emotion']}' 不在表情库中")
            return False

        if parsed_output["emotion"] in valid_actions:
            print(f"[OutputParser] 警告：表情 '{parsed_output['emotion']}' 是动作名，不是表情")
            return False

        # 新动作类型不需要验证动作列表
        if parsed_output["motion_type"] == "generated":
            return parsed_output["motion_description"] is not None

        # 叠加/顺序类型需要验证动作是否在动作库中
        for action in parsed_output["actions"]:
            if emotion_list is not None and action in emotion_list:
                print(f"[OutputParser] 警告：动作 '{action}' 是表情名，不是动作")
                return False
            if action not in valid_actions:
                print(f"[OutputParser] 警告：动作 '{action}' 不在动作库中")
                return False

        return len(parsed_output["actions"]) > 0
