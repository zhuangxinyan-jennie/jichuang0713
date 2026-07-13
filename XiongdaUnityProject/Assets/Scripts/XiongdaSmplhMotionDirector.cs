using System;
using UnityEngine;

namespace XiongdaImporter
{
    /// <summary>
    /// SMPL-H JSON 动作切换：通过 logicalId 映射到 StreamingAssets 下相对路径，调用 SmplhMotionRetarget。
    /// Agent 只需输出与 Registry 一致的 logicalId，或直接调用 PlayByStreamingRelativePath。
    /// </summary>
    [DisallowMultipleComponent]
    public sealed class XiongdaSmplhMotionDirector : MonoBehaviour
    {
        [Serializable]
        public sealed class SmplhActionSlot
        {
            [Tooltip("给 Agent / TCP 用的短名，如 stand、wave")]
            public string logicalId = "stand";

            [Tooltip("相对 StreamingAssets，如 SmplhRetarget/stand.json")]
            public string streamingRelativePath = "SmplhRetarget/stand.json";
        }

        [SerializeField]
        private SmplhMotionRetarget retarget;

        [SerializeField]
        private SmplhActionSlot[] actionRegistry =
        {
            new SmplhActionSlot { logicalId = "stand", streamingRelativePath = "SmplhRetarget/stand.json" },
        };

        public string LastRequestedLogicalId { get; private set; }

        public string LastPlayedStreamingPath { get; private set; }

        public event Action<string, string, bool> OnSmplhMotionInvoked;

        private void Awake()
        {
            if (retarget == null)
            {
                retarget = GetComponent<SmplhMotionRetarget>();
            }
        }

        public SmplhActionSlot[] GetRegistryArray()
        {
            return actionRegistry;
        }

        /// <summary>按 logicalId 查找 Registry 并切换 JSON。</summary>
        public bool PlayByLogicalId(string logicalId)
        {
            LastRequestedLogicalId = logicalId ?? string.Empty;
            if (retarget == null || string.IsNullOrEmpty(logicalId))
            {
                Raise(logicalId, "", false);
                return false;
            }

            if (actionRegistry == null)
            {
                Raise(logicalId, "", false);
                return false;
            }

            foreach (var slot in actionRegistry)
            {
                if (slot == null || string.IsNullOrEmpty(slot.logicalId))
                {
                    continue;
                }

                if (!string.Equals(slot.logicalId, logicalId, StringComparison.OrdinalIgnoreCase))
                {
                    continue;
                }

                return PlayByStreamingRelativePath(slot.streamingRelativePath, logicalId);
            }

            Debug.LogWarning("[XiongdaSmplhMotionDirector] Unknown logicalId: " + logicalId);
            Raise(logicalId, "", false);
            return false;
        }

        /// <summary>不经 Registry，直接切换为指定路径（相对 StreamingAssets）。</summary>
        public bool PlayByStreamingRelativePath(string relativePath, string logicalLabelForLog = null)
        {
            if (retarget == null)
            {
                Raise(logicalLabelForLog ?? "", relativePath ?? "", false);
                return false;
            }

            bool ok = retarget.LoadMotionFromStreamingRelativePath(relativePath, true);
            if (ok)
            {
                LastPlayedStreamingPath = SmplhMotionRetarget.NormalizeStreamingRelativePath(relativePath);
                LastRequestedLogicalId = logicalLabelForLog ?? LastPlayedStreamingPath;
                Raise(LastRequestedLogicalId, LastPlayedStreamingPath, true);
            }
            else
            {
                Raise(logicalLabelForLog ?? "", relativePath ?? "", false);
            }

            return ok;
        }

        private void Raise(string logicalId, string path, bool ok)
        {
            if (OnSmplhMotionInvoked != null)
            {
                OnSmplhMotionInvoked(logicalId, path, ok);
            }
        }
    }
}
