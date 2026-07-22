using System.IO;
using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEditor.SceneManagement;
using UnityEngine;
using XiongdaImporter;

namespace SmartParkTerminal.EditorTools
{
    /// <summary>
    /// 合并工程：同场景双熊（互动熊 SMPL+表情 / 导览熊 Run+导航）+ 单 WebGL 构建。
    /// </summary>
    public static class MergedProjectSetupMenu
    {
        private const string ScenePath = "Assets/Scenes/ParkMap3DBlockout.unity";
        private const string StagingBuildDir = @"C:\UnityWebGL\ParkMapMerged";
        private const string InteractiveModelPath =
            "Assets/XiongdaImported/xiongda_base_default/xiongda_maybe_final_new/xiongda_final_face/xiongda/xiongda.fbx";
        /** 导览熊 Prefab（地图 Legacy Run），保留勿删 */
        private const string GuideBearPrefabPath =
            "Assets/XiongdaImported/xiongda_base_default/Prefabs/熊大.prefab";
        /** 与合并场景聊天站位一致 */
        private const float InteractiveBearScale = 0.03f;
        private static readonly Vector3 ChatStandPosition = new Vector3(2.2f, 0.22f, -6.7f);
        private const float ChatStandYaw = 180f;

        [MenuItem("Tools/狗熊岭智慧终端/合并工程：挂上 UnityBridge + 模式相机")]
        public static void WireMergedBridges()
        {
            if (EditorApplication.isPlayingOrWillChangePlaymode)
            {
                EditorUtility.DisplayDialog(
                    "请先停止 Play",
                    "接线菜单只能在停止播放后使用。\n请先点 Stop，再点本菜单。\nPlay 时切换：C=聊天(互动熊) / M=地图(导览熊)",
                    "知道了");
                return;
            }

            if (!File.Exists(Path.Combine(Application.dataPath, "Scenes", "ParkMap3DBlockout.unity")))
            {
                Debug.LogWarning("[MergedSetup] 场景不存在: " + ScenePath);
                return;
            }

            var scene = EditorSceneManager.OpenScene(ScenePath, OpenSceneMode.Single);

            EnsureNamedBridge("ParkMapUnityBridge", typeof(ParkMapUnityBridge));
            var unityBridgeGo = EnsureNamedBridge("UnityBridge", typeof(UnityBridge));
            var modeBridgeGo = EnsureNamedBridge("MergedPlayModeBridge", typeof(MergedPlayModeBridge));

            var chatCamGo = EnsureChatCamera();

            DisableImportedLightsOnInteractiveModelAsset();

            // --- 导览熊（地图跑步 · 保留原 Prefab 熊大）---
            var guideBear = FindGuideBear();
            if (guideBear == null)
            {
                Debug.LogError("[MergedSetup] 找不到导览熊 PlayableXiongda / ParkMapBearController。" +
                               "请确认场景里仍有 " + GuideBearPrefabPath + " 实例。");
            }
            else
            {
                guideBear.name = MergedPlayModeBridge.GuideBearObjectName;
                StripSmplPipelineFromGuide(guideBear);
                EnsureGuideComponents(guideBear);
                Debug.Log("[MergedSetup] 已保留导览熊（Legacy Run）: " + guideBear.name);
            }

            // --- 互动熊（SMPL JSON + 表情 · xiongda.fbx）---
            var interactiveBear = EnsureInteractiveBear();
            if (interactiveBear == null)
            {
                Debug.LogError("[MergedSetup] 无法创建互动熊。请确认存在: " + InteractiveModelPath +
                               "\n可先运行 scripts/setup_merged_unity_project.ps1 从 XiongdaUnityProject 拷贝模型。");
            }
            else
            {
                interactiveBear.name = MergedPlayModeBridge.InteractiveBearObjectName;
                interactiveBear.transform.position = ChatStandPosition;
                interactiveBear.transform.rotation = Quaternion.Euler(0f, ChatStandYaw, 0f);
                StripMapComponentsFromInteractive(interactiveBear);
                StripImportedLightsFromHierarchy(interactiveBear);
                EnsureInteractiveSmplPipeline(interactiveBear);
                Debug.Log("[MergedSetup] 已配置互动熊: " + InteractiveModelPath);
            }

            ApplyDefaultDualBearVisibility(interactiveBear, guideBear);

            WireParkMapUnityBridge(guideBear);
            WireUnityBridge(unityBridgeGo, interactiveBear);
            WireModeBridge(modeBridgeGo, interactiveBear, guideBear, chatCamGo);

            EditorSceneManager.MarkSceneDirty(scene);
            EditorSceneManager.SaveScene(scene);

            EditorUtility.DisplayDialog(
                "合并工程接线完成",
                "双熊已接线并保存。\n\n" +
                "【互动熊 · 聊天】InteractiveXiongda\n" +
                "  xiongda_final_face/xiongda/xiongda.fbx\n" +
                "  JSON 动作 + 表情\n\n" +
                "【导览熊 · 地图】PlayableXiongda（已保留）\n" +
                "  Prefabs/熊大.prefab\n" +
                "  Legacy Run + 导航\n\n" +
                "Play 默认聊天；C=聊天 / M=地图。",
                "好的");
            Debug.Log("[MergedSetup] 双熊已接线。Play 默认聊天(互动熊)；C=聊天 / M=地图(导览熊)。");
        }

