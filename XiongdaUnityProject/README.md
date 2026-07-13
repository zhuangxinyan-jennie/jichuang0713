# Xiongda Unity Project

这个目录是我给你搭好的最小 Unity 工程骨架。

当前状态：
- 已经包含导入脚本和运行脚本
- 已经指向本机现有的 `extracted_xiongda_run` 数据目录
- 当前这个工程只保留熊大
- 建议安装 Unity Editor `2018.4.35f1`

怎么用：
1. 安装 Unity Editor `2018.4.35f1`
2. 用 Unity 打开这个目录
3. 等脚本编译完成
4. 点菜单 `Tools > Xiongda > Import Left Variant`
5. 点 Play，熊大会自动播放 `Run`

已经生成好的角色资源：
- 熊大默认：`Assets/XiongdaImported/xiongda_base_default/Prefabs/熊大.prefab`

已经生成好的演示场景：
- 熊大默认：`Assets/Scenes/XiongdaDefaultSkin.unity`

如果你不想往系统盘写 Hub/缓存/临时文件：
- 用便携版安装脚本：`../tools/unity-2018.4.35f1-portable/install.sh`
- 然后用：`./open_with_portable_unity.sh`
- 这个脚本会把 Unity 的 `HOME/XDG/TMPDIR` 都重定向到当前工作区下的 `portable_unity_2018_4_35f1/state/`

如果你的 Unity Editor 不在默认搜索路径里：
- 先设置环境变量 `UNITY_EDITOR=/你的/Unity/Editor/Unity`
- 再运行 `./open_with_unity_editor.sh`

如果还没装 Unity Editor：
- 脚本会先尝试启动工作区里的 `tools/unityhub/UnityHub.AppImage`
- 你可以先在 Hub 里安装 Editor，再回来打开这个项目

关键目录：
- `Assets/Editor/`
- `Assets/Scripts/`
- `Packages/manifest.json`
- `ProjectSettings/ProjectVersion.txt`

相关数据：
- 提取资源目录：`/home/kaifeng/extra/Downloads/fudan/IC_competition/unity/extracted_xiongda_run`
- 导入器脚本：`Assets/Editor/XiongdaRunImporter.cs`

## 动作选择：UI 与外部 TCP（接多模态 + Agent）

1. 在含 **Legacy `Animation` 的熊大根物体**（如 `熊大.prefab` 实例）上添加：
   - `XiongdaLegacyAnimationDirector`：在 **Action Registry** 里为每个动作填 `logicalId`（给 Agent 用）和 `clipName`（须与 Animation 里已有 clip 名一致）。
   - 二选一或同时用：
     - `XiongdaActionSelectionUI`：勾选 **Auto Build Buttons From Registry** 则运行时生成按钮；也可在别的 Button 的 OnClick 上绑 `UiPlayByLogicalId` 等公共方法。
     - `XiongdaTcpCommandServer`：默认监听 `127.0.0.1:8765`；**PC/Editor 可用，WebGL 无法监听端口**。

2. **TCP 文本协议**（一次连接发一行命令，发完即关；首行会收到 `READY xiongda-tcp`）：
   - `PING` / `HELP` / `LIST`
   - `PLAY_ID <logicalId>`（与 Registry 中 `logicalId` 一致，不区分大小写）
   - `PLAY_CLIP <clipName> LOOP` 或 `PLAY_CLIP <clipName> ONCE`

3. Python 示例：`tools/xiongda_tcp_client_example.py`。Agent 侧只要把最终动作映射成 `PLAY_ID ...` 或 `PLAY_CLIP ...` 发到本机端口即可。

## SMPL-H：多段 JSON 动作自由切换

