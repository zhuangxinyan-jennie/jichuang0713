# 熊大Agent玩法模式方案

本文档记录新增的两种玩法模式：

- 随机互动：沿用当前规则库 + Qwen3-27B API 的开放互动逻辑。
- 剧情互动：固定剧情状态机，不调用LLM，只根据游客语音回答推进剧情。

目标是让 Python 侧负责玩法状态和分支判断，Unity 侧负责播放对应动画片段。

## 1. 总体状态机

```text
NO_VISITOR
  ↓ 检测到新游客
MODE_SELECT
  ↓ 发出玩法介绍clip
WAIT_MODE_CHOICE
  ↓ 游客说“随机互动”
RANDOM_INTERACTION
  ↓ 连续无人5秒
MODE_SELECT

WAIT_MODE_CHOICE
  ↓ 游客说“剧情互动”
STORY_INTERACTION
  ↓ 剧情结束
MODE_SELECT
```

等待回答时不输出新JSON，不推进普通随机互动逻辑，只等待语音识别结果。

## 2. 新游客判断

第一版先假设始终只有一个游客。新游客触发规则：

```text
person_detected 从 False 变为 True
```

或者：

```text
person_detected=False 连续超过5秒后，再次检测到 person_detected=True
```

触发新游客后进入 `MODE_SELECT`。

## 3. Unity通信格式

所有输出都必须带 `interaction_type`，方便Unity区分玩法类型。

### 3.1 玩法选择

```json
{
  "interaction_type": "mode_select",
  "clip_ids": ["mode_select_intro"]
}
```

### 3.2 随机互动

随机互动可以继续沿用当前动作JSON，只需要保证外层有：

```json
{
  "interaction_type": "random_interaction",
  "speech": "嘿！你好呀！",
  "motion_type": "sequential",
  "actions": ["挥手致意"],
  "emotion": "smile"
}
```

### 3.3 剧情互动

剧情互动也发 `clip_ids`，动画和台词由Unity按预制片段播放。`clip_ids` 是列表，Unity按顺序连续播放。

```json
{
  "interaction_type": "story_interaction",
  "clip_ids": ["story_intro_wake_choice"]
}
```

不需要游客回答的剧情片段使用同样格式：

```json
{
  "interaction_type": "story_interaction",
  "clip_ids": ["story_finale_return"]
}
```

如果多个clip需要连续播放，直接放在同一个列表里：

```json
{
  "interaction_type": "story_interaction",
  "clip_ids": ["story_wake_no_fight_yes", "story_finale_return"]
}
```

## 4. 等待回答规则

第一版不做超时，不做retry clip，不和Unity通信确认动画播放完毕。

发出需要回答的clip后：

```text
进入等待状态
不输出任何新JSON
只读取ASR最终文本
一直等到识别出目标答案
```

等待哪一种回答由Python状态机内部维护，不放进发给Unity的JSON里。

等待状态下忽略：

- 表情
- 动作
- 手势
- 人数变化
- 非目标语音

只处理：

- 玩法选择：`随机互动` / `剧情互动`
- 剧情回答：`要` / `不要`

如果没有匹配到目标答案，返回 `None`，不向Unity发送内容。

## 5. 语音解析规则

### 5.1 玩法选择

第一版只要求游客明确回答：

```text
随机互动
剧情互动
```

后续可以扩展同义词：

```text
随机互动：随机、聊天、问答、随便玩
剧情互动：剧情、故事、熊二、演故事
```

### 5.2 要/不要

第一版只要求游客明确回答：

```text
要
不要
```

注意解析时应优先判断 `不要`，再判断 `要`，避免把“不要”误判成“要”。

## 6. 随机互动模式

随机互动沿用当前逻辑：

```text
感知数据 + 记忆上下文
  ↓
规则库优先
  ↓ 未命中
Qwen3-27B API
  ↓
解析为现有动作JSON
```

随机互动结束条件：

```text
person_detected=False 连续超过5秒
```

结束后：

```text
清空随机互动memory
进入 MODE_SELECT
重新让游客选择玩法
```

第一版不考虑从随机互动主动跳转到剧情互动。

## 7. 剧情互动流程

剧情互动完全硬编码，不调用Qwen3-27B。

整体流程：

