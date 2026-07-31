using UnityEngine;
using UnityEngine.EventSystems;

namespace SmartParkTerminal
{
    /// <summary>
    /// 嵌入 **React 网页** 的 WebGL 时：全屏 UGUI（一键生成的大屏）不需要，本组件在 Awake 关闭
    /// ScreenSpace 的 <see cref="Canvas"/> 与 <see cref="EventSystem"/>，只留 3D/熊大与 <see cref="ClipIdPlayer"/> 动作。
    /// 字幕由网页显示即可（ClipIdPlayer 的 subtitle 为可选，可不绑）。
    /// </summary>
    [DisallowMultipleComponent]
    [DefaultExecutionOrder(-100)]
    public sealed class ReactEmbedModeBootstrap : MonoBehaviour
    {
        [Tooltip("勾选：打包/运行 WebGL 时自动关闭本场景里所有「全屏叠加」型 Canvas 与 EventSystem。")]
        [SerializeField] private bool disableScreenSpaceUiOnAwake = true;

        [Tooltip("若为真，会尝试关闭名为 SmartTerminalRoot/Canvas 下的整棵 UI（不依赖上项 Canvas 模式枚举）。")]
        [SerializeField] private bool alsoDeactivateByName = true;

        private void Awake()
        {
            if (!disableScreenSpaceUiOnAwake) return;

            if (alsoDeactivateByName)
            {
                var tr = GameObject.Find("SmartTerminalRoot")?.transform;
                if (tr != null)
                {
                    var t = tr.Find("Canvas");
                    if (t != null) t.gameObject.SetActive(false);
                    t = tr.Find("EventSystem");
                    if (t != null) t.gameObject.SetActive(false);
                }
            }

            // 兜底：关掉所有全屏/摄像机空间 UI
            var canvases = FindObjectsOfType<Canvas>();
            for (int i = 0; i < canvases.Length; i++)
            {
                var c = canvases[i];
                if (c == null) continue;
                if (c.renderMode == RenderMode.WorldSpace) continue;
                c.gameObject.SetActive(false);
            }

            var es = FindObjectOfType<EventSystem>();
            if (es != null) es.gameObject.SetActive(false);
        }
    }
}