1. 把所有混元导出的 **动作 JSON** 放进 `Assets/StreamingAssets/` 下（可建子目录，如 `SmplhRetarget/mymotion1.json`），与现有 `tpose.json` 等 **同一套 bonePaths 导出** 时效果最稳。  
2. 在带 **`SmplhMotionRetarget`** 的物体上 Add Component → **`XiongdaSmplhMotionDirector`**，在 **Action Registry** 里为每段动作填写：`logicalId`（给 Agent）、`streamingRelativePath`（相对 StreamingAssets，例如 `SmplhRetarget/stand.json`）。  
3. 运行时 **`SmplhMotionRetarget.LoadMotionFromStreamingRelativePath`** 会切换 JSON 并重置播放时间；切换失败会保留当前动作。  
4. **UI**：在同一物体或任意物体上加 **`XiongdaActionSelectionUI`**；若场景里有 **`XiongdaSmplhMotionDirector`**，会自动生成 **SMPL** 绿色按钮条（优先于 Legacy）。  
5. **TCP**：`PLAY_SMPL_ID <logicalId>`、`PLAY_SMPL_REL <相对路径>`；或沿用 `PLAY_ID`，若场景中仅有 SMPL Director、无 Legacy Director，则会驱动 SMPL。
6. **`clip_manifest.json`（给 WebGL / `clip_id`）**：列表里 **第 4 条** 动作为「**双手欢呼**」，混元源文件 stem 为 **`00000004_004`**（`movemendt` 目录下对应样本）；对应 JSON 文件名为 **`双手欢呼.json`**。若你重新导出该样本，请覆盖 `StreamingAssets/SmplhRetarget/双手欢呼.json` 并保留清单里 `sourceStem` / `jsonFile` 一致。
7. **`SmplhMotionRetarget` 默认不再循环整段动作**：`loopMotion` 默认为 **关**，片段播完一次后会自动加载 **`idleMotionRelativePath`**（默认 `SmplhRetarget/stand.json`），回到站立待机；待机片段与 Idle 路径相同时由 **`loopIdleMotion`**（默认开）循环轻微呼吸。若需要展台循环演示某一串动作，可在 Inspector 勾选 **`loopMotion`**。

### SMPL JSON 动作 × 面部表情（BlendShape）

与 **`SmplhRetarget/*.json`** 并行，不修改骨骼 JSON，只驱动 **`xiongda_final_face`** 网格上的 **fun / A / O / cry / happy**（0–100）。

1. 使用 **`xiongda_final_face/xiongda/xiongda.fbx`**（含 `fun`/`happy` 等 BlendShape）；**不要用** 无表情的 `xiongda1(12)_changing`。
2. **`SmplhMotionRetarget` 与 `XiongdaFaceBlendShapeDriver` 挂在同一物体**（拖进场景的熊根，如 `xiongda`），勾选 Retarget 的 **Auto Ensure Face Driver**；`Character Root` 指向 **`Reference`**。脸网格一般会自动找到子物体 **`xiongda_xinban`**。
3. 配置表：**`Assets/StreamingAssets/SmplhRetarget/face_expression_config.json`**
   - **`presets`**：各表情预设的 5 个权重；
   - **`motions`**：每个 JSON 路径 → 播放该动作时切换到的预设；
   - **`perceptionEmotion`**：板端/Agent 的 `emotion` 字符串 → 预设（如 `happy`→`happy`，`scared`→`surprised`）；
   - **`transitions`**：预设 A→B 的过渡秒数（未列出则用 `defaultBlendInSeconds`；回到 `neutral` 用 `neutralBlendInSeconds`）。
4. 切换 JSON 时 **`SmplhMotionRetarget`** 会自动调用表情驱动；待机 **`stand.json`** 使用 **`idle_soft_smile`**。
5. WebGL 可额外：`SendMessage("UnityBridge", "SetFaceEmotion", "happy")`（与动作预设独立，用于板端实时 emotion）。

调参：改 JSON 里对应动作的 **`preset`** 或预设权重即可，无需改代码。

### Play 后好几秒熊才动？

常见原因：

1. **首段动作 JSON 很大**（多数约 **0.56MB/个**，`stand.json` 约 **0.37MB**）；`SmplhMotionRetarget` 在启动时要 **读盘 + JsonUtility 解析**，会卡主线程。
2. 场景里若有 **两个** `SmplhMotionRetarget`（例如旧熊 + 新熊各挂一个），会 **加载两遍**。
3. Inspector 里 **Streaming Relative Path** 若填的是 `原地踏步.json` 等大文件，首帧会更慢；调试可先改成 **`SmplhRetarget/stand.json`**。

已做优化：**下一帧再加载首段 JSON**（`Defer Initial Motion Load To Next Frame`）、**同路径 JSON 解析缓存**（第二套 Retarget 会打日志 `cache`）、表情配置改为 Awake 同步读小文件。

仍慢时：Hierarchy 只保留 **一只** 带 Retarget 的熊，并关掉另一只。

### 不下板：在 Unity Editor 里直接看「动作 + 表情」

1. 打开 **`Assets/Scenes/SmartParkTerminal.unity`**（场景里已有 **`SmplhMotionRetarget`**）。
2. 确认脸上能形变：选中熊的 **`SkinnedMeshRenderer`**，**BlendShapes** 里应能看到 `fun` / `happy` / `cry` / `A` / `O`。若没有，请换用 **`xiongda_maybe_final_new/xiongda_final_face`** 下的脸模网格，或把该网格挂到当前骨架上。
3. 在 **`SmplhMotionRetarget` 同一物体**（或子节点）**Add Component → `XiongdaFaceBlendShapeDriver`**，`Target Renderer` 指向上一步的脸网格（可留空自动查找）。
4. 任意物体 **Add Component → `XiongdaSmplFacePlayModePanel`**（可选把 Retarget / Face / UnityBridge 拖进 Inspector；不拖也会自动查找）。
5. 点 **Play**：屏幕左上角出现测试条 — 点 **振臂欢呼** 等切身体 JSON，点 **happy / sad** 等模拟 Agent 的 `emotion`。
6. Console 应出现 **`[FaceBlend] 已加载表情配置`**；播动作时脸会按 `face_expression_config.json` 的 `motions` 表切换。

