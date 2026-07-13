using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using UnityEngine;
using UnityEngine.Networking;

namespace XiongdaImporter
{
    /// <summary>
    /// 与 <see cref="SmplhMotionRetarget"/> 并行：按 JSON 配置驱动 SkinnedMeshRenderer 的 BlendShape（fun / A / O / cry / happy）。
    /// 配置：<c>StreamingAssets/SmplhRetarget/face_expression_config.json</c>
    /// </summary>
    [DisallowMultipleComponent]
    [DefaultExecutionOrder(32100)]
    public sealed class XiongdaFaceBlendShapeDriver : MonoBehaviour
    {
        const string DefaultConfigRelativePath = "SmplhRetarget/face_expression_config.json";

        [Tooltip("相对 StreamingAssets；留空则用 SmplhRetarget/face_expression_config.json")]
        public string configRelativePath = DefaultConfigRelativePath;

        [Tooltip("留空则在子层级查找名称含 xiongda 的 SkinnedMeshRenderer")]
        public SkinnedMeshRenderer targetRenderer;

        [Tooltip("板端 / Agent 的 emotion 是否在非动作切换时也驱动表情（叠加或覆盖待机）")]
        public bool applyPerceptionEmotionWhenIdle = true;

        [Tooltip("整体表情强度（1=配置表原值；建议不超过 1.1，且单通道权重永不超过 100，避免穿模）")]
        [Range(0.5f, 1.15f)]
        public float expressionIntensity = 1f;

        [Tooltip("笑容通道 fun+happy 合计上限（多个笑容形变会叠加，过高会穿模）")]
        [Range(40f, 100f)]
        public float maxCombinedSmileWeight = 82f;

        [Tooltip("口型 A 与 O 同时非零时，较弱一方自动衰减，避免张嘴形变叠加穿模")]
        public bool attenuateMouthShapeStacking = true;

        FaceExpressionConfigFile _cfg;
        readonly Dictionary<string, FacePresetEntry> _presets = new Dictionary<string, FacePresetEntry>(StringComparer.OrdinalIgnoreCase);
        readonly Dictionary<string, FaceMotionEntry> _motionsByPath = new Dictionary<string, FaceMotionEntry>(StringComparer.OrdinalIgnoreCase);
        readonly Dictionary<string, string> _perceptionToPreset = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        readonly Dictionary<string, float> _transitionPairSeconds = new Dictionary<string, float>(StringComparer.OrdinalIgnoreCase);

