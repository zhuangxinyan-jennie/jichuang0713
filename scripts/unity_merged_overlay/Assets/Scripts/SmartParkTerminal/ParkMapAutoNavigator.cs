using System;
using System.Collections;
using System.Collections.Generic;
using System.Globalization;
using System.Text.RegularExpressions;
using UnityEngine;
using UnityEngine.Networking;

namespace SmartParkTerminal
{
    /// <summary>
    /// 语音问路后沿 path_world 或 POI 名自动行走。
    /// </summary>
    [DisallowMultipleComponent]
    public sealed class ParkMapAutoNavigator : MonoBehaviour
    {
        [SerializeField] private ParkMapBearController bearController;
        [SerializeField] private float arriveThreshold = 0.85f;
        [SerializeField] private float groundY = 0.22f;
        [SerializeField] private float stuckSkipSeconds = 0.85f;
        [SerializeField] private int stuckBlockedFrames = 12;
        [SerializeField] private float snapSearchRadius = 6f;

        private readonly List<Vector3> waypoints = new List<Vector3>();
        private int waypointIndex;
        private bool navigating;
        private Coroutine registryCoroutine;
        private float stuckTimer;
        private int consecutiveBlockedFrames;
        private string destinationLabel = string.Empty;
        private CharacterController characterController;
        private Vector3 navigationDestination;

        public bool IsNavigating
        {
            get { return navigating; }
        }

        public Vector3 LastArrivalPosition { get; private set; }

        /// <summary>到达目的地时触发（供 MergedPlayModeBridge 切回互动熊）。参数为最终世界坐标。</summary>
        public event Action<Vector3> NavigationFinished;

        private void Awake()
        {
            if (bearController == null)
            {
                bearController = GetComponent<ParkMapBearController>();
            }

            characterController = GetComponent<CharacterController>();
        }

        public void SetDestinationLabel(string label)
        {
            destinationLabel = (label ?? string.Empty).Trim();
        }

        private void Update()
        {
            if (!navigating || waypoints.Count == 0 || bearController == null)
            {
                return;
            }

            Vector3 pos = transform.position;
            Vector3 target = SanitizeWaypoint(waypoints[waypointIndex]);
            waypoints[waypointIndex] = target;

            Vector3 to = target - pos;
            to.y = 0f;
            float dist = to.magnitude;

            if (dist <= arriveThreshold)
            {
                AdvanceWaypoint();
                return;
            }

            Vector3 dir = to.normalized;
            bool moved = bearController.StepAutoMove(dir);
            if (moved)
            {
                consecutiveBlockedFrames = 0;
                stuckTimer = 0f;
            }
            else
            {
                consecutiveBlockedFrames++;
                stuckTimer += Time.deltaTime;
                if (consecutiveBlockedFrames >= stuckBlockedFrames || stuckTimer >= stuckSkipSeconds)
                {
                    HandleStuck(dist);
                }
            }
        }

        private void AdvanceWaypoint()
        {
            waypointIndex++;
            consecutiveBlockedFrames = 0;
            stuckTimer = 0f;
            if (waypointIndex >= waypoints.Count)
            {
                FinishNavigation();
            }
        }

        private void HandleStuck(float distToTarget)
        {
            consecutiveBlockedFrames = 0;
            stuckTimer = 0f;

            if (distToTarget <= arriveThreshold * 2.5f)
            {
                AdvanceWaypoint();
                return;
            }

            waypointIndex++;
            if (waypointIndex >= waypoints.Count)
            {
                FinishNavigation();
                return;
            }

            Debug.LogWarning("[ParkMapAutoNavigator] 路点被阻挡，跳过 #" + (waypointIndex - 1));
        }

        public void NavigateAlongPathJson(string json)
        {
            CancelNavigationInternal(false);
            List<Vector3> parsed = ParsePathJson(json);
            if (parsed.Count == 0)
            {
                Debug.LogWarning("[ParkMapAutoNavigator] path JSON 为空或解析失败");
                return;
            }

            BeginNavigation(parsed);
        }

        public void NavigateToPlace(string placeName)
        {
            if (string.IsNullOrWhiteSpace(placeName))
            {
                return;
            }

            SetDestinationLabel(placeName.Trim());
            CancelNavigationInternal(false);
            if (registryCoroutine != null)
            {
                StopCoroutine(registryCoroutine);
            }

            registryCoroutine = StartCoroutine(LoadRegistryAndNavigate(placeName.Trim()));
        }

