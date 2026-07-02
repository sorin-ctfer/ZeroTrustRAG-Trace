param(
  [switch]$StartNeo4j,
  [switch]$VisibleNeo4j,
  [switch]$SkipExperiments
)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
if (!$env:NEO4J_USER) { $env:NEO4J_USER = "neo4j" }
if (!$env:NEO4J_PASSWORD) { $env:NEO4J_PASSWORD = "Lzj.123456" }
if (!$env:NEO4J_URI) { $env:NEO4J_URI = "bolt://localhost:7687" }
$Python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (!(Test-Path $Python)) {
  Write-Host "Creating local virtual environment..."
  python -m venv .venv
  $Python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
}
Write-Host "Installing/checking Python dependencies..."
& $Python -m pip install -r .\requirements.txt
if ($StartNeo4j) {
  Write-Host "Starting local Neo4j using neo4jhelp.txt settings..."
  if ($VisibleNeo4j) { .\start_neo4j.ps1 -Visible } else { .\start_neo4j.ps1 }
}
if (!$SkipExperiments) {
  Write-Host "[1/2] generating dataset"
  & $Python .\generate_dataset.py
  Write-Host "[2/2] running experiments"
  & $Python .\run_experiments.py
}
Write-Host "Starting Flask dashboard at http://127.0.0.1:5000"
& $Python -m agent_demo_app.app