        private static GameObject EnsureChatCamera()
        {
            var chatCamGo = GameObject.Find("ChatCamera");
            if (chatCamGo == null)
            {
                chatCamGo = new GameObject("ChatCamera");
                var cam = chatCamGo.AddComponent<Camera>();
                cam.fieldOfView = 35f;
                cam.nearClipPlane = 0.05f;
                Debug.Log("[MergedSetup] Created ChatCamera");
            }

            var c = chatCamGo.GetComponent<Camera>();
            if (c != null)
            {
                c.enabled = false;
            }

            return chatCamGo;
        }

        private static ParkMapBearController FindGuideBear()
        {
            var named = GameObject.Find(MergedPlayModeBridge.GuideBearObjectName);
            if (named != null)
            {
                var ctrl = named.GetComponent<ParkMapBearController>();
                if (ctrl != null)
                {
                    return ctrl;
                }
            }

            foreach (var ctrl in Object.FindObjectsOfType<ParkMapBearController>())
            {
                if (ctrl == null)
                {
                    continue;
                }

                if (ctrl.gameObject.name == MergedPlayModeBridge.InteractiveBearObjectName)
                {
                    continue;
                }

                return ctrl;
            }

            return null;
        }

        private static void StripSmplPipelineFromGuide(ParkMapBearController guideBear)
        {
            var go = guideBear.gameObject;
            RemoveComponent<SmplhMotionRetarget>(go);
            RemoveComponent<XiongdaSmplhMotionDirector>(go);
            RemoveComponent<XiongdaFaceBlendShapeDriver>(go);

            foreach (var childRetarget in go.GetComponentsInChildren<SmplhMotionRetarget>(true))
            {
                if (childRetarget != null)
                {
                    Object.DestroyImmediate(childRetarget);
                }
            }
        }

        private static void EnsureGuideComponents(ParkMapBearController guideBear)
        {
            var go = guideBear.gameObject;
            if (go.GetComponent<ParkMapAutoNavigator>() == null)
            {
                go.AddComponent<ParkMapAutoNavigator>();
            }

            foreach (var playOnStart in go.GetComponentsInChildren<XiongdaPlayOnStart>(true))
            {
                if (playOnStart != null)
                {
                    Object.DestroyImmediate(playOnStart);
                }
            }

            foreach (var anim in go.GetComponentsInChildren<Animation>(true))
            {
                if (anim != null)
                {
                    anim.playAutomatically = false;
                }
            }
        }

