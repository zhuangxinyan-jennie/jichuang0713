using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using UnityEngine;
using UnityEngine.Networking;
using Application = UnityEngine.Application;
using Debug = UnityEngine.Debug;

namespace XiongdaImporter
{
    /// <summary>
    /// 读取 StreamingAssets 下由 export_smplh_npz_to_unity_json.py 导出的混元 SMPL-H JSON；
    /// 按 JSON 内 bonePaths（如 Reference/Pelvis/…）将 52 关节旋转写到 Unity 骨骼。关节顺序与混元一致。
    /// 勿与 Humanoid Animator 同时驱动同一骨架：Animator 会在每帧覆盖骨骼旋转，导致一直像 T-pose。
    /// 本脚本默认关闭同物体 Animator，并用 LateUpdate 写入关节；若同物体有 Legacy Animation，也可在 Awake 关闭。
    /// </summary>
    /// <summary>尽量晚于其他动画/IK，避免本脚本的骨骼写入被覆盖。</summary>
    [DefaultExecutionOrder(32000)]
    public class SmplhMotionRetarget : MonoBehaviour
    {
        [Tooltip("相对 StreamingAssets，例如 SmplhRetarget/stand.json")]
        public string streamingRelativePath = "SmplhRetarget/stand.json";

        [Tooltip("角色根 Transform；bonePaths 相对此节点做 Find（如 Reference/Pelvis/…）。一般填 xiongda1 根或挂本组件的物体。")]
        public Transform characterRoot;

        [Tooltip("是否写入根物体 localPosition（来自 NPZ 的 trans × root_scale）")]
        public bool applyRootTranslation = true;

        [Tooltip("为 true：在 prefab 原有 localPosition 上叠加 trans；为 false：用 trans 替换位置")]
        public bool rootTranslationAdditive = true;

        [Tooltip("在根位移上再叠加修正（米/Unity 单位）")]
        public Vector3 rootPositionExtraOffset = Vector3.zero;

        [Tooltip("播放速度倍率")]
        public float speed = 1f;

        [Tooltip("进入场景后是否自动播放")]
        public bool playOnAwake = true;

        [Header("播放结束 → 待机")]
        [Tooltip("为 true：当前动作片段播完后从头循环（旧行为）。为 false：播完一次后自动加载 Idle Motion（通常为站立待机），避免一直卡在最后一帧重复点头等动作。")]
        public bool loopMotion = false;

        [Tooltip("为 true：非循环动作播完后自动切回 Idle Motion；调试单个动作时请保持关闭，否则 Console 会再次 loaded stand.json。")]
        public bool returnToIdleWhenMotionEnds = false;

        [Tooltip("loopMotion 为 false 时，片段结束后加载的待机 JSON（相对 StreamingAssets）。须与初始待机一致以便循环呼吸等小幅度动作。")]
        public string idleMotionRelativePath = "SmplhRetarget/stand.json";

        [Tooltip("当前片段路径与 Idle 相同时视为待机片段：是否循环播放（一般为 true）。")]
        public bool loopIdleMotion = true;

        [Header("坐标系 / 朝向")]
        [Tooltip("加在角色根物体 localRotation 上的欧拉修正（度）")]
        public Vector3 characterRootLocalEulerOffset = Vector3.zero;

        [Header("SMPL 关节轴向 → Unity（左右/上下颠倒时试调）")]
        [Tooltip("对 JSON 里每个关节局部四元数：先左乘该欧拉角。与 Python 导出时的 export basis_ex/ey/ez 同类，用于修正坐标轴不一致；会同时作用在参考姿势与当前帧，Delta 仍正确。可试 (0,180,0)、(180,0,0) 等。")]
        public Vector3 smplJointSpacePreEulerDegrees = Vector3.zero;

        [Tooltip("在上一步之后再右乘该欧拉角。若只左乘不够，再微调此项。")]
        public Vector3 smplJointSpacePostEulerDegrees = Vector3.zero;

        [Header("姿势对齐（与混元骨骼一致时只需开 Delta + 参考姿势）")]
        [Tooltip("务必勾选：用绑定姿势 ×（当前 SMPL 相对参考 SMPL）驱动关节。关闭时直接把 JSON 里的 SMPL 四元数赋给骨骼，与 Unity 绑定姿势不是同一语义，常见现象为手臂上举、整体扭曲。需配合下方 tpose 参考 JSON（与动作同套 bonePaths 导出）。")]
        public bool useDeltaFromFirstFrame = true;

        [Tooltip("Delta 四元数顺序。关（默认）：qRel = q_current * Inverse(q_ref)，与常见 R_curr = R_rel·R_ref 一致；开：qRel = Inverse(q_ref) * q_current（旧顺序）。若默认姿势手臂上举、肩扭转，可切换此项对照。")]
        public bool legacyDeltaInverseRefTimesCurrent = false;

        [Tooltip("参考姿势 JSON（与动作 JSON 同一套 bonePaths 导出），例如 SmplhRetarget/tpose.json")]
        public string smplReferencePoseRelativePath = "SmplhRetarget/tpose.json";

        [Tooltip("为 true：根位移用 (当前 trans - 参考 trans) 再叠加到 prefab")]
        public bool subtractReferenceRootTranslation = true;

        [Header("可选：calibration.json")]
        [Tooltip("为 true：Awake 时从 calibration.json 的 unity 段覆盖根朝向、根位移偏移、参考姿势路径")]
        public bool loadCalibrationFromStreamingAssets = false;

        [Tooltip("相对 StreamingAssets，默认 SmplhRetarget/calibration.json")]
        public string calibrationRelativePath = "SmplhRetarget/calibration.json";

