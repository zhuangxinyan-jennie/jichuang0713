using TMPro;
using UnityEngine;

namespace SmartParkTerminal
{
    /// <summary>右下角调试状态（低调样式由 Canvas 配色控制）</summary>
    public sealed class DebugPanelController : MonoBehaviour
    {
        [SerializeField]
        private TextMeshProUGUI debugText;

        private string _connectionStatus = "本地模拟";

        private string _lastJson = "(none)";

        public void BindDebugText(TextMeshProUGUI text)
        {
            debugText = text;
        }

        public void SetConnectionStatus(string status)
        {
            _connectionStatus = status ?? "本地模拟";
            RefreshVisual();
        }

        public void SetRawJson(string json)
        {
            _lastJson = string.IsNullOrEmpty(json) ? "(none)" : json;
            RefreshVisual();
        }

        public void UpdateStatus(TerminalCommand command, string clipId)
        {
            if (debugText == null)
            {
                return;
            }

            string module = command != null ? command.module : "-";
            string interaction = command != null ? command.interaction_type : "-";
            string emotion = command != null ? command.emotion : "-";
            string cid = string.IsNullOrEmpty(clipId) ? "-" : clipId;

            debugText.text =
                "[调试]\n" +
                "连接: " + _connectionStatus + "\n" +
                "module: " + module + "\n" +
                "interaction_type: " + interaction + "\n" +
                "clip_id: " + cid + "\n" +
                "emotion: " + emotion + "\n" +
                "last_json:\n" + Truncate(_lastJson, 420);
        }

        private void RefreshVisual()
        {
            if (debugText != null)
            {
                debugText.text =
                    "[调试]\n" +
                    "连接: " + _connectionStatus + "\n" +
                    "last_json:\n" + Truncate(_lastJson, 420);
            }
        }

        private static string Truncate(string s, int max)
        {
            if (string.IsNullOrEmpty(s))
            {
                return "(none)";
            }

            return s.Length <= max ? s : s.Substring(0, max) + "…";
        }
    }
}