        private static GameObject EnsureInteractiveBear()
        {
            var existing = GameObject.Find(MergedPlayModeBridge.InteractiveBearObjectName);
            if (existing != null && ShouldReplaceInteractiveBear(existing))
            {
                Debug.LogWarning("[MergedSetup] 旧的 InteractiveXiongda 不是 xiongda.fbx（可能是纯毛版 Prefab），将删除并重建。");
                Object.DestroyImmediate(existing);
                existing = null;
            }

            if (existing != null)
            {
                return existing;
            }

            string diskPath = Path.Combine(Application.dataPath,
                "XiongdaImported/xiongda_base_default/xiongda_maybe_final_new/xiongda_final_face/xiongda/xiongda.fbx");
            if (!File.Exists(diskPath))
            {
                Debug.LogError("[MergedSetup] 缺少互动熊模型文件: " + InteractiveModelPath);
                return null;
            }

            var modelPrefab = AssetDatabase.LoadAssetAtPath<GameObject>(InteractiveModelPath);
            if (modelPrefab == null)
            {
                Debug.LogError("[MergedSetup] Unity 无法加载: " + InteractiveModelPath + "（请点 Assets → Refresh）");
                return null;
            }

            var inst = PrefabUtility.InstantiatePrefab(modelPrefab) as GameObject;
            if (inst == null)
            {
                inst = Object.Instantiate(modelPrefab);
            }

            if (inst == null)
            {
                return null;
            }

            inst.name = MergedPlayModeBridge.InteractiveBearObjectName;
            inst.transform.localScale = Vector3.one * InteractiveBearScale;
            Debug.Log("[MergedSetup] 已实例化语音同款互动熊: " + InteractiveModelPath);
            return inst;
        }

        private static bool HasSmplReferenceRig(GameObject go)
        {
            return FindChildByName(go.transform, "Reference") != null;
        }

        private static bool ShouldReplaceInteractiveBear(GameObject go)
        {
            if (go == null)
            {
                return true;
            }

            if (!HasSmplReferenceRig(go))
            {
                return true;
            }

            string prefabPath = PrefabUtility.GetPrefabAssetPathOfNearestInstanceRoot(go) ?? string.Empty;
            if (prefabPath.IndexOf("纯毛版", System.StringComparison.OrdinalIgnoreCase) >= 0)
            {
                return true;
            }

            if (prefabPath.EndsWith(".prefab", System.StringComparison.OrdinalIgnoreCase))
            {
                return !string.Equals(
                    NormalizeAssetPath(prefabPath),
                    NormalizeAssetPath(InteractiveModelPath),
                    System.StringComparison.OrdinalIgnoreCase);
            }

            return false;
        }

        private static string NormalizeAssetPath(string path)
        {
            return (path ?? string.Empty).Replace('\\', '/').Trim();
        }

        private static void StripMapComponentsFromInteractive(GameObject interactiveBear)
        {
            if (interactiveBear == null)
            {
                return;
            }

            RemoveComponent<ParkMapBearController>(interactiveBear);
            RemoveComponent<ParkMapAutoNavigator>(interactiveBear);
            RemoveComponent<CharacterController>(interactiveBear);
        }

        private static void StripImportedLightsFromHierarchy(GameObject root)
        {
            if (root == null)
            {
                return;
            }

            foreach (var light in root.GetComponentsInChildren<Light>(true))
            {
                if (light != null)
                {
                    Object.DestroyImmediate(light);
                }
            }
        }

        private static void DisableImportedLightsOnInteractiveModelAsset()
        {
            var importer = AssetImporter.GetAtPath(InteractiveModelPath) as ModelImporter;
            if (importer == null)
            {
                return;
            }

            if (importer.importLights)
            {
                importer.importLights = false;
                importer.SaveAndReimport();
                Debug.Log("[MergedSetup] 已关闭 xiongda.fbx 的 importLights。");
            }
        }

        private static void ApplyDefaultDualBearVisibility(GameObject interactiveBear, ParkMapBearController guideBear)
        {
            if (interactiveBear != null)
            {
                interactiveBear.SetActive(true);
            }

            if (guideBear != null)
            {
                guideBear.gameObject.SetActive(false);
            }
        }

        private static Transform FindChildByName(Transform root, string name)
        {
            if (root == null)
            {
                return null;
            }

            if (root.name == name)
            {
                return root;
            }

            for (int i = 0; i < root.childCount; i++)
            {
                var found = FindChildByName(root.GetChild(i), name);
                if (found != null)
                {
                    return found;
                }
            }

            return null;
        }

