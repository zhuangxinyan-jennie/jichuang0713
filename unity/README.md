# unity — 熊大 WebGL 源码工程

演示时浏览器加载的是 **`xiongda_app/public/webgl-merged/`**（已打包 WebGL），**不是**本目录。  
改角色动作 / 地图导航时，在 Unity 里改下面工程，再重新导出 WebGL。

| 目录 | 用途 | 日常改哪个 |
|------|------|------------|
| `XiongdaParkMapMergedProject/` | **合并工程**（聊天熊 + 地图导览） | ✅ **主要改这个** |
| `XiongdaUnityProject/` | 互动熊原版（备份/回退） | 一般不动 |
| `XiongdaParkMapProject/` | 地图原版（备份/回退） | 一般不动 |

## 打开工程

Unity Hub → **Add** → 选择：

```text
clean_0606/unity/XiongdaParkMapMergedProject
```

## 导出 WebGL

```powershell
# 在仓库根目录
powershell -ExecutionPolicy Bypass -File .\scripts\build_merged_webgl.ps1
```

或 Unity 菜单：**Tools → 狗熊岭智慧终端 → 构建合并 WebGL**

产物目录：`xiongda_app/public/webgl-merged/`

## 重建合并工程

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup_merged_unity_project.ps1
```

详见 [docs/UNITY_MERGED.md](../docs/UNITY_MERGED.md)、[docs/PROJECT_MAP.md](../docs/PROJECT_MAP.md)。

**说明：** `XiongdaUnityProject` 在本仓库为指向 `unity_model` 的目录联接（junction），移动位置不影响实际工程文件。
