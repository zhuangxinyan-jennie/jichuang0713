using System.IO;
using SmartParkTerminal;
using TMPro;
using UnityEditor;
using UnityEditor.Animations;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.Rendering;
using UnityEngine.UI;

namespace SmartParkTerminal.EditorTools
{
    /// <summary>
    /// 一键生成 SmartParkTerminal 场景 + Animator Controller（菜单执行一次即可）。
    /// </summary>
    public static class SmartParkTerminalSceneBuilder
    {
        private const string ScenePath = "Assets/Scenes/SmartParkTerminal.unity";
        private const string ControllerPath = "Assets/SmartParkTerminal/Generated/SmartTerminalBear.controller";
        private const string StageFloorMaterialPath = "Assets/StylizedNatureBundle/BackgroundPlate/StageFloorGrassTint.mat";

        private static readonly Color32 DarkGreen = new Color32(27, 67, 50, 255);
        private static readonly Color32 PanelGreen = new Color32(45, 106, 79, 245);
        private static readonly Color32 AccentOrange = new Color32(255, 159, 28, 255);
        private static readonly Color32 LightMint = new Color32(149, 213, 178, 255);

        /// <summary>
        /// 棚拍式均匀光：Flat 环境光 + Directional 平行光（全身同向受光）+ 低反射。
        /// </summary>
        private static void ApplyEvenCharacterLighting()
        {
            RenderSettings.ambientMode = AmbientMode.Flat;
            RenderSettings.ambientSkyColor = new Color(0.68f, 0.70f, 0.66f);
            RenderSettings.ambientIntensity = 1.92f;
            RenderSettings.reflectionIntensity = 0.09f;
        }

