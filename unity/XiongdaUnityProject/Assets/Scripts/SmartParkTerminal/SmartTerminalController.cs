using System.Collections;
using UnityEngine;

namespace SmartParkTerminal
{
    /// <summary>
    /// 智慧乐园终端总控：页面切换、JSON 分发、串联字幕/动画/调试。
    /// 预留：WebSocket / HTTP / TTS / 310B 状态（第一版仅用本地模拟）。
    /// </summary>
    public sealed class SmartTerminalController : MonoBehaviour
    {
        [Header("Refs")]
        [SerializeField]
        private PageManager pageManager;

        [SerializeField]
        private ClipIdPlayer clipPlayer;

        [SerializeField]
        private SubtitleController subtitleController;

        [SerializeField]
        private DebugPanelController debugPanel;

        [SerializeField]
        private MapUIController mapUi;

        [SerializeField]
        private RecommendationUIController recommendationUi;

        [SerializeField]
        private DemoUIController demoUi;

        private string _lastModule = "character_interaction";
        private string _lastInteractionType = "-";
        private string _lastClipId = "-";
        private string _lastEmotion = "smile";
        private Coroutine _sequenceRoutine;

        private void Start()
        {
            if (pageManager == null || clipPlayer == null || subtitleController == null || debugPanel == null)
            {
                Debug.LogError("[SmartTerminalController] 引用未齐：请运行菜单「Tools/狗熊岭智慧终端/生成 SmartParkTerminal 场景」或手动绑定 Inspector。");
                return;
            }

            debugPanel.SetConnectionStatus("本地模拟（310B 未连接）");
            debugPanel.SetRawJson("(none)");
            debugPanel.UpdateStatus(null, "-");
            ShowCharacterPage();

            if (recommendationUi != null)
            {
                recommendationUi.WireCardClicks(this);
                recommendationUi.ShowDefaultRecommendations();
            }

            if (demoUi != null)
            {
                demoUi.BindTerminal(this);
            }
        }

        public void ShowCharacterPage()
        {
            pageManager.ShowPage(PageManager.PageCharacter);
        }

        public void ShowMapPage()
        {
            pageManager.ShowPage(PageManager.PageMap);
        }

        public void ShowRecommendationPage()
        {
            pageManager.ShowPage(PageManager.PageRecommendation);
        }

        public void ShowSystemPage()
        {
            pageManager.ShowPage(PageManager.PageSystem);
        }

        /// <summary>接入 310B / 网络后调用此入口。</summary>
        public void HandleJsonCommand(string json)
        {
            debugPanel.SetRawJson(json ?? "");
            TerminalCommand cmd = TerminalCommand.FromJson(json);
            if (cmd == null)
            {
                subtitleController.ShowSpeech("指令解析失败，请检查 JSON。");
                debugPanel.UpdateStatus(null, "-");
                return;
            }

            DispatchCommand(cmd, false);
        }

        /// <summary>本地 Demo / UI 直接构造指令。</summary>
        public void DispatchCommand(TerminalCommand cmd, bool serializeJson)
        {
            if (cmd == null)
            {
                return;
            }

            if (serializeJson)
            {
                debugPanel.SetRawJson(JsonUtility.ToJson(cmd));
            }

            _lastModule = string.IsNullOrEmpty(cmd.module) ? _lastModule : cmd.module;
            _lastInteractionType = string.IsNullOrEmpty(cmd.interaction_type) ? _lastInteractionType : cmd.interaction_type;
            _lastEmotion = string.IsNullOrEmpty(cmd.emotion) ? _lastEmotion : cmd.emotion;

            ApplySubtitle(cmd.speech);

            string previewClip = string.IsNullOrEmpty(cmd.clip_id) ? PickFirstClip(cmd.clip_ids) : cmd.clip_id;
            _lastClipId = string.IsNullOrEmpty(previewClip) ? "-" : previewClip;
            debugPanel.UpdateStatus(cmd, _lastClipId);

            clipPlayer.PlayTtsIfPresent(cmd.audio_path);

            DispatchByModule(cmd);
        }

        private static string PickFirstClip(string[] ids)
        {
            return ids != null && ids.Length > 0 ? ids[0] : null;
        }