        public void CancelNavigation()
        {
            CancelNavigationInternal(true);
        }

        private void BeginNavigation(List<Vector3> points)
        {
            waypoints.Clear();
            Vector3? last = null;
            for (int i = 0; i < points.Count; i++)
            {
                Vector3 p = SanitizeWaypoint(points[i]);
                if (last.HasValue && (p - last.Value).sqrMagnitude < 0.04f)
                {
                    continue;
                }

                waypoints.Add(p);
                last = p;
            }

            if (waypoints.Count == 0)
            {
                return;
            }

            navigationDestination = waypoints[waypoints.Count - 1];
            waypointIndex = 0;
            SkipReachedWaypoints();

            if (waypoints.Count == 0)
            {
                return;
            }

            navigating = true;
            stuckTimer = 0f;
            consecutiveBlockedFrames = 0;
            if (bearController != null)
            {
                bearController.Configure(5.8f, 420f, groundY, 1.15f, 0.23f, 0.18f, 0.04f);
                bearController.ManualControlEnabled = false;
            }

            Debug.Log("[ParkMapAutoNavigator] 开始导航，路径点 " + waypoints.Count +
                      "，终点 " + navigationDestination);
        }

        private Vector3 SanitizeWaypoint(Vector3 point)
        {
            Vector3 p = point;
            p.y = groundY;
            ParkMapWalkability walkability = ParkMapWalkability.Instance;
            if (walkability != null)
            {
                if (!walkability.TrySnapToRoadCorridor(ref p, snapSearchRadius))
                {
                    walkability.TrySnapToWalkable(ref p, snapSearchRadius);
                }
            }

            p.y = groundY;
            return p;
        }

        private void SkipReachedWaypoints()
        {
            while (waypointIndex < waypoints.Count)
            {
                Vector3 to = waypoints[waypointIndex] - transform.position;
                to.y = 0f;
                if (to.magnitude > arriveThreshold)
                {
                    break;
                }

                waypointIndex++;
            }

            if (waypointIndex >= waypoints.Count)
            {
                FinishNavigation();
            }
        }

        private void FinishNavigation()
        {
            navigating = false;
            waypoints.Clear();
            waypointIndex = 0;
            consecutiveBlockedFrames = 0;
            stuckTimer = 0f;

            // 以路径终点为准，避免卡在起点或 snap 回城堡附近
            Vector3 pos = navigationDestination;
            if (pos.sqrMagnitude < 0.0001f)
            {
                pos = transform.position;
            }

            pos.y = groundY;
            ParkMapWalkability walkability = ParkMapWalkability.Instance;
            if (walkability != null)
            {
                if (!walkability.TrySnapToRoadCorridor(ref pos, snapSearchRadius * 2f))
                {
                    walkability.TrySnapToWalkable(ref pos, snapSearchRadius * 2f);
                }
            }

            pos.y = groundY;
            LastArrivalPosition = pos;
            ApplyPosition(pos);

            if (bearController != null)
            {
                bearController.StopAutoMove();
                bearController.ManualControlEnabled = true;
            }

            Debug.Log("[ParkMapAutoNavigator] 已到达目的地 " + pos + "（label=" + destinationLabel + "）");
            // 保持导览熊画面；切互动熊由前端在路线 TTS 播完后 ConfirmNavigationArrival
            NavigationFinished?.Invoke(pos);
            NotifyWebArrival(pos);
        }

        private void ApplyPosition(Vector3 pos)
        {
            if (characterController == null)
            {
                characterController = GetComponent<CharacterController>();
            }

            if (characterController != null)
            {
                characterController.enabled = false;
                transform.position = pos;
                characterController.enabled = true;
            }
            else
            {
                transform.position = pos;
            }
        }

        private void NotifyWebArrival(Vector3 pos)
        {
            string dest = EscapeJson(destinationLabel);
            string payload = string.Format(
                CultureInfo.InvariantCulture,
                "{{\"x\":{0:F3},\"y\":{1:F3},\"z\":{2:F3},\"destination\":\"{3}\"}}",
                pos.x,
                pos.y,
                pos.z,
                dest);
            ParkMapNavWebCallback.NotifyArrived(payload);
        }