        [MenuItem("Tools/狗熊岭智慧终端/生成 SmartParkTerminal 场景（一键）", false, 10)]
        public static void BuildSceneMenu()
        {
            EnsureFolder("Assets/SmartParkTerminal");
            EnsureFolder("Assets/SmartParkTerminal/Generated");
            EnsureFolder("Assets/Scenes");

            BuildAnimatorController();

            var scene = EditorSceneManager.NewScene(NewSceneSetup.DefaultGameObjects, NewSceneMode.Single);
            GameObject.DestroyImmediate(GameObject.Find("Main Camera"));

            var root = new GameObject("SmartTerminalRoot");
            // React 网页嵌入 WebGL：运行时自动关闭大屏 UGUI，仅保留 3D 熊与 ClipIdPlayer
            root.AddComponent<ReactEmbedModeBootstrap>();

            var env = new GameObject("Environment");
            env.transform.SetParent(root.transform, false);

            var camGo = new GameObject("Main Camera");
            camGo.tag = "MainCamera";
            camGo.transform.SetParent(env.transform, false);
            // 熊大模型通常单位较大：相机略远、略抬高 + 较宽 FOV，嵌入网页时尽量头肩齐全入镜
            camGo.transform.position = new Vector3(0f, 2.15f, -11f);
            camGo.transform.rotation = Quaternion.Euler(8f, 0f, 0f);
            var cam = camGo.AddComponent<Camera>();
            cam.clearFlags = CameraClearFlags.Skybox;
            cam.fieldOfView = 54f;
            cam.backgroundColor = new Color(0.26f, 0.38f, 0.28f, 0f);
            cam.allowHDR = false;

            var lightGo = new GameObject("Directional Light");
            lightGo.transform.SetParent(env.transform, false);
            lightGo.transform.localPosition = Vector3.zero;
            lightGo.transform.localScale = Vector3.one;
            // 平行光：位置无关，勿改异常坐标；略偏顶光 + 侧向，便于全身均匀提亮
            lightGo.transform.rotation = Quaternion.Euler(48f, 118f, 0f);
            var light = lightGo.AddComponent<Light>();
            light.type = LightType.Directional;
            light.intensity = 0.52f;
            light.color = new Color(0.96f, 0.94f, 0.90f);
            light.bounceIntensity = 0.62f;

            var stage = GameObject.CreatePrimitive(PrimitiveType.Plane);
            stage.name = "StageFloor";
            stage.transform.SetParent(env.transform, false);
            stage.transform.localScale = new Vector3(1.2f, 1f, 1f);
            stage.transform.position = new Vector3(-1.5f, 0f, 0f);
            Object.DestroyImmediate(stage.GetComponent<Collider>());
            var stageMat = AssetDatabase.LoadAssetAtPath<Material>(StageFloorMaterialPath);
            if (stageMat != null)
                stage.GetComponent<MeshRenderer>().sharedMaterial = stageMat;
            // 默认隐藏：仅 2D 背景图时脚下台面容易抢眼；需要演示地面时再在 Hierarchy 里勾选
            stage.SetActive(false);

            var charArea = new GameObject("CharacterArea");
            charArea.transform.SetParent(root.transform, false);

            var placeholder = GameObject.CreatePrimitive(PrimitiveType.Capsule);
            placeholder.name = "BearPlaceholder_AssignYourModelHere";
            placeholder.transform.SetParent(charArea.transform, false);
            placeholder.transform.position = new Vector3(-2.2f, 1f, 0f);
            placeholder.transform.localScale = new Vector3(1f, 1f, 1f);
            var anim = placeholder.AddComponent<Animator>();
            anim.runtimeAnimatorController = AssetDatabase.LoadAssetAtPath<RuntimeAnimatorController>(ControllerPath);

            var canvasGo = new GameObject("Canvas");
            canvasGo.transform.SetParent(root.transform, false);
            var canvas = canvasGo.AddComponent<Canvas>();
            canvas.renderMode = RenderMode.ScreenSpaceOverlay;
            var scaler = canvasGo.AddComponent<CanvasScaler>();
            scaler.uiScaleMode = CanvasScaler.ScaleMode.ScaleWithScreenSize;
            scaler.referenceResolution = new Vector2(1920f, 1080f);
            scaler.matchWidthOrHeight = 0.5f;
            canvasGo.AddComponent<GraphicRaycaster>();
            canvasGo.AddComponent<SmartParkTerminalChineseFont>();

            var es = new GameObject("EventSystem");
            es.transform.SetParent(root.transform, false);
            es.AddComponent<EventSystem>();
            es.AddComponent<StandaloneInputModule>();

            var header = CreatePanel(canvas.transform, "Header", new Vector2(0f, 1f), new Vector2(1f, 1f), new Vector2(0f, -40f), new Vector2(0f, -40f), DarkGreen);
            var titleTmp = CreateTmp(header.transform, "TitleText", "狗熊岭智慧乐园互动终端", 34, Color.white, TextAlignmentOptions.Center);
            StretchFull(titleTmp.rectTransform);
            titleTmp.fontStyle = FontStyles.Bold;

            const float headerH = 80f;
            const float navH = 56f;
            const float subtitleH = 96f;
            float topInset = headerH + navH;

            var navStrip = CreatePanel(canvas.transform, "NavStrip", new Vector2(0f, 1f), new Vector2(1f, 1f), new Vector2(12f, -topInset), new Vector2(-12f, -headerH), new Color32(0, 0, 0, 55));
            var navHlg = navStrip.AddComponent<HorizontalLayoutGroup>();
            navHlg.padding = new RectOffset(8, 8, 6, 6);
            navHlg.spacing = 10;
            navHlg.childAlignment = TextAnchor.MiddleCenter;
            navHlg.childControlWidth = true;
            navHlg.childForceExpandWidth = true;
            AddNavStripButton(navStrip.transform, "BtnPageCharacter", "互动页");
            AddNavStripButton(navStrip.transform, "BtnPageMap", "地图");
            AddNavStripButton(navStrip.transform, "BtnPageRecommend", "推荐");
            AddNavStripButton(navStrip.transform, "BtnPageSystem", "状态");

            var kernel = new GameObject("TerminalSystems");
            kernel.transform.SetParent(root.transform, false);
            var pageMgr = kernel.AddComponent<PageManager>();
            var clipPlayer = kernel.AddComponent<ClipIdPlayer>();
            var subtitle = kernel.AddComponent<SubtitleController>();
            var debugCtl = kernel.AddComponent<DebugPanelController>();
            var mapCtl = kernel.AddComponent<MapUIController>();
            var recCtl = kernel.AddComponent<RecommendationUIController>();
            var terminal = kernel.AddComponent<SmartTerminalController>();
            var demoUi = kernel.AddComponent<DemoUIController>();

            clipPlayer.animator = anim;

            var unityBridgeGo = new GameObject("UnityBridge");
            unityBridgeGo.transform.SetParent(root.transform, false);
            var unityBridge = unityBridgeGo.AddComponent<UnityBridge>();
            unityBridge.clipIdPlayer = clipPlayer;

            var mainSplit = CreatePanel(canvas.transform, "MainSplit", Vector2.zero, Vector2.one, new Vector2(0f, subtitleH), new Vector2(0f, -topInset), new Color32(0, 0, 0, 0));
            mainSplit.GetComponent<Image>().raycastTarget = false;

            var leftPad = CreatePanel(mainSplit.transform, "CharacterPanel", new Vector2(0f, 0f), new Vector2(0.48f, 1f), Vector2.zero, Vector2.zero, new Color32(0, 0, 0, 0));
            leftPad.GetComponent<Image>().raycastTarget = false;

            var rightPanel = CreatePanel(mainSplit.transform, "RightFunctionPanel", new Vector2(0.48f, 0f), Vector2.one, Vector2.zero, Vector2.zero, PanelGreen);

            var scrollGo = new GameObject("CharacterButtonsScroll");
            scrollGo.transform.SetParent(rightPanel.transform, false);
            var scrollRect = scrollGo.AddComponent<ScrollRect>();
            var scrollImg = scrollGo.AddComponent<Image>();
            scrollImg.color = new Color32(0, 0, 0, 35);
            var scrollRt = scrollGo.GetComponent<RectTransform>();
            scrollRt.anchorMin = new Vector2(0f, 0f);
            scrollRt.anchorMax = new Vector2(1f, 1f);
            scrollRt.offsetMin = new Vector2(12f, 12f);
            scrollRt.offsetMax = new Vector2(-12f, -12f);

            var viewport = CreatePanel(scrollGo.transform, "Viewport", Vector2.zero, Vector2.one, Vector2.zero, Vector2.zero, new Color32(0, 0, 0, 0));
            viewport.AddComponent<Mask>().showMaskGraphic = false;
            viewport.GetComponent<Image>().color = new Color32(255, 255, 255, 8);

            var content = new GameObject("CharacterButtonsRoot");
            content.transform.SetParent(viewport.transform, false);
            var contentRt = content.AddComponent<RectTransform>();
            StretchFull(contentRt);
            var vlg = content.AddComponent<VerticalLayoutGroup>();
            vlg.spacing = 10f;
            vlg.padding = new RectOffset(8, 8, 8, 8);
            vlg.childAlignment = TextAnchor.UpperCenter;
            vlg.childControlHeight = true;
            vlg.childForceExpandHeight = false;
            content.AddComponent<ContentSizeFitter>().verticalFit = ContentSizeFitter.FitMode.PreferredSize;

            scrollRect.viewport = viewport.GetComponent<RectTransform>();
            scrollRect.content = contentRt;
            scrollRect.horizontal = false;
            scrollRect.vertical = true;

            AddDemoButton(content.transform, "BtnIdle", "待机");
            AddDemoButton(content.transform, "BtnWave", "挥手");
            AddDemoButton(content.transform, "BtnLaugh", "大笑");
            AddDemoButton(content.transform, "BtnNod", "点头");
            AddDemoButton(content.transform, "BtnRandom", "随机互动（双层动作）");
            AddDemoButton(content.transform, "BtnModeSelect", "玩法选择开场");
            AddDemoButton(content.transform, "BtnStoryWake", "剧情：叫醒熊二");
            AddDemoButton(content.transform, "BtnHoney", "蜂蜜骗醒");
            AddDemoButton(content.transform, "BtnCheerYes", "鼓掌加油：要");
            AddDemoButton(content.transform, "BtnCheerNo", "鼓掌加油：不要");
            AddDemoButton(content.transform, "BtnDream", "做梦惊醒");
            AddDemoButton(content.transform, "BtnFightYes", "赶跑光头强：要");
            AddDemoButton(content.transform, "BtnFightNo", "赶跑光头强：不要");
            AddDemoButton(content.transform, "BtnFinale", "剧情结尾");
            AddDemoButton(content.transform, "BtnStoryYesBranch", "模拟连续剧情（YES）");
            AddDemoButton(content.transform, "BtnStoryNoBranch", "模拟连续剧情（NO）");

            var mapPage = CreatePanel(canvas.transform, "MapPage", Vector2.zero, Vector2.one, new Vector2(0f, subtitleH), new Vector2(0f, -topInset), new Color32(20, 50, 40, 240));
            mapPage.SetActive(false);
            var mapTitle = CreateTmp(mapPage.transform, "MapTitle", "地图查询", 28, Color.white, TextAlignmentOptions.TopLeft);
            mapTitle.rectTransform.anchorMin = new Vector2(0f, 1f);
            mapTitle.rectTransform.anchorMax = new Vector2(1f, 1f);
            mapTitle.rectTransform.pivot = new Vector2(0.5f, 1f);
            mapTitle.rectTransform.anchoredPosition = new Vector2(0f, -16f);
            mapTitle.rectTransform.sizeDelta = new Vector2(-40f, 48f);

            var mapImgHolder = CreatePanel(mapPage.transform, "MapImageHolder", new Vector2(0.05f, 0.18f), new Vector2(0.95f, 0.88f), Vector2.zero, Vector2.zero, new Color32(255, 255, 255, 28));
            var mapImg = mapImgHolder.GetComponent<Image>();
            mapImg.sprite = AssetDatabase.GetBuiltinExtraResource<Sprite>("UI/Skin/UISprite.psd");
            mapImg.type = Image.Type.Sliced;

            var poiRoot = new GameObject("PoiHighlightRoot");
            poiRoot.transform.SetParent(mapImgHolder.transform, false);
            var poiRt = poiRoot.AddComponent<RectTransform>();
            StretchFull(poiRt);
            CreatePoiDot(poiRoot.transform, "carousel", new Vector2(0.72f, 0.55f));
            CreatePoiDot(poiRoot.transform, "roller_coaster", new Vector2(0.55f, 0.72f));
            CreatePoiDot(poiRoot.transform, "food_area", new Vector2(0.45f, 0.42f));
            CreatePoiDot(poiRoot.transform, "restroom", new Vector2(0.28f, 0.48f));
            CreatePoiDot(poiRoot.transform, "exit", new Vector2(0.15f, 0.22f));
            CreatePoiDot(poiRoot.transform, "xiongda_zone", new Vector2(0.62f, 0.35f));

            var mapInfo = CreateTmp(mapPage.transform, "MapInfoText", "请选择 POI", 22, LightMint, TextAlignmentOptions.BottomLeft);
            mapInfo.rectTransform.anchorMin = new Vector2(0.05f, 0.05f);
            mapInfo.rectTransform.anchorMax = new Vector2(0.95f, 0.16f);
            mapInfo.rectTransform.offsetMin = Vector2.zero;
            mapInfo.rectTransform.offsetMax = Vector2.zero;

            var mapBtnPanel = CreatePanel(mapPage.transform, "MapButtons", new Vector2(0.05f, 0.62f), new Vector2(0.95f, 0.95f), Vector2.zero, Vector2.zero, new Color32(0, 0, 0, 40));
            var mapV = mapBtnPanel.AddComponent<VerticalLayoutGroup>();
            mapV.spacing = 8f;
            mapV.childAlignment = TextAnchor.UpperLeft;
            mapV.childControlHeight = true;
            mapV.childForceExpandHeight = false;
            AddDemoButton(mapBtnPanel.transform, "BtnMapCarousel", "旋转木马");
            AddDemoButton(mapBtnPanel.transform, "BtnMapCoaster", "过山车");
            AddDemoButton(mapBtnPanel.transform, "BtnMapFood", "餐饮区");
            AddDemoButton(mapBtnPanel.transform, "BtnMapRestroom", "卫生间");
            AddDemoButton(mapBtnPanel.transform, "BtnMapExit", "出口");
            AddDemoButton(mapBtnPanel.transform, "BtnMapXiongda", "熊大互动区");

            var recPage = CreatePanel(canvas.transform, "RecommendationPage", Vector2.zero, Vector2.one, new Vector2(0f, subtitleH), new Vector2(0f, -topInset), new Color32(25, 70, 52, 245));
            recPage.SetActive(false);
            var recTitle = CreateTmp(recPage.transform, "RecTitle", "项目推荐", 28, Color.white, TextAlignmentOptions.Top);
            recTitle.rectTransform.anchorMin = new Vector2(0f, 1f);
            recTitle.rectTransform.anchorMax = new Vector2(1f, 1f);
            recTitle.rectTransform.pivot = new Vector2(0.5f, 1f);
            recTitle.rectTransform.anchoredPosition = new Vector2(0f, -12f);
            recTitle.rectTransform.sizeDelta = new Vector2(-40f, 44f);

            var detail = CreatePanel(recPage.transform, "DetailPanel", new Vector2(0.05f, 0.52f), new Vector2(0.95f, 0.9f), Vector2.zero, Vector2.zero, new Color32(0, 0, 0, 50));
            var dt = CreateTmp(detail.transform, "TitleText", "", 26, Color.white, TextAlignmentOptions.TopLeft);
            StretchFull(dt.rectTransform);
            dt.rectTransform.offsetMin = new Vector2(16f, 80f);
            var dr = CreateTmp(detail.transform, "ReasonText", "", 20, LightMint, TextAlignmentOptions.TopLeft);
            dr.rectTransform.anchorMin = new Vector2(0f, 0.35f);
            dr.rectTransform.anchorMax = new Vector2(1f, 0.85f);
            dr.rectTransform.offsetMin = new Vector2(16f, 0f);
            dr.rectTransform.offsetMax = new Vector2(-16f, 0f);
            var dq = CreateTmp(detail.transform, "QueueTimeText", "", 20, AccentOrange, TextAlignmentOptions.BottomLeft);
            dq.rectTransform.anchorMin = new Vector2(0f, 0.15f);
            dq.rectTransform.anchorMax = new Vector2(1f, 0.32f);
            dq.rectTransform.offsetMin = new Vector2(16f, 0f);
            dq.rectTransform.offsetMax = new Vector2(-16f, 0f);
            var dg = CreateTmp(detail.transform, "TargetGroupText", "", 18, Color.white, TextAlignmentOptions.BottomLeft);
            dg.rectTransform.anchorMin = new Vector2(0f, 0f);
            dg.rectTransform.anchorMax = new Vector2(1f, 0.14f);
            dg.rectTransform.offsetMin = new Vector2(16f, 8f);
            dg.rectTransform.offsetMax = new Vector2(-16f, 0f);

            var cards = CreatePanel(recPage.transform, "CardsRow", new Vector2(0.05f, 0.08f), new Vector2(0.95f, 0.46f), Vector2.zero, Vector2.zero, new Color32(0, 0, 0, 0));
            var hlg = cards.AddComponent<HorizontalLayoutGroup>();
            hlg.spacing = 16f;
            hlg.childAlignment = TextAnchor.MiddleCenter;
            hlg.childForceExpandWidth = true;
            hlg.childForceExpandHeight = true;
            var btnCar = CreateCardButton(cards.transform, "BtnRecCarousel", "旋转木马", "亲子互动");
            var btnTrain = CreateCardButton(cards.transform, "BtnRecTrain", "森林小火车", "轻松休息");
            var btnRoc = CreateCardButton(cards.transform, "BtnRecCoaster", "过山车", "刺激体验");

            var sysPage = CreatePanel(canvas.transform, "SystemPage", Vector2.zero, Vector2.one, new Vector2(0f, subtitleH), new Vector2(0f, -topInset), new Color32(15, 40, 30, 250));
            sysPage.SetActive(false);
            var sysTmp = CreateTmp(sysPage.transform, "SystemHelp", "系统状态页：连接 310B 后将显示 IP / ASR / 识别结果等。\n当前为本地模拟。", 22, LightMint, TextAlignmentOptions.TopLeft);
            sysTmp.rectTransform.anchorMin = new Vector2(0.06f, 0.35f);
            sysTmp.rectTransform.anchorMax = new Vector2(0.94f, 0.92f);
            sysTmp.rectTransform.offsetMin = Vector2.zero;
            sysTmp.rectTransform.offsetMax = Vector2.zero;

            var subtitleBar = CreatePanel(canvas.transform, "SubtitleBar", new Vector2(0f, 0f), new Vector2(1f, 0f), new Vector2(0f, 0f), new Vector2(0f, 96f), new Color32(0, 0, 0, 170));
            var subTmp = CreateTmp(subtitleBar.transform, "SubtitleText", "", 24, Color.white, TextAlignmentOptions.MidlineLeft);
            subTmp.rectTransform.anchorMin = new Vector2(0.02f, 0.1f);
            subTmp.rectTransform.anchorMax = new Vector2(0.72f, 0.9f);
            subTmp.rectTransform.offsetMin = Vector2.zero;
            subTmp.rectTransform.offsetMax = Vector2.zero;

            var debugPanel = CreatePanel(canvas.transform, "DebugPanel", new Vector2(1f, 0f), new Vector2(1f, 0f), new Vector2(-420f, 104f), new Vector2(-12f, 280f), new Color32(0, 0, 0, 120));
            var dbgTmp = CreateTmp(debugPanel.transform, "DebugText", "[调试]", 14, new Color32(200, 220, 210, 220), TextAlignmentOptions.TopLeft);
            StretchFull(dbgTmp.rectTransform);
            dbgTmp.rectTransform.offsetMin = new Vector2(8f, 8f);
            dbgTmp.rectTransform.offsetMax = new Vector2(-8f, -8f);

            recCtl.BindDetailTexts(dt, dr, dq, dg);
            recCtl.BindCardButtons(btnCar, btnTrain, btnRoc);

            subtitle.BindSubtitleText(subTmp);
            debugCtl.BindDebugText(dbgTmp);

            var soPage = new SerializedObject(pageMgr);
            soPage.FindProperty("characterPage").objectReferenceValue = mainSplit;
            soPage.FindProperty("mapPage").objectReferenceValue = mapPage;
            soPage.FindProperty("recommendationPage").objectReferenceValue = recPage;
            soPage.FindProperty("systemPage").objectReferenceValue = sysPage;
            soPage.ApplyModifiedPropertiesWithoutUndo();

            var soMap = new SerializedObject(mapCtl);
            soMap.FindProperty("mapRoot").objectReferenceValue = mapPage;
            soMap.FindProperty("poiHighlightRoot").objectReferenceValue = poiRoot.transform;
            soMap.FindProperty("mapInfoText").objectReferenceValue = mapInfo;
            soMap.ApplyModifiedPropertiesWithoutUndo();

            var soDemo = new SerializedObject(demoUi);
            soDemo.FindProperty("characterButtonsRoot").objectReferenceValue = content.transform;
            soDemo.FindProperty("navButtonsRoot").objectReferenceValue = navStrip.transform;
            soDemo.FindProperty("mapButtonsRoot").objectReferenceValue = mapBtnPanel.transform;
            soDemo.ApplyModifiedPropertiesWithoutUndo();

            var soTerm = new SerializedObject(terminal);
            soTerm.FindProperty("pageManager").objectReferenceValue = pageMgr;
            soTerm.FindProperty("clipPlayer").objectReferenceValue = clipPlayer;
            soTerm.FindProperty("subtitleController").objectReferenceValue = subtitle;
            soTerm.FindProperty("debugPanel").objectReferenceValue = debugCtl;
            soTerm.FindProperty("mapUi").objectReferenceValue = mapCtl;
            soTerm.FindProperty("recommendationUi").objectReferenceValue = recCtl;
            soTerm.FindProperty("demoUi").objectReferenceValue = demoUi;
            soTerm.ApplyModifiedPropertiesWithoutUndo();

            ApplyEvenCharacterLighting();

            EditorSceneManager.MarkSceneDirty(scene);
            EditorSceneManager.SaveScene(scene, ScenePath);
            AssetDatabase.Refresh();
            Debug.Log("[SmartParkTerminal] 已生成场景: " + ScenePath + "。SmartTerminalRoot 已挂 ReactEmbedModeBootstrap（运行/WebGL 时自动关大屏 UI）。已创建「UnityBridge」并绑定 ClipIdPlayer。若 TMP 字体粉色，请执行 Window > TextMeshPro > Import TMP Essential Resources。");
        }

