"""
玩法状态机
负责新游客、玩法选择、随机互动和剧情互动之间的切换。
"""
import re
import time

from speech_utils import normalize_user_speech_text
from story_engine import StoryEngine


def speech_text_from_perception(perception_result):
    """统一取出游客这句（兼容 camelCase、非 str）。"""
    raw = perception_result.get("speech_text", "")
    if raw is None:
        raw = ""
    elif not isinstance(raw, str):
        raw = str(raw)
    raw = raw.strip()
    if not raw:
        alt = perception_result.get("speechText")
        if isinstance(alt, str) and alt.strip():
            raw = alt.strip()
    return raw


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

    @staticmethod
    def _mark_target_mode(payload, mode):
        if isinstance(payload, dict) and mode:
            payload["target_mode"] = mode
        return payload

    @staticmethod
    def _random_mode_ack(hint="直接说话即可开始随机互动；要说地图可说「地图查询」。"):
        return {
            "interaction_type": "mode_ack",
            "speech": "好嘞，咱们随便聊聊！你想跟俺聊啥？",
            "voice_id": "mode_ack_random",
            "story_waiting_hint": hint,
        }

    @staticmethod
    def _map_mode_ack():
        return {
            "interaction_type": "mode_ack",
            "speech": "好，俺帮你查地图。你想去哪儿？",
            "voice_id": "mode_ack_map",
            "story_waiting_hint": "直接说出地点或「xxx怎么走」。",
        }

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
        speech_text = speech_text_from_perception(perception_result)
        current_time = time.time()

        new_visitor = self._update_person_state(person_detected, current_time)
        if new_visitor:
            reset_random_memory()
            self.story.reset()
            self.state = self.WAIT_MODE_CHOICE
            # 首次入园这一帧若已带来玩法口令，直接切入对应分支，避免必须再发第二遍
            mode = self.parse_mode_choice(speech_text)
            if mode == "story":
                self.state = self.WAIT_STORY_ANSWER
                return self._mark_target_mode(self.story.start(), "story")
            if mode == "random":
                self.state = self.RANDOM_INTERACTION
                return self._mark_target_mode(self._random_mode_ack(), "random")
            if mode == "map":
                self.state = self.MAP_QUERY
                return self._mark_target_mode(self._map_mode_ack(), "map")
            return self._mark_target_mode(self._mode_select_clip(), "voice")

        if self.state == self.NO_VISITOR:
            if not person_detected and (speech_text or "").strip():
                return {
                    "interaction_type": "mode_ack",
                    "speech": "俺还没看见游客呢。请先在右侧勾选「有人再来」，俺才能跟你对话哦。",
                }
            # 极端情况：状态仍为「未入园」但已检测到人且带了口令（例如异常复位后）
            if person_detected and speech_text.strip():
                mode = self.parse_mode_choice(speech_text)
                if mode == "story":
                    reset_random_memory()
                    self.story.reset()
                    self.state = self.WAIT_STORY_ANSWER
                    return self._mark_target_mode(self.story.start(), "story")
                if mode == "random":
                    reset_random_memory()
                    self.state = self.RANDOM_INTERACTION
                    return self._mark_target_mode(self._random_mode_ack(), "random")
                if mode == "map":
                    reset_random_memory()
                    self.state = self.MAP_QUERY
                    return self._mark_target_mode(self._map_mode_ack(), "map")
            return None

        if self.state == self.WAIT_MODE_CHOICE:
            mode = self.parse_mode_choice(speech_text)
            if mode == "random":
                self.state = self.RANDOM_INTERACTION
                return self._mark_target_mode(self._random_mode_ack(), "random")
            if mode == "story":
                self.state = self.WAIT_STORY_ANSWER
                return self._mark_target_mode(self.story.start(), "story")
            if mode == "map":
                self.state = self.MAP_QUERY
                return self._mark_target_mode(self._map_mode_ack(), "map")
            text_stripped = (speech_text or "").strip()
            if text_stripped:
                return self._mark_target_mode({
                    "interaction_type": "mode_ack",
                    "speech": "俺还没听懂要选哪种玩法呀。可以说「随机互动」唠嗑、「剧情互动」做任务，或者说「地图查询」问路。",
                    "voice_id": "mode_ack_voice",
                    "story_waiting_hint": "也可以说「语音聊天」进入唠嗑模式（与随机互动相同）。",
                }, "voice")
            return None

        if self.state == self.RANDOM_INTERACTION:
            if not person_detected and self._is_no_visitor_timeout(current_time):
                reset_random_memory()
                self.state = self.WAIT_MODE_CHOICE
                return self._mark_target_mode(self._mode_select_clip(), "voice")

            switch = self.parse_mode_choice(speech_text)
            if switch == "story":
                reset_random_memory()
                self.story.reset()
                self.state = self.WAIT_STORY_ANSWER
                return self._mark_target_mode(self.story.start(), "story")
            if switch == "map":
                reset_random_memory()
                self.state = self.MAP_QUERY
                return self._mark_target_mode(self._map_mode_ack(), "map")

            # 最后兜底：去掉所有空白后匹配（防止不可见分隔符破坏 parse_mode_choice）
            if self._compact_has_story_intent(speech_text):
                reset_random_memory()
                self.story.reset()
                self.state = self.WAIT_STORY_ANSWER
                print("[game_state] 紧凑匹配剧情口令 → StoryEngine.start()")
                return self._mark_target_mode(self.story.start(), "story")

            return self._mark_target_mode(random_handler(perception_result), "random")

        if self.state == self.WAIT_STORY_ANSWER:
            bail = self.parse_mode_choice(speech_text)
            if bail == "random":
                self.story.reset()
                self.state = self.RANDOM_INTERACTION
                return self._mark_target_mode(
                    self._random_mode_ack("想说地图可以说「地图查询」。"),
                    "random",
                )
            if bail == "map":
                self.story.reset()
                self.state = self.MAP_QUERY
                return self._mark_target_mode(self._map_mode_ack(), "map")
            # 已在剧情中再说「剧情互动」：重新开始本轮开场，避免用户误以为没进来
            if bail == "story":
                self.story.reset()
                self.state = self.WAIT_STORY_ANSWER
                return self._mark_target_mode(self.story.start(), "story")

            output, finished = self.story.handle_answer(speech_text)
            if finished:
                self.state = self.WAIT_MODE_CHOICE
            if output is None and (speech_text or "").strip():
                hint = self.story.current_waiting_hint()
                return self._mark_target_mode({
                    "interaction_type": "mode_ack",
                    "speech": "这句俺还没对上当前题目的选项。",
                    "voice_id": "story_invalid_choice",
                    "story_waiting_hint": hint,
                }, "story")
            return self._mark_target_mode(output, "story")

        if self.state == self.MAP_QUERY:
            switch = self.parse_mode_choice(speech_text)
            if switch == "story":
                self.story.reset()
                self.state = self.WAIT_STORY_ANSWER
                return self._mark_target_mode(self.story.start(), "story")
            if switch == "random":
                self.state = self.RANDOM_INTERACTION
                return self._mark_target_mode(
                    self._random_mode_ack("直接说话即可；要说地图接着说地点也行。"),
                    "random",
                )
            return self._mark_target_mode(map_handler(perception_result), "map")

        return None

    def parse_mode_choice(self, speech_text):
        """解析玩法选择。"""
        text = normalize_user_speech_text(speech_text)
        if not text:
            return None

        compact = re.sub(r"\s+", "", text)
        if "剧情互动" in compact or "劇情互動" in compact:
            return "story"

        if re.search(r"(?:剧情|劇情)\s*(?:互动|互動)", text):
            return "story"
        # 兜底：非常规空格 / 插入符号导致正则未命中时
        if "剧情" in text and "互动" in text:
            return "story"
        if any(
            k in text
            for k in (
                "益智小剧场",
                "小剧场",
                "智慧乐园任务",
                "做任务",
                "开始剧情",
                "玩剧情",
                "剧情任务",
            )
        ):
            return "story"
        random_keys = (
            "随机互动",
            "语音聊天",
            "语音互动",
            "聊聊天",
            "随便聊聊",
            "唠嗑",
        )
        if any(k in text for k in random_keys):
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

    @staticmethod
    def _compact_has_story_intent(speech_text):
        text = normalize_user_speech_text(speech_text)
        if not text:
            return False
        compact = re.sub(r"\s+", "", text)
        return ("剧情互动" in compact) or ("劇情互動" in compact)

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
            "voice_id": "mode_select_intro",
            "story_waiting_hint": "请输入玩法：剧情互动 / 随机互动 / 地图查询（用文字模拟游客说话即可）。",
        }
