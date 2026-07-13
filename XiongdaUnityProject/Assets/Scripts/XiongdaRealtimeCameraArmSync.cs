using System.Collections;
using UnityEngine;
using UnityEngine.Networking;

namespace XiongdaImporter
{
    /// <summary>
    /// 双模式开关（仅看 Enable Realtime Camera Arm Sync）：
    /// - 未勾选：SmplhMotionRetarget 播 JSON（Streaming Relative Path）
    /// - 勾选：JSON 暂停，全身待机，肩/肘跟 Pose 服务
    /// </summary>
    [DisallowMultipleComponent]
    [DefaultExecutionOrder(32200)]
    public sealed class XiongdaRealtimeCameraArmSync : MonoBehaviour
    {
        public enum ArmSide
        {
            Both,
            LeftOnly,
            RightOnly
        }

        [Header("模式开关（唯一入口）")]
        [Tooltip("关 = JSON 动作；开 = 摄像头跟臂（需先运行 Pose 服务 8767）。")]
        public bool enableRealtimeCameraArmSync;

        [Header("关键点来源")]
        public string landmarksUrl = "http://127.0.0.1:8767/api/pose";

        [Range(0.02f, 0.2f)]
        public float pollIntervalSeconds = 0.05f;

        [Range(0.1f, 2f)]
        public float landmarkTimeoutSeconds = 0.35f;

        public ArmSide armSide = ArmSide.Both;

        [Header("角色骨骼")]
        public SmplhMotionRetarget motionRetarget;
        public Transform characterRoot;
        public Transform leftShoulder;
        public Transform leftElbow;
        public Transform leftWrist;
        public Transform rightShoulder;
        public Transform rightElbow;
        public Transform rightWrist;

        [Header("映射调节")]
        public bool mirrorInput = true;
        [Range(0.2f, 4f)] public float horizontalScale = 1.3f;
        [Range(0.2f, 4f)] public float verticalScale = 1.25f;
        [Range(0f, 3f)] public float depthScale = 0.35f;
        [Range(0f, 3f)] public float shoulderHeight = 1.15f;
        [Range(0f, 1f)] public float smoothing = 0.45f;
        public Vector3 shoulderLocalEulerOffset = Vector3.zero;
        public Vector3 elbowLocalEulerOffset = Vector3.zero;

        [Header("调试（Play 时只读）")]
        [SerializeField] string debugControlMode = "JSON";
        [SerializeField] string status = "JSON 动作";
        [SerializeField] bool hasFreshLandmarks;
        [SerializeField] string resolvedBoneSource = "Unresolved";

        public string StatusText { get { return status; } }

        WebCamTexture _webCam;
        Coroutine _pollRoutine;
        bool _wasEnabled;
        bool _bootReady;
        bool _inRealtimeMode;
        float _lastLandmarkTime = -999f;

        Quaternion _leftShoulderBind;
        Quaternion _leftElbowBind;
        Quaternion _rightShoulderBind;
        Quaternion _rightElbowBind;
        Vector3 _leftUpperArmBindWorldDirection;
        Vector3 _leftForearmBindWorldDirection;
        Vector3 _rightUpperArmBindWorldDirection;
        Vector3 _rightForearmBindWorldDirection;

        ArmLandmarks _latestLeft;
        ArmLandmarks _latestRight;

        [System.Serializable]
        public sealed class LandmarkResponse
        {
            public bool ok = true;
            public ArmLandmarks left;
            public ArmLandmarks right;
        }

        [System.Serializable]
        public sealed class ArmLandmarks
        {
            public LandmarkPoint shoulder;
            public LandmarkPoint elbow;
            public LandmarkPoint wrist;
        }

        [System.Serializable]
        public sealed class LandmarkPoint
        {
            public float x;
            public float y;
            public float z;
            public float visibility = 1f;
        }

        void Awake()
        {
            if (characterRoot == null)
            {
                characterRoot = transform;
            }

            if (motionRetarget == null)
            {
                motionRetarget = GetComponent<SmplhMotionRetarget>();
            }

            AutoResolveBones();
            _wasEnabled = enableRealtimeCameraArmSync;
        }

