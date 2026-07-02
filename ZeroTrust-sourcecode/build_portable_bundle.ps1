param(
  [string]$BundleName = "无依赖一键启动包",
  [string]$JavaSource = "E:\game\MCmod\bkm\java21",
  [string]$Neo4jSource = "E:\tools\WindowsDomainJail\neo4j-community-2026.02.2-windows\neo4j-community-2026.02.2",
  [string]$PythonSource = "C:\Program Files\Python312"
)
$ErrorActionPreference = "Stop"
$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$ExperimentRoot = Split-Path -Parent $ScriptRoot
$BundleRoot = Join-Path $ExperimentRoot $BundleName
$RuntimeRoot = Join-Path $BundleRoot "runtime"
$LogRoot = Join-Path $BundleRoot "logs"

function Assert-UnderRoot([string]$Path, [string]$Root) {
  $rp = [System.IO.Path]::GetFullPath($Path)
  $rr = [System.IO.Path]::GetFullPath($Root)
  if (-not $rp.StartsWith($rr, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Unsafe path outside root: $rp"
  }
}
function RC([string]$From, [string]$To, [string[]]$Extra = @()) {
  if (!(Test-Path $From)) { throw "Source not found: $From" }
  New-Item -ItemType Directory -Force -Path $To | Out-Null
  $args = @($From,$To,"/E","/NFL","/NDL","/NJH","/NJS","/NP","/R:2","/W:1") + $Extra
  & robocopy @args | Out-Host
  if ($LASTEXITCODE -ge 8) { throw "robocopy failed: $From -> $To, exit=$LASTEXITCODE" }
}
function Stop-ExistingBundle {
  if (!(Test-Path $BundleRoot)) { return }
  Write-Host "[pre] stop existing portable services if any"
  $stopper = Join-Path $BundleRoot "stop_demo.bat"
  if (Test-Path $stopper) {
    Push-Location $BundleRoot
    try {
      $env:NO_PAUSE = "1"
      & cmd /c "call stop_demo.bat <nul" | Out-Host
    } finally {
      Pop-Location
      Remove-Item Env:\NO_PAUSE -ErrorAction SilentlyContinue
    }
  } else {
    Stop-BundlePorts
  }
  Stop-BundlePorts
  Close-BundleWindows
  try {
    Get-CimInstance Win32_Process |
      Where-Object { $_.Name -eq "cmd.exe" -and ($_.CommandLine -like "*run_neo4j_console.bat*" -or $_.CommandLine -like "*run_flask_server.bat*") } |
      ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
  } catch {
    Write-Warning "Could not inspect/close portable cmd launcher windows: $($_.Exception.Message)"
  }
  Close-BundleWindows
  foreach($d in @("M","N","O","P","Q","R","S","T","U","V","W","X","Y","Z")) {
    $drive = "$d`:"
    if(Test-Path "$drive\portable_manifest.json") {
      & subst $drive /D 2>$null | Out-Null
    }
  }
  $stillOpen = @()
  for($i=0; $i -lt 30; $i++) {
    $stillOpen = Get-OpenBundlePorts
    if($stillOpen.Count -eq 0) { break }
    Stop-BundlePorts
    Start-Sleep -Seconds 1
  }
  if($stillOpen.Count -gt 0) {
    throw "Cannot rebuild while ports are still in use: $($stillOpen -join ', '). Please run stop_demo.bat or close the old demo windows, then rerun build_portable_bundle.ps1."
  }
}

function Get-BundleListeningPids {
  $pids = @()
  foreach($port in @(5000,7474,7687)) {
    $lines = & netstat -ano | Select-String -Pattern (":$port\s+.*LISTENING")
    foreach($line in $lines) {
      $parts = ($line.ToString() -split "\s+") | Where-Object { $_ }
      if($parts.Count -gt 0) {
        $pidText = $parts[-1]
        if($pidText -match '^\d+$') { $pids += [int]$pidText }
      }
    }
  }
  $pids | Sort-Object -Unique
}

function Stop-BundlePorts {
  foreach($listenerPid in (Get-BundleListeningPids)) {
    Write-Host "[pre] kill listener PID $listenerPid"
    & cmd /c "taskkill /PID $listenerPid /T /F >nul 2>nul" | Out-Null
    try {
      Stop-Process -Id $listenerPid -Force -ErrorAction SilentlyContinue
    } catch {
      # Keep rebuilding logic deterministic: if the process survives, the port
      # check below will report the exact blocked port instead of failing on
      # stderr from taskkill.
    }
  }
}

function Get-OpenBundlePorts {
  $open = @()
  foreach($port in @(5000,7474,7687)) {
    $lines = & netstat -ano | Select-String -Pattern (":$port\s+.*LISTENING")
    if($lines) { $open += $port }
  }
  $open
}

function Close-BundleWindows {
  foreach($title in @("MABZT-Launcher*","MABZT-Neo4j*","MABZT-Flask*")) {
    & cmd /c "taskkill /FI `"WINDOWTITLE eq $title`" /F >nul 2>nul" | Out-Null
  }
}

foreach($src in @($JavaSource,$Neo4jSource,$PythonSource)) { if (!(Test-Path $src)) { throw "Required source missing: $src" } }
Assert-UnderRoot $BundleRoot $ExperimentRoot
Stop-ExistingBundle
if (Test-Path $BundleRoot) { Remove-Item -LiteralPath $BundleRoot -Recurse -Force }
New-Item -ItemType Directory -Force -Path $BundleRoot,$RuntimeRoot,$LogRoot | Out-Null

Write-Host "[1/8] app code"
RC (Join-Path $ExperimentRoot "实验代码") (Join-Path $BundleRoot "app") @("/XD", ".venv", "__pycache__", ".pytest_cache", "portable_templates", "/XF", "*.pyc", "*.pyo")

Write-Host "[2/8] dataset"
New-Item -ItemType Directory -Force -Path (Join-Path $BundleRoot "data") | Out-Null
RC (Join-Path $ExperimentRoot "实验数据集\mabzt_comm_dataset") (Join-Path $BundleRoot "data\mabzt_comm_dataset") @("/XF", "*.pyc", "*.pyo")

Write-Host "[3/8] result seed"
New-Item -ItemType Directory -Force -Path (Join-Path $BundleRoot "results") | Out-Null
if (!(Test-Path (Join-Path $ExperimentRoot "实验结果\neo4j_import.cypher"))) {
  & (Join-Path $ScriptRoot ".venv\Scripts\python.exe") (Join-Path $ScriptRoot "run_experiments.py")
}
Copy-Item -LiteralPath (Join-Path $ExperimentRoot "实验结果\neo4j_import.cypher") -Destination (Join-Path $BundleRoot "results\neo4j_import.cypher") -Force
foreach($name in @("agent_demo_report.md","dataset_statistics.json","baseline_comparison.csv","validation_summary.csv","risk_detection_summary.csv","root_cause_confusion.csv")){
  $src = Join-Path (Join-Path $ExperimentRoot "实验结果") $name
  if(Test-Path $src){ Copy-Item -LiteralPath $src -Destination (Join-Path (Join-Path $BundleRoot "results") $name) -Force }
}

Write-Host "[4/8] docs"
if(Test-Path (Join-Path $ExperimentRoot "其他文件")){ RC (Join-Path $ExperimentRoot "其他文件") (Join-Path $BundleRoot "docs") @("/XF", "*.tmp") }

Write-Host "[5/8] java"
RC $JavaSource (Join-Path $RuntimeRoot "java21") @("/XD", "demo", "sample", "/XF", "*.pdb")

Write-Host "[6/8] neo4j clean runtime"
RC $Neo4jSource (Join-Path $RuntimeRoot "neo4j") @("/XD", "data", "logs", "/XF", "*.lock")
New-Item -ItemType Directory -Force -Path (Join-Path $RuntimeRoot "neo4j\data"),(Join-Path $RuntimeRoot "neo4j\logs") | Out-Null

Write-Host "[7/8] python"
RC $PythonSource (Join-Path $RuntimeRoot "python312") @("/XD", "__pycache__", "tcl\tk8.6\demos", "/XF", "*.pyc", "*.pyo")
$PythonSiteTarget = Join-Path $RuntimeRoot "python_site"
$VenvSite = Join-Path $ScriptRoot ".venv\Lib\site-packages"
$Wheelhouse = Join-Path $ScriptRoot "python_wheels"
if(Test-Path $VenvSite) {
  RC $VenvSite $PythonSiteTarget @("/XD", "__pycache__", "pip", "pip-*", "setuptools", "setuptools-*", "/XF", "*.pyc", "*.pyo")
} else {
  New-Item -ItemType Directory -Force -Path $PythonSiteTarget | Out-Null
  $BundledPython = Join-Path $RuntimeRoot "python312\python.exe"
  $Req = Join-Path $ScriptRoot "requirements.txt"
  if(Test-Path $Wheelhouse) {
    Write-Host "No .venv found; installing Python deps from local wheelhouse"
    & $BundledPython -m pip install --no-index --find-links $Wheelhouse --target $PythonSiteTarget -r $Req
  } else {
    Write-Host "No .venv or wheelhouse found; installing Python deps with pip"
    & $BundledPython -m pip install --target $PythonSiteTarget -r $Req
  }
  if($LASTEXITCODE -ne 0) { throw "pip dependency install failed, exit=$LASTEXITCODE" }
}

Write-Host "[8/8] portable scripts"
Copy-Item -LiteralPath (Join-Path $ScriptRoot "portable_templates\start_demo.bat") -Destination (Join-Path $BundleRoot "start_demo.bat") -Force
Copy-Item -LiteralPath (Join-Path $ScriptRoot "portable_templates\stop_demo.bat") -Destination (Join-Path $BundleRoot "stop_demo.bat") -Force
Copy-Item -LiteralPath (Join-Path $ScriptRoot "portable_templates\run_neo4j_console.bat") -Destination (Join-Path $BundleRoot "run_neo4j_console.bat") -Force
Copy-Item -LiteralPath (Join-Path $ScriptRoot "portable_templates\run_flask_server.bat") -Destination (Join-Path $BundleRoot "run_flask_server.bat") -Force
Copy-Item -LiteralPath (Join-Path $ScriptRoot "portable_templates\README_一键启动.md") -Destination (Join-Path $BundleRoot "README_一键启动.md") -Force
$manifest = [ordered]@{
  name = "MABZT Agent Dynamic Demo Portable Bundle"
  generated_at = (Get-Date).ToString("s")
  bundle_root = $BundleRoot
  java = "runtime/java21"
  neo4j = "runtime/neo4j"
  python = "runtime/python312"
  python_site = "runtime/python_site"
  app = "app"
  dataset = "data/mabzt_comm_dataset"
  results = "results"
  docs = "docs"
  launcher = "start_demo.bat"
  stopper = "stop_demo.bat"
  alias_strategy = "start_demo.bat creates a temporary SUBST drive alias such as M: so Neo4j and Python use ASCII runtime paths even when the bundle is stored under Chinese directories"
  java_source = $JavaSource
  neo4j_source = $Neo4jSource
  python_source = $PythonSource
  dashboard = "http://127.0.0.1:5000"
  neo4j_browser = "http://127.0.0.1:7474"
  neo4j_user = "neo4j"
  neo4j_password = "Lzj.123456"
}
$manifest | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $BundleRoot "portable_manifest.json") -Encoding UTF8
Write-Host "Bundle completed: $BundleRoot"
