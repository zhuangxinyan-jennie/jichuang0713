# 配置文件模板 — 复制为 config.py 后填入自己的 API Key
#   copy config.example.py config.py

# LLM配置 - 阿里云百炼 DashScope（OpenAI兼容API）
LLM_CONFIG = {
    "api_key": "YOUR_DASHSCOPE_API_KEY",
    "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "model": "qwen3.5-27b",
    "temperature": 0.4,
    "max_tokens": 500,
}

# 记忆配置
MEMORY_CONFIG = {
    "max_history": 3,
    "reset_timeout": 60.0,
}

SPEECH_MAX_NON_PUNCT_CHARS = 20

RULES_CONFIG = {
    "enabled": True,
    "priority": "high",
}

ACTION_LIST = [
    "挥手致意",
    "张臂欢迎",
    "摇头",
    "双手欢呼",
    "原地小跳",
    "挠头歪身",
    "伸懒腰",
    "左右张望",
    "摊手疑问",
    "左转指左",
    "右转指右",
    "推手后退",
    "受惊后退",
    "原地踏步",
    "快走向前",
    "下蹲坐下",
    "躺地起身",
    "抱胸轻摆",
    "躺地睡觉",
    "转身一圈",
    "捂耳倾听",
    "自信造型",
    "点头",
    "摇头拒绝",
    "振臂欢呼",
    "挥手再见",
    "鼓掌",
    "捂脸害羞",
    "擦眼低头",
    "叉腰昂首",
    "跺脚生气",
    "后退惊讶",
    "鞠躬行礼",
    "飞吻",
    "抱臂拒绝",
    "托腮沉思",
    "奋力纵跳",
    "擦额拭汗",
]

ACTION_NAME_ALIASES = {
    "竖大拇指": "双手欢呼",
}

EMOTION_LIST = [
    "neutral",
    "smile",
    "confident",
    "confused",
    "angry",
    "surprised",
]
