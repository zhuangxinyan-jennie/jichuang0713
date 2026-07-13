using System;
using UnityEngine;

namespace XiongdaImporter
{
    /// <summary>
    /// 统一入口：按「逻辑 id」或「Clip 名」驱动 Legacy Animation。
    /// UI 按钮与 TCP 指令应调用本组件的公开方法，便于你方多模态 + Agent 只负责解析后传 id/clipName。
    /// </summary>
    [DisallowMultipleComponent]
    public sealed class XiongdaLegacyAnimationDirector : MonoBehaviour
    {
        [Serializable]
        public sealed class ActionSlot
        {
            [Tooltip("给 Agent / 外部协议用的短名，如 run、wave")]
            public string logicalId = "run";

            [Tooltip("本物体 Animation 上已存在的 State/Clip 名，须与工程里 clip.name 一致")]
            public string clipName = "Run";

            public WrapMode wrapMode = WrapMode.Loop;

            [Tooltip("CrossFade 过渡时间（秒）")]
            [Range(0.01f, 1f)]
            public float crossFade = 0.08f;
        }

        [SerializeField]
        private Animation targetAnimation;

        [SerializeField]
        private ActionSlot[] actionRegistry =
        {
            new ActionSlot { logicalId = "run", clipName = "Run", wrapMode = WrapMode.Loop },
        };

        [SerializeField]
        [Tooltip("若为 true，屏蔽同物体上的 XiongdaPlayOnStart，避免与调度冲突")]
        private bool suppressLegacyPlayOnStart = true;

        [SerializeField]
        [Tooltip("进入场景后是否自动播第一条 registry（便于测试）")]
        private bool playFirstRegistryEntryOnStart;

        /// <summary>最近一次尝试播放的逻辑 id（可为空）；PLAY_CLIP 直连时为 clip 名。</summary>
        public string LastRequestedLogicalId { get; private set; }

        /// <summary>最近一次播放的 clip 名。</summary>
        public string LastPlayedClipName { get; private set; }

        /// <summary>参数：logicalId 或说明、clipName、是否成功。</summary>
        public event Action<string, string, bool> OnActionInvoked;

        /// <summary>返回注册表副本引用（勿在运行时修改元素引用）。仅用于调试或 UI 枚举。</summary>
        public ActionSlot[] GetRegistryArray()
        {
            return actionRegistry;
        }

        public int RegistryCount
        {
            get { return actionRegistry == null ? 0 : actionRegistry.Length; }
        }

        public ActionSlot GetRegistryEntry(int index)
        {
            if (actionRegistry == null || index < 0 || index >= actionRegistry.Length)
            {
                return null;
            }

            return actionRegistry[index];
        }

        private void Awake()
        {
            if (targetAnimation == null)
            {
                targetAnimation = GetComponent<Animation>();
            }

            if (suppressLegacyPlayOnStart)
            {
                var auto = GetComponent<XiongdaPlayOnStart>();
                if (auto != null)
                {
                    auto.enabled = false;
                }
            }
        }

        private void Start()
        {
            if (!playFirstRegistryEntryOnStart || actionRegistry == null || actionRegistry.Length == 0)
            {
                return;
            }

            var first = actionRegistry[0];
            if (first != null)
            {
                PlayByLogicalId(first.logicalId);
            }
        }

        /// <summary>按注册表中的 logicalId 播放（大小写不敏感）。</summary>
        public bool PlayByLogicalId(string logicalId)
        {
            LastRequestedLogicalId = logicalId ?? string.Empty;
            if (targetAnimation == null || string.IsNullOrEmpty(logicalId))
            {
                Raise("", "", false);
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

                return PlayClipInternal(slot.clipName, slot.wrapMode, slot.crossFade, logicalId);
            }

            Raise(logicalId, "", false);
            Debug.LogWarning("[XiongdaLegacyAnimationDirector] Unknown logicalId: " + logicalId);
            return false;
        }

        /// <summary>不经过 registry，直接用 Animation 上的 clip 名播放。</summary>
        public bool PlayByClipName(string clipName, WrapMode wrapMode)
        {
            return PlayByClipName(clipName, wrapMode, 0.08f);
        }

        /// <summary>不经过 registry，直接使用 clip 名并指定过渡时间。</summary>
        public bool PlayByClipName(string clipName, WrapMode wrapMode, float crossFadeSeconds)
        {
            LastRequestedLogicalId = clipName ?? string.Empty;
            return PlayClipInternal(clipName, wrapMode, crossFadeSeconds, clipName);
        }

        private bool PlayClipInternal(string clipName, WrapMode wrapMode, float crossFadeSeconds, string logicalLabel)
        {
            if (targetAnimation == null || string.IsNullOrEmpty(clipName))
            {
                Raise(logicalLabel, clipName ?? "", false);
                return false;
            }

            var state = targetAnimation[clipName];
            if (state == null)
            {
                Debug.LogWarning("[XiongdaLegacyAnimationDirector] No AnimationState for clip: " + clipName);
                Raise(logicalLabel, clipName, false);
                return false;
            }

            state.wrapMode = wrapMode;
            targetAnimation.wrapMode = wrapMode;
            targetAnimation.clip = state.clip;
            targetAnimation.CrossFade(clipName, Mathf.Clamp(crossFadeSeconds, 0.01f, 2f));
            LastPlayedClipName = clipName;
            Raise(logicalLabel, clipName, true);
            return true;
        }

        private void Raise(string logicalId, string clipName, bool ok)
        {
            if (OnActionInvoked != null)
            {
                OnActionInvoked(logicalId, clipName, ok);
            }
        }
    }
}
