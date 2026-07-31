using System;
using UnityEngine;
using XiongdaImporter;

namespace SmartParkTerminal
{
    /// <summary>
    /// 合并场景双熊切换：
    /// - chat：显示「互动熊」（SMPL 绑骨 + 表情），近景镜头
    /// - map：显示「导览熊」（Legacy Run + 导航），跟拍镜头
    /// WebGL: SendMessage("MergedPlayModeBridge", "SetPlayMode", "chat"|"map")
    /// 别名: SetInteractionMode
    /// Editor: C=聊天, M=地图
    /// </summary>
    [DisallowMultipleComponent]
    [DefaultExecutionOrder(200)]
    public sealed class MergedPlayModeBridge : MonoBehaviour
    {
        public const string InteractiveBearObjectName = "InteractiveXiongda";
        public const string GuideBearObjectName = "PlayableXiongda";

        public enum PlayMode
        {
            Chat = 0,
            Map = 1
        }

        [Header("相机")]
        [SerializeField] private Camera chatCamera;
        [SerializeField] private Camera mapFollowCamera;
        [SerializeField] private ParkMapThirdPersonCameraFollow mapFollow;

        [Header("互动熊（SMPL + 表情）")]
        [SerializeField] private Transform interactiveBearRoot;

        [Header("导览熊（地图跑步）")]
        [SerializeField] private Transform guideBearRoot;
        [SerializeField] private ParkMapBearController guideBearController;
        [SerializeField] private ParkMapAutoNavigator guideNavigator;

        [Header("聊天站位（随机互动 / 近景）")]
        [SerializeField] private Vector3 chatStandPosition = new Vector3(2.2f, 0.22f, -6.7f);
        [SerializeField] private float chatStandYaw = 180f;
        [SerializeField] private float chatStandScale = 0.03f;
        [SerializeField] private Vector3 chatCameraOffset = new Vector3(0f, 1.35f, 3.2f);
        [SerializeField] private float chatLookHeight = 1.05f;
        [SerializeField] private float chatFieldOfView = 35f;

        [Header("导览熊（地图模式）")]
        [SerializeField] private float mapGroundY = 0.22f;
        [Tooltip("聊天站位在水域时，导览熊吸附失败则落在此（方特城堡门口道路）")]
        [SerializeField] private Vector3 mapFallbackSpawn = new Vector3(-1.612f, 0.22f, -5.549f);
        [SerializeField] private float mapSnapSearchRadius = 12f;

        [Header("启动")]
        [SerializeField] private PlayMode startMode = PlayMode.Chat;
        [Tooltip("导览到达目的地后自动切回聊天，并把互动熊对齐到导览熊位置")]
        [SerializeField] private bool autoChatAfterNavigation = false;
        [Tooltip("为 true：首次进场景用固定聊天站位；之后切回聊天时跟随导览熊最后位置")]
        [SerializeField] private bool followGuidePositionWhenEnteringChat = true;

        private PlayMode current = PlayMode.Chat;
        private CharacterController guideCc;
        private bool subscribedNav;
        /** 导览熊已参与地图/导航后，聊天模式应站在导览熊处而非固定点 */
        private bool guidePositionIsAuthoritative;
        /** 最近一次导航终点（问路到达海螺湾等），切回互动熊时优先用此坐标 */
        private Vector3? lastNavigationArrivalWorld;

        public PlayMode CurrentMode
        {
            get { return current; }
        }

        public event Action<PlayMode> OnModeChanged;

        private void Awake()
        {
            EnsureRefs();
            EnsureChatCamera();
            ApplyMode(startMode, true);
        }

        private void Start()
        {
            EnsureRefs();
            SubscribeNavigator();
            ApplyMode(startMode, true);
        }

        private void OnDestroy()
        {
            UnsubscribeNavigator();
        }

        private void Update()
        {
            if (!Application.isEditor)
            {
                return;
            }

            if (Input.GetKeyDown(KeyCode.C))
            {
                ApplyMode(PlayMode.Chat, true);
            }
            else if (Input.GetKeyDown(KeyCode.M))
            {
                ApplyMode(PlayMode.Map, true);
            }
        }

