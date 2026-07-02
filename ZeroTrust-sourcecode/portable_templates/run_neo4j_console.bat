@echo off
setlocal EnableExtensions
set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
set "JAVA_HOME=%ROOT%\runtime\java21"
set "NEO4J_HOME=%ROOT%\runtime\neo4j"
set "PATH=%JAVA_HOME%\bin;%PATH%"
if not exist "%ROOT%\logs" mkdir "%ROOT%\logs"
call "%NEO4J_HOME%\bin\neo4j.bat" console >> "%ROOT%\logs\neo4j_console.log" 2>&1
