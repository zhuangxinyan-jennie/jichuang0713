using System;
using System.Collections;
using System.Collections.Generic;
using TMPro;
using UnityEngine;

namespace SmartParkTerminal
{
    /// <summary>clip_id → Animator State；CrossFade 播放。缺失配置时不崩溃。</summary>
    public sealed class ClipIdPlayer : MonoBehaviour
    {
        public Animator animator;

        [Tooltip("可选：与字幕栏同步（优先使用 SmartTerminal 统一字幕）")]
        public TextMeshProUGUI subtitleText;

        [Tooltip("可选：本地状态一行字")]
        public TextMeshProUGUI statusText;

        private readonly Dictionary<string, string> _clipIdToStateName = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        private readonly Dictionary<string, string> _defaultSpeechMap = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);

        private string _lastResolvedState = "";

        private void Awake()
        {
            ResolveAnimatorIfMissing();
            BuildMappings();
        }

        /// <summary>场景中若未拖 Animator（例如换成 FBX 预制体后引用丢失），自动使用 CharacterArea 下第一个 Animator。</summary>
        private void ResolveAnimatorIfMissing()
        {
            if (animator != null)
            {
                return;
            }

            var area = GameObject.Find("CharacterArea");
            if (area == null)
            {
                return;
            }

            animator = area.GetComponentInChildren<Animator>(true);
            if (animator != null)
            {
                Debug.Log("[ClipIdPlayer] 已自动绑定 Animator：" + animator.gameObject.name);
            }
        }

        private void BuildMappings()
        {
            void Map(string id, string state)
            {
                _clipIdToStateName[id] = state;
            }

            Map("stand_idle_friendly", "StandIdleFriendly");
            Map("wave_right_hand", "WaveRightHand");
            Map("laugh", "Laugh");
            Map("nod", "Nod");
            Map("point_right", "PointRight");
            Map("point_left", "PointLeft");
            Map("talk_gesture_small", "TalkGestureSmall");
            Map("mode_select_intro", "ModeSelectIntro");
            Map("story_intro_wake_choice", "StoryIntroWakeChoice");
            Map("story_wake_yes_honey_trick", "StoryWakeYesHoneyTrick");
            Map("story_wake_yes_cheer_yes", "StoryWakeYesCheerYes");
            Map("story_wake_yes_cheer_no", "StoryWakeYesCheerNo");
            Map("story_wake_no_dream_wakeup", "StoryWakeNoDreamWakeup");
            Map("story_wake_no_fight_yes", "StoryWakeNoFightYes");
            Map("story_wake_no_fight_no", "StoryWakeNoFightNo");
            Map("story_finale_return", "StoryFinaleReturn");

            void Speech(string id, string line)
            {
                _defaultSpeechMap[id] = line;
            }

            Speech("stand_idle_friendly", "俺在这儿等你呢！");
            Speech("wave_right_hand", "嘿！你好呀！");
            Speech("laugh", "哈哈哈，真有意思！");
            Speech("nod", "嗯嗯，俺明白啦！");
            Speech("point_right", "就在右边，俺带你看看！");
            Speech("point_left", "往左边走就能看到啦！");
            Speech("talk_gesture_small", "俺来给你介绍一下。");
            Speech("mode_select_intro", "嘿！欢迎来狗熊岭！俺这儿有两种玩法。你想玩随机互动，还是剧情互动呀？");
            Speech("story_intro_wake_choice", "太好啦！俺这就把俺弟弟叫出来。熊二！熊二！你要不要跟俺一起把他叫醒？");
            Speech("story_wake_yes_honey_trick", "嘿嘿，叫醒他太简单了，看俺的！哇——好香啊！哪来这么一大罐甜甜的蜂蜜呀？");
            Speech("story_wake_yes_cheer_yes", "太好啦！听见没熊大，有人给俺加油呢！");
            Speech("story_wake_yes_cheer_no", "你看，没人惯着你吧！别偷懒了，赶紧起来走！");
            Speech("story_wake_no_dream_wakeup", "嘘——也对，让他多睡会儿吧。哎呀，他自己醒啦！");
            Speech("story_wake_no_fight_yes", "太仗义了！有你在，咱们肯定能把光头强赶跑！");
            Speech("story_wake_no_fight_no", "没事没事，那真遇到了你就躲在俺身后，俺保护你！");
            Speech("story_finale_return", "哈哈，俺弟弟就是个大吃货。剧情体验完啦！你还想继续玩剧情，还是试试随机互动呀？");
        }

