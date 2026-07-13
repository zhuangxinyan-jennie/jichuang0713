using System;
using System.IO;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.SceneManagement;

namespace XiongdaImporter
{
    public static class XiongdaSceneSetup
    {
        private const string DefaultVariantName = "xiongda_left_slide_variant";
        private const string SceneFolder = "Assets/Scenes";
        private const string ScenePath = SceneFolder + "/XiongdaRun.unity";
        private const string PrefabName = "熊大@蒙皮.prefab";
        private const string PreviewPath = "XiongdaRunPreview.png";
        private const string MainMenuShowcaseVariantName = "xiongda_main_menu_showcase";
        private const string MainMenuShowcaseScenePath = SceneFolder + "/XiongdaMainMenuShowcase.unity";
        private const string MainMenuShowcasePrefabName = "Player_2.prefab";
        private const string MainMenuShowcasePreviewPath = "XiongdaMainMenuShowcasePreview.png";
        private const string XiongerVariantName = "xionger_base_default";
        private const string XiongerScenePath = SceneFolder + "/XiongerDefault.unity";
        private const string XiongerPrefabName = "熊二.prefab";
        private const string XiongerPreviewPath = "XiongerDefaultPreview.png";
        private const string GuangtouqiangVariantName = "guangtouqiang_base_default";
        private const string GuangtouqiangScenePath = SceneFolder + "/GuangtouqiangDefault.unity";
        private const string GuangtouqiangPrefabName = "光头强.prefab";
        private const string GuangtouqiangPreviewPath = "GuangtouqiangDefaultPreview.png";

        [MenuItem("Tools/Xiongda/Create Demo Scene")]
        private static void CreateDemoSceneMenu()
        {
            CreateDemoScene(DefaultVariantName);
        }

        public static void CreateLeftVariantDemoSceneBatch()
        {
            CreateDemoScene(DefaultVariantName);
        }

        public static void ImportLeftVariantAndCreateDemoSceneBatch()
        {
            XiongdaRunImporter.ImportLeftVariantBatch();
            CreateDemoScene(DefaultVariantName);
        }

        [MenuItem("Tools/Xiongda/Create Main Menu Showcase Scene")]
        private static void CreateMainMenuShowcaseSceneMenu()
        {
            CreateMainMenuShowcaseScene();
        }

        public static void CreateMainMenuShowcaseSceneBatch()
        {
            CreateMainMenuShowcaseScene();
        }

        public static void ImportXiongdaMainMenuShowcaseBatch()
        {
            XiongdaRunImporter.ImportMainMenuShowcaseBatch();
            CreateMainMenuShowcaseScene();
            CaptureScenePreview(MainMenuShowcaseScenePath, MainMenuShowcasePreviewPath);
        }

        public static void CaptureDemoScenePreviewBatch()
        {
            CaptureScenePreview(ScenePath, PreviewPath);
        }

        public static void CreateXiongerDefaultDemoSceneBatch()
        {
            CreateCharacterDemoScene(XiongerVariantName, XiongerPrefabName, XiongerScenePath, "XiongerDefault");
        }

        public static void ImportXiongerAndCreateDefaultDemoSceneBatch()
        {
            XiongdaRunImporter.ImportXiongerBaseDefaultBatch();
            CreateXiongerDefaultDemoSceneBatch();
            CaptureScenePreview(XiongerScenePath, XiongerPreviewPath);
        }

        public static void CreateGuangtouqiangDefaultDemoSceneBatch()
        {
            CreateCharacterDemoScene(GuangtouqiangVariantName, GuangtouqiangPrefabName, GuangtouqiangScenePath, "GuangtouqiangDefault");
        }

        public static void ImportGuangtouqiangAndCreateDefaultDemoSceneBatch()
        {
            XiongdaRunImporter.ImportGuangtouqiangBaseDefaultBatch();
            CreateGuangtouqiangDefaultDemoSceneBatch();
            CaptureScenePreview(GuangtouqiangScenePath, GuangtouqiangPreviewPath);
        }

        public static void ImportAdditionalCharactersBatch()
        {
            ImportXiongerAndCreateDefaultDemoSceneBatch();
            ImportGuangtouqiangAndCreateDefaultDemoSceneBatch();
        }

