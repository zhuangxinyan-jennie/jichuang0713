@echo off
REM 始终在 bear_agent 仓库根目录执行，避免「No module named 'board_bridge'」
cd /d "%~dp0"
python -m board_bridge.run_visitor_pipeline %*
exit /b %ERRORLEVEL%
