from __future__ import annotations


def build_qwen_prompt(asr_text: str) -> str:
    return (
        "你是游乐园智能角色控制器，请将用户语音文本转换成动作JSON。\n"
        f"用户输入：{asr_text}\n"
        "请输出: intent/target/action/reply。"
    )


def parse_with_qwen(asr_text: str) -> dict:
    """
    规则占位实现。
    后续可替换为本地 Qwen0.7B 推理客户端。
    """
    text = (asr_text or "").strip()
    result = {
        "intent": "character_action",
        "target": "xiongda",
        "action": "idle",
        "reply": "我在呢，你可以继续告诉我想做什么动作。",
    }

    if "挥手" in text:
        result["action"] = "wave_hand"
        result["reply"] = "好呀，我来挥手啦！"
    elif "飞吻" in text:
        result["action"] = "blowing_kiss"
        result["reply"] = "收到，我给你一个飞吻！"
    elif "拍照" in text:
        result["action"] = "take_photo"
        result["reply"] = "没问题，准备拍照啦！"

    return result