        [Tooltip("为 true：Awake 时关闭同物体 Legacy Animation")]
        public bool disableLegacyAnimationOnSameObject = true;

        [Tooltip("为 true：Awake 时关闭同物体上的 Animator。Humanoid Animator 即使无 Controller 也常每帧把骨骼写回 Avatar 姿势（T-pose），会盖掉本脚本的 JSON 驱动。仅用 JSON 驱动时请保持勾选。")]
        public bool disableAnimatorOnSameObject = true;

        [Tooltip("为 true：在 characterRoot 整棵子树（含自身）上关闭所有 Animator。Animator 常挂在模型根或子物体上，若只关「同物体」仍会每帧覆盖骨骼，表现为与 JSON 混合、肩臂扭曲。仅用 JSON 驱动时请保持勾选。")]
        public bool disableAnimatorsInCharacterRootSubtree = true;

        [Tooltip("JSON 的 bonePaths 在角色下找不到时是否在控制台警告。模型无手指等骨骼时可关掉，避免黄条刷屏。")]
        public bool warnWhenBonePathMissing = true;

        [Header("面部表情（BlendShape）")]
        [Tooltip("为 true：同物体上若无 XiongdaFaceBlendShapeDriver 则自动添加（否则表情配置不会生效）")]
        public bool autoEnsureFaceDriver = true;

        [Header("启动速度")]
        [Tooltip("为 true：首段 JSON 放到下一帧再读（Play 后场景先出来，减少「卡住几秒」感）。建议保持开启。")]
        public bool deferInitialMotionLoadToNextFrame = true;

        [Header("调试（Play 时只读）")]
        [Tooltip("当前内存里真正在播的 JSON；若与 Streaming Relative Path 不一致，说明正在播待机或上次成功加载的片段。")]
        [SerializeField] string debugActuallyPlaying = "(未加载)";

        /// <summary>Inspector 里 Streaming Relative Path 上次成功同步加载的路径（回待机时不改写 Inspector 字段）。</summary>
        string _lastInspectorSyncedPath;

        /// <summary>已解析的 SMPL JSON 缓存（同一路径多组件/重复加载时避免再次 ReadAllText+FromJson）。</summary>
        static readonly Dictionary<string, SmplhMotionJson> ParsedMotionJsonCache =
            new Dictionary<string, SmplhMotionJson>(StringComparer.OrdinalIgnoreCase);

        SmplhMotionJson _data;
        Transform[] _resolved;
        int _boneCount;
        float _time;
        bool _playing = true;
        /// <summary>当前加载的片段是否与 idleMotionRelativePath 相同（待机站立等）。</summary>
        bool _isIdleClip;

        /// <summary>最近一次成功加载的 StreamingAssets 相对路径（供表情驱动在配置晚于动作加载时补同步）。</summary>
        public string LoadedStreamingRelativePath { get; private set; }
        /// <summary>当前动作播放时间（秒），供面部 BlendShape 曲线按动作进度同步。</summary>
        public float CurrentTimeSeconds { get { return _time; } }
        /// <summary>当前动作总时长（秒）。</summary>
        public float CurrentClipDurationSeconds
        {
            get
            {
                if (_data == null || _data.frames == null || _data.frames.Length == 0)
                {
                    return 0f;
                }

                float fps = _data.fps > 0.1f ? _data.fps : 30f;
                return _data.frames.Length / fps;
            }
        }
        /// <summary>当前动作归一化进度，0 为开头，1 为结尾；循环待机动作会取小数部分。</summary>
        public float CurrentClipNormalizedTime
        {
            get
            {
                float duration = CurrentClipDurationSeconds;
                if (duration <= 0.0001f)
                {
                    return 0f;
                }

                bool loopThis = _isIdleClip ? loopIdleMotion : loopMotion;
                float t = _time / duration;
                if (loopThis)
                {
                    t = t - Mathf.Floor(t);
                }

                return Mathf.Clamp01(t);
            }
        }
        public bool IsCurrentClipIdle { get { return _isIdleClip; } }
        public bool IsPlaying { get { return _playing; } }
        public bool IsRealtimeArmOverrideActive { get { return _realtimeArmOverrideActive; } }

        public Transform FindResolvedBoneByJointName(string jointName)
        {
            if (_data == null || _data.jointNames == null || _resolved == null || string.IsNullOrEmpty(jointName))
            {
                return null;
            }

            int count = Mathf.Min(_data.jointNames.Length, _resolved.Length);
            for (int i = 0; i < count; i++)
            {
                if (string.Equals(_data.jointNames[i], jointName, StringComparison.OrdinalIgnoreCase))
                {
                    return _resolved[i];
                }
            }

            return null;
        }

        public Transform FindResolvedBoneByPathEnd(string pathEnd)
        {
            if (_data == null || _data.bonePaths == null || _resolved == null || string.IsNullOrEmpty(pathEnd))
            {
                return null;
            }

            int count = Mathf.Min(_data.bonePaths.Length, _resolved.Length);
            for (int i = 0; i < count; i++)
            {
                string path = _data.bonePaths[i];
                if (!string.IsNullOrEmpty(path) && path.EndsWith(pathEnd, StringComparison.OrdinalIgnoreCase))
                {
                    return _resolved[i];
                }
            }

            return null;
        }

        /// <summary>已向待机路径发起异步加载，临时停在最后一帧避免重复触发。</summary>
        bool _returnToIdleInProgress;
        bool _realtimeArmOverrideActive;
        Quaternion _rootLocalRotBase = Quaternion.identity;
        Vector3 _rootLocalPosBase = Vector3.zero;