        public string ResolveStateName(string clipId)
        {
            if (string.IsNullOrEmpty(clipId))
            {
                return null;
            }

            return _clipIdToStateName.TryGetValue(clipId.Trim(), out string state) ? state : null;
        }

        public string GetDefaultSpeech(string clipId)
        {
            if (string.IsNullOrEmpty(clipId))
            {
                return null;
            }

            return _defaultSpeechMap.TryGetValue(clipId.Trim(), out string line) ? line : null;
        }

        public bool PlayClipById(string clipId, string speech = null, string interactionType = "ui_demo", string emotion = "smile")
        {
            _lastResolvedState = "";
            if (animator == null)
            {
                Debug.LogWarning("[ClipIdPlayer] Animator 未绑定，跳过动画。");
                SetStatus("Animator 未绑定");
                return false;
            }

            if (animator.runtimeAnimatorController == null)
            {
                Debug.LogWarning("[ClipIdPlayer] Animator Controller 未赋值。");
                SetStatus("Animator Controller 未配置");
                return false;
            }

            string stateName = ResolveStateName(clipId);
            if (string.IsNullOrEmpty(stateName))
            {
                Debug.LogWarning("[ClipIdPlayer] 未知 clip_id（未在映射表）：" + clipId);
                SetStatus("未知 clip_id: " + clipId);
                return false;
            }

            if (!HasAnimatorState(0, stateName))
            {
                Debug.LogWarning("[ClipIdPlayer] 动画未配置（Animator 无此 State）：" + stateName + "（clip_id=" + clipId + "）");
                SetStatus("动画未配置: " + stateName);
                return false;
            }

            animator.CrossFade(stateName, 0.15f, 0);
            _lastResolvedState = stateName;

            string line = string.IsNullOrEmpty(speech) ? GetDefaultSpeech(clipId) : speech;
            if (subtitleText != null && !string.IsNullOrEmpty(line))
            {
                subtitleText.text = line;
            }

            SetStatus("clip_id=" + clipId + " → " + stateName + " | " + interactionType + " | " + emotion);
            return true;
        }

        public IEnumerator PlayClipSequence(string[] clipIds, float defaultDuration = 4f)
        {
            if (clipIds == null || clipIds.Length == 0)
            {
                yield break;
            }

            foreach (string cid in clipIds)
            {
                if (string.IsNullOrEmpty(cid))
                {
                    continue;
                }

                PlayClipById(cid.Trim(), null, "sequence", "smile");
                yield return new WaitForSeconds(Mathf.Max(0.25f, defaultDuration));
            }
        }

        public string LastResolvedStateName
        {
            get { return _lastResolvedState; }
        }

        private bool HasAnimatorState(int layer, string stateName)
        {
            if (animator == null)
            {
                return false;
            }

            int hash = Animator.StringToHash(stateName);
            return animator.HasState(layer, hash);
        }

        private void SetStatus(string msg)
        {
            if (statusText != null)
            {
                statusText.text = msg ?? "";
            }
        }

        /// <summary>预留：TTS 播放 audio_path（第一版空实现）</summary>
        public void PlayTtsIfPresent(string audioPath)
        {
            if (string.IsNullOrEmpty(audioPath))
            {
                return;
            }

            Debug.Log("[ClipIdPlayer] TTS 预留 audio_path=" + audioPath);
        }
    }
}