        private static void EnsureInteractiveSmplPipeline(GameObject interactiveBear)
        {
            foreach (var playOnStart in interactiveBear.GetComponentsInChildren<XiongdaPlayOnStart>(true))
            {
                if (playOnStart != null)
                {
                    Object.DestroyImmediate(playOnStart);
                }
            }

            foreach (var anim in interactiveBear.GetComponentsInChildren<Animation>(true))
            {
                if (anim != null)
                {
                    anim.playAutomatically = false;
                    anim.Stop();
                }
            }

            foreach (var animator in interactiveBear.GetComponentsInChildren<Animator>(true))
            {
                if (animator != null)
                {
                    animator.enabled = false;
                }
            }

            var retarget = interactiveBear.GetComponent<SmplhMotionRetarget>();
            if (retarget == null)
            {
                retarget = interactiveBear.AddComponent<SmplhMotionRetarget>();
            }

            retarget.characterRoot = interactiveBear.transform;

            var retargetSo = new SerializedObject(retarget);
            retargetSo.FindProperty("streamingRelativePath").stringValue = "SmplhRetarget/stand.json";
            retargetSo.FindProperty("useDeltaFromFirstFrame").boolValue = true;
            retargetSo.FindProperty("smplReferencePoseRelativePath").stringValue = "SmplhRetarget/tpose.json";
            retargetSo.FindProperty("subtractReferenceRootTranslation").boolValue = true;
            retargetSo.FindProperty("disableLegacyAnimationOnSameObject").boolValue = true;
            retargetSo.FindProperty("disableAnimatorOnSameObject").boolValue = true;
            retargetSo.FindProperty("disableAnimatorsInCharacterRootSubtree").boolValue = true;
            retargetSo.FindProperty("autoEnsureFaceDriver").boolValue = true;
            retargetSo.FindProperty("playOnAwake").boolValue = true;
            retargetSo.FindProperty("loopIdleMotion").boolValue = true;
            retargetSo.FindProperty("idleMotionRelativePath").stringValue = "SmplhRetarget/stand.json";
            retargetSo.FindProperty("smplJointSpacePreEulerDegrees").vector3Value = new Vector3(180f, 0f, 0f);
            retargetSo.FindProperty("smplJointSpacePostEulerDegrees").vector3Value = new Vector3(180f, 0f, 0f);
            retargetSo.ApplyModifiedPropertiesWithoutUndo();

            var director = interactiveBear.GetComponent<XiongdaSmplhMotionDirector>();
            if (director == null)
            {
                director = interactiveBear.AddComponent<XiongdaSmplhMotionDirector>();
            }

            var face = interactiveBear.GetComponent<XiongdaFaceBlendShapeDriver>();
            if (face == null)
            {
                face = interactiveBear.AddComponent<XiongdaFaceBlendShapeDriver>();
            }

            var faceSo = new SerializedObject(face);
            faceSo.FindProperty("configRelativePath").stringValue = "SmplhRetarget/face_expression_config.json";
            faceSo.ApplyModifiedPropertiesWithoutUndo();

            var renderer = FindBestFaceRenderer(interactiveBear);
            if (renderer != null)
            {
                face.targetRenderer = renderer;
                EditorUtility.SetDirty(face);
            }
            else
            {
                Debug.LogWarning("[MergedSetup] 未找到带 BlendShape 的脸网格 xiongda_xinban，请确认 xiongda.fbx 已正确导入");
            }

            interactiveBear.transform.localScale = Vector3.one * InteractiveBearScale;
            EditorUtility.SetDirty(interactiveBear);
        }

        private static void WireParkMapUnityBridge(ParkMapBearController guideBear)
        {
            var bridgeGo = GameObject.Find("ParkMapUnityBridge");
            if (bridgeGo == null || guideBear == null)
            {
                return;
            }

            var bridge = bridgeGo.GetComponent<ParkMapUnityBridge>();
            if (bridge == null)
            {
                return;
            }

            var nav = guideBear.GetComponent<ParkMapAutoNavigator>();
            var so = new SerializedObject(bridge);
            so.FindProperty("bearController").objectReferenceValue = guideBear;
            so.FindProperty("autoNavigator").objectReferenceValue = nav;
            so.ApplyModifiedPropertiesWithoutUndo();
        }

