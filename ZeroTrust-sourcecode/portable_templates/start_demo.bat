@echo off
setlocal EnableExtensions EnableDelayedExpansion
set "REAL_ROOT=%~dp0"
if "%REAL_ROOT:~-1%"=="\" set "REAL_ROOT=%REAL_ROOT:~0,-1%"
set "ROOT=%REAL_ROOT%"
call :ensure_alias
set "JAVA_HOME=%ROOT%\runtime\java21"
set "NEO4J_HOME=%ROOT%\runtime\neo4j"
set "PYTHONHOME=%ROOT%\runtime\python312"
set "PYTHONPATH=%ROOT%\app;%ROOT%\runtime\python_site"
set "PATH=%JAVA_HOME%\bin;%PYTHONHOME%;%PYTHONHOME%\Scripts;%PATH%"
set "HOST=0.0.0.0"
set "PORT=5000"
set "FLASK_DEBUG=0"
set "NEO4J_USER=neo4j"
set "NEO4J_PASSWORD=Lzj.123456"
set "NEO4J_URI=bolt://127.0.0.1:7687"
set "MABZT_DATASET_DIR=%ROOT%\data\mabzt_comm_dataset"
set "MABZT_RESULTS_DIR=%ROOT%\results"
set "MABZT_OTHER_DIR=%ROOT%\docs"
set "MABZT_SQLITE_PATH=%ROOT%\results\runtime.db"
set "LOG_DIR=%ROOT%\logs"
set "MARKER_DIR=%ROOT%\runtime\markers"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"
if not exist "%MARKER_DIR%" mkdir "%MARKER_DIR%"

call :banner
if not exist "%JAVA_HOME%\bin\java.exe" goto missing_runtime
if not exist "%NEO4J_HOME%\bin\neo4j.bat" goto missing_runtime
if not exist "%PYTHONHOME%\python.exe" goto missing_runtime
if not exist "%ROOT%\app\agent_demo_app\app.py" goto missing_runtime
if not exist "%MABZT_DATASET_DIR%\manifest.json" goto missing_runtime

call :is_port_open 7687
if errorlevel 1 (
  echo [MABZT] Initializing bundled Neo4j password if data is fresh...
  if not exist "%NEO4J_HOME%\data\dbms\auth.ini" (
    call "%NEO4J_HOME%\bin\neo4j-admin.bat" dbms set-initial-password --require-password-change=false "%NEO4J_PASSWORD%" >> "%LOG_DIR%\neo4j_init.log" 2>&1
    if errorlevel 1 goto neo4j_init_failed
  )
  echo [MABZT] Starting bundled Neo4j...
  start "MABZT-Neo4j" /min cmd /c ""%ROOT%\run_neo4j_console.bat""
  call :wait_port 7687 90
  if errorlevel 1 goto neo4j_failed
) else (
  echo [MABZT] Neo4j bolt 7687 is already listening; reuse it.
)

call :wait_neo4j_ready 60
if errorlevel 1 goto neo4j_failed

call :check_neo4j_auth
if errorlevel 1 (
  echo [WARN] Neo4j auth check failed. See logs\neo4j_auth_check.log. Flask demo will still start.
) else (
  if exist "%ROOT%\results\neo4j_import.cypher" (
    call :graph_count_ok
    if not errorlevel 1 (
      type nul > "%MARKER_DIR%\neo4j_imported.flag"
      > "%LOG_DIR%\neo4j_import.log" echo [MABZT] Existing Neo4j graph detected; import skipped.
      echo [MABZT] Neo4j graph already present; skip import.
    ) else (
      echo [MABZT] Importing claim graph into Neo4j, first run may take 1-3 minutes...
      call :import_neo4j_graph
      if errorlevel 1 (
        echo [WARN] Neo4j import failed after retries. See logs\neo4j_import.log. Flask demo can still run.
      ) else (
        type nul > "%MARKER_DIR%\neo4j_imported.flag"
        echo [MABZT] Neo4j graph imported.
      )
    )
  )
)

call :is_port_open %PORT%
if errorlevel 1 (
  echo [MABZT] Starting Flask dynamic dashboard...
  start "MABZT-Flask" /min cmd /c ""%ROOT%\run_flask_server.bat""
  call :wait_port %PORT% 60
  if errorlevel 1 goto flask_failed
) else (
  echo [MABZT] Flask port %PORT% is already listening; reuse it.
)

echo.
echo [OK] Dashboard: http://127.0.0.1:%PORT%
echo [OK] Neo4j Browser: http://127.0.0.1:7474  user=neo4j password=Lzj.123456
echo [OK] Logs: %LOG_DIR%
if not "%NO_OPEN%"=="1" start "" "http://127.0.0.1:%PORT%"
exit /b 0

