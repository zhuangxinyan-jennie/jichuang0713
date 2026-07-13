using UnityEngine;

namespace XiongdaImporter
{
    /// <summary>
    /// Editor / Standalone 按 Play 后左上角测试条：切换 SMPL JSON 与 emotion，无需板子与 WebGL。
    /// 挂到场景任意物体（建议 TerminalSystems 或熊根），勾选 Show Panel。
    /// </summary>
    [DisallowMultipleComponent]
    public sealed class XiongdaSmplFacePlayModePanel : MonoBehaviour
    {
        [SerializeField] bool showPanel = true;

        [SerializeField] SmplhMotionRetarget retarget;

        [SerializeField] XiongdaFaceBlendShapeDriver faceDriver;

        [SerializeField] SmartParkTerminal.UnityBridge unityBridge;

        [SerializeField] XiongdaRealtimeCameraArmSync armSync;

        static readonly string[] SampleMotions =
        {
            "SmplhRetarget/stand.json",
            "SmplhRetarget/振臂欢呼.json",
            "SmplhRetarget/双手欢呼.json",
            "SmplhRetarget/挥手致意.json",
            "SmplhRetarget/摊手疑问.json",
            "SmplhRetarget/受惊后退.json",
            "SmplhRetarget/擦眼低头.json",
            "SmplhRetarget/跺脚生气.json",
        };

        static readonly string[] SampleEmotions =
        {
            "neutral", "happy", "sad", "angry", "surprised", "smile", "scared",
        };

        void Awake()
        {
            if (retarget == null)
            {
                retarget = FindObjectOfType<SmplhMotionRetarget>();
            }

            if (faceDriver == null && retarget != null)
            {
                faceDriver = XiongdaFaceBlendShapeDriver.FindForRetarget(retarget);
            }

            if (unityBridge == null)
            {
                unityBridge = FindObjectOfType<SmartParkTerminal.UnityBridge>();
            }

            if (armSync == null)
            {
                armSync = FindObjectOfType<XiongdaRealtimeCameraArmSync>();
            }
        }

        void OnGUI()
        {
            if (!showPanel || !Application.isPlaying)
            {
                return;
            }

            const int w = 320;
            GUILayout.BeginArea(new Rect(12f, 12f, w, Screen.height - 24f), GUI.skin.box);
            GUILayout.Label("SMPL + 表情（本地 Play 测试，无需板子）");

            if (retarget == null)
            {
                GUILayout.Label("未找到 SmplhMotionRetarget");
                GUILayout.EndArea();
                return;
            }

            if (faceDriver == null)
            {
                GUILayout.Label("未找到 XiongdaFaceBlendShapeDriver（请挂到熊上并指定带 BlendShape 的脸）");
            }

            GUILayout.Label("动作 JSON");
            foreach (var path in SampleMotions)
            {
                var label = path.Replace("SmplhRetarget/", "");
                if (GUILayout.Button(label))
                {
                    PlayMotion(path);
                }
            }

            GUILayout.Space(8f);
            GUILayout.Label("情绪（模拟 Agent emotion）");
            GUILayout.BeginHorizontal();
            foreach (var em in SampleEmotions)
            {
                if (GUILayout.Button(em, GUILayout.Width(72f)))
                {
                    ApplyEmotion(em);
                }
            }

            GUILayout.EndHorizontal();

            GUILayout.Space(8f);
            GUILayout.Label("玩法切换：JSON 动作 ↔ 摄像头跟臂");
            if (armSync == null)
            {
                GUILayout.Label("未找到 XiongdaRealtimeCameraArmSync（跟臂不可用）");
            }
            else
            {
                bool jsonMode = !armSync.enableRealtimeCameraArmSync;
                if (GUILayout.Button(jsonMode ? "● JSON 动作（当前）" : "○ 切到 JSON 动作"))
                {
                    armSync.enableRealtimeCameraArmSync = false;
                }

                if (GUILayout.Button(!jsonMode ? "● 摄像头跟臂（当前）" : "○ 切到摄像头跟臂"))
                {
                    armSync.enableRealtimeCameraArmSync = true;
                }

                GUILayout.Label("与 Inspector 里 Enable Realtime Camera Arm Sync 相同");
                if (!jsonMode)
                {
                    GUILayout.Label("跟臂时 JSON 已暂停；需先运行 Pose 服务。");
                    GUILayout.Label("状态: " + armSync.StatusText);
                }
                else
                {
                    GUILayout.Label("当前由 Smplh JSON 驱动（上方按钮切动作）。");
                }
            }

            GUILayout.EndArea();
        }

        void PlayMotion(string relativePath)
        {
            if (armSync != null && armSync.enableRealtimeCameraArmSync)
            {
                armSync.enableRealtimeCameraArmSync = false;
            }

            if (unityBridge != null)
            {
                unityBridge.PlaySmplStreamingRelativePath(relativePath);
                return;
            }

            if (retarget != null)
            {
                retarget.LoadMotionFromStreamingRelativePath(relativePath, true);
            }
        }

        void ApplyEmotion(string emotion)
        {
            if (unityBridge != null)
            {
                unityBridge.SetFaceEmotion(emotion);
                return;
            }

            if (faceDriver != null)
            {
                faceDriver.ApplyPerceptionEmotion(emotion);
            }
        }
    }
}
