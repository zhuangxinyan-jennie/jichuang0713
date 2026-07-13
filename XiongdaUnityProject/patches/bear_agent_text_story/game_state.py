"""
玩法状态机
负责新游客、玩法选择、随机互动和剧情互动之间的切换。
"""
import time

from story_engine import StoryEngine


class GameStateController:
    """玩法模式控制器。"""

    NO_VISITOR = "no_visitor"
    WAIT_MODE_CHOICE = "wait_mode_choice"
    RANDOM_INTERACTION = "random_interaction"
    WAIT_STORY_ANSWER = "wait_story_answer"
    MAP_QUERY = "map_query"

    def __init__(self, no_visitor_timeout=5.0):
        self.no_visitor_timeout = no_visitor_timeout
        self.state = self.NO_VISITOR
        self.last_person_detected = False
        self.last_person_seen_time = 0.0
        self.story = StoryEngine()

    def route(self, perception_result, random_handler, map_handler, reset_random_memory):
        """
        根据当前状态处理输入。

        Args:
            perception_result: 原始感知输入
            random_handler: 随机互动处理函数
            map_handler: 地图查询处理函数
            reset_random_memory: 清空随机互动记忆的函数

        Returns:
            dict | None: 需要发给Unity的JSON，等待回答时可能返回None。
        """
        person_detected = perception_result.get("person_detected", False)
        speech_text = perception_result.get("speech_text", "")
        current_time = time.time()

        new_visitor = self._update_person_state(person_detected, current_time)
        if new_visitor:
            reset_random_memory()
            self.story.reset()
            self.state = self.WAIT_MODE_CHOICE
            return self._mode_select_clip()

        if self.state == self.NO_VISITOR:
            return None

        if self.state == self.WAIT_MODE_CHOICE:
            mode = self.parse_mode_choice(speech_text)
            if mode == "random":
                self.state = self.RANDOM_INTERACTION
                return {
                    "interaction_type": "mode_ack",
                    "speech": "好嘞，咱们随便聊聊！你想跟俺聊啥？",
                    "story_waiting_hint": "直接说话即可开始随机互动；要说地图可说「地图查询」。",
                }
            if mode == "story":
                self.state = self.WAIT_STORY_ANSWER
                return self.story.start()
            if mode == "map":
                self.state = self.MAP_QUERY
                return {
                    "interaction_type": "mode_ack",
                    "speech": "好，俺帮你查地图。你想去哪儿？",
                    "story_waiting_hint": "直接说出地点或「xxx怎么走」。",
                }
            return None

        if self.state == self.RANDOM_INTERACTION:
            if not person_detected and self._is_no_visitor_timeout(current_time):
                reset_random_memory()
                self.state = self.WAIT_MODE_CHOICE
                return self._mode_select_clip()

            return random_handler(perception_result)

        if self.state == self.WAIT_STORY_ANSWER:
            output, finished = self.story.handle_answer(speech_text)
            if finished:
                self.state = self.WAIT_MODE_CHOICE
            return output

        if self.state == self.MAP_QUERY:
            return map_handler(perception_result)

        return None

    def parse_mode_choice(self, speech_text):
        """解析玩法选择。"""
        text = (speech_text or "").strip()
        if not text:
            return None

        if any(
            k in text
            for k in (
                "剧情互动",
                "益智小剧场",
                "小剧场",
                "智慧乐园任务",
                "做任务",
                "开始剧情",
            )
        ):
            return "story"
        if "随机互动" in text:
            return "random"
        # 不用单独「路线」——会与剧情第二幕「路线 A/B/C」冲突
        map_words = [
            "地图查询",
            "查地图",
            "打开地图",
            "园区地图",
            "问路",
            "怎么去",
            "怎么走",
            "导航",
        ]
        if any(word in text for word in map_words):
            return "map"
        return None

    def _update_person_state(self, person_detected, current_time):
        previous_detected = self.last_person_detected
        previous_seen_time = self.last_person_seen_time

        if person_detected:
            self.last_person_seen_time = current_time

        self.last_person_detected = person_detected

        if person_detected and not previous_detected:
            if previous_seen_time == 0:
                return True
            return current_time - previous_seen_time > self.no_visitor_timeout

        return False

    def _is_no_visitor_timeout(self, current_time):
        if self.last_person_seen_time == 0:
            return False
        return current_time - self.last_person_seen_time > self.no_visitor_timeout

    def _mode_select_clip(self):
        return {
            "interaction_type": "mode_select",
            "clip_ids": ["mode_select_intro"],
            "speech": "欢迎来到智慧乐园！可以说「随机互动」「剧情互动」或「地图查询」。",
            "story_waiting_hint": "请输入玩法：剧情互动 / 随机互动 / 地图查询（用文字模拟游客说话即可）。",
        }
