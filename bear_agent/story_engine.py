"""
剧情互动状态机（固定分支 + 固定台词 + 前端固定 WAV）

- 入口：游客在完整状态机里先说「剧情互动」等口令，进入 WAIT_STORY_ANSWER。
- 之后每一轮只读 perception 里的 speech_text（语音 ASR 或键盘），由 parse_choice 映射到 A/B/C，推进 StoryEngine。
- 不调用 LLM；返回 interaction_type=story_interaction、clip_ids、speech、story_voice_ids，
  前端播放 public/theater_voice/tp_{id}.wav。
- 台词须与 xiongda_app/scripts/theater_voice_manifest.json 同源（改台词请同步 manifest 并运行 generate_theater_voices）。
"""
import re

from speech_utils import normalize_user_speech_text

CLIP_SPEECH = {
    "0": "俺今天是智慧乐园守护员，有一个益智小任务要和你一起完成。",
    "0A": "太好啦！那咱们这就出发，先把任务一项一项完成！",
    "0B": "行，俺简单说下：每一幕会给你几个选项，你帮俺选；选对了俺会表扬，选错了俺会提示，最后再一起拿智慧徽章！",
    "1": "小松鼠要去「森林剧场」，站在岔路口。\n路牌写着：左边森林剧场 300 米，右边美食广场 100 米，前方过山车 500 米。\n你觉得它该往哪走？",
    "1A": "对啦！路牌上写着森林剧场在左边，你观察得真仔细！",
    "1B": "右边是美食广场，不是森林剧场。咱们再看看路牌上的目的地呀。",
    "1C": "前方是过山车，方向不对。找路要先看清目的地再选路哦。",
    "2": "要去「梦幻花园」：\n路线 A 很近但要排队约 20 分钟；路线 B 要走 8 分钟但不用排队；路线 C 走 15 分钟还要再等 10 分钟。\n想最快到达，该选哪条？",
    "2A": "A 虽然看着近，但要等 20 分钟，加起来不一定最快哦。",
    "2B": "没错！路线 B 不用排队，总时间最短，脑子真灵光！",
    "2C": "C 又远又要等，时间花得最多，再想想「走路 + 排队」加起来谁最短？",
    "3": "下面哪个行为在乐园里是正确、文明的？",
    "3A": "翻越栏杆很危险，排队要走规定通道，可不能偷懒抄近道。",
    "3B": "对啦！垃圾分类能让乐园更干净，大家都舒服！",
    "3C": "设备运行时千万不能伸手触碰，要保持安全距离！",
    "4": "太棒啦！三个任务都完成了。你又会看路牌、又会算时间，还懂得安全和环保——这枚智慧徽章送给你！下次再来帮俺守护乐园！",
}

CLIP_TO_VOICE = {
    "0": "intro_prompt",
    "0A": "intro_resolve_a",
    "0B": "intro_resolve_b",
    "1": "act1_direction_prompt",
    "1A": "act1_direction_resolve_a",
    "1B": "act1_direction_resolve_b",
    "1C": "act1_direction_resolve_c",
    "2": "act2_route_prompt",
    "2A": "act2_route_resolve_a",
    "2B": "act2_route_resolve_b",
    "2C": "act2_route_resolve_c",
    "3": "act3_safety_prompt",
    "3A": "act3_safety_resolve_a",
    "3B": "act3_safety_resolve_b",
    "3C": "act3_safety_resolve_c",
    "4": "finale",
}