```text
story_intro_wake_choice
  ↓ 等待 要/不要

如果 要：
  story_wake_yes_honey_trick + story_wake_yes_cheer_choice
    ↓ 等待 要/不要
    要：story_wake_yes_cheer_yes + story_finale_return
    不要：story_wake_yes_cheer_no + story_finale_return
  回到 MODE_SELECT

如果 不要：
  story_wake_no_dream_wakeup + story_wake_no_fight_choice
    ↓ 等待 要/不要
    要：story_wake_no_fight_yes + story_finale_return
    不要：story_wake_no_fight_no + story_finale_return
  回到 MODE_SELECT
```

## 8. 玩法选择动画

### clip_id: `mode_select_intro`

用途：检测到新游客，或上一轮玩法结束后，让游客选择玩法。

角色：熊大

内容：

```text
熊大：“嘿！欢迎来狗熊岭！俺这儿有两种玩法。”
熊大：“一种是随机互动，你说啥俺就陪你聊聊，还能做动作回应你。”
熊大：“另一种是剧情互动，俺和熊二一起陪你演一小段故事。”
熊大：“你想玩随机互动，还是剧情互动呀？”
```

等待游客回答：

```text
随机互动 / 剧情互动
```

## 9. 剧情动画详细内容

### clip_id: `story_intro_wake_choice`

用途：剧情开场，询问是否叫醒熊二。

角色：熊大、熊二

内容：

```text
熊大：“太好啦！那咱们来玩点有意思的！俺这就把俺弟弟叫出来。熊二！熊二！”
```

动画：

```text
熊二出场，直接躺在地上睡觉。
熊大走近熊二，弯腰看他。
```

台词：

```text
熊大：“哎呀，俺这贪睡的弟弟又在地上睡着了。你要不要跟俺一起把他叫醒？”
```

等待游客回答：

```text
要 / 不要
```

### clip_id: `story_wake_yes_honey_trick`

用途：游客选择叫醒熊二，进入蜂蜜馋醒线。

角色：熊大、熊二

内容：

```text
熊大：“嘿嘿，叫醒他太简单了，看俺的！”
```

动画：

```text
熊大深吸一口气，假装大喊。
```

台词：

```text
熊大：“哇——好香啊！哪来这么一大罐甜甜的蜂蜜呀？还有红彤彤的大苹果！”
```

动画：

```text
熊二瞬间惊醒，一边流口水一边四处张望。
```

台词：

```text
熊二：“蜂蜜？苹果？在哪呢在哪呢？俺要吃俺要吃！”
熊大：“哈哈哈哈，骗你的！瞧把你馋的，口水都流出来了。”
熊二：“啊？熊大你又骗俺，俺梦里正吃着蜂蜜大餐呢……”
熊大：“既然醒了，赶紧起来活动活动，天天睡，肚子又胖了一圈。”
熊二：“俺没力气，没吃饱走不动……除非，除非有人给俺鼓鼓掌，加加油！”
```

此clip结束后自动进入下一clip：`story_wake_yes_cheer_choice`。

### clip_id: `story_wake_yes_cheer_choice`

用途：蜂蜜馋醒线第二个问题，询问游客是否给熊二鼓掌加油。

角色：熊大、熊二

内容：

```text
熊大（看向镜头）：“这贪吃鬼又耍赖了。你要不要给他鼓鼓掌加加油？”
```

等待游客回答：

```text
要 / 不要
```

### clip_id: `story_wake_yes_cheer_yes`

用途：游客愿意给熊二加油。

角色：熊二、熊大

内容：

```text
熊二：“太好啦！听见没熊大，有人给俺加油呢！俺感觉现在浑身都是劲儿！走着！”
```

动画：

```text
熊二从赖着不动变成精神起来，做一个开心起身或小跑动作。
熊大在旁边点头或笑。
```

实际输出时可和 `story_finale_return` 放在同一个 `clip_ids` 列表中连续播放。

### clip_id: `story_wake_yes_cheer_no`

用途：游客不愿意给熊二加油。

角色：熊大、熊二

内容：

```text
熊大：“你看，没人惯着你吧！别偷懒了，赶紧起来走！”
熊二：“哎哟喂，好吧好吧，俺自己慢慢走……”
```

动画：

```text
熊大叉腰或挥手催促。
熊二慢吞吞起身。
```

实际输出时可和 `story_finale_return` 放在同一个 `clip_ids` 列表中连续播放。

