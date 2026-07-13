using UnityEngine;

namespace SmartParkTerminal
{
    /// <summary>页面 GameObject 显隐</summary>
    public sealed class PageManager : MonoBehaviour
    {
        public const string PageCharacter = "character";
        public const string PageMap = "map";
        public const string PageRecommendation = "recommendation";
        public const string PageSystem = "system";

        [SerializeField]
        private GameObject characterPage;

        [SerializeField]
        private GameObject mapPage;

        [SerializeField]
        private GameObject recommendationPage;

        [SerializeField]
        private GameObject systemPage;

        private void Awake()
        {
            HideAllPages();
            if (characterPage != null)
            {
                characterPage.SetActive(true);
            }
        }

        public void HideAllPages()
        {
            SetActiveSafe(characterPage, false);
            SetActiveSafe(mapPage, false);
            SetActiveSafe(recommendationPage, false);
            SetActiveSafe(systemPage, false);
        }

        public void ShowPage(string pageName)
        {
            HideAllPages();
            switch ((pageName ?? "").Trim().ToLowerInvariant())
            {
                case PageCharacter:
                case "":
                    SetActiveSafe(characterPage, true);
                    break;
                case PageMap:
                    SetActiveSafe(mapPage, true);
                    break;
                case PageRecommendation:
                case "recommend":
                    SetActiveSafe(recommendationPage, true);
                    break;
                case PageSystem:
                case "debug":
                    SetActiveSafe(systemPage, true);
                    break;
                default:
                    SetActiveSafe(characterPage, true);
                    break;
            }
        }

        private static void SetActiveSafe(GameObject go, bool v)
        {
            if (go != null)
            {
                go.SetActive(v);
            }
        }
    }
}