        void Start()
        {
            StartCoroutine(CoBoot());
        }

        void Update()
        {
            if (!_bootReady)
            {
                return;
            }

            if (_wasEnabled != enableRealtimeCameraArmSync)
            {
                ApplyModeFromCheckbox();
            }

            hasFreshLandmarks = _inRealtimeMode && Time.time - _lastLandmarkTime <= landmarkTimeoutSeconds;
        }

        void LateUpdate()
        {
            if (!_inRealtimeMode || !hasFreshLandmarks)
            {
                return;
            }

            if (armSide == ArmSide.Both || armSide == ArmSide.LeftOnly)
            {
                ApplyArm(leftShoulder, leftElbow, leftWrist, _latestLeft, true);
            }

            if (armSide == ArmSide.Both || armSide == ArmSide.RightOnly)
            {
                ApplyArm(rightShoulder, rightElbow, rightWrist, _latestRight, false);
            }
        }

        void OnDisable()
        {
            StopCapture();
            if (Application.isPlaying && _inRealtimeMode)
            {
                ExitRealtimeMode();
            }
        }

        void OnValidate()
        {
            if (characterRoot == null)
            {
                characterRoot = transform;
            }

            AutoResolveBones();
        }

        IEnumerator CoBoot()
        {
            if (motionRetarget == null)
            {
                motionRetarget = GetComponent<SmplhMotionRetarget>();
            }

            for (int i = 0; i < 120; i++)
            {
                AutoResolveBones();
                if (motionRetarget != null
                    && !string.IsNullOrEmpty(motionRetarget.LoadedStreamingRelativePath))
                {
                    break;
                }

                yield return null;
            }

            _bootReady = true;
            ApplyModeFromCheckbox();
        }

        void ApplyModeFromCheckbox()
        {
            if (enableRealtimeCameraArmSync)
            {
                EnterRealtimeMode();
            }
            else
            {
                ExitRealtimeMode();
            }

            _wasEnabled = enableRealtimeCameraArmSync;
        }

        void EnterRealtimeMode()
        {
            AutoResolveBones();
            if (motionRetarget != null)
            {
                motionRetarget.EnterRealtimeArmOverrideMode();
            }

            if (!_inRealtimeMode)
            {
                CacheArmBindFromCurrentPose();
                Debug.Log(
                    "[XiongdaRealtimeCameraArmSync] 模式→摄像头跟臂。"
                    + " 请运行 Pose 服务；取消勾选 Enable 可回到 JSON。");
            }

            _inRealtimeMode = true;
            debugControlMode = "REALTIME";
            status = HasRequiredBones() ? "Waiting landmarks" : "Missing arm bones";
            StartCapture();
        }

        void ExitRealtimeMode()
        {
            StopCapture();
            if (!_inRealtimeMode && motionRetarget != null && !motionRetarget.IsRealtimeArmOverrideActive)
            {
                debugControlMode = "JSON";
                status = "JSON 动作";
                return;
            }

            if (motionRetarget != null)
            {
                motionRetarget.ExitRealtimeArmOverrideMode();
            }

            _inRealtimeMode = false;
            hasFreshLandmarks = false;
            debugControlMode = "JSON";
            status = "JSON 动作";

            Debug.Log("[XiongdaRealtimeCameraArmSync] 模式→JSON 动作（Streaming Relative Path）。");
        }

        void StartCapture()
        {
            if (_pollRoutine != null)
            {
                StopCoroutine(_pollRoutine);
                _pollRoutine = null;
            }

            _pollRoutine = StartCoroutine(PollLandmarksLoop());
        }

        void StopCapture()
        {
            if (_pollRoutine != null)
            {
                StopCoroutine(_pollRoutine);
                _pollRoutine = null;
            }

            if (_webCam != null)
            {
                _webCam.Stop();
                Destroy(_webCam);
                _webCam = null;
            }
        }

