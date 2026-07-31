using System;
using UnityEditor;
using UnityEngine;

namespace XiongdaImporter
{
    public static class XiongdaBoundsRepair
    {
        private const string PrefabPath = "Assets/XiongdaImported/xiongda_left_slide_variant/Prefabs/熊大@蒙皮.prefab";

        [MenuItem("Tools/Xiongda/Repair Left Variant Bounds")]
        private static void RepairLeftVariantBoundsMenu()
        {
            RepairLeftVariantBoundsBatch();
        }

        public static void RepairLeftVariantBoundsBatch()
        {
            var prefabRoot = PrefabUtility.LoadPrefabContents(PrefabPath);
            if (prefabRoot == null)
            {
                throw new InvalidOperationException($"Failed to load prefab: {PrefabPath}");
            }

            try
            {
                var renderers = prefabRoot.GetComponentsInChildren<SkinnedMeshRenderer>(true);
                foreach (var renderer in renderers)
                {
                    var mesh = renderer.sharedMesh;
                    if (mesh == null)
                    {
                        continue;
                    }

                    var bounds = mesh.bounds.size == Vector3.zero
                        ? new Bounds(Vector3.zero, Vector3.one)
                        : new Bounds(mesh.bounds.center, mesh.bounds.size * 1.05f);
                    renderer.localBounds = bounds;
                    renderer.updateWhenOffscreen = true;
                    EditorUtility.SetDirty(renderer);
                }

                PrefabUtility.SaveAsPrefabAsset(prefabRoot, PrefabPath);
            }
            finally
            {
                PrefabUtility.UnloadPrefabContents(prefabRoot);
            }

            AssetDatabase.SaveAssets();
            AssetDatabase.Refresh();
            Debug.Log($"Repaired skinned mesh bounds in {PrefabPath}");
        }
    }
}