        /// <summary>已在场景里摆好熊大时：勿整场景重生，用本菜单补挂嵌入组件即可。</summary>
        [MenuItem("Tools/狗熊岭智慧终端/当前场景：启用 React 嵌入模式（关闭大屏 UI）", false, 11)]
        public static void AddReactEmbedToActiveScene()
        {
            var root = GameObject.Find("SmartTerminalRoot");
            if (root == null)
            {
                EditorUtility.DisplayDialog(
                    "SmartParkTerminal",
                    "场景中找不到 SmartTerminalRoot。\n请先打开 SmartParkTerminal 场景，或使用菜单「生成 SmartParkTerminal 场景（一键）」。",
                    "确定");
                return;
            }

            if (root.GetComponent<ReactEmbedModeBootstrap>() != null)
            {
                EditorUtility.DisplayDialog("SmartParkTerminal", "SmartTerminalRoot 上已有 ReactEmbedModeBootstrap，无需重复添加。", "确定");
                return;
            }

            Undo.AddComponent<ReactEmbedModeBootstrap>(root);
            EditorSceneManager.MarkSceneDirty(EditorSceneManager.GetActiveScene());
            Debug.Log("[SmartParkTerminal] 已为 SmartTerminalRoot 添加 ReactEmbedModeBootstrap：Play/WebGL 时将自动关闭 Canvas 与 EventSystem。");
        }

