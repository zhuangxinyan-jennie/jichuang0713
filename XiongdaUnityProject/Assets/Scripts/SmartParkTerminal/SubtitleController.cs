using System.Collections;
using TMPro;
using UnityEngine;

namespace SmartParkTerminal
{
    /// <summary>底部字幕栏（对话风格）</summary>
    public sealed class SubtitleController : MonoBehaviour
    {
        [SerializeField]
        private TextMeshProUGUI subtitleText;

        private Coroutine _tempRoutine;

        public void BindSubtitleText(TextMeshProUGUI text)
        {
            subtitleText = text;
        }

        public void ShowSpeech(string speech)
        {
            if (_tempRoutine != null)
            {
                StopCoroutine(_tempRoutine);
                _tempRoutine = null;
            }

            if (subtitleText == null)
            {
                return;
            }

            subtitleText.text = string.IsNullOrEmpty(speech) ? "" : speech;
        }

        public void ClearSpeech()
        {
            if (_tempRoutine != null)
            {
                StopCoroutine(_tempRoutine);
                _tempRoutine = null;
            }

            if (subtitleText != null)
            {
                subtitleText.text = "";
            }
        }

        public void ShowTemporarySpeech(string speech, float duration)
        {
            if (subtitleText == null)
            {
                return;
            }

            if (_tempRoutine != null)
            {
                StopCoroutine(_tempRoutine);
            }

            _tempRoutine = StartCoroutine(TempSpeechRoutine(speech, duration));
        }

        private IEnumerator TempSpeechRoutine(string speech, float duration)
        {
            subtitleText.text = speech ?? "";
            yield return new WaitForSeconds(Mathf.Max(0.1f, duration));
            subtitleText.text = "";
            _tempRoutine = null;
        }
    }
}