        Quaternion[] _bindLocalRot;
        /// <summary>已从 Unity 模型读取的绑定局部旋转；切换 JSON 时<strong>不得</strong>从当前帧再采样（否则会叠在上一段动作扭曲的姿势上）。</summary>
        int _bindLocalRotBoneCount = -1;

        /// <summary>参考姿势里每个关节的局部四元数（JSON 读出后经 smplJointSpacePre/Post 修正）。</summary>
        Quaternion[] _smplReferenceLocalRot;
        Vector3 _smplReferenceRootTrans = Vector3.zero;
        bool _hasSmplReferencePoseFile;

        [Serializable]
        class SmplhMotionJson
        {
            public int version;
            public int frameCount;
            public float fps;
            public string[] bonePaths;
            public string[] jointNames;
            public FrameRow[] frames;
        }

        [Serializable]
        class FrameRow
        {
            public float tx;
            public float ty;
            public float tz;
            public float[] q;
        }

        [Serializable]
        class CalVec3
        {
            public float x;
            public float y;
            public float z;
        }

        [Serializable]
        class CalibrationUnityBlock
        {
            public CalVec3 characterRootLocalEulerOffset;
            public CalVec3 rootPositionExtraOffset;
            public string smplReferencePoseRelativePath;
        }

        [Serializable]
        class CalibrationFile
        {
            public int version;
            public CalibrationUnityBlock unity;
        }

        static Vector3 ToVector3(CalVec3 v)
        {
            if (v == null)
                return Vector3.zero;
            return new Vector3(v.x, v.y, v.z);
        }

        /// <summary>
        /// 当 loadCalibrationFromStreamingAssets 为 true 时，从 calibration.json 的 unity 段覆盖 Inspector 中对应字段。
        /// </summary>
        public void ApplyCalibrationFromJsonFile()
        {
            if (!loadCalibrationFromStreamingAssets)
                return;
            string rel = calibrationRelativePath != null ? calibrationRelativePath.Trim() : string.Empty;
            if (rel.Length == 0)
                return;
            string abs = Path.Combine(Application.streamingAssetsPath, rel);
            if (!File.Exists(abs))
                return;
            try
            {
                string text = File.ReadAllText(abs);
                var cal = JsonUtility.FromJson<CalibrationFile>(text);
                if (cal == null || cal.unity == null)
                    return;
                CalibrationUnityBlock u = cal.unity;
                if (u.characterRootLocalEulerOffset != null)
                    characterRootLocalEulerOffset = ToVector3(u.characterRootLocalEulerOffset);
                if (u.rootPositionExtraOffset != null)
                    rootPositionExtraOffset = ToVector3(u.rootPositionExtraOffset);
                if (u.smplReferencePoseRelativePath != null && u.smplReferencePoseRelativePath.Length > 0)
                    smplReferencePoseRelativePath = u.smplReferencePoseRelativePath;
                Debug.Log("SmplhMotionRetarget: applied unity block from " + rel);
            }
            catch (Exception e)
            {
                Debug.LogWarning("SmplhMotionRetarget: calibration JSON failed: " + e.Message);
            }
        }

        void Awake()
        {
            if (characterRoot == null)
                characterRoot = transform;
            ApplyCalibrationFromJsonFile();
            if (disableLegacyAnimationOnSameObject)
            {
                var legacyAnim = GetComponent<Animation>();
                if (legacyAnim != null)
                {
                    legacyAnim.Stop();
                    legacyAnim.enabled = false;
                    Debug.Log("SmplhMotionRetarget: disabled Legacy Animation on this GameObject (use JSON motion only).");
                }
            }
            if (disableAnimatorOnSameObject)
            {
                var animator = GetComponent<Animator>();
                if (animator != null)
                {
                    animator.enabled = false;
                    Debug.Log("SmplhMotionRetarget: disabled Animator on this GameObject (Humanoid would overwrite bone rotations each frame).");
                }
            }
            if (disableAnimatorsInCharacterRootSubtree && characterRoot != null)
            {
                var animators = characterRoot.GetComponentsInChildren<Animator>(true);
                int n = 0;
                for (int i = 0; i < animators.Length; i++)
                {
                    if (animators[i] != null && animators[i].enabled)
                    {
                        animators[i].enabled = false;
                        n++;
                    }
                }
                if (n > 0)
                    Debug.Log("SmplhMotionRetarget: disabled " + n + " Animator(s) under characterRoot (JSON-driven bones).");
            }
            _rootLocalRotBase = characterRoot.localRotation;
            _rootLocalPosBase = characterRoot.localPosition;
            if (autoEnsureFaceDriver)
            {
                EnsureFaceDriverOnThisCharacter();
            }

#if UNITY_WEBGL && !UNITY_EDITOR
            StartCoroutine(CoAwakeWebGL());
#else
            if (deferInitialMotionLoadToNextFrame)
            {
                _playing = false;
                StartCoroutine(CoBootLoadInitialMotion());
            }
            else
            {
                BootLoadInitialMotionSync();
            }
#endif
        }

        void OnValidate()
        {
#if UNITY_EDITOR
            if (Application.isPlaying)
            {
                UnityEditor.EditorApplication.delayCall -= ReloadInspectorPathFromEditor;
                UnityEditor.EditorApplication.delayCall += ReloadInspectorPathFromEditor;
            }
#endif
        }

#if UNITY_EDITOR
        void ReloadInspectorPathFromEditor()
        {
            if (this == null || !Application.isPlaying)
            {
                return;
            }

            ReloadInspectorPathIfNeeded(false);
        }
#endif

#if !UNITY_WEBGL || UNITY_EDITOR
        void BootLoadInitialMotionSync()
        {
            if (!LoadMotionFromStreamingRelativePath(streamingRelativePath, true, true))
            {
                enabled = false;
                return;
            }

            if (playOnAwake)
            {
                _playing = true;
            }
        }