        private static void BuildAnimatorController()
        {
            var existing = AssetDatabase.LoadAssetAtPath<AnimatorController>(ControllerPath);
            if (existing != null)
            {
                AssetDatabase.DeleteAsset(ControllerPath);
            }

            string[] states =
            {
                "StandIdleFriendly", "WaveRightHand", "Laugh", "Nod", "PointRight", "PointLeft", "TalkGestureSmall",
                "ModeSelectIntro", "StoryIntroWakeChoice", "StoryWakeYesHoneyTrick", "StoryWakeYesCheerYes",
                "StoryWakeYesCheerNo", "StoryWakeNoDreamWakeup", "StoryWakeNoFightYes", "StoryWakeNoFightNo",
                "StoryFinaleReturn"
            };

            var controller = AnimatorController.CreateAnimatorControllerAtPath(ControllerPath);
            AnimatorStateMachine sm = controller.layers[0].stateMachine;
            AnimatorState defaultState = null;
            foreach (string sn in states)
            {
                AnimatorState st = sm.AddState(sn);
                if (sn == "StandIdleFriendly")
                {
                    defaultState = st;
                }
            }

            if (defaultState != null)
            {
                sm.defaultState = defaultState;
            }

            AssetDatabase.SaveAssets();
        }

        private static void EnsureFolder(string path)
        {
            if (!AssetDatabase.IsValidFolder(path))
            {
                string parent = Path.GetDirectoryName(path)?.Replace("\\", "/");
                string leaf = Path.GetFileName(path);
                if (!string.IsNullOrEmpty(parent) && !AssetDatabase.IsValidFolder(parent))
                {
                    EnsureFolder(parent);
                }

                AssetDatabase.CreateFolder(parent ?? "Assets", leaf);
            }
        }

