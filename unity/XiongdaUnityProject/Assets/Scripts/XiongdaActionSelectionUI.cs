using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;

namespace XiongdaImporter
{
    /// <summary>
    /// 根据 Director 注册表自动生成按钮：优先使用 SMPL（XiongdaSmplhMotionDirector）；否则使用 Legacy Animation Director。
    /// </summary>
    [DisallowMultipleComponent]
    public sealed class XiongdaActionSelectionUI : MonoBehaviour
    {
        [SerializeField]
        private XiongdaLegacyAnimationDirector director;

        [SerializeField]
        private XiongdaSmplhMotionDirector smplDirector;

        [SerializeField]
        [Tooltip("为 true 时在 Awake 根据 registry 动态创建按钮")]
        private bool autoBuildButtonsFromRegistry = true;

        [SerializeField]
        [Tooltip("自动创建 UI 时使用的 Canvas；为空则自动创建带 CanvasScaler 的 Canvas")]
        private Canvas targetCanvas;

        [SerializeField]
        private Vector2 panelAnchorMin = new Vector2(0.02f, 0.65f);

        [SerializeField]
        private Vector2 panelAnchorMax = new Vector2(0.35f, 0.98f);

        [SerializeField]
        private int buttonFontSize = 22;

        private readonly List<Button> spawnedButtons = new List<Button>();

        private void Awake()
        {
            if (smplDirector == null && director == null)
            {
                smplDirector = FindObjectOfType<XiongdaSmplhMotionDirector>();
                if (smplDirector == null)
                {
                    director = FindObjectOfType<XiongdaLegacyAnimationDirector>();
                }
            }

            if (smplDirector == null && director == null)
            {
                Debug.LogWarning("[XiongdaActionSelectionUI] 需要至少挂一个：XiongdaSmplhMotionDirector 或 XiongdaLegacyAnimationDirector（可在 Inspector 指定，或放一个在场景里）。");
                return;
            }

            if (autoBuildButtonsFromRegistry)
            {
                if (smplDirector != null)
                {
                    BuildSmplButtons();
                }
                else
                {
                    BuildButtons();
                }
            }
        }

        /// <summary>可在 Inspector 里绑到自定义按钮 OnClick：传入 logicalId。</summary>
        public void UiPlayByLogicalId(string logicalId)
        {
            if (smplDirector != null)
            {
                smplDirector.PlayByLogicalId(logicalId);
            }
            else if (director != null)
            {
                director.PlayByLogicalId(logicalId);
            }
        }

        /// <summary>显式走 SMPL Registry（若同时挂了 Legacy / SMPL，用此方法区分）。</summary>
        public void UiPlaySmplByLogicalId(string logicalId)
        {
            if (smplDirector != null)
            {
                smplDirector.PlayByLogicalId(logicalId);
            }
        }

        /// <summary>相对 StreamingAssets 的路径，例如 SmplhRetarget/foo.json。</summary>
        public void UiPlaySmplByRelativePath(string streamingRelativePath)
        {
            if (smplDirector != null)
            {
                smplDirector.PlayByStreamingRelativePath(streamingRelativePath, null);
            }
        }

        /// <summary>可在 Inspector 里绑到自定义按钮：传入 Animation clip 名。</summary>
        public void UiPlayClipLoop(string clipName)
        {
            if (director != null)
            {
                director.PlayByClipName(clipName, WrapMode.Loop);
            }
        }

        /// <summary>可在 Inspector 里绑到自定义按钮：传入 Animation clip 名，单次播放。</summary>
        public void UiPlayClipOnce(string clipName)
        {
            if (director != null)
            {
                director.PlayByClipName(clipName, WrapMode.Once);
            }
        }