:ensure_alias
rem Neo4j 2026 command scripts may mis-handle non-ASCII parent paths. Use a temporary SUBST drive alias.
for %%D in (M N O P Q R S T U V W X Y Z) do (
  if exist %%D:\portable_manifest.json if exist %%D:\runtime\neo4j\bin\neo4j.bat (
    set "ROOT=%%D:"
    set "SUBST_DRIVE=%%D:"
    exit /b 0
  )
)
for %%D in (M N O P Q R S T U V W X Y Z) do (
  if not exist %%D:\NUL (
    subst %%D: "%REAL_ROOT%" >nul 2>&1
    if not errorlevel 1 (
      set "ROOT=%%D:"
      set "SUBST_DRIVE=%%D:"
      exit /b 0
    )
  )
)
echo [WARN] Could not create an ASCII drive alias with SUBST. Continue with original path.
exit /b 0

:banner
echo [MABZT] Portable root: %REAL_ROOT%
echo [MABZT] Runtime alias: %ROOT%
echo [MABZT] Runtime: bundled Java + bundled Neo4j + bundled Python
echo [MABZT] Data: %MABZT_DATASET_DIR%
exit /b 0

:missing_runtime
echo [ERROR] Bundled runtime incomplete. Check app, data, runtime/java21, runtime/neo4j, runtime/python312.
if not "%NO_PAUSE%"=="1" pause
exit /b 1

:neo4j_init_failed
echo [ERROR] Neo4j initial password setup failed. See logs\neo4j_init.log.
if not "%NO_PAUSE%"=="1" pause
exit /b 2

:neo4j_failed
echo [ERROR] Neo4j did not become ready. See logs\neo4j_console.log, logs\neo4j_ready.log and logs\neo4j_init.log.
if not "%NO_PAUSE%"=="1" pause
exit /b 3

:flask_failed
echo [ERROR] Flask did not open port %PORT%. See logs\flask.log.
if not "%NO_PAUSE%"=="1" pause
exit /b 4

:check_neo4j_auth
call "%NEO4J_HOME%\bin\cypher-shell.bat" -a bolt://127.0.0.1:7687 -d neo4j -u "%NEO4J_USER%" -p "%NEO4J_PASSWORD%" --non-interactive "RETURN 1 AS ok;" > "%LOG_DIR%\neo4j_auth_check.log" 2>&1
exit /b %ERRORLEVEL%

:wait_neo4j_ready
set "_MAX=%1"
for /L %%i in (1,1,%_MAX%) do (
  call "%NEO4J_HOME%\bin\cypher-shell.bat" -a bolt://127.0.0.1:7687 -d neo4j -u "%NEO4J_USER%" -p "%NEO4J_PASSWORD%" --non-interactive "RETURN 1 AS ok;" > "%LOG_DIR%\neo4j_ready.log" 2>&1
  if not errorlevel 1 exit /b 0
  ping -n 3 127.0.0.1 >nul
)
exit /b 1

:graph_count_ok
call "%NEO4J_HOME%\bin\cypher-shell.bat" -a bolt://127.0.0.1:7687 -d neo4j -u "%NEO4J_USER%" -p "%NEO4J_PASSWORD%" --non-interactive --format plain "MATCH (n:ZTNode) RETURN count(n) AS nodes;" > "%LOG_DIR%\neo4j_graph_count.log" 2>&1
if errorlevel 1 exit /b 1
findstr /R /C:"^[1-9][0-9]*$" "%LOG_DIR%\neo4j_graph_count.log" >nul
exit /b %ERRORLEVEL%

:import_neo4j_graph
> "%LOG_DIR%\neo4j_import.log" echo [MABZT] Import started %DATE% %TIME%
for /L %%R in (1,1,3) do (
  echo [MABZT] Import attempt %%R >> "%LOG_DIR%\neo4j_import.log"
  call :wait_neo4j_ready 30
  call "%NEO4J_HOME%\bin\cypher-shell.bat" -a bolt://127.0.0.1:7687 -d neo4j -u "%NEO4J_USER%" -p "%NEO4J_PASSWORD%" --non-interactive -f "%ROOT%\results\neo4j_import.cypher" >> "%LOG_DIR%\neo4j_import.log" 2>&1
  if not errorlevel 1 (
    call :graph_count_ok
    if not errorlevel 1 exit /b 0
  )
  ping -n 6 127.0.0.1 >nul
)
exit /b 1

:is_port_open
powershell -NoProfile -ExecutionPolicy Bypass -Command "try{$c=[Net.Sockets.TcpClient]::new('127.0.0.1',%1);$c.Close();exit 0}catch{exit 1}"
exit /b %ERRORLEVEL%

:wait_port
set "_PORT=%1"
set "_MAX=%2"
for /L %%i in (1,1,%_MAX%) do (
  call :is_port_open %_PORT%
  if not errorlevel 1 exit /b 0
  ping -n 3 127.0.0.1 >nul
)
exit /b 1
