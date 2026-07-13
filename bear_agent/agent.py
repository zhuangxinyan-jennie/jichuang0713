"""
熊大Agent主循环
感知 → 记忆 → 规划 → 输出
"""
import json
from perception import PerceptionFusion
from memory import SimpleMemory
from planner import Planner
from output_parser import OutputParser
from config import MEMORY_CONFIG, ACTION_LIST, EMOTION_LIST
from game_state import GameStateController
from map_guide import MapGuide

class BearAgent:
    def __init__(self, rules_path="rules.json"):
        """
        初始化熊大Agent

        Args:
            rules_path: 规则库JSON文件路径
        """
        self.perception = PerceptionFusion()
        self.memory = SimpleMemory(
            max_history=MEMORY_CONFIG["max_history"],
            reset_timeout=MEMORY_CONFIG["reset_timeout"]
        )
        self.planner = Planner(rules_path)
        self.parser = OutputParser()
        self.game_state = GameStateController()
        self.map_guide = MapGuide()

        print("[BearAgent] 初始化完成")

    def process(self, perception_result):
        """
        处理一次输入，返回响应

        Args:
            perception_result: {
                "emotion": "happy",
                "emotion_confidence": 0.92,
                "gesture": "wave_hand",
                "gesture_confidence": 0.85,
                "hand_gesture": "like",
                "hand_gesture_confidence": 0.78,
                "person_detected": True,
                "person_count": 1,
                "face_bbox": [120, 80, 280, 300],
                "speech_text": "熊大你好呀"
            }

        Returns:
            {
                "speech": "嘿！你好呀！来跟熊大挥挥手！",
                "motion_type": "sequential",
                "actions": ["挥手致意"],
                "motion_description": None,
                "emotion": "smile"
            }
        """
        return self.game_state.route(
            perception_result,
            random_handler=self._process_random_interaction,
            map_handler=self._process_map_query,
            reset_random_memory=self.memory.clear
        )

    def _process_random_interaction(self, perception_result):
        """执行原有随机互动流程：感知融合 → 记忆 → 规划 → 输出。"""
        # 1. 感知融合
        perception_data = self.perception.fuse(perception_result)
        print(f"[BearAgent] 感知: {perception_data['description']}")

        # 2. 检查记忆重置
        self.memory.check_reset(perception_data["person_detected"])

        # 3. 获取记忆上下文
        memory_context = self.memory.get_context()
        memory_prompt = self.memory.to_prompt()

        # 4. 规划响应
        llm_output = self.planner.plan(perception_data, memory_context, memory_prompt)

        # 5. 解析输出
        parsed_output = self.parser.parse(llm_output)
        parsed_output = self.parser.repair(parsed_output, ACTION_LIST, EMOTION_LIST)

        # 6. 验证输出（仅对顺序类型）
        if parsed_output["motion_type"] != "generated":
            if not self.parser.validate(parsed_output, ACTION_LIST, EMOTION_LIST):
                print("[BearAgent] 警告：输出验证失败，使用默认响应")
                parsed_output = {
                    "speech": "嗯...熊大有点累了，休息一下哦",
                    "motion_type": "sequential",
                    "actions": ["挠头歪身"],
                    "motion_description": None,
                    "emotion": "confused"
                }

        # 7. 更新记忆
        if perception_data["person_detected"] and parsed_output["speech"]:
            self.memory.add(perception_data["description"], parsed_output["speech"])

        parsed_output["interaction_type"] = "random_interaction"
        print(f"[BearAgent] 输出: {json.dumps(parsed_output, ensure_ascii=False, indent=2)}")
        return parsed_output

    def _process_map_query(self, perception_result):
        """执行地图问路模式。"""
        speech_text = perception_result.get("speech_text", "")
        if not speech_text:
            return None

        response = self.map_guide.answer(speech_text)
        print(f"[BearAgent] 地图问路输出: {json.dumps(response, ensure_ascii=False, indent=2)}")
        return response

    def reset(self):
        """手动重置记忆"""
        self.memory.clear()
        self.game_state = GameStateController()
        self.map_guide = MapGuide()
        print("[BearAgent] 记忆已重置")