        IEnumerator CoBootLoadInitialMotion()
        {
            yield return null;
            BootLoadInitialMotionSync();
        }
#endif

#if UNITY_WEBGL && !UNITY_EDITOR
        IEnumerator CoAwakeWebGL()
        {
            yield return CoLoadMotionFromStreamingRelativePath(
                NormalizeStreamingRelativePath(streamingRelativePath),
                true,
                true);
            if (_data == null)
            {
                enabled = false;
                yield break;
            }

            if (playOnAwake)
                _playing = true;
        }

        /// <summary>WebGL：StreamingAssets 为 HTTP URL，不能用 File API。</summary>
        static string BuildStreamingAssetUrl(string normalizedRelativePath)
        {
            string norm = NormalizeStreamingRelativePath(normalizedRelativePath);
            if (string.IsNullOrEmpty(norm))
                return Application.streamingAssetsPath;
            string baseUrl = Application.streamingAssetsPath;
            if (!baseUrl.EndsWith("/"))
                baseUrl += "/";
            string[] segs = norm.Split('/');
            for (int i = 0; i < segs.Length; i++)
            {
                if (string.IsNullOrEmpty(segs[i]))
                    continue;
                segs[i] = UnityWebRequest.EscapeURL(segs[i]).Replace("+", "%20");
            }

            return baseUrl + string.Join("/", segs);
        }

        IEnumerator CoLoadMotionFromStreamingRelativePath(string normalized, bool resetTime, bool syncInspectorPath)
        {
            if (string.IsNullOrEmpty(normalized))
            {
                Debug.LogError("SmplhMotionRetarget: empty motion path.");
                yield break;
            }

            string motionUrl = BuildStreamingAssetUrl(normalized);
            using (UnityWebRequest req = UnityWebRequest.Get(motionUrl))
            {
                yield return req.SendWebRequest();
                if (req.isNetworkError || req.isHttpError)
                {
                    _returnToIdleInProgress = false;
                    Debug.LogError("SmplhMotionRetarget: WebGL 无法加载动作 JSON（检查 WebGL 是否包含 StreamingAssets 且路径中文已编码）: " + motionUrl + " → " + req.error);
                    yield break;
                }

                SmplhMotionJson motionDoc = null;
                if (!TryGetCachedMotionJson(normalized, out motionDoc))
                {
                    motionDoc = JsonUtility.FromJson<SmplhMotionJson>(req.downloadHandler.text);
                    if (motionDoc != null)
                    {
                        ParsedMotionJsonCache[normalized] = motionDoc;
                    }
                }

                SmplhMotionJson refDoc = null;
                string refPathTrim = smplReferencePoseRelativePath != null ? smplReferencePoseRelativePath.Trim() : string.Empty;
                if (refPathTrim.Length > 0)
                {
                    string refNorm = NormalizeStreamingRelativePath(refPathTrim);
                    if (!TryGetCachedMotionJson(refNorm, out refDoc))
                    {
                        string refUrl = BuildStreamingAssetUrl(refNorm);
                        using (UnityWebRequest reqRef = UnityWebRequest.Get(refUrl))
                        {
                            yield return reqRef.SendWebRequest();
                            if (reqRef.isNetworkError || reqRef.isHttpError)
                            {
                                Debug.LogWarning("SmplhMotionRetarget: WebGL 参考姿势加载失败（将用动作首帧）: " + refUrl + " → " + reqRef.error);
                            }
                            else
                            {
                                refDoc = JsonUtility.FromJson<SmplhMotionJson>(reqRef.downloadHandler.text);
                                if (refDoc != null)
                                {
                                    ParsedMotionJsonCache[refNorm] = refDoc;
                                }
                            }
                        }
                    }
                }

                if (!ApplyLoadedMotionJson(motionDoc, normalized, resetTime, refDoc, syncInspectorPath))
                {
                    _returnToIdleInProgress = false;
                    yield break;
                }

                LogLoadedMotion(normalized, syncInspectorPath);
            }
        }
#endif

        /// <summary>
        /// 仅允许相对 StreamingAssets 的路径，例如 SmplhRetarget/stand.json。
        /// </summary>
        public static string NormalizeStreamingRelativePath(string relativePath)
        {
            if (string.IsNullOrEmpty(relativePath))
            {
                return null;
            }

            string p = relativePath.Trim().Replace('\\', '/');
            while (p.StartsWith("/", StringComparison.Ordinal))
            {
                p = p.Substring(1);
            }

            p = TryRepairSplitUnicodeEscapePath(p);
            return p;
        }

        /// <summary>
        /// Unity 场景 YAML 若未加引号，中文路径会变成 SmplhRetarget/u644A/u624B/.../u95EE.json，此处尝试还原。
        /// </summary>
        static string TryRepairSplitUnicodeEscapePath(string path)
        {
            if (string.IsNullOrEmpty(path) || path.IndexOf("/u", StringComparison.Ordinal) < 0)
            {
                return path;
            }

            int splitIndex = path.IndexOf("/u", StringComparison.Ordinal);
            string prefix = path.Substring(0, splitIndex);
            string tail = path.Substring(splitIndex + 1);
            string[] segments = tail.Split('/');
            var chars = new System.Text.StringBuilder();
            string jsonSuffix = ".json";
            bool sawEscape = false;

            for (int i = 0; i < segments.Length; i++)
            {
                string seg = segments[i];
                if (TryParseUnityUnicodeSegment(seg, out char ch, out string remainder))
                {
                    chars.Append(ch);
                    sawEscape = true;
                    if (!string.IsNullOrEmpty(remainder))
                    {
                        jsonSuffix = remainder;
                    }
                }
                else if (i == segments.Length - 1 && seg.EndsWith(".json", StringComparison.OrdinalIgnoreCase))
                {
                    jsonSuffix = seg.StartsWith("u", StringComparison.Ordinal) ? ".json" : seg;
                }
            }

            if (!sawEscape || chars.Length == 0)
            {
                return path;
            }

            string repaired = prefix + "/" + chars + jsonSuffix;
            Debug.LogWarning(
                "SmplhMotionRetarget: 检测到损坏的中文路径（Unity 场景里 Unicode 未加引号），已自动修复："
                + path + " → " + repaired);
            return repaired;
        }

