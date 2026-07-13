using System.Collections.Generic;
using TMPro;
using UnityEngine;

namespace SmartParkTerminal
{
    /// <summary>地图 POI 与高亮（第一版：UI 占位图 + 亮点）</summary>
    public sealed class MapUIController : MonoBehaviour
    {
        [SerializeField]
        private GameObject mapRoot;

        [SerializeField]
        private Transform poiHighlightRoot;

        [SerializeField]
        private TextMeshProUGUI mapInfoText;

        private readonly Dictionary<string, GameObject> _poiHighlightById = new Dictionary<string, GameObject>();

        private void Awake()
        {
            CacheHighlights();
        }

        public void Bind(TextMeshProUGUI info)
        {
            mapInfoText = info;
        }

        private void CacheHighlights()
        {
            _poiHighlightById.Clear();
            if (poiHighlightRoot == null)
            {
                return;
            }

            for (int i = 0; i < poiHighlightRoot.childCount; i++)
            {
                Transform c = poiHighlightRoot.GetChild(i);
                string key = c.name.ToLowerInvariant();
                _poiHighlightById[key] = c.gameObject;
            }
        }

        public void ClearHighlights()
        {
            foreach (var kv in _poiHighlightById)
            {
                if (kv.Value != null)
                {
                    kv.Value.SetActive(false);
                }
            }
        }

        public void ShowPOI(string poiId)
        {
            ClearHighlights();
            if (string.IsNullOrEmpty(poiId))
            {
                return;
            }

            string key = poiId.Trim().ToLowerInvariant();
            if (_poiHighlightById.TryGetValue(key, out GameObject go) && go != null)
            {
                go.SetActive(true);
            }
        }

        public void SetMapInfo(string text)
        {
            if (mapInfoText != null)
            {
                mapInfoText.text = text ?? "";
            }
        }

        public string GetPoiDisplayName(string poiId)
        {
            switch ((poiId ?? "").Trim().ToLowerInvariant())
            {
                case "carousel":
                    return "旋转木马";
                case "roller_coaster":
                    return "过山车";
                case "food_area":
                    return "餐饮区";
                case "restroom":
                    return "卫生间";
                case "exit":
                    return "出口";
                case "xiongda_zone":
                    return "熊大互动区";
                default:
                    return poiId ?? "";
            }
        }

        public void SimulateCarousel()
        {
            ShowPOI("carousel");
            SetMapInfo("旋转木马：园区东侧主路旁。");
        }

        public void SimulateRollerCoaster()
        {
            ShowPOI("roller_coaster");
            SetMapInfo("过山车：动感地带核心区。");
        }

        public void SimulateFoodArea()
        {
            ShowPOI("food_area");
            SetMapInfo("餐饮区： Central Plaza 北侧。");
        }

        public void SimulateRestroom()
        {
            ShowPOI("restroom");
            SetMapInfo("卫生间：各主题区均有指示牌。");
        }

        public void SimulateExit()
        {
            ShowPOI("exit");
            SetMapInfo("出口：请跟随地面绿色指引标识。");
        }

        public void SimulateXiongdaZone()
        {
            ShowPOI("xiongda_zone");
            SetMapInfo("熊大互动区：您当前所在位置附近。");
        }
    }
}
