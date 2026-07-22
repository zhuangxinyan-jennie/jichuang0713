# Unity 合并方案（双熊 · 单 WebGL · 可回退）

## 目标

一个 WebGL：**互动熊**（SMPL+表情）+ **导览熊**（地图跑步），同一场景按模式切换。

## 两只熊（重要）

| 模式 | 出场的熊 | 桥接 | 能力 |
|------|----------|------|------|
| 语音聊天 / 剧情 | `InteractiveXiongda` | `UnityBridge` | SMPL 动作 + 表情 |
| 地图查询 / 导航 | `PlayableXiongda` | `ParkMapUnityBridge` | Run 动画 + path_world 寻路 |

切换时互斥显隐，并对齐位置（导览跑到哪，切回聊天时互动熊站在同一位置）。

## 安全回退

| 路径 | 角色 |
|------|------|
| `XiongdaUnityProject/` | **原**语音熊工程，不改 |
| `XiongdaParkMapProject/` | **原**地图工程，不改 |
| `XiongdaParkMapMergedProject/` | **合并副本**（可删可重建） |
| `xiongda_app/public/webgl/` | 旧语音包（已退役，保留备份） |
| `xiongda_app/public/webgl-map/` | 旧地图包（保留） |
| `xiongda_app/public/webgl-merged/` | **新统一包** |

回退：删除或清空 `webgl-merged/build-info.json`，或设 `VITE_UNITY_MERGED=0`。

## Unity 操作

```powershell
cd F:\jichuang2026\clean_0606
powershell -ExecutionPolicy Bypass -File .\scripts\setup_merged_unity_project.ps1
```

1. Unity Hub → `XiongdaParkMapMergedProject`
2. 打开 `ParkMap3DBlockout.unity`，**先 Stop Play**
3. **Tools → 狗熊岭智慧终端 → 合并工程：挂上 UnityBridge + 模式相机**
4. Play：默认互动熊近景；**C**=聊天 **M**=地图
5. **Tools → 构建合并 WebGL（Development）到 webgl-merged**
6. `cd xiongda_app && npm run dev`

## 前端

- 顶栏 **「全图互动」** = 原「语音聊天」+「地图查询」合并（`TopNavId = world`）
- 有 `webgl-merged/build-info.json` → 加载 `WorldUnityEmbed`（单 WebGL、双熊）
- 闲聊 / 随机动作 → 互动熊（`UnityBridge`）
- 问路（如「海螺湾怎么走」）→ `map-query` → 导览熊跑路（`ParkMapUnityBridge`）
- 导航结束后自动切回聊天，互动熊对齐导览熊位置
- 未构建时显示占位提示；强制关闭合并：`VITE_UNITY_MERGED=0`

## 阶段进度

- [x] 双熊同场景 + 模式显隐 + 相机
- [x] 前端单 WebGL + 模式 API
- [x] 导航结束可自动切回互动熊
- [ ] 正式 WebGL 构建验收
- [ ] 体积瘦身
