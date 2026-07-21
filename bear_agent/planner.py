"""
规划模块
规则库 + LLM双通道决策
"""
import json
from config import ACTION_NAME_ALIASES, LLM_CONFIG, ACTION_LIST, EMOTION_LIST
from llm_backend import build_llm_backend

class Planner:
    def __init__(self, rules_path="rules.json"):
        """
        Args:
            rules_path: 规则库JSON文件路径
        """
        # 加载规则库
        with open(rules_path, 'r', encoding='utf-8') as f:
            self.rules = json.load(f)["rules"]

        # 初始化 LLM 后端。默认仍兼容 DashScope，也可用环境变量切到板端本地服务。
        try:
            self.llm_settings, self.llm_backend = build_llm_backend(LLM_CONFIG)
            print(
                "[Planner] LLM后端: "
                f"provider={self.llm_settings.provider} "
                f"base_url={self.llm_settings.base_url} "
                f"model={self.llm_settings.model}"
            )
        except Exception as e:
            print(f"[Planner] LLM后端初始化失败，规则库未命中时使用默认响应: {e}")
            self.llm_settings, self.llm_backend = build_llm_backend({"provider": "rules_only"})
        self.debug_prompt = self.llm_settings.debug_prompt

        # 构建系统prompt
        self.system_prompt = self._build_system_prompt()

    def _build_system_prompt(self):
        """构建LLM的系统prompt"""
        action_list_str = "、".join(ACTION_LIST)
        emotion_list_str = "、".join(EMOTION_LIST)

        return f"""你是熊大，《熊出没》中的角色。你现在在方特乐园和游客互动。

【说话风格】
模仿熊大,像熊大一样热情、憨厚，有东北口吻。

【可用动作库】
{action_list_str}

【可用表情】
{emotion_list_str}

【硬性限制】
1. 动作只能从【可用动作库】里选择，不能把表情词写进动作字段。
2. 表情只能从【可用表情】里选择。
3. sequential 的动作内容只能包含动作名和连接符，不要写解释。
4. generated 的动作内容才允许写自然语言动作描述。
5. 选择动作时要考虑身体协调性，动作组合必须像真实角色能自然完成。
6. 情绪状态优先放在“表情”字段，不要用身体动作代替表情。
7. 「说话」要自然，像和小朋友面对面聊天那样有起承转合；可以多说几句，但别拖沓罗嗦，控制在两三句之内。
8. 禁止使用已下架的动作名「竖大拇指」；表达赞许、庆祝请用动作库里的「双手欢呼」。

【动作规则】
1. 只能使用 sequential 或 generated，不允许使用 layered。
2. sequential 用于动作依次播放，用 -> 连接，例如：挥手致意 -> 双手欢呼。
3. sequential 里的动作必须直接使用中文动作库名称。
4. generated 用于规则库没有的创意动作，直接用自然语言描述，需要比较简短，例如：熊大向后跳起，在空中翻转一圈，稳稳落地。

【输出格式】
你必须严格按照以下4行格式输出（不要有任何其他内容）：

说话：<你要说的话>
方式：<sequential/generated>中的一种
动作：<动作内容>
表情：<表情>

【动作类型说明】
1. sequential：动作依次做（用->连接），只从动作库选择，例如：挥手致意 -> 双手欢呼
2. generated：动作库没有的创意动作，用自然语言描述，例如：熊大向后跳起，在空中翻转一圈，稳稳落地

【示例】
说话：嘿！你好哇！俺是熊大！
方式：sequential
动作：挥手致意
表情：smile

说话：包在俺身上！看俺露一手！
方式：sequential
动作：张臂欢迎 -> 原地小跳 -> 双手欢呼
表情：confident

说话：
方式：generated
动作：熊大向后跳起，在空中翻转一圈，稳稳落地
表情：surprised
"""

    def _match_rule(self, perception_data, memory_context):
        """
        匹配规则库

        Args:
            perception_data: 感知数据 {person_detected, emotion, gesture, hand_gesture, speech_text, description}
            memory_context: 记忆上下文 {is_first_interaction, last_saw, last_said}

        Returns:
            dict or None: 匹配到的响应，或None
        """
        for rule in self.rules:
            conditions = rule["conditions"]
            matched = True

            # 检查每个条件
            for key, value in conditions.items():
                if key == "is_first_interaction":
                    if memory_context.get(key) != value:
                        matched = False
                        break
                elif key in perception_data:
                    if perception_data[key] != value:
                        matched = False
                        break

            # 如果匹配到了，还需要检查游客是否说话
            # 除了"初次见面"规则，其他规则要求游客不能说话
            if matched:
                if rule["name"] != "初次见面" and rule["name"] != "无人时待机":
                    if perception_data.get("speech_text", "").strip():
                        # 游客说话了，不匹配规则库，交给LLM处理
                        continue

                print(f"[Planner] 匹配到规则: {rule['name']}")
                return rule["response"]

        return None

    def _call_llm(self, perception_data, memory_prompt):
        """
        调用LLM生成响应（使用OpenAI兼容API）

        Args:
            perception_data: 感知数据
            memory_prompt: 记忆prompt

        Returns:
            str: LLM的原始输出
        """
        # 构建用户prompt
        user_prompt = f"""{memory_prompt}

【当前情况】
{perception_data['description']}

请根据当前情况，以熊大的身份做出回应。"""

        if self.debug_prompt:
            print("\n" + "-" * 60)
            print("【Planner 发给LLM的 user prompt】")
            print("-" * 60)
            print(user_prompt)

        try:
            llm_output = self.llm_backend.generate(self.system_prompt, user_prompt)
            print(f"[Planner] LLM输出:\n{llm_output}")
            return llm_output

        except Exception as e:
            print(f"[Planner] LLM调用失败: {e}")
            # 返回默认响应
            return """说话：嗯...熊大有点累了，休息一下哦
方式：sequential
动作：挠头歪身
表情：confused"""

    def plan(self, perception_data, memory_context, memory_prompt):
        """
        规划响应（规则库优先，LLM兜底）

        Args:
            perception_data: 感知数据
            memory_context: 记忆上下文
            memory_prompt: 记忆prompt

        Returns:
            str: LLM格式的输出文本（4行）
        """
        # 1. 先尝试匹配规则库
        rule_response = self._match_rule(perception_data, memory_context)

        if rule_response:
            # 规则库命中，转换为LLM格式
            if rule_response["motion_type"] == "generated":
                action_str = rule_response.get("motion_description", "")
            else:
                raw_actions = rule_response.get("actions") or []
                norm_actions = [ACTION_NAME_ALIASES.get(a, a) for a in raw_actions]
                if norm_actions != raw_actions:
                    print(f"[Planner] 动作别名规范化: {raw_actions} → {norm_actions}")
                action_str = " -> ".join(norm_actions)

            return f"""说话：{rule_response['speech']}
方式：{rule_response['motion_type']}
动作：{action_str}
表情：{rule_response['emotion']}"""

        # 2. 规则库未命中，调用LLM
        print("[Planner] 规则库未命中，调用LLM")
        return self._call_llm(perception_data, memory_prompt)