        private static void CreateDemoScene(string variantName)
        {
            var prefabPath = $"Assets/XiongdaImported/{variantName}/Prefabs/{PrefabName}";
            CreateSceneFromPrefab(prefabPath, ScenePath, "XiongdaRun");
        }

        private static void CreateMainMenuShowcaseScene()
        {
            var prefabPath = $"Assets/XiongdaImported/{MainMenuShowcaseVariantName}/Prefabs/{MainMenuShowcasePrefabName}";
            var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(prefabPath);
            if (prefab == null)
            {
                throw new InvalidOperationException($"Prefab not found: {prefabPath}");
            }

            EnsureFolder("Assets", "Scenes");

            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            scene.name = "XiongdaMainMenuShowcase";

            var instance = PrefabUtility.InstantiatePrefab(prefab) as GameObject;
            if (instance == null)
            {
                throw new InvalidOperationException($"Failed to instantiate prefab: {prefabPath}");
            }

            instance.transform.position = Vector3.zero;
            instance.transform.rotation = Quaternion.identity;

            var playOnStart = instance.GetComponent<XiongdaPlayOnStart>();
            if (playOnStart != null)
            {
                UnityEngine.Object.DestroyImmediate(playOnStart);
            }

            if (instance.GetComponent<XiongdaMainMenuShowcase>() == null)
            {
                instance.AddComponent<XiongdaMainMenuShowcase>();
            }

            CreateShowcaseCamera(instance);
            CreateDirectionalLight();

            if (!EditorSceneManager.SaveScene(scene, MainMenuShowcaseScenePath))
            {
                throw new InvalidOperationException($"Failed to save scene: {MainMenuShowcaseScenePath}");
            }

            EditorBuildSettings.scenes = new[]
            {
                new EditorBuildSettingsScene(MainMenuShowcaseScenePath, true)
            };

            AssetDatabase.SaveAssets();
            AssetDatabase.Refresh();
            Debug.Log($"Xiongda main menu showcase scene saved to {MainMenuShowcaseScenePath}");
        }

        private static void CreateCharacterDemoScene(string variantName, string prefabName, string scenePath, string sceneName)
        {
            var prefabPath = $"Assets/XiongdaImported/{variantName}/Prefabs/{prefabName}";
            CreateSceneFromPrefab(prefabPath, scenePath, sceneName);
        }

        public static void CreateSceneFromPrefab(string prefabPath, string scenePath, string sceneName)
        {
            var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(prefabPath);
            if (prefab == null)
            {
                throw new InvalidOperationException($"Prefab not found: {prefabPath}");
            }

            EnsureFolder("Assets", "Scenes");

            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            scene.name = sceneName;

            var instance = PrefabUtility.InstantiatePrefab(prefab) as GameObject;
            if (instance == null)
            {
                throw new InvalidOperationException($"Failed to instantiate prefab: {prefabPath}");
            }

            instance.transform.position = Vector3.zero;
            instance.transform.rotation = Quaternion.identity;

            CreateMainCamera(instance);
            CreateDirectionalLight();

            if (!EditorSceneManager.SaveScene(scene, scenePath))
            {
                throw new InvalidOperationException($"Failed to save scene: {scenePath}");
            }

            EditorBuildSettings.scenes = new[]
            {
                new EditorBuildSettingsScene(scenePath, true)
            };

            AssetDatabase.SaveAssets();
            AssetDatabase.Refresh();
            Debug.Log($"Xiongda demo scene saved to {scenePath}");
        }

