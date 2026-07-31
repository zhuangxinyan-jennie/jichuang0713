using UnityEngine;

namespace XiongdaImporter
{
    [DisallowMultipleComponent]
    public sealed class XiongdaPlayOnStart : MonoBehaviour
    {
        [SerializeField] private string clipName = "Run";

        private void Start()
        {
            if (GetComponent<XiongdaMainMenuShowcase>() != null)
            {
                return;
            }

            var animationComponent = GetComponent<Animation>();
            if (animationComponent == null)
            {
                return;
            }

            var clip = animationComponent.GetClip(clipName);
            if (clip == null)
            {
                clip = animationComponent.clip;
            }

            if (clip == null)
            {
                return;
            }

            animationComponent.wrapMode = WrapMode.Loop;
            animationComponent.clip = clip;
            animationComponent.Play(clip.name);
        }
    }
}
