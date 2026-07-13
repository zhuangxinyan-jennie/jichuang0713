using UnityEditor;
using UnityEngine;
using XiongdaImporter;

namespace XiongdaImporter.Editor
{
    /// <summary>
    /// 在 Hierarchy 选中带骨骼的熊根物体后，一键挂上表情驱动与 Play 测试条。
    /// </summary>
    public static class XiongdaSmplFaceSetupMenu
    {
        const string MenuRoot = "Tools/Xiongda/表情+动作/";

        [MenuItem(MenuRoot + "为选中角色一键配置（Retarget + 表情 + 测试条）", false, 600)]
        static void SetupSelectedCharacter()
        {
            var go = Selection.activeGameObject;
            if (go == null)
            {
                EditorUtility.DisplayDialog("熊大 SMPL+表情", "请先在 Hierarchy 里选中挂骨骼的根物体（例如 xiongda (1) 或 xiongda1）。", "好的");
                return;
            }

            Undo.RegisterFullObjectHierarchyUndo(go, "Xiongda SMPL+Face Setup");

            var retarget = go.GetComponent<SmplhMotionRetarget>();
            if (retarget == null)
            {
                retarget = Undo.AddComponent<SmplhMotionRetarget>(go);
            }

            if (retarget.characterRoot == null)
            {
                var reference = go.transform.Find("Reference");
                retarget.characterRoot = reference != null ? reference : go.transform;
                EditorUtility.SetDirty(retarget);
            }

            var face = go.GetComponent<XiongdaFaceBlendShapeDriver>();
            if (face == null)
            {
                face = Undo.AddComponent<XiongdaFaceBlendShapeDriver>(go);
            }

            var renderer = FindBestFaceRenderer(go);
            if (renderer != null)
            {
                face.targetRenderer = renderer;
                EditorUtility.SetDirty(face);
            }

            EnsurePlayModePanel(go, retarget, face);

            int shapeCount = renderer != null && renderer.sharedMesh != null ? renderer.sharedMesh.blendShapeCount : 0;
            string meshPath = renderer != null ? renderer.gameObject.name : "（未找到）";
            EditorUtility.DisplayDialog(
                "配置完成",
                "已在「" + go.name + "」上配置：\n"
                + "• SmplhMotionRetarget（Character Root → "
                + (retarget.characterRoot != null ? retarget.characterRoot.name : "?")
                + "）\n"
                + "• XiongdaFaceBlendShapeDriver（脸网格 → " + meshPath
                + "，BlendShape 数量 " + shapeCount + "）\n"
                + "• XiongdaSmplFacePlayModePanel（Play 后左上角测试按钮）\n\n"
                + "请保存场景，按 Play，点「振臂欢呼」看身体+脸。\n"
                + "Console 应出现 [FaceBlend] 已加载表情配置。",
                "好的");
        }

        [MenuItem(MenuRoot + "为选中角色一键配置（Retarget + 表情 + 测试条）", true)]
        static bool SetupSelectedCharacterValidate()
        {
            return Selection.activeGameObject != null;
        }

        [MenuItem(MenuRoot + "检查脸上 BlendShape 名称", false, 601)]
        static void LogBlendShapeNames()
        {
            var go = Selection.activeGameObject;
            if (go == null)
            {
                EditorUtility.DisplayDialog("检查 BlendShape", "请先选中熊根或 xiongda_xinban 物体。", "好的");
                return;
            }

            var r = go.GetComponent<SkinnedMeshRenderer>() ?? go.GetComponentInChildren<SkinnedMeshRenderer>(true);
            if (r == null || r.sharedMesh == null)
            {
                EditorUtility.DisplayDialog("检查 BlendShape", "未找到 SkinnedMeshRenderer / Mesh。", "好的");
                return;
            }

            var mesh = r.sharedMesh;
            var sb = new System.Text.StringBuilder();
            sb.AppendLine("网格: " + r.gameObject.name + "，共 " + mesh.blendShapeCount + " 个 BlendShape：");
            for (int i = 0; i < mesh.blendShapeCount; i++)
            {
                sb.AppendLine("  [" + i + "] " + mesh.GetBlendShapeName(i));
            }

            sb.AppendLine();
            sb.AppendLine("推荐模型: xiongda_maybe_final_new/xiongda_final_face/xiongda/xiongda.fbx（含 fun/happy）。");
            sb.AppendLine("表情驱动需映射到: fun, happy, cry, A, O（可与导入名 fun.001 等形式自动匹配）。");
            Debug.Log(sb.ToString());
            EditorUtility.DisplayDialog("BlendShape 列表", "已输出到 Console（Window → Console）。\n共 " + mesh.blendShapeCount + " 个。", "好的");
        }

        static SkinnedMeshRenderer FindBestFaceRenderer(GameObject root)
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

                string n = r.gameObject.name;
                if (n.IndexOf("xinban", System.StringComparison.OrdinalIgnoreCase) >= 0
                    || n.IndexOf("xiongda", System.StringComparison.OrdinalIgnoreCase) >= 0)
                {
                    return r;
                }
            }

            return fallback;
        }

        static void EnsurePlayModePanel(GameObject character, SmplhMotionRetarget retarget, XiongdaFaceBlendShapeDriver face)
        {
            var panel = Object.FindObjectOfType<XiongdaSmplFacePlayModePanel>();
            if (panel == null)
            {
                var panelGo = new GameObject("XiongdaSmplFacePlayModePanel");
                Undo.RegisterCreatedObjectUndo(panelGo, "Create play panel");
                panel = Undo.AddComponent<XiongdaSmplFacePlayModePanel>(panelGo);
            }

            var so = new SerializedObject(panel);
            so.FindProperty("retarget").objectReferenceValue = retarget;
            so.FindProperty("faceDriver").objectReferenceValue = face;
            so.FindProperty("showPanel").boolValue = true;
            so.ApplyModifiedPropertiesWithoutUndo();
            EditorUtility.SetDirty(panel);
        }
    }
}