        private void LateUpdate()
        {
            if (current != PlayMode.Chat || chatCamera == null)
            {
                return;
            }

            Transform target = GetChatCameraTarget();
            if (target == null)
            {
                return;
            }

            PlaceChatCamera(target);
            DisableMapCamera();
            if (chatCamera != null && !chatCamera.enabled)
            {
                chatCamera.enabled = true;
            }
        }

        /// <summary>
        /// 导览熊默认隐藏时 GameObject.Find / FindObjectOfType 找不到，需扫 inactive。
        /// </summary>
        public static Transform FindSceneTransformByName(string objectName)
        {
            if (string.IsNullOrEmpty(objectName))
            {
                return null;
            }

            var all = Resources.FindObjectsOfTypeAll<Transform>();
            for (int i = 0; i < all.Length; i++)
            {
                Transform t = all[i];
                if (t == null || t.name != objectName)
                {
                    continue;
                }

                if (!t.gameObject.scene.IsValid())
                {
                    continue;
                }

                return t;
            }

            return null;
        }

        public static ParkMapBearController FindSceneGuideBearController()
        {
            var all = Resources.FindObjectsOfTypeAll<ParkMapBearController>();
            for (int i = 0; i < all.Length; i++)
            {
                ParkMapBearController ctrl = all[i];
                if (ctrl == null)
                {
                    continue;
                }

                if (!ctrl.gameObject.scene.IsValid())
                {
                    continue;
                }

                if (ctrl.gameObject.name == InteractiveBearObjectName)
                {
                    continue;
                }

                return ctrl;
            }

            return null;
        }

        private void EnsureRefs()
        {
            if (interactiveBearRoot == null)
            {
                Transform t = FindSceneTransformByName(InteractiveBearObjectName);
                if (t != null)
                {
                    interactiveBearRoot = t;
                }
            }

            if (guideBearRoot == null)
            {
                Transform t = FindSceneTransformByName(GuideBearObjectName);
                if (t != null)
                {
                    guideBearRoot = t;
                }
            }

            if (guideBearController == null && guideBearRoot != null)
            {
                guideBearController = guideBearRoot.GetComponent<ParkMapBearController>();
            }

            if (guideBearController == null)
            {
                guideBearController = FindSceneGuideBearController();
                if (guideBearController != null)
                {
                    guideBearRoot = guideBearController.transform;
                }
            }

            if (guideNavigator == null && guideBearRoot != null)
            {
                guideNavigator = guideBearRoot.GetComponent<ParkMapAutoNavigator>();
            }

            if (mapFollow == null)
            {
                mapFollow = FindObjectOfType<ParkMapThirdPersonCameraFollow>();
            }

            if (mapFollowCamera == null && mapFollow != null)
            {
                mapFollowCamera = mapFollow.GetComponent<Camera>();
                if (mapFollowCamera == null)
                {
                    mapFollowCamera = mapFollow.GetComponentInChildren<Camera>();
                }
            }

            if (mapFollowCamera == null)
            {
                var main = Camera.main;
                if (main != null && (chatCamera == null || main != chatCamera))
                {
                    mapFollowCamera = main;
                }
            }

            if (guideBearRoot != null)
            {
                guideCc = guideBearRoot.GetComponent<CharacterController>();
            }

            SubscribeNavigator();
        }

        private void SubscribeNavigator()
        {
            if (subscribedNav || guideNavigator == null)
            {
                return;
            }

            guideNavigator.NavigationFinished += OnGuideNavigationFinished;
            subscribedNav = true;
        }

        private void UnsubscribeNavigator()
        {
            if (!subscribedNav || guideNavigator == null)
            {
                return;
            }

            guideNavigator.NavigationFinished -= OnGuideNavigationFinished;
            subscribedNav = false;
        }

        private void OnGuideNavigationFinished(Vector3 arrivalWorld)
        {
            lastNavigationArrivalWorld = arrivalWorld;
            guidePositionIsAuthoritative = true;
            ApplyGuideBearPosition(arrivalWorld);
            WarpInteractiveBearToWorld(arrivalWorld, GetGuideFacingOrDefault());
            if (autoChatAfterNavigation)
            {
                ApplyMode(PlayMode.Chat, true);
            }
        }