        private static GameObject CreatePanel(Transform parent, string name, Vector2 anchorMin, Vector2 anchorMax, Vector2 offsetMin, Vector2 offsetMax, Color32 color)
        {
            var go = new GameObject(name);
            go.transform.SetParent(parent, false);
            var rt = go.AddComponent<RectTransform>();
            rt.anchorMin = anchorMin;
            rt.anchorMax = anchorMax;
            rt.offsetMin = offsetMin;
            rt.offsetMax = offsetMax;
            var img = go.AddComponent<Image>();
            img.color = color;
            img.raycastTarget = color.a > 10;
            return go;
        }

        private static TextMeshProUGUI CreateTmp(Transform parent, string name, string text, float size, Color color, TextAlignmentOptions align)
        {
            var go = new GameObject(name);
            go.transform.SetParent(parent, false);
            var tmp = go.AddComponent<TextMeshProUGUI>();
            tmp.text = text;
            tmp.fontSize = size;
            tmp.color = color;
            tmp.alignment = align;
            tmp.enableWordWrapping = true;
            tmp.raycastTarget = false;
            return tmp;
        }

        private static void StretchFull(RectTransform rt)
        {
            rt.anchorMin = Vector2.zero;
            rt.anchorMax = Vector2.one;
            rt.offsetMin = Vector2.zero;
            rt.offsetMax = Vector2.zero;
        }