        IEnumerator PollLandmarksLoop()
        {
            var wait = new WaitForSeconds(pollIntervalSeconds);
            while (_inRealtimeMode && enableRealtimeCameraArmSync)
            {
                if (!string.IsNullOrEmpty(landmarksUrl))
                {
                    using (var req = UnityWebRequest.Get(landmarksUrl))
                    {
                        yield return req.SendWebRequest();
                        if (req.isNetworkError || req.isHttpError)
                        {
                            status = "Landmark service error: " + req.error;
                        }
                        else
                        {
                            ConsumeLandmarkJson(req.downloadHandler.text);
                        }
                    }
                }

                yield return wait;
            }

            _pollRoutine = null;
        }

        void ConsumeLandmarkJson(string json)
        {
            if (string.IsNullOrEmpty(json))
            {
                return;
            }

            LandmarkResponse data = JsonUtility.FromJson<LandmarkResponse>(json);
            if (data == null || !data.ok)
            {
                status = "No valid landmarks";
                return;
            }

            bool gotAny = false;
            if (IsComplete(data.left))
            {
                _latestLeft = data.left;
                gotAny = true;
            }

            if (IsComplete(data.right))
            {
                _latestRight = data.right;
                gotAny = true;
            }

            if (gotAny)
            {
                _lastLandmarkTime = Time.time;
                status = HasRequiredBones() ? "Tracking arms" : "Missing arm bones";
            }
            else if (data.ok)
            {
                status = "Landmarks parse incomplete";
            }
        }

        static bool IsComplete(ArmLandmarks arm)
        {
            return arm != null && arm.shoulder != null && arm.elbow != null && arm.wrist != null;
        }

        void CacheArmBindFromCurrentPose()
        {
            if (leftShoulder != null) _leftShoulderBind = leftShoulder.localRotation;
            if (leftElbow != null) _leftElbowBind = leftElbow.localRotation;
            if (rightShoulder != null) _rightShoulderBind = rightShoulder.localRotation;
            if (rightElbow != null) _rightElbowBind = rightElbow.localRotation;
            _leftUpperArmBindWorldDirection = DirectionBetween(leftShoulder, leftElbow);
            _leftForearmBindWorldDirection = DirectionBetween(leftElbow, leftWrist);
            _rightUpperArmBindWorldDirection = DirectionBetween(rightShoulder, rightElbow);
            _rightForearmBindWorldDirection = DirectionBetween(rightElbow, rightWrist);
        }

        void ApplyArm(Transform shoulder, Transform elbow, Transform wrist, ArmLandmarks arm, bool left)
        {
            if (shoulder == null || elbow == null || wrist == null || !IsComplete(arm))
            {
                return;
            }

            Vector3 s = ToLocalPoint(arm.shoulder, left);
            Vector3 e = ToLocalPoint(arm.elbow, left);
            Vector3 w = ToLocalPoint(arm.wrist, left);

            Vector3 upperBindDirection = left ? _leftUpperArmBindWorldDirection : _rightUpperArmBindWorldDirection;
            Vector3 forearmBindDirection = left ? _leftForearmBindWorldDirection : _rightForearmBindWorldDirection;
            Quaternion shoulderBind = left ? _leftShoulderBind : _rightShoulderBind;
            Quaternion elbowBind = left ? _leftElbowBind : _rightElbowBind;

            ApplyFromBindDirection(shoulder, shoulderBind, upperBindDirection, e - s, shoulderLocalEulerOffset);
            ApplyFromBindDirection(elbow, elbowBind, forearmBindDirection, w - e, elbowLocalEulerOffset);
        }

        Vector3 ToLocalPoint(LandmarkPoint p, bool left)
        {
            float x = (p.x - 0.5f) * horizontalScale;
            if (mirrorInput)
            {
                x = -x;
            }

            float y = (0.5f - p.y) * verticalScale + shoulderHeight;
            float z = -p.z * depthScale;
            return new Vector3(x, y, z);
        }