        /// <summary>WebGL：前端收到到达上报后再次锁定互动熊到终点（防重复 SetPlayMode 把熊拉回城堡）。</summary>
        public void ConfirmNavigationArrival(string payloadJson)
        {
            EnsureRefs();
            if (!TryParseArrivalJson(payloadJson, out Vector3 pos))
            {
                return;
            }

            lastNavigationArrivalWorld = pos;
            guidePositionIsAuthoritative = true;
            ApplyGuideBearPosition(pos);
            WarpInteractiveBearToWorld(pos, GetGuideFacingOrDefault());

            if (current != PlayMode.Chat)
            {
                ApplyMode(PlayMode.Chat, false);
            }
            else
            {
                PlaceInteractiveBearForChatMode();
            }

            Debug.Log("[MergedPlayModeBridge] ConfirmNavigationArrival → " + pos);
        }

        private static bool TryParseArrivalJson(string json, out Vector3 pos)
        {
            pos = Vector3.zero;
            if (string.IsNullOrWhiteSpace(json))
            {
                return false;
            }

            var match = System.Text.RegularExpressions.Regex.Match(
                json,
                "\"x\"\\s*:\\s*([-+0-9.eE]+)\\s*,\\s*\"y\"\\s*:\\s*([-+0-9.eE]+)\\s*,\\s*\"z\"\\s*:\\s*([-+0-9.eE]+)",
                System.Text.RegularExpressions.RegexOptions.Singleline);
            if (!match.Success)
            {
                return false;
            }

            try
            {
                float x = float.Parse(match.Groups[1].Value, System.Globalization.CultureInfo.InvariantCulture);
                float y = float.Parse(match.Groups[2].Value, System.Globalization.CultureInfo.InvariantCulture);
                float z = float.Parse(match.Groups[3].Value, System.Globalization.CultureInfo.InvariantCulture);
                pos = new Vector3(x, y > 0.001f ? y : 0.22f, z);
                return true;
            }
            catch
            {
                return false;
            }
        }

        private Quaternion GetGuideFacingOrDefault()
        {
            if (guideBearRoot != null)
            {
                return guideBearRoot.rotation;
            }

            return Quaternion.Euler(0f, chatStandYaw, 0f);
        }

        private void EnsureChatCamera()
        {
            if (chatCamera != null)
            {
                chatCamera.depth = 50f;
                chatCamera.fieldOfView = chatFieldOfView;
                return;
            }

            var existing = GameObject.Find("ChatCamera");
            if (existing != null)
            {
                chatCamera = existing.GetComponent<Camera>();
            }

            if (chatCamera == null)
            {
                var go = new GameObject("ChatCamera");
                chatCamera = go.AddComponent<Camera>();
                chatCamera.nearClipPlane = 0.05f;
                chatCamera.farClipPlane = 200f;
            }

            chatCamera.fieldOfView = chatFieldOfView;
            chatCamera.depth = 50f;
        }

        /// <summary>WebGL: "chat" or "map"</summary>
        public void SetPlayMode(string mode)
        {
            SetInteractionMode(mode);
        }

        /// <summary>WebGL alias from plan.</summary>
        public void SetInteractionMode(string mode)
        {
            EnsureRefs();
            EnsureChatCamera();
            string m = (mode ?? string.Empty).Trim().ToLowerInvariant();
            if (m == "map" || m == "navigate" || m == "nav")
            {
                ApplyMode(PlayMode.Map, true);
            }
            else
            {
                ApplyMode(PlayMode.Chat, true);
            }
        }

        public void ApplyMode(PlayMode mode, bool log)
        {
            EnsureRefs();
            EnsureChatCamera();
            current = mode;
            bool map = mode == PlayMode.Map;

            if (map)
            {
                EnterMapMode();
            }
            else
            {
                EnterChatMode();
            }

            OnModeChanged?.Invoke(mode);

            if (log)
            {
                Debug.Log("[MergedPlayModeBridge] mode=" + mode +
                          (map ? "（导览熊 · 可跑）" : "（互动熊 · " +
                           (guidePositionIsAuthoritative ? "跟随导览位置" : "固定站位") + "）") +
                          " interactive=" + (interactiveBearRoot != null) +
                          " guide=" + (guideBearRoot != null));
            }
        }

