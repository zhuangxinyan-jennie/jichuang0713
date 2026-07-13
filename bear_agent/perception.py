"""
感知融合模块
将perception_result融合成自然语言描述
"""

class PerceptionFusion:
    def __init__(self):
        self.emotion_map = {
            "angry": "生气",
            "disgust": "厌恶",
            "scared": "害怕",
            "happy": "开心",
            "sad": "难过",
            "surprised": "惊讶",
            "neutral": "平静"
        }

        self.gesture_map = {
            "wave_hand": "挥手",
            "clapping": "鼓掌",
            "none": None
        }

        self.hand_gesture_map = {
            "call": "打电话手势",
            "dislike": "倒赞手势",
            "fist": "握拳",
            "four": "四",
            "like": "点赞手势",
            "mute": "嘘声手势",
            "grabbing": "抓握手势",
            "grip": "捏合手势",
            "ok": "OK手势",
            "one": "一",
            "palm": "张开手掌",
            "peace": "剪刀手",
            "peace_inv": "反向剪刀手",
            "rock": "摇滚手势",
            "point": "指向手势",
            "pinkie": "小拇指手势",
            "stop": "停止手势",
            "stop_inv": "反向停止手势",
            "three": "三",
            "three2": "三",
            "two_up": "两指向上",
            "two_up_inv": "反向两指向上",
            "mid_finger": "中指手势",
            "three3": "三",
            "gun": "手枪手势",
            "thumb_index": "拇指食指手势",
            "thumb_index2": "拇指食指手势",
            "holy": "合十手势",
            "timeout": "暂停手势",
            "take_photo": "拍照手势",
            "xsign": "X手势",
            "heart": "比心手势",
            "heart2": "双手比心",
            "none": None
        }

    def fuse(self, perception_result):
        """
        融合感知结果，返回结构化数据和自然语言描述

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
                "person_detected": True,
                "emotion": "happy",
                "gesture": "wave_hand",
                "hand_gesture": "like",
                "speech_text": "熊大你好呀",
                "description": "游客挥手，点赞手势，表情开心，说：熊大你好呀"
            }
        """
        person_detected = perception_result.get("person_detected", False)

        if not person_detected:
            return {
                "person_detected": False,
                "emotion": None,
                "gesture": None,
                "hand_gesture": None,
                "speech_text": "",
                "description": "没有检测到游客"
            }

        emotion = perception_result.get("emotion", "neutral")
        gesture = perception_result.get("gesture", "none")
        hand_gesture = perception_result.get("hand_gesture", "none")
        speech_text = perception_result.get("speech_text", "")

        # 构建自然语言描述
        description_parts = []

        # 身体动作描述
        if gesture and gesture != "none":
            gesture_cn = self.gesture_map.get(gesture, gesture)
            if gesture_cn:
                description_parts.append(f"游客{gesture_cn}")

        # 手势描述
        if hand_gesture and hand_gesture != "none":
            hand_gesture_cn = self.hand_gesture_map.get(hand_gesture, hand_gesture)
            if hand_gesture_cn:
                description_parts.append(f"{hand_gesture_cn}")

        # 表情描述
        emotion_cn = self.emotion_map.get(emotion, "平静")
        description_parts.append(f"表情{emotion_cn}")

        # 语音描述
        if speech_text:
            description_parts.append(f"说：{speech_text}")

        description = "，".join(description_parts) if description_parts else "游客站在你面前"

        return {
            "person_detected": True,
            "emotion": emotion,
            "gesture": gesture,
            "hand_gesture": hand_gesture,
            "speech_text": speech_text,
            "description": description
        }
