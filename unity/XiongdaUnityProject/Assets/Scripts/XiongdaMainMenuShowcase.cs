using UnityEngine;

namespace XiongdaImporter
{
    [DisallowMultipleComponent]
    public sealed class XiongdaMainMenuShowcase : MonoBehaviour
    {
        [SerializeField] private string introClipName = "Sit2";
        [SerializeField] private string idleClipName = "Idle2";
        [SerializeField] private string fallbackIdleClipName = "Idle";
        [SerializeField] private string specialClipName = "Pose2";
        [SerializeField] private float queuedLoopLeadTime = 0.08f;
        [SerializeField] private bool enableKeyboardPreview = true;

        private Animation animationComponent;
        private string queuedLoopPrimary;
        private string queuedLoopFallback;
        private string watchedStateName;

        private void Awake()
        {
            animationComponent = GetComponent<Animation>();
            ConfigureStates();
        }

        private void Start()
        {
            PlayIntro();
        }

        private void Update()
        {
            if (animationComponent == null)
            {
                return;
            }

            TryRunQueuedLoop();
            HandleKeyboardPreview();
        }

        public void PlayIntro()
        {
            if (TryPlayClip(introClipName, WrapMode.Once))
            {
                QueueLoopAfterCurrent(introClipName, idleClipName, fallbackIdleClipName);
                return;
            }

            PlayIdle();
        }

        public void PlayIdle()
        {
            ClearQueuedLoop();
            if (TryPlayClip(idleClipName, WrapMode.Loop))
            {
                return;
            }

            TryPlayClip(fallbackIdleClipName, WrapMode.Loop);
        }

        public void PlayBaseIdle()
        {
            ClearQueuedLoop();
            if (TryPlayClip(fallbackIdleClipName, WrapMode.Loop))
            {
                return;
            }

            TryPlayClip(idleClipName, WrapMode.Loop);
        }

        public void PlaySpecialIdle()
        {
            if (TryPlayClip(specialClipName, WrapMode.Once))
            {
                QueueLoopAfterCurrent(specialClipName, idleClipName, fallbackIdleClipName);
                return;
            }

            PlayIdle();
        }

        private void ConfigureStates()
        {
            if (animationComponent == null)
            {
                return;
            }

            foreach (AnimationState state in animationComponent)
            {
                if (state == null)
                {
                    continue;
                }

                switch (state.name)
                {
                    case "Sit2":
                    case "Pose2":
                        state.wrapMode = WrapMode.Once;
                        break;
                    case "Idle":
                    case "Idle2":
                        state.wrapMode = WrapMode.Loop;
                        break;
                }
            }
        }

        private void HandleKeyboardPreview()
        {
            if (!enableKeyboardPreview)
            {
                return;
            }

            if (Input.GetKeyDown(KeyCode.Alpha1))
            {
                PlayIntro();
            }

            if (Input.GetKeyDown(KeyCode.Alpha2))
            {
                PlayIdle();
            }

            if (Input.GetKeyDown(KeyCode.Alpha3))
            {
                PlayBaseIdle();
            }

            if (Input.GetKeyDown(KeyCode.Alpha4))
            {
                PlaySpecialIdle();
            }
        }

        private void TryRunQueuedLoop()
        {
            if (string.IsNullOrEmpty(watchedStateName) || string.IsNullOrEmpty(queuedLoopPrimary))
            {
                return;
            }

            var watchedState = animationComponent[watchedStateName];
            if (watchedState == null)
            {
                var queuedPrimary = queuedLoopPrimary;
                var queuedFallback = queuedLoopFallback;
                ClearQueuedLoop();
                PlayLoopFromQueue(queuedPrimary, queuedFallback);
                return;
            }

            if (!animationComponent.IsPlaying(watchedStateName) || watchedState.length - watchedState.time <= queuedLoopLeadTime)
            {
                var queuedPrimary = queuedLoopPrimary;
                var queuedFallback = queuedLoopFallback;
                ClearQueuedLoop();
                PlayLoopFromQueue(queuedPrimary, queuedFallback);
            }
        }

        private void PlayLoopFromQueue(string primary, string fallback)
        {
            if (TryPlayClip(primary, WrapMode.Loop))
            {
                return;
            }

            TryPlayClip(fallback, WrapMode.Loop);
        }

        private void QueueLoopAfterCurrent(string currentStateName, string primaryLoop, string fallbackLoop)
        {
            watchedStateName = currentStateName;
            queuedLoopPrimary = primaryLoop;
            queuedLoopFallback = fallbackLoop;
        }

        private void ClearQueuedLoop()
        {
            watchedStateName = null;
            queuedLoopPrimary = null;
            queuedLoopFallback = null;
        }

        private bool TryPlayClip(string clipName, WrapMode wrapMode)
        {
            if (string.IsNullOrEmpty(clipName) || animationComponent == null)
            {
                return false;
            }

            var state = animationComponent[clipName];
            if (state == null)
            {
                return false;
            }

            state.wrapMode = wrapMode;
            animationComponent.wrapMode = wrapMode;
            animationComponent.clip = state.clip;
            animationComponent.CrossFade(clipName, 0.08f);
            return true;
        }
    }
}
