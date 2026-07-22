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
        [SerializeField] private float stuckSkipSeconds = 1.2f;
        [SerializeField] private float stuckMinProgress = 0.08f;

        private readonly List<Vector3> waypoints = new List<Vector3>();
        private int waypointIndex;
        private bool navigating;
        private Coroutine registryCoroutine;
        private Vector3 lastProgressPos;
        private float stuckTimer;

        public bool IsNavigating
        {
            get { return navigating; }
        }

        /// <summary>到达目的地时触发（供 MergedPlayModeBridge 切回互动熊）。</summary>
        public event Action NavigationFinished;

        private void Awake()
        {
            if (bearController == null)
            {
                bearController = GetComponent<ParkMapBearController>();
            }
        }

        private void Update()
        {
            if (!navigating || waypoints.Count == 0 || bearController == null)
            {
                return;
            }

            Vector3 pos = transform.position;
            Vector3 target = waypoints[waypointIndex];
            target.y = groundY;

            Vector3 to = target - pos;
            to.y = 0f;
            float dist = to.magnitude;

            if (dist <= arriveThreshold)
            {
                waypointIndex++;
                if (waypointIndex >= waypoints.Count)
                {
                    FinishNavigation();
                    return;
                }

                return;
            }

            Vector3 dir = to.normalized;
            bearController.StepAutoMove(dir);
            UpdateStuckRecovery(pos, dist);
        }

        private void UpdateStuckRecovery(Vector3 pos, float distToTarget)
        {
            Vector3 flatDelta = pos - lastProgressPos;
            flatDelta.y = 0f;
            if (flatDelta.magnitude >= stuckMinProgress)
            {
                lastProgressPos = pos;
                stuckTimer = 0f;
                return;
            }

            stuckTimer += Time.deltaTime;
            if (stuckTimer < stuckSkipSeconds)
            {
                return;
            }

            stuckTimer = 0f;
            lastProgressPos = pos;
            if (distToTarget <= arriveThreshold * 2.5f)
            {
                waypointIndex++;
                if (waypointIndex >= waypoints.Count)
                {
                    FinishNavigation();
                }

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
            for (int i = 0; i < points.Count; i++)
            {
                Vector3 p = points[i];
                p.y = groundY;
                waypoints.Add(p);
            }

            waypointIndex = 0;
            SkipReachedWaypoints();

            if (waypoints.Count == 0)
            {
                return;
            }

            navigating = true;
            stuckTimer = 0f;
            lastProgressPos = transform.position;
            if (bearController != null)
            {
                bearController.ManualControlEnabled = false;
            }

            Debug.Log("[ParkMapAutoNavigator] 开始导航，路径点 " + waypoints.Count + " 个");
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
            if (bearController != null)
            {
                bearController.StopAutoMove();
                bearController.ManualControlEnabled = true;
            }

            Debug.Log("[ParkMapAutoNavigator] 已到达目的地");
            NavigationFinished?.Invoke();
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