无需 WebGL 打包、无需板子、无需 `integration_test/server.py`。

### Unity Editor：摄像头实时跟臂（可选，默认不开启）

与 **Smplh JSON 动作** 是两种玩法，**默认仍走 JSON**（`stand.json` 待机等），互不影响：

| 模式 | 怎么开 | JSON |
|------|--------|------|
| **JSON 动作** | 直接 Play（默认） | 正常 |
| **摄像头跟臂** | 勾选 `XiongdaRealtimeCameraArmSync` → Enable；先运行 `clean_0606/start-unity-pose-server.ps1` | 跟臂开启时会暂停 JSON；关跟臂后自动恢复 |

若希望 **JSON 全身继续播、只覆盖手臂**：勾选跟臂，并取消 **Pause Motion Retarget While Realtime**。

### 多套熊模型（例如 `xiongda_maybe_final_new`）与「不调零、不影响旧版」

- **是否需要新的 `tpose.json`？**  
  若新 FBX 的 **骨骼层级 / `bonePaths` 与旧版导出不一致**，或混元按**新网格**重新导出 SMPL-H，则需要 **用同一套 `bonePaths` 再导一帧 T-pose**（与动作 NPZ 同一管线），作为 **`Smpl Reference Pose Relative Path`**。  
  若仅换贴图/材质、**骨骼与旧 JSON 的 `bonePaths` 完全一致**，可继续用原来的 `SmplhRetarget/tpose.json` 试播；若出现抬臂、扭曲再补导新 tpose。

- **怎样不覆盖 `xiongda_maybe_final` 用的文件？**  
  1. 在 **`Assets/StreamingAssets/`** 下**新建子目录**（例如 **`SmplhRetarget_new/`**），把新模型的 **`tpose.json`、`stand.json`、各动作 `.json`** 都放在这里，**不要改** `SmplhRetarget/` 里旧熊正在用的文件。  
  2. 在场景里**单独实例化**新模型 prefab（或复制一份 prefab），只改该物体上 **`SmplhMotionRetarget`** 的 Inspector：  
     - **`Smpl Reference Pose Relative Path`** → `SmplhRetarget_new/tpose.json`  
     - **`Streaming Relative Path` / `Idle Motion Relative Path`** → 指到 `SmplhRetarget_new/` 下的对应文件  
     - 若用 **`calibration.json`**：可复制一份为 **`SmplhRetarget_new/calibration.json`**，并把 **`Calibration Relative Path`** 指过去；**不要**让新熊去写公共的 `SmplhRetarget/calibration.json`（菜单 `Tools/Xiongda/SMPL Retarget/Merge…` 默认合并到旧路径，新套建议手拷 JSON 或改 Editor 脚本目标路径后再合并）。  
  3. **`XiongdaSmplhMotionDirector`** 的 **Action Registry** 里每条 **`streamingRelativePath`** 也改成 `SmplhRetarget_new/xxx.json`。  
  这样 **旧场景 / 旧 prefab** 仍指向 **`SmplhRetarget/`**，新熊只读 **`SmplhRetarget_new/`**，互不覆盖。

---

## 离线互动演示方案（不接 310b，先有点击切换动作）

**目标**：在 Unity Play、或日后 WebGL/EXE 里，用 **屏幕上的 UI 按钮** 切换熊大的不同动作并立刻看到效果；**不依赖** 外部服务器或 310b。

### 第一步：选定一条动作数据来源（二选一）

| 路线 | 适用情况 | 核心组件 |
|------|----------|----------|
| **A. Legacy 动画** | 场景里是 **`熊大.prefab`** 这类，带 **`Animation`** 组件和很多 **AnimationClip** | `XiongdaLegacyAnimationDirector` + `XiongdaActionSelectionUI` |
| **B. SMPL JSON** | 场景里是 **`xiongda1(12)_changing`** 等，用 **`SmplhMotionRetarget`** 读 JSON | `SmplhMotionRetarget` + `XiongdaSmplhMotionDirector` + `XiongdaActionSelectionUI` |

两条路线 **不要混在同一个「切换逻辑」里 confusion**：只做 SMPL 时建议 **删掉** `XiongdaLegacyAnimationDirector`。

