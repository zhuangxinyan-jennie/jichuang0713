using System;
using System.Collections.Generic;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading;
using UnityEngine;

namespace XiongdaImporter
{
    /// <summary>
    /// 本机 TCP 文本指令（默认 127.0.0.1），方便外部 Python Agent 发送 PLAY 命令。
    /// WebGL 构建不支持监听端口；PC/Mac Standalone 与 Editor 可用。
    /// </summary>
    [DisallowMultipleComponent]
    public sealed class XiongdaTcpCommandServer : MonoBehaviour
    {
        [SerializeField]
        private XiongdaLegacyAnimationDirector director;

        [SerializeField]
        private XiongdaSmplhMotionDirector smplDirector;

        // WebGL Player 上 TCP 不运行，部分 SerializeField 在 Player 中不会被读到 → 统一抑制 CS0414
#pragma warning disable CS0414
        [SerializeField]
        private string bindAddress = "127.0.0.1";

        [SerializeField]
        private int port = 8765;

        [SerializeField]
        [Tooltip("WebGL 打包后 TCP 不可用；该字段仅在 Editor / Standalone 的 OnEnable 中读取。")]
        private bool startListenerOnEnable = true;
#pragma warning restore CS0414

        private TcpListener listener;
        private Thread acceptThread;
        private volatile bool listening;

        private readonly Queue<string> pendingLines = new Queue<string>();
        private readonly object queueLock = new object();

        private void OnEnable()
        {
#if UNITY_WEBGL && !UNITY_EDITOR
            Debug.LogWarning("[XiongdaTcpCommandServer] TCP listener is not supported on WebGL builds.");
            enabled = false;
            return;
#else
            if (director == null)
            {
                director = FindObjectOfType<XiongdaLegacyAnimationDirector>();
            }

            if (smplDirector == null)
            {
                smplDirector = FindObjectOfType<XiongdaSmplhMotionDirector>();
            }

            if (startListenerOnEnable)
            {
                StartListen();
            }
#endif
        }

        private void OnDisable()
        {
            StopListen();
        }

        private void Update()
        {
            while (true)
            {
                string line;
                lock (queueLock)
                {
                    if (pendingLines.Count == 0)
                    {
                        break;
                    }

                    line = pendingLines.Dequeue();
                }

                HandleLine(line);
            }
        }

        /// <summary>可在运行时再次调用（例如端口占用失败后改 port）。</summary>
        public void StartListen()
        {
#if UNITY_WEBGL && !UNITY_EDITOR
            return;
#else
            StopListen();
            try
            {
                listener = new TcpListener(IPAddress.Parse(bindAddress), port);
                listener.Start();
                listening = true;
                acceptThread = new Thread(AcceptLoop)
                {
                    IsBackground = true,
                    Name = "XiongdaTcpAccept"
                };
                acceptThread.Start();
                Debug.Log($"[XiongdaTcpCommandServer] Listening on {bindAddress}:{port}");
            }
            catch (Exception ex)
            {
                Debug.LogError("[XiongdaTcpCommandServer] Start failed: " + ex.Message);
            }
#endif
        }

        public void StopListen()
        {
            listening = false;
            if (listener != null)
            {
                try
                {
                    listener.Stop();
                }
                catch (Exception)
                {
                    // ignored
                }

                listener = null;
            }

            if (acceptThread != null && acceptThread.IsAlive)
            {
                try
                {
                    acceptThread.Join(300);
                }
                catch (Exception)
                {
                    // ignored
                }

                acceptThread = null;
            }
        }

        private void AcceptLoop()
        {
            while (listening && listener != null)
            {
                TcpClient client = null;
                try
                {
                    client = listener.AcceptTcpClient();
                }
                catch (SocketException)
                {
                    break;
                }
                catch (ObjectDisposedException)
                {
                    break;
                }

                if (client == null)
                {
                    continue;
                }

                try
                {
                    using (client)
                    using (var stream = client.GetStream())
                    using (var reader = new StreamReader(stream, Encoding.UTF8, false, 1024, leaveOpen: false))
                    using (var writer = new StreamWriter(stream, new UTF8Encoding(false)) { AutoFlush = true })
                    {
                        WriteReply(writer, "READY xiongda-tcp");
                        while (client.Connected && listening)
                        {
                            var line = reader.ReadLine();
                            if (line == null)
                            {
                                break;
                            }

                            line = line.Trim();
                            if (line.Length == 0)
                            {
                                continue;
                            }

                            var reply = ProcessCommand(line);
                            WriteReply(writer, reply);
                            break;
                        }
                    }
                }
                catch (Exception ex)
                {
                    Debug.LogWarning("[XiongdaTcpCommandServer] Client handler: " + ex.Message);
                }
            }
        }

        private static void WriteReply(StreamWriter writer, string text)
        {
            if (string.IsNullOrEmpty(text))
            {
                return;
            }

            var lines = text.Split(new[] { "\r\n", "\n" }, StringSplitOptions.None);
            foreach (var l in lines)
            {
                writer.WriteLine(l);
            }
        }