        void ApplyFromBindDirection(
            Transform bone,
            Quaternion bindLocalRotation,
            Vector3 bindWorldDirection,
            Vector3 targetLocalDirection,
            Vector3 localEulerOffset)
        {
            if (bone == null || bindWorldDirection.sqrMagnitude < 0.0001f || targetLocalDirection.sqrMagnitude < 0.0001f)
            {
                return;
            }

            Quaternion parentWorld = bone.parent != null ? bone.parent.rotation : Quaternion.identity;
            Quaternion bindWorldRotation = parentWorld * bindLocalRotation;
            Vector3 targetWorldDirection = characterRoot != null
                ? characterRoot.TransformDirection(targetLocalDirection.normalized)
                : targetLocalDirection.normalized;
            Quaternion delta = Quaternion.FromToRotation(bindWorldDirection.normalized, targetWorldDirection.normalized);
            Quaternion targetWorld = delta * bindWorldRotation;
            Quaternion targetLocal = Quaternion.Inverse(parentWorld) * targetWorld * Quaternion.Euler(localEulerOffset);
            bone.localRotation = Quaternion.Slerp(bone.localRotation, targetLocal, 1f - smoothing);
        }

        static Vector3 DirectionBetween(Transform from, Transform to)
        {
            if (from == null || to == null)
            {
                return Vector3.zero;
            }

            Vector3 direction = to.position - from.position;
            return direction.sqrMagnitude > 0.0001f ? direction.normalized : Vector3.zero;
        }

        [ContextMenu("Auto Resolve Arm Bones")]
        public void AutoResolveBones()
        {
            if (characterRoot == null)
            {
                characterRoot = transform;
            }

            if (motionRetarget == null)
            {
                motionRetarget = GetComponent<SmplhMotionRetarget>();
            }

            bool resolvedFromRetarget = false;
            if (motionRetarget != null)
            {
                Transform ls = FindRetargetBone("L_Shoulder");
                Transform le = FindRetargetBone("L_Elbow");
                Transform lw = FindRetargetBone("L_Wrist");
                Transform rs = FindRetargetBone("R_Shoulder");
                Transform re = FindRetargetBone("R_Elbow");
                Transform rw = FindRetargetBone("R_Wrist");

                if (ls != null) leftShoulder = ls;
                if (le != null) leftElbow = le;
                if (lw != null) leftWrist = lw;
                if (rs != null) rightShoulder = rs;
                if (re != null) rightElbow = re;
                if (rw != null) rightWrist = rw;

                resolvedFromRetarget = ls != null || le != null || lw != null || rs != null || re != null || rw != null;
            }

            if (leftShoulder == null) leftShoulder = FindDescendantByName(characterRoot, "L_Shoulder");
            if (leftElbow == null) leftElbow = FindDescendantByName(characterRoot, "L_Elbow");
            if (leftWrist == null) leftWrist = FindDescendantByName(characterRoot, "L_Wrist");
            if (rightShoulder == null) rightShoulder = FindDescendantByName(characterRoot, "R_Shoulder");
            if (rightElbow == null) rightElbow = FindDescendantByName(characterRoot, "R_Elbow");
            if (rightWrist == null) rightWrist = FindDescendantByName(characterRoot, "R_Wrist");

            resolvedBoneSource = resolvedFromRetarget ? "SmplhMotionRetarget JSON bones" : "Hierarchy fallback";
        }

        Transform FindRetargetBone(string jointName)
        {
            if (motionRetarget == null)
            {
                return null;
            }

            Transform bone = motionRetarget.FindResolvedBoneByJointName(jointName);
            if (bone != null)
            {
                return bone;
            }

            return motionRetarget.FindResolvedBoneByPathEnd("/" + jointName);
        }

        bool HasRequiredBones()
        {
            if (armSide == ArmSide.LeftOnly)
            {
                return leftShoulder != null && leftElbow != null && leftWrist != null;
            }

            if (armSide == ArmSide.RightOnly)
            {
                return rightShoulder != null && rightElbow != null && rightWrist != null;
            }

            return leftShoulder != null && leftElbow != null && leftWrist != null
                && rightShoulder != null && rightElbow != null && rightWrist != null;
        }

        static Transform FindDescendantByName(Transform root, string targetName)
        {
            if (root == null || string.IsNullOrEmpty(targetName))
            {
                return null;
            }

            if (root.name == targetName)
            {
                return root;
            }

            for (int i = 0; i < root.childCount; i++)
            {
                Transform found = FindDescendantByName(root.GetChild(i), targetName);
                if (found != null)
                {
                    return found;
                }
            }

            return null;
        }
    }
}
