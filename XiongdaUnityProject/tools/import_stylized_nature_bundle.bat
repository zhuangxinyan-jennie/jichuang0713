@echo off
chcp 65001 >nul
set UNITY=F:\APPS\Unity\2018.4.35f1\Editor\Unity.exe
set PROJECT=F:\jichuang2026\unity_model\XiongdaUnityProject
set PKG=%PROJECT%\PackagesToImport\StylizedNatureBundle.unitypackage
set LOG=%PROJECT%\import_stylized_nature.log

if not exist "%UNITY%" (
  echo 未找到 Unity，请用记事本编辑本 bat，把 UNITY= 改成你的 Unity.exe 路径。
  pause
  exit /b 1
)
if not exist "%PKG%" (
  echo 未找到资源包: %PKG%
  pause
  exit /b 1
)

echo 将关闭其他 Unity 窗口后再运行！正在以批处理模式导入（勿同时打开本工程）...
echo 日志: %LOG%

"%UNITY%" -batchmode -quit -nographics -projectPath "%PROJECT%" -importPackage "%PKG%" -logFile "%LOG%"
echo 退出码: %ERRORLEVEL%
echo 若失败请打开日志查看；常见原因：另一 Unity 实例已打开此工程。
pause