        private static void AddDemoButton(Transform parent, string name, string label)
        {
            var go = new GameObject(name);
            go.transform.SetParent(parent, false);
            var rt = go.AddComponent<RectTransform>();
            rt.sizeDelta = new Vector2(0f, 64f);
            var img = go.AddComponent<Image>();
            img.color = AccentOrange;
            img.sprite = AssetDatabase.GetBuiltinExtraResource<Sprite>("UI/Skin/UISprite.psd");
            img.type = Image.Type.Sliced;
            var btn = go.AddComponent<Button>();
            btn.targetGraphic = img;
            var le = go.AddComponent<LayoutElement>();
            le.minHeight = 64f;
            le.preferredHeight = 64f;

            var txtGo = new GameObject("Label");
            txtGo.transform.SetParent(go.transform, false);
            var tmp = txtGo.AddComponent<TextMeshProUGUI>();
            tmp.text = label;
            tmp.fontSize = 22f;
            tmp.color = DarkGreen;
            tmp.alignment = TextAlignmentOptions.Midline;
            StretchFull(tmp.rectTransform);
        }

        private static void AddNavStripButton(Transform parent, string name, string label)
        {
            var go = new GameObject(name);
            go.transform.SetParent(parent, false);
            go.AddComponent<RectTransform>();
            var img = go.AddComponent<Image>();
            img.color = LightMint;
            img.sprite = AssetDatabase.GetBuiltinExtraResource<Sprite>("UI/Skin/UISprite.psd");
            img.type = Image.Type.Sliced;
            go.AddComponent<Button>();
            var le = go.AddComponent<LayoutElement>();
            le.flexibleWidth = 1f;
            le.minHeight = 44f;
            le.preferredHeight = 44f;

            var txtGo = new GameObject("Label");
            txtGo.transform.SetParent(go.transform, false);
            var tmp = txtGo.AddComponent<TextMeshProUGUI>();
            tmp.text = label;
            tmp.fontSize = 22f;
            tmp.color = DarkGreen;
            tmp.alignment = TextAlignmentOptions.Midline;
            StretchFull(tmp.rectTransform);
        }

