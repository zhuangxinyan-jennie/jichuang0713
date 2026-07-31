using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace SmartParkTerminal.EditorTools
{
    /// <summary>
    /// 将购入预览图 3.jpg 作为 SmartTerminalRoot 下首张 Quad 布景（无需导入整包 .unitypackage）。
    /// 批处理：Unity -batchmode -quit -executeMethod SmartParkTerminal.EditorTools.BackgroundPlateSceneSetup.ApplyPurchasePreview3AsBackdrop
    /// </summary>
    public static class BackgroundPlateSceneSetup
    {
        private const string ScenePath = "Assets/Scenes/SmartParkTerminal.unity";
        private const string TextureAssetPath = "Assets/StylizedNatureBundle/VendorPreviewImages/3.jpg";
        private const string MaterialAssetPath = "Assets/StylizedNatureBundle/BackgroundPlate/BackgroundPlate_3.mat";
        private const string PlateName = "\u80CC\u666F\u56FE_3jpg";

        public static void ApplyPurchasePreview3AsBackdrop()
        {
            var tex = AssetDatabase.LoadAssetAtPath<Texture2D>(TextureAssetPath);
            if (tex == null)
            {
                Debug.LogError("[BackgroundPlate] 找不到贴图: " + TextureAssetPath);
                EditorApplication.Exit(1);
                return;
            }

            if (!AssetDatabase.IsValidFolder("Assets/StylizedNatureBundle/BackgroundPlate"))
            {
                AssetDatabase.CreateFolder("Assets/StylizedNatureBundle", "BackgroundPlate");
            }

            var scene = EditorSceneManager.OpenScene(ScenePath, OpenSceneMode.Single);

            var root = GameObject.Find("SmartTerminalRoot");
            if (root == null)
            {
                Debug.LogError("[BackgroundPlate] 找不到 SmartTerminalRoot");
                EditorApplication.Exit(2);
                return;
            }

            var existing = root.transform.Find(PlateName);
            if (existing != null)
                Object.DestroyImmediate(existing.gameObject);

            var quad = GameObject.CreatePrimitive(PrimitiveType.Quad);
            quad.name = PlateName;
            quad.transform.SetParent(root.transform, false);
            quad.transform.SetAsFirstSibling();
            quad.transform.localPosition = new Vector3(-0.5f, 0.85f, 7.2f);
            // Quad 单面可见：Unity 默认正面朝向 +Z；相机在场景后方朝 +Z 看，勿再绕 Y=180，否则会对着背面（灰黑一片）
            quad.transform.localRotation = Quaternion.identity;
            quad.transform.localScale = new Vector3(74f, 48f, 1f);

            Object.DestroyImmediate(quad.GetComponent<Collider>());

            var shader = Shader.Find("Unlit/Texture");
            if (shader == null)
                shader = Shader.Find("Mobile/Unlit (Texture)");

            var mat = new Material(shader);
            mat.mainTexture = tex;

            var existingMat = AssetDatabase.LoadAssetAtPath<Material>(MaterialAssetPath);
            if (existingMat != null)
                AssetDatabase.DeleteAsset(MaterialAssetPath);

            AssetDatabase.CreateAsset(mat, MaterialAssetPath);

            var mr = quad.GetComponent<MeshRenderer>();
            mr.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            mr.receiveShadows = false;
            mr.sharedMaterial = AssetDatabase.LoadAssetAtPath<Material>(MaterialAssetPath);

            EditorSceneManager.MarkSceneDirty(scene);
            if (!EditorSceneManager.SaveScene(scene))
            {
                Debug.LogError("[BackgroundPlate] 保存场景失败");
                EditorApplication.Exit(4);
                return;
            }

            Debug.Log("[BackgroundPlate] 已写入布景 Quad + " + MaterialAssetPath);
            EditorApplication.Exit(0);
        }
    }
}
