using UnityEngine;
using XiongdaImporter;

namespace SmartParkTerminal
{
    /// <summary>
    /// 网页端 WebGL 通信桥：React 中
    /// <c>unityInstance.SendMessage("UnityBridge", "PlayClipById", clipId)</c>。
    /// <para>
    /// <b>SMPL-H JSON</b>（<c>StreamingAssets/SmplhRetarget/*.json</c>）与 <see cref="ClipIdPlayer"/>（Animator 状态）是两套驱动：
    /// JSON 由 <see cref="SmplhMotionRetarget"/> 写骨骼，通常会关掉 Humanoid Animator，避免与 clip_id 动画混用同一角色。
    /// </para>
    /// 场景中建空物体命名为 <b>UnityBridge</b>，挂本组件，并拖入 <see cref="ClipIdPlayer"/>；若用 JSON，请在熊上挂 Retarget/Director 并在下方引用（或依赖全局查找）。
    /// </summary>
    [DisallowMultipleComponent]
    public sealed class UnityBridge : MonoBehaviour
    {
        public ClipIdPlayer clipIdPlayer;

        [Tooltip("可选：挂在熊（与 SmplhMotionRetarget 同物体或同场景）上，用于 JSON 动作")]
        [SerializeField] private XiongdaSmplhMotionDirector smplhDirector;

        [Tooltip("可选：未填 Director 时直接用 Retarget 切 JSON")]
        [SerializeField] private SmplhMotionRetarget smplhRetarget;

        [Tooltip("可选：xiongda_final_face 的 BlendShape 驱动；留空则自动查找")]
        [SerializeField] private XiongdaFaceBlendShapeDriver faceDriver;

        /// <summary>
        /// WebGL：<c>SendMessage("UnityBridge", "SetFaceEmotion", "happy")</c>；
        /// 与板端 perception.emotion / Agent 的 emotion 字段一致（见 face_expression_config.json）。
        /// </summary>
        public void SetFaceEmotion(string emotion)
        {
            var face = ResolveFaceDriver();
            if (face == null)
            {
                Debug.LogWarning("[UnityBridge] 未找到 XiongdaFaceBlendShapeDriver，无法 SetFaceEmotion。");
                return;
            }

            face.ApplyPerceptionEmotion(emotion);
        }

        public void PlayClipById(string clipId)
        {
            if (clipIdPlayer == null)
            {
                Debug.LogWarning("[UnityBridge] ClipIdPlayer 未分配。");
                return;
            }

            clipIdPlayer.PlayClipById(clipId ?? string.Empty, null, "webgl_bridge", "smile");
        }

        /// <summary>
        /// WebGL：<c>SendMessage("UnityBridge", "PlaySmplStreamingRelativePath", "SmplhRetarget/挥手致意.json")</c>。
        /// 路径相对 <see cref="Application.streamingAssetsPath"/>，与 Inspector 里 Smplh 组件填写方式一致。
        /// </summary>
        public void PlaySmplStreamingRelativePath(string relativePath)
        {
            if (string.IsNullOrWhiteSpace(relativePath))
            {
                Debug.LogWarning("[UnityBridge] PlaySmplStreamingRelativePath：路径为空。");
                return;
            }

            var dir = smplhDirector != null ? smplhDirector : FindObjectOfType<XiongdaSmplhMotionDirector>();
            if (dir != null)
            {
                bool ok = dir.PlayByStreamingRelativePath(relativePath.Trim(), "webgl_bridge_smpl");
                if (ok)
                {
                    Debug.Log("[UnityBridge] SMPL JSON → " + relativePath.Trim());
                }

                return;
            }

            var ret = smplhRetarget != null ? smplhRetarget : FindObjectOfType<SmplhMotionRetarget>();
            if (ret == null)
            {
                Debug.LogWarning("[UnityBridge] 未找到 XiongdaSmplhMotionDirector / SmplhMotionRetarget，无法播放 JSON。请在角色上添加组件并配置 characterRoot、tpose 等。");
                return;
            }

            bool loaded = ret.LoadMotionFromStreamingRelativePath(relativePath.Trim(), true);
            if (loaded)
            {
                Debug.Log("[UnityBridge] SMPL JSON（Retarget）→ " + relativePath.Trim());
            }
        }

        /// <summary>
        /// WebGL：<c>SendMessage("UnityBridge", "PlaySmplByLogicalId", "stand")</c>；
        /// 需在 <see cref="XiongdaSmplhMotionDirector"/> 的 Registry 里登记 logicalId。
        /// </summary>
        public void PlaySmplByLogicalId(string logicalId)
        {
            if (string.IsNullOrWhiteSpace(logicalId))
            {
                Debug.LogWarning("[UnityBridge] PlaySmplByLogicalId：id 为空。");
                return;
            }

            var dir = smplhDirector != null ? smplhDirector : FindObjectOfType<XiongdaSmplhMotionDirector>();
            if (dir == null)
            {
                Debug.LogWarning("[UnityBridge] 未找到 XiongdaSmplhMotionDirector，无法用 logicalId 播放。");
                return;
            }

            dir.PlayByLogicalId(logicalId.Trim());
        }

        XiongdaFaceBlendShapeDriver ResolveFaceDriver()
        {
            if (faceDriver != null)
            {
                return faceDriver;
            }

            if (smplhDirector != null)
            {
                var r = smplhDirector.GetComponent<SmplhMotionRetarget>();
                if (r != null)
                {
                    faceDriver = XiongdaFaceBlendShapeDriver.FindForRetarget(r);
                    if (faceDriver != null)
                    {
                        return faceDriver;
                    }
                }
            }

            var ret = smplhRetarget != null ? smplhRetarget : FindObjectOfType<SmplhMotionRetarget>();
            if (ret != null)
            {
                faceDriver = XiongdaFaceBlendShapeDriver.FindForRetarget(ret);
            }

            if (faceDriver == null)
            {
                faceDriver = FindObjectOfType<XiongdaFaceBlendShapeDriver>();
            }

            return faceDriver;
        }
    }
}
