using System.Runtime.InteropServices;
using UnityEngine;

namespace SmartParkTerminal
{
    /// <summary>
    /// WebGL：导航到达后通知前端更新 Agent 当前位置（供第二轮问路算路）。
    /// </summary>
    public static class ParkMapNavWebCallback
    {
#if UNITY_WEBGL && !UNITY_EDITOR
        [DllImport("__Internal")]
        private static extern void XiongdaNotifyNavArrived(string payloadJson);
#endif

        public static void NotifyArrived(string payloadJson)
        {
            if (string.IsNullOrEmpty(payloadJson))
            {
                return;
            }

#if UNITY_WEBGL && !UNITY_EDITOR
            XiongdaNotifyNavArrived(payloadJson);
#else
            Debug.Log("[ParkMapNavWebCallback] " + payloadJson);
#endif
        }
    }
}
