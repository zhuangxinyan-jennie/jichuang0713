using TMPro;
using UnityEngine;

namespace SmartParkTerminal
{
    /// <summary>
    /// 解决中文显示为「方框」：使用 Font Asset Creator 从中文字体生成 SDF 资源后拖到本组件。
    /// </summary>
    public sealed class SmartParkTerminalChineseFont : MonoBehaviour
    {
        [SerializeField]
        [Tooltip("由 Window → TextMeshPro → Font Asset Creator 从 .ttf 生成（需包含项目中用到的汉字）")]
        private TMP_FontAsset chineseFontAsset;

        [SerializeField]
        [Tooltip("为 true 时只处理本物体子节点下的 TMP（略省性能）")]
        private bool onlyChildren = false;

        private void Start()
        {
            ApplyFont();
        }

        /// <summary>可在编辑器改字体后运行时调用。</summary>
        [ContextMenu("Apply Chinese Font Now")]
        public void ApplyFont()
        {
            if (chineseFontAsset == null)
            {
                Debug.LogWarning("[SmartParkTerminalChineseFont] 未指定 chineseFontAsset，中文仍会显示为方框。请生成 TMP 字体资源并拖到此处。");
                return;
            }

            TextMeshProUGUI[] texts = onlyChildren
                ? GetComponentsInChildren<TextMeshProUGUI>(true)
                : FindObjectsOfType<TextMeshProUGUI>();

            foreach (TextMeshProUGUI t in texts)
            {
                if (t != null)
                {
                    t.font = chineseFontAsset;
                }
            }

            Debug.Log("[SmartParkTerminalChineseFont] 已替换 TMP 字体数量: " + texts.Length);
        }
    }
}