        public static void CaptureScenePreview(string scenePath, string previewPath)
        {
            var scene = EditorSceneManager.OpenScene(scenePath, OpenSceneMode.Single);
            if (!scene.IsValid())
            {
                throw new InvalidOperationException($"Failed to open scene: {scenePath}");
            }

            var camera = Camera.main;
            if (camera == null)
            {
                throw new InvalidOperationException($"Main Camera not found in scene: {scenePath}");
            }

            var previewAbsolutePath = Path.Combine(Directory.GetParent(Application.dataPath)?.FullName ?? Application.dataPath, previewPath);
            var directory = Path.GetDirectoryName(previewAbsolutePath);
            if (!string.IsNullOrEmpty(directory))
            {
                Directory.CreateDirectory(directory);
            }

            const int width = 1280;
            const int height = 720;
            var renderTexture = new RenderTexture(width, height, 24);
            var texture = new Texture2D(width, height, TextureFormat.RGB24, false);

            var previousTarget = camera.targetTexture;
            var previousActive = RenderTexture.active;
            try
            {
                camera.targetTexture = renderTexture;
                RenderTexture.active = renderTexture;
                camera.Render();

                texture.ReadPixels(new Rect(0, 0, width, height), 0, 0);
                texture.Apply();
                File.WriteAllBytes(previewAbsolutePath, texture.EncodeToPNG());
            }
            finally
            {
                camera.targetTexture = previousTarget;
                RenderTexture.active = previousActive;
                UnityEngine.Object.DestroyImmediate(renderTexture);
                UnityEngine.Object.DestroyImmediate(texture);
            }

            Debug.Log($"Xiongda demo scene preview saved to {previewAbsolutePath}");
        }

        private static void CreateMainCamera(GameObject target)
        {
            var bounds = CalculateBounds(target);
            var cameraObject = new GameObject("Main Camera");
            cameraObject.tag = "MainCamera";

            var camera = cameraObject.AddComponent<Camera>();
            camera.clearFlags = CameraClearFlags.Skybox;
            camera.nearClipPlane = 0.01f;
            camera.farClipPlane = 100f;
            camera.fieldOfView = 40f;
            var orbit = cameraObject.AddComponent<XiongdaOrbitCamera>();
            orbit.Configure(target.transform, bounds, 180f);
        }

        private static void CreateShowcaseCamera(GameObject target)
        {
            var bounds = CalculateBounds(target);
            var cameraObject = new GameObject("Main Camera");
            cameraObject.tag = "MainCamera";

            var camera = cameraObject.AddComponent<Camera>();
            camera.clearFlags = CameraClearFlags.Skybox;
            camera.nearClipPlane = 0.01f;
            camera.farClipPlane = 100f;
            camera.fieldOfView = 34f;

            var focus = bounds.center + new Vector3(0f, bounds.size.y * 0.06f, 0f);
            var distance = Mathf.Max(bounds.size.y * 1.2f, bounds.size.x * 0.95f, 13f);
            cameraObject.transform.position = focus + new Vector3(0f, bounds.size.y * 0.18f, distance);
            cameraObject.transform.LookAt(focus);
        }

        private static void CreateDirectionalLight()
        {
            RenderSettings.ambientMode = AmbientMode.Flat;
            RenderSettings.ambientLight = new Color(0.42f, 0.44f, 0.48f);

            var keyLightObject = new GameObject("Key Light");
            var keyLight = keyLightObject.AddComponent<Light>();
            keyLight.type = LightType.Directional;
            keyLight.intensity = 1.1f;
            keyLight.shadows = LightShadows.Soft;
            keyLightObject.transform.rotation = Quaternion.Euler(28f, 150f, 0f);

            var fillLightObject = new GameObject("Fill Light");
            var fillLight = fillLightObject.AddComponent<Light>();
            fillLight.type = LightType.Directional;
            fillLight.intensity = 0.55f;
            fillLight.shadows = LightShadows.None;
            fillLightObject.transform.rotation = Quaternion.Euler(42f, 30f, 0f);
        }

        private static Bounds CalculateBounds(GameObject root)
        {
            var renderers = root.GetComponentsInChildren<Renderer>();
            if (renderers.Length == 0)
            {
                return new Bounds(root.transform.position + new Vector3(0f, 1f, 0f), new Vector3(2f, 2f, 2f));
            }

            var bounds = renderers[0].bounds;
            for (var i = 1; i < renderers.Length; i++)
            {
                bounds.Encapsulate(renderers[i].bounds);
            }

            return bounds;
        }

        private static void EnsureFolder(string parent, string child)
        {
            var path = $"{parent}/{child}";
            if (!AssetDatabase.IsValidFolder(path))
            {
                AssetDatabase.CreateFolder(parent, child);
            }
        }
    }
}