        private void ApplySubtitle(string speech)
        {
            if (!string.IsNullOrEmpty(speech))
            {
                subtitleController.ShowSpeech(speech);
            }
        }

        private void DispatchByModule(TerminalCommand cmd)
        {
            string module = (cmd.module ?? "").Trim().ToLowerInvariant();
            switch (module)
            {
                case "character_interaction":
                    DispatchCharacter(cmd);
                    break;
                case "map_query":
                    DispatchMap(cmd);
                    break;
                case "recommendation":
                    DispatchRecommendation(cmd);
                    break;
                default:
                    DispatchCharacter(cmd);
                    break;
            }
        }

        private void DispatchCharacter(TerminalCommand cmd)
        {
            ShowCharacterPage();

            if (_sequenceRoutine != null)
            {
                StopCoroutine(_sequenceRoutine);
                _sequenceRoutine = null;
            }

            string layered = (cmd.motion_type ?? "").Trim().ToLowerInvariant();
            if (layered == "layered" && cmd.actions != null && cmd.actions.Length > 0)
            {
                _sequenceRoutine = StartCoroutine(RunClipSequence(cmd.actions, cmd.speech, 3.2f));
                return;
            }

            if (cmd.clip_ids != null && cmd.clip_ids.Length > 0)
            {
                _sequenceRoutine = StartCoroutine(RunClipSequence(cmd.clip_ids, cmd.speech, 4f));
                return;
            }

            if (!string.IsNullOrEmpty(cmd.clip_id))
            {
                bool ok = clipPlayer.PlayClipById(cmd.clip_id, cmd.speech, cmd.interaction_type, cmd.emotion);
                _lastClipId = cmd.clip_id;
                if (!ok && string.IsNullOrEmpty(cmd.speech))
                {
                    subtitleController.ShowSpeech("动画未配置或 Animator 未就绪。");
                }

                debugPanel.UpdateStatus(cmd, _lastClipId);
            }
        }

        private IEnumerator RunClipSequence(string[] ids, string speechHint, float gap)
        {
            if (!string.IsNullOrEmpty(speechHint))
            {
                subtitleController.ShowSpeech(speechHint);
            }

            yield return StartCoroutine(clipPlayer.PlayClipSequence(ids, gap));
            _sequenceRoutine = null;
        }

        private void DispatchMap(TerminalCommand cmd)
        {
            ShowMapPage();
            string ui = (cmd.ui_action ?? "").Trim().ToLowerInvariant();
            if (ui == "show_map" || string.IsNullOrEmpty(ui))
            {
                // 保持地图页
            }

            if (mapUi != null && !string.IsNullOrEmpty(cmd.highlight_poi))
            {
                mapUi.ShowPOI(cmd.highlight_poi);
                string poiName = mapUi.GetPoiDisplayName(cmd.highlight_poi);
                mapUi.SetMapInfo(poiName + " 已高亮。");
            }

            if (!string.IsNullOrEmpty(cmd.clip_id))
            {
                clipPlayer.PlayClipById(cmd.clip_id, cmd.speech, "map_query", cmd.emotion);
                _lastClipId = cmd.clip_id;
            }
            else
            {
                clipPlayer.PlayClipById("point_right", cmd.speech, "map_query", cmd.emotion);
                _lastClipId = "point_right";
            }

            debugPanel.UpdateStatus(cmd, _lastClipId);
        }

        private void DispatchRecommendation(TerminalCommand cmd)
        {
            ShowRecommendationPage();
            if (recommendationUi != null && cmd.recommendation != null)
            {
                recommendationUi.ShowRecommendation(cmd.recommendation);
            }

            if (!string.IsNullOrEmpty(cmd.clip_id))
            {
                clipPlayer.PlayClipById(cmd.clip_id, cmd.speech, "recommendation", cmd.emotion);
                _lastClipId = cmd.clip_id;
            }
            else
            {
                clipPlayer.PlayClipById("talk_gesture_small", cmd.speech, "recommendation", cmd.emotion);
                _lastClipId = "talk_gesture_small";
            }

            debugPanel.UpdateStatus(cmd, _lastClipId);
        }

        /* ========== 预留扩展（第一版不实现） ==========
         * void ConnectWebSocket(string url) { }
         * void ConnectHttpPoll(string baseUrl) { }
         * void OnVisitorAsrText(string text) { }
         */
    }
}
