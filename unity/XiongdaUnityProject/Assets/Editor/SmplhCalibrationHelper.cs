using System.Diagnostics;
using System.IO;
using System.Text;
using UnityEditor;
using UnityEngine;
using Debug = UnityEngine.Debug;

namespace XiongdaImporter
{
    /// <summary>
    /// ?????? SmplhMotionRetarget ??unity??????????? calibration.json?
    /// ???????? characterRootLocalEulerOffset?rootPositionExtraOffset?smplReferencePoseRelativePath?
    /// </summary>
    public static class SmplhCalibrationHelper
    {
        const string StreamingCalibrationPath = "Assets/StreamingAssets/SmplhRetarget/calibration.json";

        [MenuItem("Tools/Xiongda/SMPL Retarget/Copy unity block to clipboard (for calibration.json)", true, 500)]
        static bool ValidateRetargetSelected()
        {
            return Selection.activeGameObject != null
                && Selection.activeGameObject.GetComponent<SmplhMotionRetarget>() != null;
        }

        [MenuItem("Tools/Xiongda/SMPL Retarget/Copy unity block to clipboard (for calibration.json)", false, 500)]
        static void CopyUnityBlockToClipboard()
        {
            var r = GetSelectedRetarget();
            if (r == null)
                return;

            string json = BuildUnityBlockJson(r);
            EditorGUIUtility.systemCopyBuffer = json;
            Debug.Log("??? calibration.json ? unity ????????????? \"unity\": { ... } ??");
        }

        [MenuItem("Tools/Xiongda/SMPL Retarget/Merge into StreamingAssets/calibration.json", true, 501)]
        static bool ValidateRetargetSelectedWrite()
        {
            return ValidateRetargetSelected();
        }

        [MenuItem("Tools/Xiongda/SMPL Retarget/Merge into StreamingAssets/calibration.json", false, 501)]
        static void WriteUnityBlockToCalibrationFile()
        {
            var r = GetSelectedRetarget();
            if (r == null)
                return;

            if (!EditorUtility.DisplayDialog(
                    "?? calibration.json",
                    "??? SmplhMotionRetarget ? Inspector ??????? \"unity\" ??export ?????\n\n" + StreamingCalibrationPath,
                    "??",
                    "??"))
                return;

            if (!File.Exists(StreamingCalibrationPath))
            {
                EditorUtility.DisplayDialog("??", "??????\n" + StreamingCalibrationPath, "??");
                return;
            }

            string full = File.ReadAllText(StreamingCalibrationPath, Encoding.UTF8);
            string inner = BuildUnityInnerJson(r);
            string merged = ReplaceUnitySection(full, inner);
            File.WriteAllText(StreamingCalibrationPath, merged, Encoding.UTF8);
            AssetDatabase.Refresh();
            Debug.Log("????" + StreamingCalibrationPath);
        }

        static SmplhMotionRetarget GetSelectedRetarget()
        {
            GameObject go = Selection.activeGameObject;
            if (go == null)
            {
                EditorUtility.DisplayDialog("SMPL Retarget", "?? Hierarchy ????? SmplhMotionRetarget ????", "??");
                return null;
            }

            var r = go.GetComponent<SmplhMotionRetarget>();
            if (r == null)
            {
                EditorUtility.DisplayDialog("SMPL Retarget", "??????? SmplhMotionRetarget ???", "??");
                return null;
            }

            return r;
        }

        static string BuildUnityBlockJson(SmplhMotionRetarget r)
        {
            return "  \"unity\": {\n" + BuildUnityInnerJson(r) + "\n  }";
        }

        static string BuildUnityInnerJson(SmplhMotionRetarget r)
        {
            var sb = new StringBuilder();
            sb.AppendLine("    \"characterRootLocalEulerOffset\": " + Vec(r.characterRootLocalEulerOffset) + ",");
            sb.AppendLine("    \"rootPositionExtraOffset\": " + Vec(r.rootPositionExtraOffset) + ",");
            sb.AppendLine("    \"smplReferencePoseRelativePath\": \"" + JsonEscape(r.smplReferencePoseRelativePath) + "\"");
            return sb.ToString().TrimEnd();
        }

        static string Vec(Vector3 v)
        {
            return string.Format("{{ \"x\": {0}, \"y\": {1}, \"z\": {2} }}", JsonFloat(v.x), JsonFloat(v.y), JsonFloat(v.z));
        }

        static string JsonFloat(float f)
        {
            return f.ToString("G9", System.Globalization.CultureInfo.InvariantCulture);
        }

        static string JsonEscape(string s)
        {
            if (string.IsNullOrEmpty(s))
                return "";
            return s.Replace("\\", "\\\\").Replace("\"", "\\\"");
        }

        static string ReplaceUnitySection(string fullJson, string newInner)
        {
            const string key = "\"unity\"";
            int k = fullJson.IndexOf(key);
            if (k < 0)
                return fullJson;

            int braceStart = fullJson.IndexOf('{', k);
            if (braceStart < 0)
                return fullJson;

            int depth = 0;
            int unityCloseIdx = -1;
            for (int i = braceStart; i < fullJson.Length; i++)
            {
                char c = fullJson[i];
                if (c == '{') depth++;
                else if (c == '}')
                {
                    depth--;
                    if (depth == 0)
                    {
                        unityCloseIdx = i;
                        break;
                    }
                }
            }

            if (unityCloseIdx < 0)
                return fullJson;

            string before = fullJson.Substring(0, braceStart + 1);
            string after = fullJson.Substring(unityCloseIdx + 1);
            return before + "\n" + newInner + "\n  }" + after;
        }
    }
}