        private void BuildButtons()
        {
            ClearSpawned();

            var canvas = EnsureCanvas();
            var panel = new GameObject("ActionButtonPanel", typeof(RectTransform), typeof(Image), typeof(VerticalLayoutGroup));
            panel.transform.SetParent(canvas.transform, false);
            var rt = panel.GetComponent<RectTransform>();
            rt.anchorMin = panelAnchorMin;
            rt.anchorMax = panelAnchorMax;
            rt.offsetMin = Vector2.zero;
            rt.offsetMax = Vector2.zero;
            var bg = panel.GetComponent<Image>();
            bg.color = new Color(0f, 0f, 0f, 0.35f);
            var vlg = panel.GetComponent<VerticalLayoutGroup>();
            vlg.spacing = 6f;
            vlg.childAlignment = TextAnchor.UpperCenter;
            vlg.childControlHeight = true;
            vlg.childControlWidth = true;
            vlg.childForceExpandHeight = false;
            vlg.childForceExpandWidth = true;

            var registry = director.GetRegistryArray();
            if (registry == null)
            {
                return;
            }

            foreach (var slot in registry)
            {
                if (slot == null || string.IsNullOrEmpty(slot.logicalId))
                {
                    continue;
                }

                var btnGo = new GameObject("Btn_" + slot.logicalId, typeof(RectTransform), typeof(Image), typeof(Button));
                btnGo.transform.SetParent(panel.transform, false);
                var img = btnGo.GetComponent<Image>();
                img.color = new Color(0.2f, 0.45f, 0.85f, 0.92f);
                var btn = btnGo.GetComponent<Button>();
                var labelGo = new GameObject("Label", typeof(RectTransform), typeof(Text));
                labelGo.transform.SetParent(btnGo.transform, false);
                var text = labelGo.GetComponent<Text>();
                text.font = Resources.GetBuiltinResource<Font>("Arial.ttf");
                text.resizeTextForBestFit = false;
                text.fontSize = buttonFontSize;
                text.alignment = TextAnchor.MiddleCenter;
                text.color = Color.white;
                text.text = slot.logicalId + "  →  " + slot.clipName;

                var lid = slot.logicalId;
                btn.onClick.AddListener(() =>
                {
                    if (director != null)
                    {
                        director.PlayByLogicalId(lid);
                    }
                });

                spawnedButtons.Add(btn);
            }
        }

        private void BuildSmplButtons()
        {
            ClearSpawned();

            var canvas = EnsureCanvas();
            var panel = new GameObject("SmplActionButtonPanel", typeof(RectTransform), typeof(Image), typeof(VerticalLayoutGroup));
            panel.transform.SetParent(canvas.transform, false);
            var rt = panel.GetComponent<RectTransform>();
            rt.anchorMin = panelAnchorMin;
            rt.anchorMax = panelAnchorMax;
            rt.offsetMin = Vector2.zero;
            rt.offsetMax = Vector2.zero;
            var bg = panel.GetComponent<Image>();
            bg.color = new Color(0f, 0f, 0f, 0.35f);
            var vlg = panel.GetComponent<VerticalLayoutGroup>();
            vlg.spacing = 6f;
            vlg.childAlignment = TextAnchor.UpperCenter;
            vlg.childControlHeight = true;
            vlg.childControlWidth = true;
            vlg.childForceExpandHeight = false;
            vlg.childForceExpandWidth = true;

            var registry = smplDirector.GetRegistryArray();
            if (registry == null)
            {
                return;
            }

            foreach (var slot in registry)
            {
                if (slot == null || string.IsNullOrEmpty(slot.logicalId))
                {
                    continue;
                }

                var btnGo = new GameObject("BtnSMPL_" + slot.logicalId, typeof(RectTransform), typeof(Image), typeof(Button));
                btnGo.transform.SetParent(panel.transform, false);
                var img = btnGo.GetComponent<Image>();
                img.color = new Color(0.15f, 0.55f, 0.35f, 0.92f);
                var btn = btnGo.GetComponent<Button>();
                var labelGo = new GameObject("Label", typeof(RectTransform), typeof(Text));
                labelGo.transform.SetParent(btnGo.transform, false);
                var text = labelGo.GetComponent<Text>();
                text.font = Resources.GetBuiltinResource<Font>("Arial.ttf");
                text.resizeTextForBestFit = false;
                text.fontSize = buttonFontSize;
                text.alignment = TextAnchor.MiddleCenter;
                text.color = Color.white;
                text.text = slot.logicalId + "  →  " + slot.streamingRelativePath;

                var lid = slot.logicalId;
                btn.onClick.AddListener(() =>
                {
                    if (smplDirector != null)
                    {
                        smplDirector.PlayByLogicalId(lid);
                    }
                });

                spawnedButtons.Add(btn);
            }
        }

        private void ClearSpawned()
        {
            foreach (var b in spawnedButtons)
            {
                if (b != null)
                {
                    Destroy(b.gameObject);
                }
            }

            spawnedButtons.Clear();
        }

        private Canvas EnsureCanvas()
        {
            if (targetCanvas != null)
            {
                return targetCanvas;
            }

            var existing = FindObjectOfType<Canvas>();
            if (existing != null && existing.gameObject.activeInHierarchy)
            {
                targetCanvas = existing;
                return existing;
            }

            var canvasGo = new GameObject("XiongdaActionCanvas", typeof(Canvas), typeof(CanvasScaler), typeof(GraphicRaycaster));
            targetCanvas = canvasGo.GetComponent<Canvas>();
            targetCanvas.renderMode = RenderMode.ScreenSpaceOverlay;
            var scaler = canvasGo.GetComponent<CanvasScaler>();
            scaler.uiScaleMode = CanvasScaler.ScaleMode.ScaleWithScreenSize;
            scaler.referenceResolution = new Vector2(1920f, 1080f);
            return targetCanvas;
        }
    }
}
