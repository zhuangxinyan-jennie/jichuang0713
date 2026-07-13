# 狗熊岭智慧乐园互动终端（Unity 前端）

## 一键生成（最少手动操作）

1. **首次打开工程**：Unity 会拉取 `TextMeshPro` 包；若字体粉色方块，执行菜单  
   **Window → TextMeshPro → Import TMP Essential Resources**。
2. 菜单：**Tools → 狗熊岭智慧终端 → 生成 SmartParkTerminal 场景（一键）**  
   - 生成：`Assets/Scenes/SmartParkTerminal.unity`  
   - 生成：`Assets/SmartParkTerminal/Generated/SmartTerminalBear.controller`（各 State 已绑定 **熊大基础包** 下的演示用 `.anim`，便于立刻 Play / WebGL 联调；可在 Animator 窗口里换成正式动作）
3. **双击打开场景** `SmartParkTerminal`，按 Play。

## 中文变成方框 □□□（必做其一）

**原因**：TMP 默认字体不含汉字。

### 推荐做法（TMP 官方流程）

1. 准备支持中文的 `.ttf`（可自用下载 **[思源黑体 / Noto Sans SC](https://fonts.google.com/noto/specimen/Noto+Sans+SC)** 等，注意发行授权）。把 `.ttf` 放进工程，例如 `Assets/SmartParkTerminal/Fonts/`。  
2. 菜单：**Window → TextMeshPro → Font Asset Creator**  
   - **Source Font File**：选你的 `.ttf`  
   - **Sampling Point Size**：50～72  
   - **Padding**：5  
   - **Atlas Resolution**：4096×4096（字多时用大图）  
   - **Character Set**：选 **Characters from File**，新建一个 `.txt`，把界面里会出现的所有中文台词、按钮字复制进去；或选 **Custom Characters** 粘贴一段常用汉字。  
3. 点 **Generate Font Atlas**，保存为如 `Assets/SmartParkTerminal/Fonts/NotoSansSC_SDF.asset`。  
4. 选中场景里的 **Canvas**，找到 **`Smart Park Terminal Chinese Font`**，把 **`Chinese Font Asset`** 拖成刚生成的 **`.asset`**。  
5. 再 Play；若仍有个别字是方框，说明该字没打进图集，把缺失字补进 txt 再生成一次。

> 一键生成的场景里 **Canvas 上已挂好** `SmartParkTerminalChineseFont`，你只需指定字体资源。

## 绑定真实熊大模型（替换占位胶囊）

1. Hierarchy 里删掉或隐藏 `BearPlaceholder_AssignYourModelHere`。  
2. 将你的 **Humanoid / Generic** 模型拖到 `CharacterArea` 下，命名为 `XiongdaModel`。  
3. **Animator**：拖入 `Assets/SmartParkTerminal/Generated/SmartTerminalBear.controller`（或自建同名 State）。  
4. **`ClipIdPlayer`**：可将 **Animator** 手动拖到 `TerminalSystems` 上；若留空，运行时会自动在 **`CharacterArea`** 下查找第一个 **Animator**（换模型后不必每次手拖）。

> 若 Animator 里缺少某个 State，控制台会提示「动画未配置」，**不会崩溃**。

### React / WebGL：右侧按钮→熊大动作（默认 SMPL JSON）

1. 熊模型上配置 **`SmplhMotionRetarget`**（及 tpose、Delta 等），否则网页发来的 JSON 路径无法驱动骨骼。  
2. Unity：**File → Build Settings → WebGL → Build**，输出拷到前端 `public/webgl/`，并维护 `build-info.json`（见 `xiongda_app` README）。  
3. 浏览器打开终端页，待顶部显示 **实例已连接**。前端按钮调用 **`SendMessage("UnityBridge","PlaySmplStreamingRelativePath","SmplhRetarget/挥手致意.json")`**。  
4. 若仍不动：Console 是否提示找不到 JSON、骨骼路径不匹配；确认 **Animator 已被 Retarget 关掉**（否则会盖掉 SMPL）。

### 连续点多个动作后熊「越扭越怪」

Delta 模式需要 Unity 里一套 **固定的绑定局部旋转** `_bindLocalRot`。旧逻辑在**每次**换 JSON 时都从你当前骨骼再读一遍绑定——上一段动作已经把骨骼拧歪，就会把「歪姿势」当成新的绑定，下一段再乘 SMPL 增量就会叠加扭曲。  
当前脚本已改为：**只在首次（或骨骼数量变化时）采样绑定**，之后换动作沿用第一次的绑定，并在加载后立刻 **ApplyFrame(0)**。仍请重新 **Build WebGL** 再拷到前端。

### WebGL 专用：`SmplhMotionRetarget` 必须用 HTTP 读 JSON

编辑器里可用 `File.ReadAllText`，**浏览器里 StreamingAssets 是 URL**，旧版仅用 `File.Exists` 会导致 **WebGL 里永远不加载、熊呈 T-Pose**。工程内脚本已对在 **`UNITY_WEBGL && !UNITY_EDITOR`** 下用 **`UnityWebRequest`** 拉取 `StreamingAssets` 下文件；改完后请 **重新 Build WebGL** 再拷到 `xiongda_app/public/webgl/`。

## 场景打光（全身均匀受光、避免局部高光死白）

**原因简述**：熊材质多为 **Standard**：**强平行光 + 高反射 + Skybox 环境** 会在胸口、肩头打出 **镜面高光**，容易 **曝成纯白**；侧面又会偏暗。

**当前 `SmartParkTerminal.unity` 默认策略（近似棚拍柔光）**：

1. **环境光模式：`Ambient Mode = Flat`**：周身底色一致。颜色约 **RGB(0.68, 0.70, 0.66)**，**Intensity ≈ 1.92**。  
2. **`Environment` 下主光源须为「平行光 Directional」**（Type = Directional）：**平行光无距离衰减**，全身明暗只随法线与光方向变化，最适合「整体提亮 + 相对均匀」。若误改成 **Spot / Point**，熊会容易欠曝或只有局部亮。**Transform 的 Position 建议保持 (0,0,0)**（平行光位置不参与计算，但请勿出现离谱坐标）。  
3. **根节点**多余的 **Directional Light** 保持 **禁用**，避免叠光。  
4. **平行光参数示例**：**Intensity ≈ 0.52**，颜色 **(0.96, 0.94, 0.90)**，旋转约 **48° / 118° / 0°**；**Indirect Multiplier（Bounce）≈ 0.62**。  
5. **Reflection Intensity ≈ 0.09**；**Main Camera：HDR 关闭**。  

**Scene 视图偏暗**：打开 Scene 工具栏 **灯泡 Lighting**。  

**仍局部死白**：降 **`熊大.prefab`** 材质 **Smoothness**。另可加 **Point Light** 作弱补光（你已调的球光），与平行光叠加时注意总亮度别过曝。

「一键生成场景」脚本会在保存前调用 **`ApplyEvenCharacterLighting()`**，与上述一致；已手工调好的场景勿被一键覆盖。

改光照后请 **重新 Build WebGL** 再覆盖前端 `public/webgl/`。

## 购入的风格化自然场景包（Stylized Nature Bundle）

你已购买的资源在仓库 **`background`** 目录；工程内为方便 Unity 使用已整理为：

| 内容 | 路径 |
|------|------|
| **正式资源（须导入）** | 工程根目录 **`PackagesToImport/StylizedNatureBundle.unitypackage`**（从购入素材复制，勿放在 `Assets` 下以免多余索引） |
| **卖家预览图（已进工程）** | **`Assets/StylizedNatureBundle/VendorPreviewImages/`**（`1.jpg`～`8.jpg`）+ **`VendorPreview_effect.png`** |
| **教程视频** | 仍在你的 **`background/.../`** 文件夹里的 `.mp4`，按需自行观看 |

**导入 `.unitypackage`（必做其一）**：

1. **菜单导入（最稳妥）**：关闭其它占用本工程的 Unity 窗口 → 打开本工程 → **Assets → Import Package → Custom Package…** → 选 **`PackagesToImport/StylizedNatureBundle.unitypackage`** → **Import**（列表里可取消不需要的子资源以减小体积）。  
2. **命令行**：**先完全退出 Unity**，再双击运行 **`tools/import_stylized_nature_bundle.bat`**（或按其中注释手动执行）；若提示「另一 Unity 已打开本工程」，必须先关掉编辑器。

导入完成后，资源一般在 **`Assets`** 下由包作者命名的文件夹里；把其中的 **Prefab / 场景片段** 拖进 **`SmartParkTerminal`**，或替换 **Skybox / 地面**，按卖家文档摆放即可。**WebGL** 需注意模型与贴图体量，必要时只选用部分预制体。

**只用预览图当 2D 远景（不必导入整包）**：若你只需要 **`VendorPreviewImages/3.jpg`** 这种平面布景，场景中已在 **`SmartTerminalRoot` 最上方** 放置 **`背景图_3jpg`**（Quad + **`BackgroundPlate/BackgroundPlate_3.mat`**，`Unlit/Texture`；已放大并下移以铺满相机视野）。若网页窗口比例特别扁仍露出空隙：**Main Camera → Background** 已设为 **近似草地色**，空隙不会太显眼；也可继续加大 Quad **Scale Y** 或略降 **Position Y**。**Rotation Y 须为 0**（勿绕 180°）。左右反了可把 **Scale X** 改为负数。

**脚下台面**：`Environment/StageFloor` 在当前 **`SmartParkTerminal` 场景里已默认取消勾选（禁用）**，避免与纯 2D 背景叠加显得突兀；需要实体地面时在 Hierarchy 里重新勾选 **StageFloor** 即可。一键生成的新场景里 **StageFloor** 也会默认隐藏。再次自动生成布景可关闭 Unity 后命令行执行  
`Unity.exe -batchmode -quit -executeMethod SmartParkTerminal.EditorTools.BackgroundPlateSceneSetup.ApplyPurchasePreview3AsBackdrop`  
（详见 `Assets/Editor/SmartParkTerminal/BackgroundPlateSceneSetup.cs`）。

---

## 两套动作系统（容易混）：`clip_id`Animator ≠ `SmplhRetarget/*.json`

| | **`PlayClipById`（clip_id）** | **`StreamingAssets/SmplhRetarget/` 下中文 `.json`** |
|--|-------------------------------|-----------------------------------------------------|
| **谁来播** | `Animator` + `SmartTerminalBear.controller`（里面是 `.anim` 片段） | `SmplhMotionRetarget` 读 JSON，按帧写骨骼旋转 |
| **Agent / 网页怎么调** | `SendMessage("UnityBridge", "PlayClipById", "wave_right_hand")` | `SendMessage("UnityBridge", "PlaySmplStreamingRelativePath", "SmplhRetarget/挥手致意.json")` |
| **文件名** | 无：只有固定的十几个 **英文 clip_id** | 你工程里真实的 **`挥手致意.json`** 等（见 `clip_manifest.json` 的 `jsonFile`） |
| **能否同时开** | **不要**在同一角色上指望两套一起驱动：Humanoid **Animator 每帧会盖掉骨骼**，JSON 就不生效；`SmplhMotionRetarget` 默认会关掉角色上的 Animator。 |

**要用中文 JSON 控制熊大（与你资源一致）时：**

1. 在 **`CharacterArea/xiongda1(12)_changing`（或你的熊根）** 上添加 **`SmplhMotionRetarget`**，按脚本说明填 **characterRoot**、**tpose**、勾选 **Use Delta From First Frame** 等（与 README 主文档「SMPL-H」一节一致）。  
2. 可选：同物体或同场景再加 **`XiongdaSmplhMotionDirector`**，在 **Action Registry** 里把 `logicalId`（给 Agent 用短名）映射到 `SmplhRetarget/某某.json`。  
3. 选中 **`UnityBridge`**，把上面的 **Director / Retarget** 拖到 Inspector（可不拖，运行时会 `FindObjectOfType`，但指定更稳）。  
4. 网页侧改调 **`PlaySmplStreamingRelativePath`** 或 **`PlaySmplByLogicalId`**，不要指望 **`挥手致意.json`** 会自动等于 **`wave_right_hand`**——除非你自己在前端或 Registry 里做一层映射。

## 测试清单（第一版验收）

| 步骤 | 操作 | 预期 |
|------|------|------|
| 1 | Play | 见标题、导航、右侧橙色按钮、底部字幕、右下角调试 |
| 2 | 点「挥手」 | 占位模型 CrossFade `WaveRightHand`，字幕「嘿！你好呀！」，调试 `clip_id=wave_right_hand` |
| 3 | 点导航「地图」→「旋转木马」 | 地图页、POI 高亮、`PointRight`、字幕指路 |
| 4 | 点「推荐」→ 点小火车卡片 | 推荐详情 + `TalkGestureSmall` + 台词 |

## JSON（后续接 310B）

运行时调用：

```csharp
FindObjectOfType<SmartParkTerminal.SmartTerminalController>().HandleJsonCommand(jsonString);
```

结构见 `TerminalCommand.cs`。**Unity JsonUtility** 可解析文中示例（含嵌套 `recommendation`）；若将来改用任意 JSON，可替换为 Newtonsoft.Json。

## 预留扩展（代码内注释）

- WebSocket / HTTP 接收线程 → 汇总调用 `HandleJsonCommand`
- `audio_path` → `ClipIdPlayer.PlayTtsIfPresent` 空实现处接入播放器

## Windows exe 打包

1. **File → Build Settings**  
2. 平台 **PC, Mac & Standalone**，**Target** Windows x86_64  
3. **Scenes In Build** 勾选 `SmartParkTerminal`  
4. **Player Settings**：Resolution **Fullscreen**（按需）、Company/Product Name  
5. **Build**，输出文件夹运行 exe。

## WebGL 打包失败：`asm2wasm` / exit `-1073740791`（`0xC0000409`）

说明：**IL2CPP 已成功**，失败发生在 **Binaryen 的 `asm2wasm.exe`**（链接阶段转 WASM），多为 **系统拦截旧工具链崩溃**，不是脚本语法错误。

### 建议按顺序尝试

1. **排除杀毒干扰**  
   把 **`F:\APPS\Unity\2018.4.35f1\`**、工程目录 **`XiongdaUnityProject`**、临时目录 **`Temp`** 加入 Windows 安全中心「排除项」；或打包前暂时关闭实时防护再试一次。

2. **缩短路径**  
   将整个工程复制到 **`C:\U\Xiongda`**（短路径、纯英文），用 Unity 打开后再 **WebGL Build**（减少命令行过长导致的老工具异常）。

3. **Unity Player Settings（打包更轻松）**  
   **Edit → Project Settings → Player → WebGL**：  
   - **Publishing Settings**：**Compression Format** 先改为 **Disabled** 试一次。  
   - **Resolution and Presentation**：可先保持默认。  
   - 勾选一次 **Development Build** 再打包（优化路径不同，有时可绕过崩溃）。

4. **重装 WebGL 模块**  
   Unity Hub → 本编辑器 → **Add modules** → 勾选 **WebGL Build Support** 修复安装。

5. **安装 VC++ 运行库**  
   安装 Microsoft **Visual C++ 2015–2022 Redistributable (x64)**。

6. **仍失败**  
   考虑用 **Unity 2022.3 LTS** 新建工程迁移 SmartParkTerminal 相关脚本与场景再打 WebGL（工具链更新，但需自行评估升级成本）。

日志关键字：`Emscripten_FastComp_Win\\binaryen\\bin\\asm2wasm`、`CalledProcessError`、`exit status -1073740791`。

## React + WebGL：只要熊大、不要 Unity 大屏 UI

一键生成的场景里带有 **整块 Canvas（绿顶栏、按钮等）**，那是给「纯 Unity 触摸屏」用的。  
若 **UI 在 React**、Unity 只负责 **看熊大 / 播 clip**，有两种做法：

### 做法 A（推荐）：挂 `ReactEmbedModeBootstrap`

1. 在 Hierarchy 选中 **`SmartTerminalRoot`**（或场景里任意物体）。  
2. **Add Component** → **`React Embed Mode Bootstrap`**。  
3. 保持默认勾选 **`Disable Screen Space Ui On Awake`**，保存场景。  
4. Play / 再打 WebGL：**全屏 UI 与 EventSystem 会自动关掉**，只剩摄像机 + 地面 + **CharacterArea** 里的熊；React 仍通过 **`SendMessage → UnityBridge`** 驱动动作。  
5. 若熊太小：选中熊模型，把 **Scale** 调到 **2～8** 之间直到镜头里大小合适。

### 做法 B：手动关 UI

在 Hierarchy 里取消勾选 **`SmartTerminalRoot → Canvas`** 和 **`SmartTerminalRoot → EventSystem`**，保存场景。

> **字幕**：关掉 Canvas 后，`ClipIdPlayer` 若曾绑定底部的 TMP 字幕会失效——正好由 **React 页面底部字幕栏** 显示台词。

## 脚本索引

| 脚本 | 职责 |
|------|------|
| `SmartTerminalController` | 页面切换、JSON 分发、协程多段动作 |
| `TerminalCommand` | JSON 数据结构 |
| `ClipIdPlayer` | clip_id→State、`CrossFade`、默认台词 |
| `DemoUIController` | 触摸屏按钮（运行时绑定） |
| `PageManager` | 四页显隐 |
| `MapUIController` | POI 高亮与说明 |
| `RecommendationUIController` | 推荐卡片与详情 |
| `DebugPanelController` | 右下角调试 |
| `SubtitleController` | 底部字幕 |
| `ReactEmbedModeBootstrap` | WebGL 嵌入 React 时自动关闭大屏 Canvas |