        readonly Dictionary<int, float> _current = new Dictionary<int, float>();
        readonly Dictionary<int, float> _target = new Dictionary<int, float>();
        readonly Dictionary<string, int> _shapeIndex = new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase);
        readonly Dictionary<string, int> _logicalIndex = new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase);

        static readonly string[] LogicalShapeNames = { "fun", "happy", "cry", "A", "O" };

        SmplhMotionRetarget _boundRetarget;
        string _pendingMotionPath;
        FaceMotionEntry _activeMotion;
        string _activeMotionPreset = "neutral";
        string _activePresetId = "neutral";
        string _pendingPresetId = "neutral";
        float _blendT;
        float _blendDuration = 0.35f;
        bool _configReady;

        [Serializable]
        class FaceExpressionConfigFile
        {
            public int version = 1;
            public float defaultBlendInSeconds = 0.35f;
            public float defaultBlendOutSeconds = 0.5f;
            public float neutralBlendInSeconds = 0.55f;
            public string idleMotionPath = "SmplhRetarget/stand.json";
            public string idlePreset = "idle_soft_smile";
            public FacePresetEntry[] presets;
            public FacePerceptionEntry[] perceptionEmotion;
            public FaceTransitionEntry[] transitions;
            public FaceMotionEntry[] motions;
        }

        [Serializable]
        public class FacePresetEntry
        {
            public string id;
            public string note;
            public float fun;
            public float happy;
            public float cry;
            public float A;
            public float O;
        }

        [Serializable]
        class FacePerceptionEntry
        {
            public string emotion;
            public string preset;
        }

        [Serializable]
        class FaceTransitionEntry
        {
            public string from;
            public string to;
            public float seconds;
        }

        [Serializable]
        class FaceMotionEntry
        {
            public string json;
            public string preset;
            public float blendIn = -1f;
            public string releasePreset;
            public FaceCurveEntry[] curves;
        }

        [Serializable]
        class FaceCurveEntry
        {
            public string shape;
            public bool additive;
            public FaceKeyframeEntry[] keys;
        }

        [Serializable]
        class FaceKeyframeEntry
        {
            public float t;
            public float value;
        }

        void Awake()
        {
            EnsureTargetRenderer();
            LoadConfigSync();
        }

        /// <summary>由 <see cref="SmplhMotionRetarget"/> 在 Awake 调用，从 characterRoot 子树查找带 BlendShape 的脸网格。</summary>
        public void BindToRetarget(SmplhMotionRetarget retarget)
        {
            _boundRetarget = retarget;
            EnsureTargetRenderer();
        }

        void LoadConfigSync()
        {
#if UNITY_WEBGL && !UNITY_EDITOR
            StartCoroutine(CoLoadConfigWebGL());
            return;
#else
            string rel = SmplhMotionRetarget.NormalizeStreamingRelativePath(
                string.IsNullOrWhiteSpace(configRelativePath) ? DefaultConfigRelativePath : configRelativePath);
            if (string.IsNullOrEmpty(rel))
            {
                return;
            }

            string abs = Path.Combine(Application.streamingAssetsPath, rel.Replace('/', Path.DirectorySeparatorChar));
            if (!File.Exists(abs))
            {
                Debug.LogWarning("[FaceBlend] 找不到配置: " + abs);
                return;
            }

            ApplyConfigJson(File.ReadAllText(abs));
#endif
        }

#if UNITY_WEBGL && !UNITY_EDITOR
        IEnumerator CoLoadConfigWebGL()
        {
            EnsureTargetRenderer();
            string rel = SmplhMotionRetarget.NormalizeStreamingRelativePath(
                string.IsNullOrWhiteSpace(configRelativePath) ? DefaultConfigRelativePath : configRelativePath);
            if (string.IsNullOrEmpty(rel))
            {
                yield break;
            }

            string url = Application.streamingAssetsPath;
            if (!url.EndsWith("/"))
            {
                url += "/";
            }

            string[] segs = rel.Split('/');
            for (int i = 0; i < segs.Length; i++)
            {
                if (string.IsNullOrEmpty(segs[i]))
                {
                    continue;
                }

                segs[i] = UnityWebRequest.EscapeURL(segs[i]).Replace("+", "%20");
            }

            url += string.Join("/", segs);
            using (var req = UnityWebRequest.Get(url))
            {
                yield return req.SendWebRequest();
                if (req.isNetworkError || req.isHttpError)
                {
                    Debug.LogWarning("[FaceBlend] 配置加载失败: " + url + " → " + req.error);
                    yield break;
                }

                ApplyConfigJson(req.downloadHandler.text);
            }
        }