        /// <summary>线程安全：工作线程仅入队，主线程 Update 执行。</summary>
        private void Enqueue(string line)
        {
            lock (queueLock)
            {
                pendingLines.Enqueue(line);
            }
        }

        private string ProcessCommand(string line)
        {
            if (line.StartsWith("#", StringComparison.Ordinal))
            {
                return string.Empty;
            }

            var parts = line.Split(new[] { ' ', '\t' }, StringSplitOptions.RemoveEmptyEntries);
            if (parts.Length == 0)
            {
                return string.Empty;
            }

            var cmd = parts[0].ToUpperInvariant();

            if (cmd == "PING")
            {
                return "OK PONG";
            }

            if (cmd == "HELP")
            {
                return "OK COMMANDS: PING | HELP | LIST | PLAY_ID <id> (Legacy 或 SMPL 择一)"
                       + " | PLAY_CLIP <clip> LOOP|ONCE | PLAY_SMPL_ID <id> | PLAY_SMPL_REL <StreamingAssets相对路径>";
            }

            if (cmd == "LIST")
            {
                if (director == null && smplDirector == null)
                {
                    return "ERR NO_DIRECTOR";
                }

                var sb = new StringBuilder();
                sb.AppendLine("OK LIST_BEGIN");
                if (director != null)
                {
                    var reg = director.GetRegistryArray();
                    if (reg != null)
                    {
                        foreach (var slot in reg)
                        {
                            if (slot == null || string.IsNullOrEmpty(slot.logicalId))
                            {
                                continue;
                            }

                            var wrap = slot.wrapMode == WrapMode.Loop ? "LOOP" : "ONCE";
                            sb.AppendLine("OK LEGACY " + slot.logicalId + "\t" + slot.clipName + "\t" + wrap);
                        }
                    }
                }

                if (smplDirector != null)
                {
                    var regSmpl = smplDirector.GetRegistryArray();
                    if (regSmpl != null)
                    {
                        foreach (var slot in regSmpl)
                        {
                            if (slot == null || string.IsNullOrEmpty(slot.logicalId))
                            {
                                continue;
                            }

                            sb.AppendLine("OK SMPL " + slot.logicalId + "\t" + slot.streamingRelativePath);
                        }
                    }
                }

                sb.Append("OK LIST_END");
                return sb.ToString();
            }

            if (cmd == "PLAY_ID" && parts.Length >= 2)
            {
                var id = parts[1];
                Enqueue("PLAY_ID " + id);
                return "OK QUEUED PLAY_ID " + id;
            }

            if (cmd == "PLAY_CLIP" && parts.Length >= 3)
            {
                var clip = parts[1];
                var mode = parts[2].ToUpperInvariant();
                Enqueue("PLAY_CLIP " + clip + " " + mode);
                return "OK QUEUED PLAY_CLIP " + clip + " " + mode;
            }

            if (cmd == "PLAY_SMPL_ID" && parts.Length >= 2)
            {
                var id = parts[1];
                Enqueue("PLAY_SMPL_ID " + id);
                return "OK QUEUED PLAY_SMPL_ID " + id;
            }

            if (cmd == "PLAY_SMPL_REL" && parts.Length >= 2)
            {
                var rel = parts[1];
                Enqueue("PLAY_SMPL_REL " + rel);
                return "OK QUEUED PLAY_SMPL_REL " + rel;
            }

            return "ERR UNKNOWN_OR_BAD_ARGS";
        }

        private void HandleLine(string line)
        {
            var parts = line.Split(new[] { ' ', '\t' }, StringSplitOptions.RemoveEmptyEntries);
            if (parts.Length < 1)
            {
                return;
            }

            if (parts[0] == "PLAY_ID" && parts.Length >= 2)
            {
                if (smplDirector != null)
                {
                    smplDirector.PlayByLogicalId(parts[1]);
                }
                else if (director != null)
                {
                    director.PlayByLogicalId(parts[1]);
                }
                else
                {
                    Debug.LogWarning("[XiongdaTcpCommandServer] PLAY_ID but no director.");
                }

                return;
            }

            if (parts[0] == "PLAY_SMPL_ID" && parts.Length >= 2)
            {
                if (smplDirector != null)
                {
                    smplDirector.PlayByLogicalId(parts[1]);
                }

                return;
            }

            if (parts[0] == "PLAY_SMPL_REL" && parts.Length >= 2)
            {
                if (smplDirector != null)
                {
                    smplDirector.PlayByStreamingRelativePath(parts[1], null);
                }

                return;
            }

            if (parts[0] == "PLAY_CLIP" && parts.Length >= 3)
            {
                if (director == null)
                {
                    Debug.LogWarning("[XiongdaTcpCommandServer] PLAY_CLIP 需要 XiongdaLegacyAnimationDirector。");
                    return;
                }

                var clip = parts[1];
                var mode = parts[2].ToUpperInvariant();
                var wrap = mode == "LOOP" ? WrapMode.Loop : WrapMode.Once;
                director.PlayByClipName(clip, wrap);
            }
        }
    }
}