### clip_id: `story_wake_no_dream_wakeup`

用途：游客选择不叫醒熊二，进入做梦惊醒线。

角色：熊大、熊二

内容：

```text
熊大：“嘘——也对，让他多睡会儿吧。咱们小点声。”
```

动画：

```text
安静两秒钟。
熊二睡着，身体轻微起伏。
突然开始说梦话。
```

台词：

```text
熊二：（吧唧吧唧嘴，说梦话）“好吃……真好吃……光头强你别跑，把蜂蜜放下……”
```

动画：

```text
熊二翻了个身，突然自己把自己惊醒了，揉了揉眼睛。
```

台词：

```text
熊二：“咦？熊大？俺咋睡着了？”
熊二：“嘿嘿，俺刚才做梦，梦见光头强要把咱们的树都砍了，还要抢俺的蜂蜜，吓死俺了！”
```

此clip结束后自动进入下一clip：`story_wake_no_fight_choice`。

### clip_id: `story_wake_no_fight_choice`

用途：做梦惊醒线第二个问题，询问游客是否一起赶跑光头强。

角色：熊二

内容：

```text
熊二（看向镜头）：“俺正准备在梦里教训光头强呢！如果光头强真来了，你要不要和俺们一起把他赶跑？”
```

等待游客回答：

```text
要 / 不要
```

### clip_id: `story_wake_no_fight_yes`

用途：游客愿意一起赶跑光头强。

角色：熊二、熊大

内容：

```text
熊二：“太仗义了！有你在，咱们肯定能把光头强打得落花流水！”
```

动画：

```text
熊二兴奋挥拳或摆出勇敢姿势。
熊大在旁边点头认可。
```

实际输出时可和 `story_finale_return` 放在同一个 `clip_ids` 列表中连续播放。

### clip_id: `story_wake_no_fight_no`

用途：游客不愿意一起赶跑光头强。

角色：熊二、熊大

内容：

```text
熊二：“啊？不想打呀？没事没事，那真遇到了你就躲在俺身后，俺熊二保护你！”
```

动画：

```text
熊二拍拍胸口，摆出保护游客的姿势。
熊大在旁边笑。
```

实际输出时可和 `story_finale_return` 放在同一个 `clip_ids` 列表中连续播放。

### clip_id: `story_finale_return`

用途：剧情结束，熊二退场，系统回到玩法选择。

角色：熊大、熊二

内容：

```text
熊二：“哎呀不行了，折腾半天，俺的肚子都快饿扁啦，俺要去森林深处找野果子吃了。再见啦！”
```

动画：

```text
熊二挥手退场。
熊大转向镜头。
```

台词：

```text
熊大：“哈哈，俺弟弟就是个大吃货。咱们的剧情体验完啦！你还想继续玩剧情，还是试试俺随机回答你的问题呀？”
```

此clip结束后，Python状态回到：

```text
WAIT_MODE_CHOICE
```

不需要再输出 `mode_select_intro`，因为 `story_finale_return` 的最后一句已经完成了玩法选择提问。

## 10. 建议模块划分

后续实现时可以新增两个模块。

### `game_state.py`

职责：

- 管理当前玩法状态
- 判断新游客
- 判断随机互动无人5秒结束
- 决定当前输入应该交给随机互动还是剧情互动

### `story_engine.py`

职责：

- 保存剧情节点
- 保存 `clip_ids`
- 处理 `要/不要` 分支
- 判断剧情是否结束
- 输出剧情clip JSON

现有模块建议：

- `planner.py`：只负责随机互动里的规则库 + Qwen3-27B。
- `memory.py`：主要用于随机互动，进入剧情时不让随机互动记忆影响剧情。
- `agent.py`：作为总入口，先经过玩法状态机，再决定调用随机互动或剧情互动。

## 11. 第一版不做的事情

为了保证实现稳定，第一版暂不做：

- 等待回答超时
- retry clip
- Unity clip_finished 回调
- 多游客身份识别
- 剧情中调用LLM
- 随机互动主动跳转剧情互动
- 复杂自然语言理解
- 动作/手势作为剧情回答

后续增强方向：

- 加入等待超时和重复提问
- 加入Unity播放完成回调
- 加入更多剧情脚本
- 加入园区地图问路等工具能力
- 让Qwen3-27B只负责开放问题，剧情仍保持硬编码