        static bool TryParseUnityUnicodeSegment(string segment, out char ch, out string remainder)
        {
            ch = '\0';
            remainder = string.Empty;
            if (string.IsNullOrEmpty(segment) || segment[0] != 'u')
            {
                return false;
            }

            if (segment.Length >= 5)
            {
                string hex = segment.Substring(1, 4);
                int code;
                if (int.TryParse(hex, System.Globalization.NumberStyles.HexNumber, null, out code))
                {
                    ch = (char)code;
                    remainder = segment.Length > 5 ? segment.Substring(5) : string.Empty;
                    return true;
                }
            }

            return false;
        }

        /// <summary>
        /// 运行时切换动作 JSON。成功则更新 streamingRelativePath 并重置时间；失败则保持当前动作并返回 false（不会关闭本组件）。
        /// WebGL 下为异步加载，本方法立即返回 true（实际结果见控制台）；编辑器/Standalone 同步返回是否成功。
        /// </summary>
        public bool LoadMotionFromStreamingRelativePath(string relativePath, bool resetTime)
        {
            return LoadMotionFromStreamingRelativePath(relativePath, resetTime, true);
        }

        public bool LoadMotionFromStreamingRelativePath(string relativePath, bool resetTime, bool syncInspectorPath)
        {
            string normalized = NormalizeStreamingRelativePath(relativePath);
            if (string.IsNullOrEmpty(normalized))
            {
                _returnToIdleInProgress = false;
                Debug.LogError("SmplhMotionRetarget: empty motion path.");
                return false;
            }

#if UNITY_WEBGL && !UNITY_EDITOR
            StartCoroutine(CoLoadMotionFromStreamingRelativePath(normalized, resetTime, syncInspectorPath));
            return true;
#else
            string abs = Path.Combine(Application.streamingAssetsPath, normalized);
            if (!File.Exists(abs))
            {
                _returnToIdleInProgress = false;
                Debug.LogError(
                    "SmplhMotionRetarget: file not found: " + abs
                    + "。请从 Project 窗口把 JSON 拖到 Streaming Relative Path，或检查中文文件名是否写错（例如 摊=U+644A）。"
                    + " 加载失败时会继续播上一段动作（常见为 stand.json）。");
                return false;
            }

            try
            {
                SmplhMotionJson doc;
                string jsonText = null;
                if (!TryGetCachedMotionJson(normalized, out doc))
                {
                    jsonText = File.ReadAllText(abs);
                    doc = JsonUtility.FromJson<SmplhMotionJson>(jsonText);
                    if (doc != null)
                    {
                        ParsedMotionJsonCache[normalized] = doc;
                    }
                }

                if (doc == null)
                {
                    _returnToIdleInProgress = false;
                    return false;
                }

                if (!ApplyLoadedMotionJson(doc, normalized, resetTime, null, syncInspectorPath))
                {
                    _returnToIdleInProgress = false;
                    return false;
                }

                LogLoadedMotion(normalized, syncInspectorPath);
                return true;
            }
            catch (Exception e)
            {
                _returnToIdleInProgress = false;
                Debug.LogError("SmplhMotionRetarget: load failed: " + e.Message);
                return false;
            }
#endif
        }

        static bool TryGetCachedMotionJson(string normalized, out SmplhMotionJson doc)
        {
            doc = null;
            if (string.IsNullOrEmpty(normalized))
            {
                return false;
            }

            return ParsedMotionJsonCache.TryGetValue(normalized, out doc) && doc != null;
        }

        static SmplhMotionJson LoadReferencePoseDocument(string refPath)
        {
            string normRef = NormalizeStreamingRelativePath(refPath);
            if (string.IsNullOrEmpty(normRef))
            {
                return null;
            }

            if (ParsedMotionJsonCache.TryGetValue(normRef, out SmplhMotionJson cached) && cached != null)
            {
                return cached;
            }

#if UNITY_WEBGL && !UNITY_EDITOR
            return null;
#else
            string refAbs = Path.Combine(Application.streamingAssetsPath, normRef);
            if (!File.Exists(refAbs))
            {
                return null;
            }

            try
            {
                var refDoc = JsonUtility.FromJson<SmplhMotionJson>(File.ReadAllText(refAbs));
                if (refDoc != null)
                {
                    ParsedMotionJsonCache[normRef] = refDoc;
                }

                return refDoc;
            }
            catch
            {
                return null;
            }
#endif
        }