        private static string EscapeJson(string value)
        {
            if (string.IsNullOrEmpty(value))
            {
                return string.Empty;
            }

            return value.Replace("\\", "\\\\").Replace("\"", "\\\"");
        }

        private void CancelNavigationInternal(bool reenableManual)
        {
            if (registryCoroutine != null)
            {
                StopCoroutine(registryCoroutine);
                registryCoroutine = null;
            }

            navigating = false;
            waypoints.Clear();
            waypointIndex = 0;
            consecutiveBlockedFrames = 0;
            stuckTimer = 0f;
            if (bearController != null)
            {
                bearController.StopAutoMove();
                if (reenableManual)
                {
                    bearController.ManualControlEnabled = true;
                }
            }
        }

        private IEnumerator LoadRegistryAndNavigate(string placeName)
        {
            string url = Application.streamingAssetsPath + "/poi_registry.json";
            using (UnityWebRequest req = UnityWebRequest.Get(url))
            {
                yield return req.SendWebRequest();
#if UNITY_2020_1_OR_NEWER
                if (req.result != UnityWebRequest.Result.Success)
#else
                if (req.isNetworkError || req.isHttpError)
#endif
                {
                    Debug.LogWarning("[ParkMapAutoNavigator] 无法加载 poi_registry.json: " + req.error);
                    registryCoroutine = null;
                    yield break;
                }

                string text = req.downloadHandler.text;
                Vector3? world = ParsePlaceWorld(text, placeName);
                registryCoroutine = null;
                if (!world.HasValue)
                {
                    Debug.LogWarning("[ParkMapAutoNavigator] registry 中无 POI: " + placeName);
                    yield break;
                }

                BeginNavigation(new List<Vector3> { world.Value });
            }
        }

        internal static List<Vector3> ParsePathJson(string json)
        {
            var list = new List<Vector3>();
            if (string.IsNullOrWhiteSpace(json))
            {
                return list;
            }

            MatchCollection matches = Regex.Matches(
                json,
                "\\{\\s*\"x\"\\s*:\\s*([-+0-9.eE]+)\\s*,\\s*\"y\"\\s*:\\s*([-+0-9.eE]+)\\s*,\\s*\"z\"\\s*:\\s*([-+0-9.eE]+)\\s*\\}");
            if (matches.Count == 0)
            {
                matches = Regex.Matches(
                    json,
                    "\\{\\s*\"x\"\\s*:\\s*([-+0-9.eE]+)\\s*,\\s*\"z\"\\s*:\\s*([-+0-9.eE]+)\\s*\\}");
                for (int i = 0; i < matches.Count; i++)
                {
                    Match m = matches[i];
                    float x = ParseFloat(m.Groups[1].Value);
                    float z = ParseFloat(m.Groups[2].Value);
                    list.Add(new Vector3(x, ParkMapPoiRegistryDefinitions.NavGroundY, z));
                }

                return list;
            }

            for (int i = 0; i < matches.Count; i++)
            {
                Match m = matches[i];
                float x = ParseFloat(m.Groups[1].Value);
                float y = ParseFloat(m.Groups[2].Value);
                float z = ParseFloat(m.Groups[3].Value);
                list.Add(new Vector3(x, y, z));
            }

            return list;
        }

        internal static Vector3? ParsePlaceWorld(string registryJson, string placeName)
        {
            if (string.IsNullOrEmpty(registryJson) || string.IsNullOrEmpty(placeName))
            {
                return null;
            }

            string escaped = Regex.Escape(placeName);
            Match m = Regex.Match(
                registryJson,
                "\"" + escaped + "\"\\s*:\\s*\\{[^}]*\"world\"\\s*:\\s*\\{\\s*\"x\"\\s*:\\s*([-+0-9.eE]+)\\s*,\\s*\"y\"\\s*:\\s*([-+0-9.eE]+)\\s*,\\s*\"z\"\\s*:\\s*([-+0-9.eE]+)",
                RegexOptions.Singleline);
            if (!m.Success)
            {
                return null;
            }

            return new Vector3(ParseFloat(m.Groups[1].Value), ParseFloat(m.Groups[2].Value), ParseFloat(m.Groups[3].Value));
        }

        private static float ParseFloat(string s)
        {
            return float.Parse(s, CultureInfo.InvariantCulture);
        }
    }
}