class StoryEngine:
    """管理“智慧乐园任务”固定剧情。"""

    QUESTION_OPENING = "opening_choice"
    QUESTION_SCENE_1 = "scene_1_direction"
    QUESTION_SCENE_2 = "scene_2_route"
    QUESTION_SCENE_3 = "scene_3_safety"

    def __init__(self):
        self.current_question = None

    def start(self):
        """开始一轮剧情互动。"""
        self.current_question = self.QUESTION_OPENING
        return self._clip(["0"])

    def handle_answer(self, speech_text):
        """
        处理游客的 A/B/C 选择。

        Returns:
            tuple[dict | None, bool]: (输出JSON, 剧情是否结束)
        """
        if self.current_question is None:
            return None, False

        choice = self.parse_choice(speech_text, self.current_question)
        if choice is None:
            return None, False

        if self.current_question == self.QUESTION_OPENING:
            self.current_question = self.QUESTION_SCENE_1
            return self._clip([f"0{choice}", "1"]), False

        if self.current_question == self.QUESTION_SCENE_1:
            if choice == "A":
                self.current_question = self.QUESTION_SCENE_2
                return self._clip(["1A", "2"]), False
            return self._clip([f"1{choice}", "1"]), False

        if self.current_question == self.QUESTION_SCENE_2:
            if choice == "B":
                self.current_question = self.QUESTION_SCENE_3
                return self._clip(["2B", "3"]), False
            return self._clip([f"2{choice}", "2"]), False

        if self.current_question == self.QUESTION_SCENE_3:
            if choice == "B":
                self.current_question = None
                return self._clip(["3B", "4"], story_finished=True), True
            return self._clip([f"3{choice}", "3"]), False

        return None, False

    def reset(self):
        """重置剧情状态。"""
        self.current_question = None

    def current_waiting_hint(self):
        """当前剧情问题的作答提示（用于答非所问时的友好回复）。"""
        if self.current_question is None:
            return "剧情已结束，请说「随机互动」或「剧情互动」重新开始。"
        return {
            self.QUESTION_OPENING: "请回答：「好一起完成任务」直接开始，或「先听听规则」听说明；也可以说 A 或 B。",
            self.QUESTION_SCENE_1: "可以说：往左 / 往右 / 往前，或 A、B、C。",
            self.QUESTION_SCENE_2: "可以说：路线A / 路线B / 路线C，或第二条 / 不用排队。",
            self.QUESTION_SCENE_3: "可以说：翻越栏杆 / 垃圾分类 / 触碰轨道，或 A、B、C。",
        }.get(self.current_question, "请继续用语音或文字作答。")

    def parse_choice(self, speech_text, question=None):
        """根据当前题目解析 A/B/C 选项。"""
        text = normalize_user_speech_text(speech_text)
        if not text:
            return None

        letter_choice = self._parse_letter_choice(text)
        if letter_choice:
            return letter_choice

        question = question or self.current_question
        if question == self.QUESTION_OPENING:
            # 避免单字「好」「开始」误匹配；与字幕文案对齐
            return self._parse_by_keywords(
                text,
                {
                    "A": [
                        "好一起完成任务",
                        "一起完成任务",
                        "完成任务",
                        "直接开始",
                        "马上开始",
                        "开始闯关",
                        "直接闯关",
                        "现在就玩",
                    ],
                    "B": [
                        "先听听规则",
                        "听听规则",
                        "听规则",
                        "先听规则",
                        "讲讲玩法",
                        "说一下玩法",
                        "听说明",
                        "玩法说明",
                    ],
                },
            )

        if question == self.QUESTION_SCENE_1:
            return self._parse_by_keywords(
                text,
                {
                    "A": ["左", "左边", "往左"],
                    "B": ["右", "右边", "往右"],
                    "C": ["前", "前方", "往前", "直走"],
                },
            )

        if question == self.QUESTION_SCENE_2:
            return self._parse_by_keywords(
                text,
                {
                    "A": ["路线A", "路线一", "第一条", "近路"],
                    "B": ["路线B", "路线二", "第二条", "不用排队", "8分钟", "八分钟"],
                    "C": ["路线C", "路线三", "第三条", "最远", "25分钟", "二十五分钟"],
                },
            )

        if question == self.QUESTION_SCENE_3:
            return self._parse_by_keywords(
                text,
                {
                    "A": ["翻越栏杆", "栏杆"],
                    "B": ["垃圾分类", "分类垃圾桶", "垃圾桶", "分类"],
                    "C": ["触碰轨道", "摸轨道", "轨道", "设备运行"],
                },
            )

        return None

    @staticmethod
    def _parse_letter_choice(text):
        normalized = text.upper()
        match = re.search(r"(^|[^A-Z])([ABC])([^A-Z]|$)", normalized)
        if match:
            return match.group(2)
        return None

    @staticmethod
    def _parse_by_keywords(text, choices):
        for choice, keywords in choices.items():
            if any(keyword in text for keyword in keywords):
                return choice
        return None

    def _clip(self, clip_ids, *, story_finished=False, prebaked=True):
        segments = []
        voice_ids = []
        for c in clip_ids:
            key = str(c).strip()
            t = CLIP_SPEECH.get(key)
            if t:
                segments.append(t)
            if prebaked:
                voice_ids.append(CLIP_TO_VOICE.get(key))
        speech = "\n".join(segments) if segments else ""
        payload = {
            "interaction_type": "story_interaction",
            "clip_ids": clip_ids,
            "speech": speech,
        }
        if prebaked:
            payload["story_voice_ids"] = voice_ids
        if story_finished:
            payload["story_finished"] = True
            payload["story_waiting_hint"] = (
                "本轮剧情结束。请说「随机互动」「剧情互动」或「地图查询」进入下一轮。"
            )
        elif self.current_question is not None:
            payload["story_waiting_hint"] = {
                self.QUESTION_OPENING: "请回答：「好一起完成任务」直接开始，或「先听听规则」听说明；也可以说 A 或 B。",
                self.QUESTION_SCENE_1: "可以说：往左 / 往右 / 往前，或 A、B、C。",
                self.QUESTION_SCENE_2: "可以说：路线A / 路线B / 路线C，或第二条 / 不用排队。",
                self.QUESTION_SCENE_3: "可以说：翻越栏杆 / 垃圾分类 / 触碰轨道，或 A、B、C。",
            }.get(self.current_question, "请继续用语音或文字作答。")
        return payload