#endif

        void ApplyConfigJson(string json)
        {
            if (string.IsNullOrEmpty(json))
            {
                return;
            }

            _cfg = JsonUtility.FromJson<FaceExpressionConfigFile>(json);
            if (_cfg == null)
            {
                Debug.LogWarning("[FaceBlend] 配置 JSON 解析失败");
                return;
            }

            _presets.Clear();
            _motionsByPath.Clear();
            _perceptionToPreset.Clear();
            _transitionPairSeconds.Clear();

            if (_cfg.presets != null)
            {
                foreach (var p in _cfg.presets)
                {
                    if (p == null || string.IsNullOrWhiteSpace(p.id)) continue;
                    _presets[p.id.Trim()] = p;
                }
            }

            if (_cfg.perceptionEmotion != null)
            {
                foreach (var e in _cfg.perceptionEmotion)
                {
                    if (e == null || string.IsNullOrWhiteSpace(e.emotion)) continue;
                    _perceptionToPreset[e.emotion.Trim()] = string.IsNullOrWhiteSpace(e.preset) ? "neutral" : e.preset.Trim();
                }
            }

            if (_cfg.transitions != null)
            {
                foreach (var t in _cfg.transitions)
                {
                    if (t == null || string.IsNullOrWhiteSpace(t.from) || string.IsNullOrWhiteSpace(t.to)) continue;
                    string key = TransitionKey(t.from.Trim(), t.to.Trim());
                    _transitionPairSeconds[key] = t.seconds > 0f ? t.seconds : _cfg.defaultBlendInSeconds;
                }
            }

            if (_cfg.motions != null)
            {
                foreach (var m in _cfg.motions)
                {
                    if (m == null || string.IsNullOrWhiteSpace(m.json)) continue;
                    string norm = SmplhMotionRetarget.NormalizeStreamingRelativePath(m.json);
                    if (!string.IsNullOrEmpty(norm))
                    {
                        _motionsByPath[norm] = m;
                    }
                }
            }

            EnsureTargetRenderer();
            CacheBlendShapeIndices();

            if (targetRenderer == null || targetRenderer.sharedMesh == null)
            {
                Debug.LogWarning(
                    "[FaceBlend] 未找到带网格的 SkinnedMeshRenderer。"
                    + " 请把本组件与 SmplhMotionRetarget 挂在同一物体（如 xiongda 根），"
                    + " 或手动将子物体 xiongda_xinban 的 Renderer 拖到 Target Renderer。");
                return;
            }

            if (targetRenderer.sharedMesh.blendShapeCount == 0)
            {
                Debug.LogWarning(
                    "[FaceBlend] 网格「" + targetRenderer.gameObject.name + "」BlendShape 数量为 0。"
                    + " 请使用 xiongda_final_face/xiongda/xiongda.fbx（含 fun/happy 等），不要用无表情的 xiongda1(12)_changing。");
                return;
            }

            if (_logicalIndex.Count == 0)
            {
                Debug.LogWarning(
                    "[FaceBlend] 无法将配置表映射到 BlendShape。导入名列表: "
                    + string.Join(", ", _shapeIndex.Keys));
                return;
            }

            bool canSmile = HasShape("fun") || HasShape("happy");
            if (!canSmile)
            {
                Debug.LogWarning(
                    "[FaceBlend] 缺少 fun 与 happy，无法做笑容。已映射: "
                    + string.Join(", ", _logicalIndex.Keys));
                return;
            }

            _configReady = true;
            SnapToPreset("neutral", 0f);
            Debug.Log(
                "[FaceBlend] 已就绪 | 脸=" + targetRenderer.gameObject.name
                + " | BlendShape=" + targetRenderer.sharedMesh.blendShapeCount
                + " | 通道=" + string.Join(",", _logicalIndex.Keys)
                + " | 预设=" + _presets.Count);

            ApplyPendingMotionSync();
        }

        void EnsureTargetRenderer()
        {
            if (targetRenderer != null && targetRenderer.sharedMesh != null
                && targetRenderer.sharedMesh.blendShapeCount > 0)
            {
                return;
            }

            targetRenderer = FindFaceRenderer();
        }

        SkinnedMeshRenderer FindFaceRenderer()
        {
            SkinnedMeshRenderer best = null;
            int bestShapes = 0;

            void Consider(Transform root)
            {
                if (root == null)
                {
                    return;
                }

                foreach (var r in root.GetComponentsInChildren<SkinnedMeshRenderer>(true))
                {
                    if (r == null || r.sharedMesh == null)
                    {
                        continue;
                    }

                    int n = r.sharedMesh.blendShapeCount;
                    if (n <= 0)
                    {
                        continue;
                    }

                    string goName = r.gameObject.name;
                    bool nameBoost = goName.IndexOf("xinban", StringComparison.OrdinalIgnoreCase) >= 0
                        || goName.IndexOf("xiongda", StringComparison.OrdinalIgnoreCase) >= 0;
                    int score = n + (nameBoost ? 1000 : 0);
                    if (score > bestShapes)
                    {
                        bestShapes = score;
                        best = r;
                    }
                }
            }

            Consider(transform);
            if (_boundRetarget == null)
            {
                _boundRetarget = GetComponent<SmplhMotionRetarget>()
                    ?? GetComponentInParent<SmplhMotionRetarget>();
            }

            if (_boundRetarget != null)
            {
                Consider(_boundRetarget.characterRoot);
                Consider(_boundRetarget.transform);
            }

            return best;
        }

        void CacheBlendShapeIndices()
        {
            _shapeIndex.Clear();
            _logicalIndex.Clear();
            if (targetRenderer == null || targetRenderer.sharedMesh == null)
            {
                return;
            }

            var mesh = targetRenderer.sharedMesh;
            int count = mesh.blendShapeCount;
            for (int i = 0; i < count; i++)
            {
                string imported = mesh.GetBlendShapeName(i);
                if (!_shapeIndex.ContainsKey(imported))
                {
                    _shapeIndex[imported] = i;
                }

                foreach (string logical in LogicalShapeNames)
                {
                    if (MatchesLogicalShapeName(imported, logical))
                    {
                        _logicalIndex[logical] = i;
                    }
                }
            }
        }

        static bool MatchesLogicalShapeName(string imported, string logical)
        {
            if (string.IsNullOrEmpty(imported) || string.IsNullOrEmpty(logical))
            {
                return false;
            }

            if (string.Equals(imported, logical, StringComparison.OrdinalIgnoreCase))
            {
                return true;
            }

            if (imported.EndsWith("." + logical, StringComparison.OrdinalIgnoreCase))
            {
                return true;
            }

            int dot = imported.LastIndexOf('.');
            string tail = dot >= 0 ? imported.Substring(dot + 1) : imported;
            return string.Equals(tail, logical, StringComparison.OrdinalIgnoreCase);
        }

        bool HasShape(string logicalName)
        {
            return _logicalIndex.ContainsKey(logicalName);
        }

        void ApplyPendingMotionSync()
        {
            if (!_configReady)
            {
                return;
            }

            if (!string.IsNullOrEmpty(_pendingMotionPath))
            {
                string p = _pendingMotionPath;
                _pendingMotionPath = null;
                OnMotionLoaded(p);
                return;
            }

            if (_boundRetarget == null)
            {
                _boundRetarget = GetComponent<SmplhMotionRetarget>();
            }

            if (_boundRetarget != null && !string.IsNullOrEmpty(_boundRetarget.LoadedStreamingRelativePath))
            {
                OnMotionLoaded(_boundRetarget.LoadedStreamingRelativePath);
            }
        }

        static string TransitionKey(string from, string to)
        {
            return from.ToLowerInvariant() + "->" + to.ToLowerInvariant();
        }

        /// <summary>由 SmplhMotionRetarget 在成功加载 JSON 后调用。</summary>
        public void OnMotionLoaded(string normalizedStreamingPath)
        {
            if (string.IsNullOrEmpty(normalizedStreamingPath))
            {
                return;
            }

            if (!_configReady)
            {
                _pendingMotionPath = normalizedStreamingPath;
                EnsureTargetRenderer();
                return;
            }

            string norm = SmplhMotionRetarget.NormalizeStreamingRelativePath(normalizedStreamingPath);
            if (string.IsNullOrEmpty(norm))
            {
                return;
            }

            if (_cfg != null && !string.IsNullOrEmpty(_cfg.idleMotionPath))
            {
                string idle = SmplhMotionRetarget.NormalizeStreamingRelativePath(_cfg.idleMotionPath);
                if (idle == norm)
                {
                    _activeMotion = null;
                    string idlePreset = string.IsNullOrWhiteSpace(_cfg.idlePreset) ? "idle_soft_smile" : _cfg.idlePreset;
                    BlendToPreset(idlePreset, -1f);
                    return;
                }
            }

            if (_motionsByPath.TryGetValue(norm, out FaceMotionEntry entry) && !string.IsNullOrWhiteSpace(entry.preset))
            {
                float dur = entry.blendIn > 0f ? entry.blendIn : (_cfg != null ? _cfg.defaultBlendInSeconds : 0.35f);
                string preset = entry.preset.Trim();
                _activeMotion = HasCurves(entry) ? entry : null;
                _activeMotionPreset = preset;
                BlendToPreset(preset, dur);
                Debug.Log("[FaceBlend] 动作→表情 " + norm + " → " + preset);
                return;
            }

            _activeMotion = null;
            BlendToPreset("neutral_attentive", -1f);
        }

        /// <summary>WebGL / 外部：板端 perception.emotion 或 Agent output.emotion。</summary>
        public void ApplyPerceptionEmotion(string emotion)
        {
            if (!_configReady)
            {
                return;
            }

            string key = (emotion ?? "").Trim();
            if (string.IsNullOrEmpty(key))
            {
                key = "neutral";
            }

            if (_perceptionToPreset.TryGetValue(key, out string presetId))
            {
                BlendToPreset(presetId, -1f);
            }
            else
            {
                BlendToPreset("neutral", -1f);
            }
        }

        public void BlendToPreset(string presetId, float durationSeconds)
        {
            if (!_configReady || string.IsNullOrWhiteSpace(presetId))
            {
                return;
            }

            presetId = presetId.Trim();
            if (!_presets.ContainsKey(presetId))
            {
                Debug.LogWarning("[FaceBlend] 未知预设: " + presetId);
                return;
            }

            if (string.Equals(_pendingPresetId, presetId, StringComparison.OrdinalIgnoreCase)
                && _blendT >= _blendDuration - 0.001f)
            {
                return;
            }

            float dur = durationSeconds > 0f
                ? durationSeconds
                : ResolveTransitionDuration(_activePresetId, presetId);

            _activePresetId = _pendingPresetId;
            _pendingPresetId = presetId;
            _blendDuration = Mathf.Max(0.05f, dur);
            _blendT = 0f;
            FillTargetFromPreset(presetId);
        }

        float ResolveTransitionDuration(string fromId, string toId)
        {
            if (_cfg == null)
            {
                return 0.35f;
            }

            if (string.Equals(toId, "neutral", StringComparison.OrdinalIgnoreCase))
            {
                return _cfg.neutralBlendInSeconds > 0f ? _cfg.neutralBlendInSeconds : _cfg.defaultBlendOutSeconds;
            }

            string key = TransitionKey(fromId, toId);
            if (_transitionPairSeconds.TryGetValue(key, out float sec))
            {
                return sec;
            }

            return _cfg.defaultBlendInSeconds > 0f ? _cfg.defaultBlendInSeconds : 0.35f;
        }

        void FillTargetFromPreset(string presetId)
        {
            _target.Clear();
            float fun;
            float happy;
            float cry;
            float mouthA;
            float mouthO;
            if (!TryGetPresetWeights(presetId, out fun, out happy, out cry, out mouthA, out mouthO))
            {
                return;
            }

            SetTargetWeight("fun", fun);
            SetTargetWeight("happy", happy);
            SetTargetWeight("cry", cry);
            SetTargetWeight("A", mouthA);
            SetTargetWeight("O", mouthO);
        }

        bool TryGetPresetWeights(string presetId, out float fun, out float happy, out float cry, out float mouthA, out float mouthO)
        {
            fun = 0f;
            happy = 0f;
            cry = 0f;
            mouthA = 0f;
            mouthO = 0f;

            if (!_presets.TryGetValue(presetId, out FacePresetEntry p))
            {
                return false;
            }

            fun = p.fun;
            happy = p.happy;
            cry = p.cry;
            mouthA = p.A;
            mouthO = p.O;
            ApplyAntiStacking(ref fun, ref happy, ref cry, ref mouthA, ref mouthO);
            return true;
        }

        /// <summary>
        /// 熊大脸模上 fun / happy / A / O 会叠加改同一区域，不能同时拉满 100，否则嘴部穿模。
        /// </summary>
        void ApplyAntiStacking(ref float fun, ref float happy, ref float cry, ref float mouthA, ref float mouthO)
        {
            float smileSum = fun + happy;
            if (smileSum > maxCombinedSmileWeight && smileSum > 0.01f)
            {
                float s = maxCombinedSmileWeight / smileSum;
                fun *= s;
                happy *= s;
            }

            if (attenuateMouthShapeStacking && mouthA > 1f && mouthO > 1f)
            {
                if (mouthA >= mouthO)
                {
                    mouthO *= 0.2f;
                    mouthA = Mathf.Min(mouthA, 58f);
                }
                else
                {
                    mouthA *= 0.2f;
                    mouthO = Mathf.Min(mouthO, 58f);
                }
            }
            else
            {
                mouthA = Mathf.Min(mouthA, 65f);
                mouthO = Mathf.Min(mouthO, 65f);
            }
        }

        float ScaleWeight(float w)
        {
            return Mathf.Clamp(w * expressionIntensity, 0f, 100f);
        }

        void SetTargetWeight(string shapeName, float weight)
        {
            if (_logicalIndex.TryGetValue(shapeName, out int idx))
            {
                _target[idx] = ScaleWeight(weight);
            }
        }

        void ResetAllBlendShapesToZero()
        {
            if (targetRenderer == null)
            {
                return;
            }

            foreach (var kv in _logicalIndex)
            {
                int idx = kv.Value;
                _current[idx] = 0f;
                targetRenderer.SetBlendShapeWeight(idx, 0f);
            }

            _target.Clear();
        }

        void SnapToPreset(string presetId, float duration)
        {
            _activePresetId = presetId;
            _pendingPresetId = presetId;
            _blendT = 1f;
            _blendDuration = duration;
            ResetAllBlendShapesToZero();
            FillTargetFromPreset(presetId);
            foreach (var kv in _target)
            {
                _current[kv.Key] = kv.Value;
                if (targetRenderer != null)
                {
                    targetRenderer.SetBlendShapeWeight(kv.Key, kv.Value);
                }
            }
        }

        static bool HasCurves(FaceMotionEntry entry)
        {
            return entry != null && entry.curves != null && entry.curves.Length > 0;
        }

        float CurrentMotionNormalizedTime()
        {
            if (_boundRetarget == null)
            {
                _boundRetarget = GetComponent<SmplhMotionRetarget>();
            }

            return _boundRetarget != null ? _boundRetarget.CurrentClipNormalizedTime : 0f;
        }

        void ApplyActiveMotionCurves()
        {
            if (_activeMotion == null || !HasCurves(_activeMotion) || targetRenderer == null)
            {
                return;
            }

            float fun;
            float happy;
            float cry;
            float mouthA;
            float mouthO;
            if (!TryGetPresetWeights(_activeMotionPreset, out fun, out happy, out cry, out mouthA, out mouthO))
            {
                return;
            }

            float t = CurrentMotionNormalizedTime();
            foreach (var curve in _activeMotion.curves)
            {
                if (curve == null || curve.keys == null || curve.keys.Length == 0)
                {
                    continue;
                }

                float value = EvaluateCurve(curve.keys, t);
                ApplyCurveValue(curve.shape, curve.additive, value, ref fun, ref happy, ref cry, ref mouthA, ref mouthO);
            }

            ApplyAntiStacking(ref fun, ref happy, ref cry, ref mouthA, ref mouthO);
            SetCurrentWeight("fun", fun);
            SetCurrentWeight("happy", happy);
            SetCurrentWeight("cry", cry);
            SetCurrentWeight("A", mouthA);
            SetCurrentWeight("O", mouthO);
        }

        static float EvaluateCurve(FaceKeyframeEntry[] keys, float t)
        {
            FaceKeyframeEntry prev = keys[0];
            if (t <= prev.t)
            {
                return prev.value;
            }

            for (int i = 1; i < keys.Length; i++)
            {
                FaceKeyframeEntry next = keys[i];
                if (t <= next.t)
                {
                    float span = Mathf.Max(0.0001f, next.t - prev.t);
                    float u = Mathf.Clamp01((t - prev.t) / span);
                    u = u * u * (3f - 2f * u);
                    return Mathf.Lerp(prev.value, next.value, u);
                }

                prev = next;
            }

            return prev.value;
        }

        static void ApplyCurveValue(string shape, bool additive, float value, ref float fun, ref float happy, ref float cry, ref float mouthA, ref float mouthO)
        {
            if (string.IsNullOrWhiteSpace(shape))
            {
                return;
            }

            if (string.Equals(shape, "fun", StringComparison.OrdinalIgnoreCase))
            {
                fun = additive ? fun + value : value;
            }
            else if (string.Equals(shape, "happy", StringComparison.OrdinalIgnoreCase))
            {
                happy = additive ? happy + value : value;
            }
            else if (string.Equals(shape, "cry", StringComparison.OrdinalIgnoreCase))
            {
                cry = additive ? cry + value : value;
            }
            else if (string.Equals(shape, "A", StringComparison.OrdinalIgnoreCase))
            {
                mouthA = additive ? mouthA + value : value;
            }
            else if (string.Equals(shape, "O", StringComparison.OrdinalIgnoreCase))
            {
                mouthO = additive ? mouthO + value : value;
            }
        }

        void SetCurrentWeight(string shapeName, float weight)
        {
            if (!_logicalIndex.TryGetValue(shapeName, out int idx))
            {
                return;
            }

            float scaled = ScaleWeight(weight);
            _current[idx] = scaled;
            targetRenderer.SetBlendShapeWeight(idx, scaled);
        }

        void LateUpdate()
        {
            if (!_configReady || targetRenderer == null)
            {
                return;
            }

            if (_blendT < _blendDuration)
            {
                _blendT += Time.deltaTime;
                float u = Mathf.Clamp01(_blendT / _blendDuration);
                u = u * u * (3f - 2f * u);
                foreach (var kv in _target)
                {
                    int idx = kv.Key;
                    float from = _current.TryGetValue(idx, out float f) ? f : 0f;
                    float w = Mathf.Lerp(from, kv.Value, u);
                    _current[idx] = w;
                    targetRenderer.SetBlendShapeWeight(idx, w);
                }

                foreach (var kv in _logicalIndex)
                {
                    int idx = kv.Value;
                    if (_target.ContainsKey(idx))
                    {
                        continue;
                    }

                    float from = _current.TryGetValue(idx, out float f) ? f : 0f;
                    if (from > 0.01f)
                    {
                        float w = Mathf.Lerp(from, 0f, u);
                        _current[idx] = w;
                        targetRenderer.SetBlendShapeWeight(idx, w);
                    }
                }

                if (u >= 1f - 0.0001f)
                {
                    _activePresetId = _pendingPresetId;
                }
            }

            ApplyActiveMotionCurves();
        }

        public static XiongdaFaceBlendShapeDriver FindForRetarget(SmplhMotionRetarget retarget)
        {
            if (retarget == null)
            {
                return null;
            }

            var face = retarget.GetComponent<XiongdaFaceBlendShapeDriver>();
            if (face != null)
            {
                return face;
            }

            if (retarget.characterRoot != null)
            {
                face = retarget.characterRoot.GetComponentInChildren<XiongdaFaceBlendShapeDriver>(true);
                if (face != null)
                {
                    return face;
                }
            }

            face = FindObjectOfType<XiongdaFaceBlendShapeDriver>();
            if (face != null)
            {
                face.BindToRetarget(retarget);
            }

            return face;
        }
    }
}
