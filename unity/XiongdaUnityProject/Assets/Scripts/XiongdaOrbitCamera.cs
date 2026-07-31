using UnityEngine;

namespace XiongdaImporter
{
    [DisallowMultipleComponent]
    public sealed class XiongdaOrbitCamera : MonoBehaviour
    {
        [SerializeField] private Transform target;
        [SerializeField] private Vector3 focusOffset = new Vector3(0f, 6f, 0f);
        [SerializeField] private float distance = 18f;
        [SerializeField] private float yaw = 180f;
        [SerializeField] private float pitch = 8f;
        [SerializeField] private float rotateSensitivity = 180f;
        [SerializeField] private float zoomSensitivity = 12f;
        [SerializeField] private float minPitch = -10f;
        [SerializeField] private float maxPitch = 35f;
        [SerializeField] private float minDistance = 6f;
        [SerializeField] private float maxDistance = 40f;

        public void Configure(Transform targetTransform, Bounds bounds, float initialYaw)
        {
            target = targetTransform;

            var height = Mathf.Max(bounds.size.y, 2f);
            var width = Mathf.Max(bounds.size.x, 2f);
            focusOffset = bounds.center - targetTransform.position + new Vector3(0f, height * 0.05f, 0f);
            distance = Mathf.Max(height * 1.6f, width * 0.8f, 12f);
            minDistance = Mathf.Max(6f, distance * 0.45f);
            maxDistance = Mathf.Max(distance * 2.5f, minDistance + 8f);
            yaw = initialYaw;
            pitch = 8f;

            ApplyTransform();
        }

        private void LateUpdate()
        {
            if (target == null)
            {
                return;
            }

            if (Input.GetMouseButton(0))
            {
                yaw += Input.GetAxis("Mouse X") * rotateSensitivity * Time.deltaTime;
                pitch -= Input.GetAxis("Mouse Y") * rotateSensitivity * 0.6f * Time.deltaTime;
                pitch = Mathf.Clamp(pitch, minPitch, maxPitch);
            }

            var scroll = Input.GetAxis("Mouse ScrollWheel");
            if (Mathf.Abs(scroll) > 0.0001f)
            {
                distance = Mathf.Clamp(distance - scroll * zoomSensitivity, minDistance, maxDistance);
            }

            ApplyTransform();
        }

#if UNITY_EDITOR
        private void OnValidate()
        {
            pitch = Mathf.Clamp(pitch, minPitch, maxPitch);
            minDistance = Mathf.Max(0.1f, minDistance);
            maxDistance = Mathf.Max(minDistance, maxDistance);
            distance = Mathf.Clamp(distance, minDistance, maxDistance);

            if (!Application.isPlaying && target != null)
            {
                ApplyTransform();
            }
        }
#endif

        private void ApplyTransform()
        {
            var focusPoint = target.position + focusOffset;
            var rotation = Quaternion.Euler(pitch, yaw, 0f);

            transform.position = focusPoint - rotation * Vector3.forward * distance;
            transform.rotation = rotation;
        }
    }
}