        /// <param name="refPoseDoc">WebGL 下已由协程拉取的 tpose；否则在 Standalone 由 CacheBindPose 读文件。</param>
        bool ApplyLoadedMotionJson(
            SmplhMotionJson newData,
            string normalized,
            bool resetTime,
            SmplhMotionJson refPoseDoc,
            bool syncInspectorPath)
        {
            try
            {
                if (newData == null || newData.frames == null || newData.frames.Length == 0)
                {
                    Debug.LogError("SmplhMotionRetarget: invalid JSON: " + normalized);
                    return false;
                }

                if (syncInspectorPath)
                {
                    streamingRelativePath = normalized;
                    _lastInspectorSyncedPath = normalized;
                }

                _data = newData;
                _boneCount = _data.bonePaths.Length;
                _resolved = new Transform[_boneCount];
                var missingPaths = warnWhenBonePathMissing ? new List<string>() : null;
                for (int i = 0; i < _boneCount; i++)
                {
                    string path = _data.bonePaths[i];
                    Transform t = characterRoot.Find(path);
                    if (t == null && missingPaths != null)
                    {
                        missingPaths.Add(path);
                    }

                    _resolved[i] = t;
                }

                if (missingPaths != null && missingPaths.Count > 0)
                {
                    const int maxList = 16;
                    string detail = missingPaths.Count <= maxList
                        ? string.Join("\n", missingPaths.ToArray())
                        : string.Join("\n", missingPaths.GetRange(0, maxList).ToArray())
                          + "\n... 共 " + missingPaths.Count + " 条（见上为首 " + maxList + " 条）";
                    Debug.LogWarning("SmplhMotionRetarget: 下列 " + missingPaths.Count + " 个路径在 Character Root 下未找到（请对照 Hierarchy 命名或改导出 bonePaths）：\n" + detail);
                }

                CacheBindPoseAndSmplFirstFrame(refPoseDoc);

                if (!useDeltaFromFirstFrame)
                {
                    Debug.LogWarning(
                        "SmplhMotionRetarget: 未勾选「Use Delta From First Frame」。当前为「原始 SMPL 四元数」模式，不会叠到模型绑定姿势上，极易出现手臂上举、姿势错误。请勾选该项，并保证 Smpl Reference Pose Relative Path 指向与动作同一 bonePaths 导出的 tpose.json。");
                }
                else if (_smplReferenceLocalRot == null || _smplReferenceLocalRot.Length != _boneCount)
                {
                    Debug.LogError(
                        "SmplhMotionRetarget: 已启用 Delta，但参考姿势四元数未成功缓存（JSON 无效或 q 长度不足），将退回原始四元数模式。请检查 tpose.json 与动作 JSON 的 bonePaths、帧数据是否完整。");
                }

                if (resetTime)
                {
                    _time = 0f;
                }

                _playing = true;
                _returnToIdleInProgress = false;
                RefreshIdleClipFlag();
                LoadedStreamingRelativePath = normalized;
                debugActuallyPlaying = normalized;
                // 立刻刷一帧，避免在下一帧 LateUpdate 之前仍显示上一段动作的扭曲姿势
                ApplyFrame(0);
                NotifyFaceForMotion(normalized);
                return true;
            }
            catch (Exception e)
            {
                Debug.LogError("SmplhMotionRetarget: load failed: " + e.Message);
                return false;
            }
        }

        /// <summary>与 Awake 首次加载一致；失败时可能禁用组件（仅建议在初始化调用）。</summary>
        public void LoadClip()
        {
#if UNITY_WEBGL && !UNITY_EDITOR
            StartCoroutine(CoLoadMotionFromStreamingRelativePath(
                NormalizeStreamingRelativePath(streamingRelativePath),
                true,
                true));
#else
            if (!LoadMotionFromStreamingRelativePath(streamingRelativePath, true, true))
            {
                enabled = false;
            }
#endif
        }

        [ContextMenu("Reload Current Motion")]
        public void ReloadCurrentMotion()
        {
            string norm = NormalizeStreamingRelativePath(streamingRelativePath);
            if (string.IsNullOrEmpty(norm))
            {
                return;
            }

#if UNITY_WEBGL && !UNITY_EDITOR
            StartCoroutine(CoLoadMotionFromStreamingRelativePath(norm, true, true));
#else
            LoadMotionFromStreamingRelativePath(norm, true, true);
#endif
        }

        static void LogLoadedMotion(string normalized, bool syncInspectorPath)
        {
            if (syncInspectorPath)
            {
                Debug.Log("SmplhMotionRetarget: loaded motion " + normalized);
                return;
            }

            Debug.Log("SmplhMotionRetarget: loaded idle motion " + normalized + "（Inspector 里的 Streaming Relative Path 未改）");
        }

        /// <summary>
        /// 仅在骨架骨骼数量首次就绪或发生变化时，从当前 Transform 采样绑定姿势。
        /// 连续切换 SMPL 片段时骨骼已被上一段动作改写，若再采样会把扭曲当成「绑定」，导致越点越崩。
        /// </summary>
        void EnsureRigBindLocalRotCached()
        {
            if (_bindLocalRot != null && _bindLocalRotBoneCount == _boneCount)
                return;

            if (_bindLocalRot != null && _bindLocalRotBoneCount > 0 && _bindLocalRotBoneCount != _boneCount)
                Debug.LogWarning(
                    "SmplhMotionRetarget: 动作 JSON 骨骼数量与上一段不一致，将重新采样绑定姿势；若姿势怪异请先切回待机再换动作。");

            _bindLocalRot = new Quaternion[_boneCount];
            for (int i = 0; i < _boneCount; i++)
            {
                Transform bone = _resolved[i];
                _bindLocalRot[i] = bone != null ? bone.localRotation : Quaternion.identity;
            }

            _bindLocalRotBoneCount = _boneCount;
        }

