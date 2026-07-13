# 版本管理说明

这个项目使用 Git 管理代码版本。

## 这套方案管什么

会进 Git 的内容：

- 代码、脚本、README、配置模板
- Python 依赖清单，例如 `requirements*.txt`
- 前端依赖锁定文件，例如 `package-lock.json`
- Unity 项目源码文件，如果它们没有被 `.gitignore` 排除

不会进 Git 的内容：

- Python 虚拟环境，例如 `.venv`
- 前端依赖目录，例如 `node_modules`
- 日志、缓存、运行输出
- 模型权重和下载的大文件，例如 `pretrained_models`
- zip 压缩包和生成出来的 Unity WebGL Build
- 参考素材包、第三方源码仓库，例如 `cozy_ref`、`third_party/CosyVoice`
- 本机私有环境变量文件，例如 `env.local.ps1`

原因：虚拟环境和依赖目录体积很大，而且不同电脑经常不兼容。正确做法是保存依赖清单和安装脚本，回到某个版本后再重建环境。

## 保存一个版本

先看改了哪些文件：

```powershell
git status
```

保存当前版本：

```powershell
git add .
git commit -m "说明这次改了什么"
```

给重要版本打标签：

```powershell
git tag v1.0-demo
```

## 查看历史版本

```powershell
git log --oneline --decorate --graph
```

## 回到旧版本看看

```powershell
git switch --detach 版本号或标签名
```

例如：

```powershell
git switch --detach v1.0-demo
```

如果只是看看旧代码，看完回到最新版本：

```powershell
git switch main
```

## 真正回退到旧版本

更稳的做法是新建一个分支：

```powershell
git switch -c restore-v1 v1.0-demo
```

这样不会破坏现在的 `main` 分支。

## 恢复环境

前端依赖：

```powershell
cd xiongda_app
npm install
```

Python 依赖按对应模块安装，例如：

```powershell
cd bear_agent
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements_visitor_pc.txt
```

CosyVoice 依赖优先使用根目录已有脚本：

```powershell
.\setup-cosyvoice-venv.ps1
```

模型文件如果不存在，使用：

```powershell
.\download-cosyvoice-model.ps1
```

## 一个实用习惯

每次准备大改之前先提交一次：

```powershell
git add .
git commit -m "baseline before ..."
```

这样后面试错时，随时能回到这条线。