        private static void CreatePoiDot(Transform parent, string poiName, Vector2 anchorPos)
        {
            var go = new GameObject(poiName);
            go.transform.SetParent(parent, false);
            go.SetActive(false);
            var rt = go.AddComponent<RectTransform>();
            rt.anchorMin = anchorPos;
            rt.anchorMax = anchorPos;
            rt.pivot = new Vector2(0.5f, 0.5f);
            rt.sizeDelta = new Vector2(36f, 36f);
            var img = go.AddComponent<Image>();
            img.color = AccentOrange;
            img.sprite = AssetDatabase.GetBuiltinExtraResource<Sprite>("UI/Skin/Knob.psd");
        }

        private static Button CreateCardButton(Transform parent, string name, string title, string sub)
        {
            var go = new GameObject(name);
            go.transform.SetParent(parent, false);
            var rt = go.AddComponent<RectTransform>();
            var img = go.AddComponent<Image>();
            img.color = new Color32(240, 248, 243, 255);
            img.sprite = AssetDatabase.GetBuiltinExtraResource<Sprite>("UI/Skin/UISprite.psd");
            img.type = Image.Type.Sliced;
            var btn = go.AddComponent<Button>();
            var le = go.AddComponent<LayoutElement>();
            le.flexibleWidth = 1f;
            le.minHeight = 180f;

            var t1 = CreateTmp(go.transform, "T1", title, 22, DarkGreen, TextAlignmentOptions.Top);
            t1.rectTransform.anchorMin = new Vector2(0f, 0.55f);
            t1.rectTransform.anchorMax = new Vector2(1f, 0.95f);
            t1.rectTransform.offsetMin = new Vector2(8f, 0f);
            t1.rectTransform.offsetMax = new Vector2(-8f, 0f);
            var t2 = CreateTmp(go.transform, "T2", sub, 18, PanelGreen, TextAlignmentOptions.Top);
            t2.rectTransform.anchorMin = new Vector2(0f, 0.15f);
            t2.rectTransform.anchorMax = new Vector2(1f, 0.52f);
            t2.rectTransform.offsetMin = new Vector2(8f, 0f);
            t2.rectTransform.offsetMax = new Vector2(-8f, 0f);
            return btn;
        }
    }
}