        void CacheBindPoseAndSmplFirstFrame(SmplhMotionJson refPoseDocOverride = null)
        {
            if (_data == null || _data.frames == null || _data.frames.Length == 0)
                return;

            EnsureRigBindLocalRotCached();

            _hasSmplReferencePoseFile = false;
            float[] q0 = null;
            string refPath = smplReferencePoseRelativePath != null ? smplReferencePoseRelativePath.Trim() : string.Empty;
            if (refPath.Length > 0)
            {
                SmplhMotionJson refDoc = refPoseDocOverride;
                if (refDoc == null)
                {
#if UNITY_WEBGL && !UNITY_EDITOR
                    Debug.LogWarning("SmplhMotionRetarget: WebGL 下参考姿势应由 HTTP 预加载；当前无 override，改用动作首帧作为参考。");
#else
                    refDoc = LoadReferencePoseDocument(refPath);
                    if (refDoc == null)
                    {
                        Debug.LogWarning("SmplhMotionRetarget: reference pose file not found or invalid: " + refPath);
                    }
#endif
                }

                if (refDoc != null && refDoc.frames != null && refDoc.frames.Length > 0 && refDoc.frames[0].q != null
                    && refDoc.frames[0].q.Length >= _boneCount * 4)
                {
                    q0 = refDoc.frames[0].q;
                    FrameRow r0 = refDoc.frames[0];
                    _smplReferenceRootTrans = new Vector3(r0.tx, r0.ty, r0.tz);
                    _hasSmplReferencePoseFile = true;
                    Debug.Log("SmplhMotionRetarget: using SMPL reference pose from " + refPath);
                }
#if !(UNITY_WEBGL && !UNITY_EDITOR)
                else if (refDoc == null && refPath.Length > 0)
                    Debug.LogWarning("SmplhMotionRetarget: reference pose 未就绪，使用动作首帧。");
#endif
            }

            if (q0 == null)
            {
                q0 = _data.frames[0].q;
                FrameRow m0 = _data.frames[0];
                _smplReferenceRootTrans = new Vector3(m0.tx, m0.ty, m0.tz);
            }

            if (q0 == null || q0.Length < _boneCount * 4)
                return;

            _smplReferenceLocalRot = new Quaternion[_boneCount];
            for (int i = 0; i < _boneCount; i++)
                _smplReferenceLocalRot[i] = ApplySmplJointSpaceFix(ReadSmplQuatWxyz(q0, i));
        }

        /// <summary>与参考姿势、当前帧使用同一套修正，保证 Delta 为 (修正后当前) 相对 (修正后参考)。</summary>
        Quaternion ApplySmplJointSpaceFix(Quaternion qLocal)
        {
            if (smplJointSpacePreEulerDegrees.sqrMagnitude > 1e-8f)
                qLocal = Quaternion.Euler(smplJointSpacePreEulerDegrees) * qLocal;
            if (smplJointSpacePostEulerDegrees.sqrMagnitude > 1e-8f)
                qLocal = qLocal * Quaternion.Euler(smplJointSpacePostEulerDegrees);
            return qLocal;
        }

        /// <summary>JSON 内四元数为 w,x,y,z 顺序。</summary>
        static Quaternion ReadSmplQuatWxyz(float[] src, int boneIndex)
        {
            int o = boneIndex * 4;
            return new Quaternion(src[o + 1], src[o + 2], src[o + 3], src[o]);
        }

        void RefreshIdleClipFlag()
        {
            string idle = NormalizeStreamingRelativePath(idleMotionRelativePath);
            string cur = NormalizeStreamingRelativePath(
                !string.IsNullOrEmpty(LoadedStreamingRelativePath)
                    ? LoadedStreamingRelativePath
                    : streamingRelativePath);
            _isIdleClip = !string.IsNullOrEmpty(idle) && idle == cur;
        }

        void EnsureFaceDriverOnThisCharacter()
        {
            var face = GetComponent<XiongdaFaceBlendShapeDriver>();
            if (face == null)
            {
                face = gameObject.AddComponent<XiongdaFaceBlendShapeDriver>();
                Debug.Log("[SmplhMotionRetarget] 已自动添加 XiongdaFaceBlendShapeDriver（与 Retarget 同物体）。");
            }

            face.BindToRetarget(this);
        }

        void NotifyFaceForMotion(string normalizedPath)
        {
            XiongdaFaceBlendShapeDriver face = null;
            if (autoEnsureFaceDriver)
            {
                face = GetComponent<XiongdaFaceBlendShapeDriver>();
                if (face == null)
                {
                    EnsureFaceDriverOnThisCharacter();
                    face = GetComponent<XiongdaFaceBlendShapeDriver>();
                }
            }
            else
            {
                face = XiongdaFaceBlendShapeDriver.FindForRetarget(this);
            }

            if (face != null)
            {
                face.OnMotionLoaded(normalizedPath);
            }
            else
            {
                Debug.LogWarning(
                    "[SmplhMotionRetarget] 未找到 XiongdaFaceBlendShapeDriver，面部表情不会变化。"
                    + " 请在与本模型同一物体上 Add Component，或勾选 Auto Ensure Face Driver。");
            }
        }

