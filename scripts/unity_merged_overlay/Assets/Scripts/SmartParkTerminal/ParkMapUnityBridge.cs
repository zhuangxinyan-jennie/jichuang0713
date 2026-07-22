using UnityEngine;

namespace SmartParkTerminal
{
    /// <summary>
    /// 网页地图 WebGL 通信桥：React 中
    /// unityInstance.SendMessage("ParkMapUnityBridge", "NavigateAlongPathJson", json)
    /// </summary>
    [DisallowMultipleComponent]
    public sealed class ParkMapUnityBridge : MonoBehaviour
    {
        [SerializeField] private ParkMapBearController bearController;
        [SerializeField] private ParkMapAutoNavigator autoNavigator;

        private void Awake()
        {
            EnsureReferences();
            ParkMapCollisionPolicy.Apply();
        }

        private void Start()
        {
            EnsureReferences();
        }

        private void EnsureReferences()
        {
            if (bearController == null)
            {
                var guide = GameObject.Find(MergedPlayModeBridge.GuideBearObjectName);
                if (guide != null)
                {
                    bearController = guide.GetComponent<ParkMapBearController>();
                }
            }

            if (bearController == null)
            {
                bearController = FindObjectOfType<ParkMapBearController>();
            }

            if (autoNavigator == null && bearController != null)
            {
                autoNavigator = bearController.GetComponent<ParkMapAutoNavigator>();
                if (autoNavigator == null)
                {
                    autoNavigator = bearController.gameObject.AddComponent<ParkMapAutoNavigator>();
                }
            }
        }

        /// <summary>WebGL：沿 Agent 下发的 path_world 行走。</summary>
        public void NavigateAlongPathJson(string json)
        {
            EnsureReferences();
            if (autoNavigator == null)
            {
                Debug.LogWarning("[ParkMapUnityBridge] 无 ParkMapAutoNavigator");
                return;
            }

            Debug.Log("[ParkMapUnityBridge] NavigateAlongPathJson");
            autoNavigator.NavigateAlongPathJson(json);
        }

        /// <summary>WebGL：按中文地名查 registry 后走过去。</summary>
        public void NavigateToPlace(string placeName)
        {
            EnsureReferences();
            if (autoNavigator == null)
            {
                Debug.LogWarning("[ParkMapUnityBridge] 无 ParkMapAutoNavigator");
                return;
            }

            Debug.Log("[ParkMapUnityBridge] NavigateToPlace: " + placeName);
            autoNavigator.NavigateToPlace(placeName);
        }

        /// <summary>取消当前自动导航。</summary>
        public void CancelNavigation(string unused)
        {
            EnsureReferences();
            if (autoNavigator != null)
            {
                autoNavigator.CancelNavigation();
            }
        }

        /// <summary>调试用：网页可 SendMessage 验证 WebGL 桥已连通。</summary>
        public void Ping(string message)
        {
            Debug.Log("[ParkMapUnityBridge] Ping: " + (message ?? ""));
        }
    }
}
