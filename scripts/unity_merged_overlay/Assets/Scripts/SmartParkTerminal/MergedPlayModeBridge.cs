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

        [Header("启动")]
        [SerializeField] private PlayMode startMode = PlayMode.Chat;
        [Tooltip("导览到达目的地后自动切回聊天，并把互动熊对齐到导览熊位置")]
        [SerializeField] private bool autoChatAfterNavigation = true;
        [Tooltip("为 true：首次进场景用固定聊天站位；之后切回聊天时跟随导览熊最后位置")]
        [SerializeField] private bool followGuidePositionWhenEnteringChat = true;

        private PlayMode current = PlayMode.Chat;
        private CharacterController guideCc;
        private bool subscribedNav;
        /** 导览熊已参与地图/导航后，聊天模式应站在导览熊处而非固定点 */
        private bool guidePositionIsAuthoritative;

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

        private void EnsureRefs()
        {
            if (interactiveBearRoot == null)
            {
                var go = GameObject.Find(InteractiveBearObjectName);
                if (go != null)
                {
                    interactiveBearRoot = go.transform;
                }
            }

            if (guideBearRoot == null)
            {
                var go = GameObject.Find(GuideBearObjectName);
                if (go != null)
                {
                    guideBearRoot = go.transform;
                }
            }

            if (guideBearController == null && guideBearRoot != null)
            {
                guideBearController = guideBearRoot.GetComponent<ParkMapBearController>();
            }

            if (guideBearController == null)
            {
                guideBearController = FindObjectOfType<ParkMapBearController>();
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

        private void OnGuideNavigationFinished()
        {
            guidePositionIsAuthoritative = true;
            SyncInteractiveToGuide();
            if (autoChatAfterNavigation)
            {
                ApplyMode(PlayMode.Chat, true);
            }
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
                if (guideNavigator != null)
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
            guidePositionIsAuthoritative = true;
            SyncGuideToInteractive();

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

        /** 聊天模式：首次用固定站位；问路/导览后站在导览熊最后位置 */
        private void PlaceInteractiveBearForChatMode()
        {
            if (interactiveBearRoot == null)
            {
                return;
            }

            if (followGuidePositionWhenEnteringChat
                && guidePositionIsAuthoritative
                && guideBearRoot != null)
            {
                SyncInteractiveToGuide();
                interactiveBearRoot.localScale = Vector3.one * chatStandScale;
                return;
            }

            WarpInteractiveToChatStand();
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