        private static void WireUnityBridge(GameObject unityBridgeGo, GameObject interactiveBear)
        {
            if (unityBridgeGo == null || interactiveBear == null)
            {
                return;
            }

            var bridge = unityBridgeGo.GetComponent<UnityBridge>();
            if (bridge == null)
            {
                return;
            }

            var director = interactiveBear.GetComponent<XiongdaSmplhMotionDirector>();
            var retarget = interactiveBear.GetComponent<SmplhMotionRetarget>();
            var face = interactiveBear.GetComponent<XiongdaFaceBlendShapeDriver>();

            var so = new SerializedObject(bridge);
            so.FindProperty("smplhDirector").objectReferenceValue = director;
            so.FindProperty("smplhRetarget").objectReferenceValue = retarget;
            so.FindProperty("faceDriver").objectReferenceValue = face;
            so.ApplyModifiedPropertiesWithoutUndo();
        }

        private static void WireModeBridge(
            GameObject modeBridgeGo,
            GameObject interactiveBear,
            ParkMapBearController guideBear,
            GameObject chatCamGo)
        {
            if (modeBridgeGo == null)
            {
                return;
            }

            var mode = modeBridgeGo.GetComponent<MergedPlayModeBridge>();
            if (mode == null)
            {
                return;
            }

            var so = new SerializedObject(mode);
            so.FindProperty("interactiveBearRoot").objectReferenceValue =
                interactiveBear != null ? interactiveBear.transform : null;
            so.FindProperty("guideBearRoot").objectReferenceValue =
                guideBear != null ? guideBear.transform : null;
            so.FindProperty("guideBearController").objectReferenceValue = guideBear;
            so.FindProperty("guideNavigator").objectReferenceValue =
                guideBear != null ? guideBear.GetComponent<ParkMapAutoNavigator>() : null;
            so.FindProperty("chatCamera").objectReferenceValue =
                chatCamGo != null ? chatCamGo.GetComponent<Camera>() : null;

            var follow = Object.FindObjectOfType<ParkMapThirdPersonCameraFollow>();
            if (follow != null)
            {
                so.FindProperty("mapFollow").objectReferenceValue = follow;
                var mapCam = follow.GetComponent<Camera>();
                if (mapCam == null)
                {
                    mapCam = follow.GetComponentInChildren<Camera>();
                }

                so.FindProperty("mapFollowCamera").objectReferenceValue = mapCam;
            }

            so.ApplyModifiedPropertiesWithoutUndo();
        }

        private static SkinnedMeshRenderer FindBestFaceRenderer(GameObject root)
        {
            SkinnedMeshRenderer fallback = null;
            foreach (var r in root.GetComponentsInChildren<SkinnedMeshRenderer>(true))
            {
                if (r == null || r.sharedMesh == null)
                {
                    continue;
                }

                if (fallback == null)
                {
                    fallback = r;
                }

                string n = r.gameObject.name.ToLowerInvariant();
                if (n.Contains("xinban") || n.Contains("face") || n.Contains("xiongda"))
                {
                    if (r.sharedMesh.blendShapeCount > 0)
                    {
                        return r;
                    }
                }
            }

            return fallback;
        }

        private static void RemoveComponent<T>(GameObject go) where T : Component
        {
            var c = go.GetComponent<T>();
            if (c != null)
            {
                Object.DestroyImmediate(c);
            }
        }

        private static GameObject EnsureNamedBridge(string objectName, System.Type componentType)
        {
            var go = GameObject.Find(objectName);
            if (go == null)
            {
                go = new GameObject(objectName);
            }

            if (go.GetComponent(componentType) == null)
            {
                go.AddComponent(componentType);
            }

            return go;
        }

        [MenuItem("Tools/狗熊岭智慧终端/构建合并 WebGL（Development）到 webgl-merged")]
        public static void BuildMergedWebGLDevelopment()
        {
            if (EditorApplication.isPlayingOrWillChangePlaymode)
            {
                EditorUtility.DisplayDialog("请先停止 Play", "构建 WebGL 前请先点红色 Stop。", "知道了");
                return;
            }

            WireMergedBridges();
            RunBuild(BuildOptions.Development, "Development");
        }