        private void EnterChatMode()
        {
            if (guideBearController != null)
            {
                if (guideNavigator != null && guideNavigator.IsNavigating)
                {
                    guideNavigator.CancelNavigation();
                }

                guideBearController.ManualControlEnabled = false;
                guideBearController.StopAutoMove();
            }

            SetBearVisible(guideBearRoot, false);
            SetBearVisible(interactiveBearRoot, true);

            PlaceInteractiveBearForChatMode();
            DisableMapCamera();

            if (chatCamera != null)
            {
                chatCamera.enabled = true;
                chatCamera.fieldOfView = chatFieldOfView;
                chatCamera.depth = 50f;
            }

            Transform camTarget = GetChatCameraTarget();
            if (camTarget != null)
            {
                PlaceChatCamera(camTarget);
            }
        }

        private void EnterMapMode()
        {
            EnsureRefs();
            bool navigating = guideNavigator != null && guideNavigator.IsNavigating;
            if (!navigating)
            {
                guidePositionIsAuthoritative = true;
                lastNavigationArrivalWorld = null;
                SyncGuideToInteractive();
                SnapGuideBearToWalkableGround();
                if (guideBearController != null)
                {
                    guideBearController.Configure(5.8f, 420f, mapGroundY, 1.15f, 0.23f, 0.18f, 0.04f);
                }
            }
            else
            {
                Debug.Log("[MergedPlayModeBridge] 导航进行中，不重置导览熊位置");
            }

            SetBearVisible(interactiveBearRoot, false);
            SetBearVisible(guideBearRoot, true);

            if (guideBearController != null)
            {
                guideBearController.ManualControlEnabled = true;
            }

            if (chatCamera != null)
            {
                chatCamera.enabled = false;
            }

            if (mapFollow != null)
            {
                mapFollow.enabled = true;
                if (guideBearRoot != null)
                {
                    mapFollow.Configure(guideBearRoot);
                }
            }

            if (mapFollowCamera != null)
            {
                mapFollowCamera.enabled = true;
                mapFollowCamera.depth = 0f;
            }
        }

        /** 聊天站位常落在喷泉水域；切地图时把导览熊吸到最近灰色道路。 */
        private void SnapGuideBearToWalkableGround()
        {
            if (guideBearRoot == null)
            {
                return;
            }

            Vector3 pos = guideBearRoot.position;
            Vector3 before = pos;
            if (!TrySnapGuidePosition(ref pos, mapFallbackSpawn, mapSnapSearchRadius, mapGroundY))
            {
                pos = mapFallbackSpawn;
                pos.y = mapGroundY;
            }

            ApplyGuideBearPosition(pos);

            if ((pos - before).sqrMagnitude > 0.04f)
            {
                Debug.Log("[MergedPlayModeBridge] 导览熊已从不可走区域移到: " + pos);
            }
        }

        public static bool TrySnapGuidePosition(
            ref Vector3 worldPosition,
            Vector3 fallback,
            float searchRadius,
            float groundY)
        {
            worldPosition.y = groundY;
            ParkMapWalkability walkability = ParkMapWalkability.Instance;
            if (walkability == null)
            {
                worldPosition = fallback;
                worldPosition.y = groundY;
                return false;
            }

            if (walkability.IsWalkable(worldPosition))
            {
                return true;
            }

            if (walkability.TrySnapToRoadCorridor(ref worldPosition, searchRadius))
            {
                worldPosition.y = groundY;
                return true;
            }

            if (walkability.TrySnapToWalkable(ref worldPosition, searchRadius))
            {
                worldPosition.y = groundY;
                return true;
            }

            worldPosition = fallback;
            worldPosition.y = groundY;
            return false;
        }

        private void ApplyGuideBearPosition(Vector3 pos)
        {
            if (guideBearRoot == null)
            {
                return;
            }

            if (guideCc == null)
            {
                guideCc = guideBearRoot.GetComponent<CharacterController>();
            }

            if (guideCc != null)
            {
                guideCc.enabled = false;
                guideBearRoot.position = pos;
                guideCc.enabled = true;
            }
            else
            {
                guideBearRoot.position = pos;
            }
        }

        private Transform GetChatCameraTarget()
        {
            return interactiveBearRoot != null ? interactiveBearRoot : guideBearRoot;
        }

