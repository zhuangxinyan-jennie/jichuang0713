using System;

namespace SmartParkTerminal
{
    /// <summary>
    /// 310B → Unity JSON。使用 Unity JsonUtility 解析；字段名需与 JSON 一致（snake_case）。
    /// </summary>
    [Serializable]
    public sealed class RecommendationData
    {
        public string name;
        public string reason;
        public string queue_time;
        public string target_group;
    }

    [Serializable]
    public sealed class TerminalCommand
    {
        public string module;
        public string interaction_type;
        public string speech;
        public string motion_type;
        public string[] actions;
        public string clip_id;
        public string[] clip_ids;
        public string emotion;
        public string ui_action;
        public string highlight_poi;
        public RecommendationData recommendation;

        /// <summary>预留：TTS 音频路径（第一版可不填）</summary>
        public string audio_path;

        public static TerminalCommand FromJson(string json)
        {
            if (string.IsNullOrWhiteSpace(json))
            {
                return null;
            }

            try
            {
                return UnityEngine.JsonUtility.FromJson<TerminalCommand>(json.Trim());
            }
            catch (Exception)
            {
                return null;
            }
        }
    }
}