        private static void RunBuild(BuildOptions extraOptions, string label)
        {
            string projectRoot = Path.GetFullPath(Path.Combine(Application.dataPath, ".."));
            string finalDir = Path.GetFullPath(Path.Combine(projectRoot, "..", "xiongda_app", "public", "webgl-merged"));
            string stagingDir = StagingBuildDir;

            Directory.CreateDirectory(stagingDir);
            Directory.CreateDirectory(finalDir);

            if (EditorUserBuildSettings.activeBuildTarget != BuildTarget.WebGL)
            {
                Debug.Log("[MergedSetup] Switching to WebGL…");
                if (!EditorUserBuildSettings.SwitchActiveBuildTarget(BuildTargetGroup.WebGL, BuildTarget.WebGL))
                {
                    Debug.LogError("[MergedSetup] Switch WebGL failed.");
                    return;
                }
            }

            Debug.Log("[MergedSetup] " + label + " → " + stagingDir);
            var options = new BuildPlayerOptions
            {
                scenes = new[] { ScenePath },
                locationPathName = stagingDir,
                target = BuildTarget.WebGL,
                options = extraOptions
            };

            BuildReport report = BuildPipeline.BuildPlayer(options);
            if (report.summary.result != BuildResult.Succeeded)
            {
                Debug.LogError("[MergedSetup] Build failed: " + report.summary.result);
                return;
            }

            CopyStagingToFinal(stagingDir, finalDir);
            WriteMergedBuildInfo(finalDir);
            Debug.Log("[MergedSetup] OK → " + finalDir);
            EditorUtility.RevealInFinder(finalDir);
        }

        private static void WriteMergedBuildInfo(string outputDir)
        {
            string buildDir = Path.Combine(outputDir, "Build");
            string manifestName = "ParkMapMerged.json";
            if (Directory.Exists(buildDir))
            {
                string[] jsonFiles = Directory.GetFiles(buildDir, "*.json");
                foreach (string file in jsonFiles)
                {
                    string name = Path.GetFileName(file);
                    if (!name.Equals("UnityLoader.js", System.StringComparison.OrdinalIgnoreCase))
                    {
                        manifestName = name;
                        break;
                    }
                }
            }

            string stem = Path.GetFileNameWithoutExtension(manifestName);
            string buildInfoPath = Path.Combine(outputDir, "build-info.json");
            string json = @"{
  ""loaderMode"": ""unity2018"",
  ""unityLoaderUrl"": ""/webgl-merged/Build/UnityLoader.js"",
  ""unityProgressUrl"": ""/webgl-merged/TemplateData/UnityProgress.js"",
  ""templateStyleUrl"": ""/webgl-merged/TemplateData/style.css"",
  ""jsonManifest"": ""/webgl-merged/Build/" + manifestName + @""",
  ""streamingAssetsUrl"": ""/webgl-merged/StreamingAssets"",
  ""loaderStem"": """ + stem + @""",
  ""merged"": true,
  ""dualBear"": true
}
";
            File.WriteAllText(buildInfoPath, json);
            Debug.Log("[MergedSetup] 已写入 " + buildInfoPath + " (manifest=" + manifestName + ")");
        }

        private static void CopyStagingToFinal(string stagingDir, string finalDir)
        {
            foreach (string name in new[] { "Build", "TemplateData", "StreamingAssets", "index.html" })
            {
                string src = Path.Combine(stagingDir, name);
                string dst = Path.Combine(finalDir, name);
                if (File.Exists(src))
                {
                    File.Copy(src, dst, true);
                    continue;
                }

                if (!Directory.Exists(src))
                {
                    continue;
                }

                if (Directory.Exists(dst))
                {
                    Directory.Delete(dst, true);
                }

                CopyDirectory(src, dst);
            }
        }

        private static void CopyDirectory(string source, string target)
        {
            Directory.CreateDirectory(target);
            foreach (string file in Directory.GetFiles(source))
            {
                File.Copy(file, Path.Combine(target, Path.GetFileName(file)), true);
            }

            foreach (string dir in Directory.GetDirectories(source))
            {
                CopyDirectory(dir, Path.Combine(target, Path.GetFileName(dir)));
            }
        }
    }
}
