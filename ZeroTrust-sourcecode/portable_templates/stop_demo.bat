@echo off
setlocal EnableExtensions
set "REAL_ROOT=%~dp0"
if "%REAL_ROOT:~-1%"=="\" set "REAL_ROOT=%REAL_ROOT:~0,-1%"
echo [MABZT] Stopping dashboard and bundled Neo4j by ports 5000/7474/7687...
call :kill_ports_once
for /L %%I in (1,1,20) do (
  call :any_port_open
  if errorlevel 1 goto ports_closed
  call :kill_ports_once
  ping -n 2 127.0.0.1 >nul
)
echo [WARN] Some demo ports are still listening. Close old demo windows or run this script again.
:ports_closed
echo [MABZT] Closing portable cmd launcher windows...
taskkill /FI "WINDOWTITLE eq MABZT-Launcher*" /F >nul 2>nul
taskkill /FI "WINDOWTITLE eq MABZT-Neo4j*" /F >nul 2>nul
taskkill /FI "WINDOWTITLE eq MABZT-Flask*" /F >nul 2>nul
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'cmd.exe' -and ($_.CommandLine -like '*run_neo4j_console.bat*' -or $_.CommandLine -like '*run_flask_server.bat*') } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue } } catch { }" >nul 2>nul
for %%D in (M N O P Q R S T U V W X Y Z) do (
  if exist %%D:\portable_manifest.json if exist %%D:\runtime\neo4j\bin\neo4j.bat (
    echo Removing SUBST alias %%D:
    subst %%D: /D >nul 2>nul
  )
)
echo [OK] Stopped if processes were running.
if not "%NO_PAUSE%"=="1" pause
exit /b 0

:kill_ports_once
for %%P in (5000 7474 7687) do (
  for /f "tokens=5" %%A in ('netstat -ano ^| findstr /R /C:":%%P .*LISTENING"') do (
    echo Killing PID %%A on port %%P
    taskkill /PID %%A /T /F >nul 2>nul
  )
)
exit /b 0

:any_port_open
for %%P in (5000 7474 7687) do (
  netstat -ano | findstr /R /C:":%%P .*LISTENING" >nul
  if not errorlevel 1 exit /b 0
)
exit /b 1
