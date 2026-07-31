using System;
using UnityEditor;
using UnityEngine;

namespace XiongdaImporter
{
    public static class XiongdaSkinVariants
    {
        private const string SourcePrefabPath = "Assets/XiongdaImported/xiongda_left_slide_variant/Prefabs/熊大@蒙皮.prefab";
        private const string BaseSkinPrefabPath = "Assets/XiongdaImported/xiongda_left_slide_variant/Prefabs/熊大@原始皮肤.prefab";
        private const string BaseSkinScenePath = "Assets/Scenes/XiongdaBaseSkin.unity";
        private const string BaseSkinPreviewPath = "XiongdaBaseSkinPreview.png";
        private const string DefaultSourcePrefabPath = "Assets/XiongdaImported/xiongda_base_default/Prefabs/熊大.prefab";
        private const string DefaultPureSkinPrefabPath = "Assets/XiongdaImported/xiongda_base_default/Prefabs/熊大@纯毛版.prefab";
        private const string DefaultSkinScenePath = "Assets/Scenes/XiongdaDefaultSkin.unity";
        private const string DefaultSkinPreviewPath = "XiongdaDefaultSkinPreview.png";
        private const string DefaultPureSkinScenePath = "Assets/Scenes/XiongdaDefaultPureSkin.unity";
        private const string DefaultPureSkinPreviewPath = "XiongdaDefaultPureSkinPreview.png";

        private static readonly string[] RemoveNodes =
        {
            "Mod_xiongda_zuqiufu_tuan",
            "Mod_xiongda_zuqiufu_yifu",
            "Mod_xiongda_jinsexie",
            "Mod_guanzi",
            "ball",
        };

        private static readonly string[] DefaultPureRemoveNodes =
        {
            "Bone_guanzi",
            "Mod_guanzi",
            "Mod_Xiongda_xiongmaoxie",
            "Tex_Xiongda_tiezhangxie",
            "Xiongda_xiaoya",
        };

        [MenuItem("Tools/Xiongda/Create Base Skin Prefab")]
        private static void CreateBaseSkinPrefabMenu()
        {
            CreateBaseSkinPrefab();
        }

        [MenuItem("Tools/Xiongda/Create Base Skin Demo Scene")]
        private static void CreateBaseSkinDemoSceneMenu()
        {
            CreateBaseSkinDemoSceneBatch();
        }

        public static void CreateBaseSkinPrefabBatch()
        {
            CreateBaseSkinPrefab();
        }

        public static void CreateBaseSkinDemoSceneBatch()
        {
            CreateBaseSkinPrefab();
            XiongdaSceneSetup.CreateSceneFromPrefab(BaseSkinPrefabPath, BaseSkinScenePath, "XiongdaBaseSkin");
            XiongdaSceneSetup.CaptureScenePreview(BaseSkinScenePath, BaseSkinPreviewPath);
        }

        [MenuItem("Tools/Xiongda/Create Default Pure Skin Prefab")]
        private static void CreateDefaultPureSkinPrefabMenu()
        {
            CreateDefaultPureSkinPrefab();
        }

        [MenuItem("Tools/Xiongda/Create Default Skin Demo Scenes")]
        private static void CreateDefaultSkinDemoScenesMenu()
        {
            CreateDefaultSkinDemoScenesBatch();
        }

        public static void CreateDefaultPureSkinPrefabBatch()
        {
            CreateDefaultPureSkinPrefab();
        }

        public static void CreateDefaultSkinDemoScenesBatch()
        {
            XiongdaRunImporter.ImportBaseDefaultBatch();
            CreateDefaultSkinScenes();
        }

        private static void CreateBaseSkinPrefab()
        {
            CreatePrefabVariant(SourcePrefabPath, BaseSkinPrefabPath, RemoveNodes, "Xiongda base skin");
        }

        private static void CreateDefaultPureSkinPrefab()
        {
            CreatePrefabVariant(DefaultSourcePrefabPath, DefaultPureSkinPrefabPath, DefaultPureRemoveNodes, "Xiongda default pure skin");
        }

        private static void CreateDefaultSkinScenes()
        {
            XiongdaSceneSetup.CreateSceneFromPrefab(DefaultSourcePrefabPath, DefaultSkinScenePath, "XiongdaDefaultSkin");
            XiongdaSceneSetup.CaptureScenePreview(DefaultSkinScenePath, DefaultSkinPreviewPath);

            CreateDefaultPureSkinPrefab();
            XiongdaSceneSetup.CreateSceneFromPrefab(DefaultPureSkinPrefabPath, DefaultPureSkinScenePath, "XiongdaDefaultPureSkin");
            XiongdaSceneSetup.CaptureScenePreview(DefaultPureSkinScenePath, DefaultPureSkinPreviewPath);
        }

        private static void CreatePrefabVariant(string sourcePrefabPath, string targetPrefabPath, string[] removeNodes, string logLabel)
        {
            var sourceRoot = PrefabUtility.LoadPrefabContents(sourcePrefabPath);
            if (sourceRoot == null)
            {
                throw new InvalidOperationException($"Failed to load prefab: {sourcePrefabPath}");
            }

            try
            {
                foreach (var nodeName in removeNodes)
                {
                    var target = FindDeepChild(sourceRoot.transform, nodeName);
                    if (target != null)
                    {
                        UnityEngine.Object.DestroyImmediate(target.gameObject);
                    }
                }

                PrefabUtility.SaveAsPrefabAsset(sourceRoot, targetPrefabPath);
            }
            finally
            {
                PrefabUtility.UnloadPrefabContents(sourceRoot);
            }

            AssetDatabase.SaveAssets();
            AssetDatabase.Refresh();
            Debug.Log($"{logLabel} prefab saved to {targetPrefabPath}");
        }

        private static Transform FindDeepChild(Transform root, string nodeName)
        {
            if (root.name == nodeName)
            {
                return root;
            }

            for (var i = 0; i < root.childCount; i++)
            {
                var child = root.GetChild(i);
                var match = FindDeepChild(child, nodeName);
                if (match != null)
                {
                    return match;
                }
            }

            return null;
        }
    }
}