### 第二步：在「场景里的角色根物体」上挂脚本（不要只改 Project 里的裸 FBX）

1. **Hierarchy** 选中实例（例如 `Xiongda` 或 `xiongda1(12)_changing`）。  
2. **路线 A**：Add **`Xiongda Legacy Animation Director`** → **Action Registry** 里每项填写 **Logical Id**（按钮显示用）+ **Clip Name**（必须与 **Animation** 列表里 **State 名** 完全一致，如 `Run`）。  
3. **路线 B**：确保已有 **`Smplh Motion Retarget`**；Add **`Xiongda Smplh Motion Director`** → **Retarget** 拖同一物体上的 **`Smplh Motion Retarget`** → **Action Registry** 填 **Logical Id** + **Streaming Relative Path**（如 `SmplhRetarget/摊手疑问.json`，文件须在 **`Assets/StreamingAssets/`** 下）。  
4. **共同**：Add **`Xiongda Action Selection UI`**  
   - **路线 A**：**Director** 拖 `Xiongda Legacy Animation Director`；**Smpl Director** 留空。  
   - **路线 B**：**Smpl Director** 拖 `Xiongda Smplh Motion Director`；**Director** 留空。  
   - 勾选 **Auto Build Buttons From Registry**。  
5. **Ctrl+S 保存场景**；**Play**：屏幕一侧应出现半透明条 + 按钮（Legacy 偏蓝、SMPL 偏绿）。点击即切换动作。

### 第三步：Build 到网页或 exe（可选）

- **网页**：`File → Build Settings → WebGL`，勾选当前场景，Build 后用本地 HTTP 打开 `index.html`（勿用 `file://`）。  
- **展台 exe**：同一套 UI；Build **PC Standalone**。  

### 第四步：以后接 310b / Agent（接口已预留）

- 外部程序只需把「最终动作」映射成 Registry 里的 **`logicalId`**，通过 **`XiongdaTcpCommandServer`** 发 `PLAY_ID` / `PLAY_SMPL_ID`（**仅 Editor / Standalone**，WebGL 不能当 TCP 服务端）。  
- 或在你方中间层里直接调 Unity 侧封装好的 **`PlayByLogicalId`**（若以后做成插件/进程通信）。

### 常见问题

- **没有按钮**：检查 **Action Selection UI** 是否拖了 **Director** 或 **Smpl Director**；Registry 是否非空；是否保存了场景。  
- **点了没反应**：SMPL 路线检查 JSON 路径与 **StreamingAssets** 是否一致；Legacy 路线检查 **Clip Name** 是否与 Animation 里 clip 名一致。  
- **Web 上还是旧场景**：**Build Settings → Scenes In Build** 里勾的必须是刚保存过的那个场景。

---

## 智慧乐园互动终端（Animator + 大屏 UI，接 310B 预留）

集创赛「游客→310B→Unity 大屏」专用前端：**菜单 `Tools → 狗熊岭智慧终端 → 生成 SmartParkTerminal 场景`**，详见  
`Assets/Scripts/SmartParkTerminal/README_SmartTerminal.md`。

一键场景里已自动放 **「UnityBridge」**（挂 `SmartParkTerminal/UnityBridge.cs` 并引用 **ClipIdPlayer**），给 **Vite 网页**（`F:\jichuang2026\xiongda_app`）的 WebGL 发 `clip_id` 用。  
网页侧步骤见 **`xiongda_app\README.md`** 与 **`xiongda_app\public\webgl\说明.txt`**（你只需在 Unity 里点 WebGL 打包、拷文件、填 `build-info.json`）。

**嵌入网页里熊太大 / 头顶被裁切**：在 **`SmartParkTerminal`** 里调 **`Main Camera`** —— 再拉远 Z（例如约 `-11`）、抬高 Y（约 `2.1`）、加大 **Field of View**（约 `54°`）；或在 **`CharacterArea`** 下略减熊的 **Scale**（当前场景约 `0.065`）。机位与体积会一起影响构图。

**正面过曝（高光死白）或侧面太暗**：场景内已压低 **平行光强度**、**环境光**与 **反射强度**，并关闭相机 **HDR**；仍不满意时在 **`README_SmartTerminal.md` →「场景打光」** 里微调。改完后需重新 **WebGL Build**。

**React 点按钮熊不动**：确认 **`SmartTerminalBear.controller`** 已挂在模型 **Animator** 上；**`TerminalSystems` → `Clip Id Player`** 的 Animator 已绑定或留空（会自动查找 `CharacterArea`）。详情与 WebGL 联调步骤见 **`Assets/Scripts/SmartParkTerminal/README_SmartTerminal.md`**。