        private void DisableMapCamera()
        {
            if (mapFollow != null)
            {
                mapFollow.enabled = false;
            }

            if (mapFollowCamera != null)
            {
                mapFollowCamera.enabled = false;
            }
        }

        private static void SetBearVisible(Transform root, bool visible)
        {
            if (root == null)
            {
                return;
            }

            root.gameObject.SetActive(visible);
        }

        private void SyncGuideToInteractive()
        {
            if (interactiveBearRoot == null || guideBearRoot == null)
            {
                return;
            }

            CopyTransform(interactiveBearRoot, guideBearRoot, guideCc);
        }

        private void SyncInteractiveToGuide()
        {
            if (interactiveBearRoot == null || guideBearRoot == null)
            {
                return;
            }

            CopyTransform(guideBearRoot, interactiveBearRoot, null);
        }

        /** 聊天模式：首次用固定站位；问路/导览后站在导航终点（海螺湾等） */
        private void PlaceInteractiveBearForChatMode()
        {
            if (interactiveBearRoot == null)
            {
                return;
            }

            if (lastNavigationArrivalWorld.HasValue)
            {
                WarpInteractiveBearToWorld(lastNavigationArrivalWorld.Value, GetGuideFacingOrDefault());
                return;
            }

            if (followGuidePositionWhenEnteringChat
                && guidePositionIsAuthoritative
                && guideBearRoot != null)
            {
                SyncInteractiveToGuide();
                interactiveBearRoot.localScale = Vector3.one * chatStandScale;
                RecaptureInteractiveSmplRootBase();
                return;
            }

            WarpInteractiveToChatStand();
        }

        private void WarpInteractiveBearToWorld(Vector3 worldPos, Quaternion rotation)
        {
            if (interactiveBearRoot == null)
            {
                return;
            }

            worldPos.y = mapGroundY;
            interactiveBearRoot.SetPositionAndRotation(worldPos, rotation);
            interactiveBearRoot.localScale = Vector3.one * chatStandScale;
            RecaptureInteractiveSmplRootBase();
        }

        /** SMPL 根位移基准在 Awake 时锁定；挪到海螺湾等终点后必须刷新，否则下一帧动作会把熊拉回城堡。 */
        private void RecaptureInteractiveSmplRootBase()
        {
            if (interactiveBearRoot == null)
            {
                return;
            }

            SmplhMotionRetarget retarget = interactiveBearRoot.GetComponent<SmplhMotionRetarget>();
            if (retarget != null)
            {
                retarget.RecaptureRootTransformBase();
            }
        }

        private void WarpInteractiveToChatStand()
        {
            if (interactiveBearRoot == null)
            {
                return;
            }

            Vector3 pos = chatStandPosition;
            Quaternion rot = Quaternion.Euler(0f, chatStandYaw, 0f);
            interactiveBearRoot.SetPositionAndRotation(pos, rot);
            interactiveBearRoot.localScale = Vector3.one * chatStandScale;
        }

        private static void CopyTransform(Transform from, Transform to, CharacterController cc)
        {
            if (from == null || to == null)
            {
                return;
            }

            if (cc != null)
            {
                cc.enabled = false;
                to.SetPositionAndRotation(from.position, from.rotation);
                cc.enabled = true;
            }
            else
            {
                to.SetPositionAndRotation(from.position, from.rotation);
            }
        }

        private void PlaceChatCamera(Transform bear)
        {
            if (chatCamera == null || bear == null)
            {
                return;
            }

            Vector3 flatForward = bear.forward;
            flatForward.y = 0f;
            if (flatForward.sqrMagnitude < 0.0001f)
            {
                flatForward = Vector3.forward;
            }

            flatForward.Normalize();
            Vector3 right = Vector3.Cross(Vector3.up, flatForward).normalized;

            Vector3 camPos =
                bear.position
                + Vector3.up * chatCameraOffset.y
                + flatForward * chatCameraOffset.z
                + right * chatCameraOffset.x;

            chatCamera.transform.position = camPos;
            Vector3 look = bear.position + Vector3.up * chatLookHeight;
            chatCamera.transform.rotation = Quaternion.LookRotation((look - camPos).normalized, Vector3.up);
        }
    }
}
