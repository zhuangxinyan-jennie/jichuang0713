using TMPro;
using UnityEngine;
using UnityEngine.UI;

namespace SmartParkTerminal
{
    /// <summary>推荐卡片（假数据 + 详情展示）</summary>
    public sealed class RecommendationUIController : MonoBehaviour
    {
        [SerializeField]
        private TextMeshProUGUI titleText;

        [SerializeField]
        private TextMeshProUGUI reasonText;

        [SerializeField]
        private TextMeshProUGUI queueTimeText;

        [SerializeField]
        private TextMeshProUGUI targetGroupText;

        [SerializeField]
        private Button cardCarouselButton;

        [SerializeField]
        private Button cardTrainButton;

        [SerializeField]
        private Button cardCoasterButton;

        private SmartTerminalController _terminal;

        private void Awake()
        {
            _terminal = FindObjectOfType<SmartTerminalController>();
        }

        public void BindDetailTexts(TextMeshProUGUI title, TextMeshProUGUI reason, TextMeshProUGUI queue, TextMeshProUGUI group)
        {
            titleText = title;
            reasonText = reason;
            queueTimeText = queue;
            targetGroupText = group;
        }

        public void BindCardButtons(Button carousel, Button train, Button coaster)
        {
            cardCarouselButton = carousel;
            cardTrainButton = train;
            cardCoasterButton = coaster;
        }

        public void WireCardClicks(SmartTerminalController terminal)
        {
            _terminal = terminal;
            if (cardCarouselButton != null)
            {
                cardCarouselButton.onClick.RemoveAllListeners();
                cardCarouselButton.onClick.AddListener(RecommendCarousel);
            }

            if (cardTrainButton != null)
            {
                cardTrainButton.onClick.RemoveAllListeners();
                cardTrainButton.onClick.AddListener(RecommendTrain);
            }

            if (cardCoasterButton != null)
            {
                cardCoasterButton.onClick.RemoveAllListeners();
                cardCoasterButton.onClick.AddListener(RecommendRollerCoaster);
            }
        }

        public void ShowRecommendation(RecommendationData data)
        {
            if (data == null)
            {
                ClearDetail();
                return;
            }

            if (titleText != null)
            {
                titleText.text = data.name ?? "";
            }

            if (reasonText != null)
            {
                reasonText.text = data.reason ?? "";
            }

            if (queueTimeText != null)
            {
                queueTimeText.text = string.IsNullOrEmpty(data.queue_time) ? "" : "预计等待：" + data.queue_time;
            }

            if (targetGroupText != null)
            {
                targetGroupText.text = string.IsNullOrEmpty(data.target_group) ? "" : "适合：" + data.target_group;
            }
        }

        public void ClearDetail()
        {
            ShowRecommendation(new RecommendationData());
        }

        public void ShowDefaultRecommendations()
        {
            ClearDetail();
            if (titleText != null)
            {
                titleText.text = "点击下方卡片体验推荐";
            }
        }

        public void RecommendCarousel()
        {
            var d = new RecommendationData
            {
                name = "旋转木马",
                reason = "适合亲子互动，节奏舒缓。",
                queue_time = "8 分钟",
                target_group = "亲子家庭"
            };
            ShowRecommendation(d);
            NotifyTerminalRecommendation(d);
        }

        public void RecommendTrain()
        {
            var d = new RecommendationData
            {
                name = "森林小火车",
                reason = "路线轻松，适合休息观览。",
                queue_time = "5 分钟",
                target_group = "全年龄"
            };
            ShowRecommendation(d);
            NotifyTerminalRecommendation(d);
        }

        public void RecommendRollerCoaster()
        {
            var d = new RecommendationData
            {
                name = "过山车",
                reason = "刺激项目，动感体验。",
                queue_time = "20 分钟",
                target_group = "年轻游客"
            };
            ShowRecommendation(d);
            NotifyTerminalRecommendation(d);
        }

        private void NotifyTerminalRecommendation(RecommendationData data)
        {
            if (_terminal == null)
            {
                _terminal = FindObjectOfType<SmartTerminalController>();
            }

            if (_terminal == null)
            {
                return;
            }

            var cmd = new TerminalCommand
            {
                module = "recommendation",
                speech = "我推荐你试试「" + (data.name ?? "") + "」。",
                clip_id = "talk_gesture_small",
                emotion = "smile",
                recommendation = data
            };
            _terminal.DispatchCommand(cmd, serializeJson: true);
        }
    }
}