        void LateUpdate()
        {
            if (_realtimeArmOverrideActive)
            {
                return;
            }

            ReloadInspectorPathIfNeeded(false);

            if (!_playing || _data == null || _data.frames.Length == 0)
                return;

            int n = _data.frames.Length;

            if (_returnToIdleInProgress)
            {
                ApplyFrame(n - 1);
                return;
            }

            float fps = _data.fps > 0.1f ? _data.fps : 30f;
            bool loopThis = _isIdleClip ? loopIdleMotion : loopMotion;

            _time += Time.deltaTime * speed;

            if (!loopThis && n > 0)
            {
                float clipDuration = n / fps;
                if (_time >= clipDuration)
                {
                    string idleNorm = NormalizeStreamingRelativePath(idleMotionRelativePath);
                    string curNorm = NormalizeStreamingRelativePath(streamingRelativePath);
                    if (returnToIdleWhenMotionEnds && !string.IsNullOrEmpty(idleNorm) && idleNorm != curNorm)
                    {
                        _returnToIdleInProgress = true;
                        _time = clipDuration;
                        ApplyFrame(n - 1);
                        LoadMotionFromStreamingRelativePath(idleMotionRelativePath, true, false);
                        return;
                    }

                    _time = clipDuration;
                    ApplyFrame(n - 1);
                    return;
                }
            }

            float frameTime = _time * fps;
            int frameIndex;
            if (loopThis)
            {
                float m = frameTime % n;
                if (m < 0f)
                    m += n;
                frameIndex = (int)m;
                if (frameIndex >= n)
                    frameIndex = n - 1;
            }
            else
            {
                frameIndex = Mathf.Min((int)frameTime, n - 1);
            }

            ApplyFrame(frameIndex);
        }

        bool ReloadInspectorPathIfNeeded(bool force)
        {
            if (_realtimeArmOverrideActive || !Application.isPlaying)
            {
                return false;
            }

            string norm = NormalizeStreamingRelativePath(streamingRelativePath);
            if (string.IsNullOrEmpty(norm))
            {
                return false;
            }

            if (!force
                && string.Equals(norm, _lastInspectorSyncedPath, StringComparison.OrdinalIgnoreCase))
            {
                return false;
            }

            Debug.Log("SmplhMotionRetarget: reload requested " + norm + "（Inspector Streaming Relative Path）");
            ReloadCurrentMotion();
            return true;
        }

        public void ApplyFrame(int frameIndex)
        {
            if (_data == null || frameIndex < 0 || frameIndex >= _data.frames.Length)
                return;

            FrameRow fr = _data.frames[frameIndex];
            if (applyRootTranslation)
            {
                Vector3 t = new Vector3(fr.tx, fr.ty, fr.tz);
                if (_hasSmplReferencePoseFile && subtractReferenceRootTranslation)
                    t -= _smplReferenceRootTrans;
                if (rootTranslationAdditive)
                    characterRoot.localPosition = _rootLocalPosBase + t + rootPositionExtraOffset;
                else
                    characterRoot.localPosition = t + rootPositionExtraOffset;
            }
            else
                characterRoot.localPosition = _rootLocalPosBase + rootPositionExtraOffset;

            characterRoot.localRotation = _rootLocalRotBase * Quaternion.Euler(characterRootLocalEulerOffset);

            float[] qsrc = fr.q;
            if (qsrc == null || qsrc.Length < _boneCount * 4)
            {
                Debug.LogWarning("SmplhMotionRetarget: frame q[] length mismatch");
                return;
            }

            bool useDelta = useDeltaFromFirstFrame && _bindLocalRot != null && _smplReferenceLocalRot != null
                && _bindLocalRot.Length == _boneCount && _smplReferenceLocalRot.Length == _boneCount;

            for (int i = 0; i < _boneCount; i++)
            {
                Transform bone = _resolved[i];
                if (bone == null)
                    continue;
                Quaternion q = ApplySmplJointSpaceFix(ReadSmplQuatWxyz(qsrc, i));
                if (useDelta)
                {
                    Quaternion qRel = legacyDeltaInverseRefTimesCurrent
                        ? Quaternion.Inverse(_smplReferenceLocalRot[i]) * q
                        : q * Quaternion.Inverse(_smplReferenceLocalRot[i]);
                    bone.localRotation = _bindLocalRot[i] * qRel;
                }
                else
                    bone.localRotation = q;
            }
        }

        public void SetPlaying(bool playing)
        {
            _playing = playing;
        }

        /// <summary>勾选 Enable Realtime Camera Arm Sync 时调用：待机 + 停止 JSON 时间轴。</summary>
        public void EnterRealtimeArmOverrideMode()
        {
            if (_realtimeArmOverrideActive)
            {
                return;
            }

            _realtimeArmOverrideActive = true;
            string idle = NormalizeStreamingRelativePath(idleMotionRelativePath);
            if (!string.IsNullOrEmpty(idle))
            {
                LoadMotionFromStreamingRelativePath(idle, true, false);
            }

            SetPlaying(false);
            debugActuallyPlaying = idle ?? LoadedStreamingRelativePath;
            Debug.Log(
                "[SmplhMotionRetarget] 模式→摄像头跟臂 | 实际播放待机: "
                + debugActuallyPlaying + " | Inspector JSON 路径保留: " + streamingRelativePath);
        }

        /// <summary>取消勾选 Enable Realtime Camera Arm Sync 时调用：恢复 Inspector JSON。</summary>
        public void ExitRealtimeArmOverrideMode()
        {
            if (!_realtimeArmOverrideActive)
            {
                return;
            }

            _realtimeArmOverrideActive = false;
            string action = NormalizeStreamingRelativePath(streamingRelativePath);
            if (string.IsNullOrEmpty(action))
            {
                SetPlaying(true);
                return;
            }

            LoadMotionFromStreamingRelativePath(action, true, true);
            SetPlaying(true);
            Debug.Log("[SmplhMotionRetarget] 模式→JSON 动作 | 正在播放: " + action);
        }

        // 兼容旧调用
        public void PrepareBodyForRealtimeArmOverride()
        {
            EnterRealtimeArmOverrideMode();
        }

        public void ResumeJsonMotionAfterRealtimeArmOverride()
        {
            ExitRealtimeArmOverrideMode();
        }
    }
}
