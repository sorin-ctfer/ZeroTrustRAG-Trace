param(
  [string]$User = $(if ($env:NEO4J_USER) { $env:NEO4J_USER } else { "neo4j" }),
  [string]$Password = $(if ($env:NEO4J_PASSWORD) { $env:NEO4J_PASSWORD } else { "Lzj.123456" }),
  [string]$Address = $(if ($env:NEO4J_URI) { $env:NEO4J_URI } else { "bolt://localhost:7687" })
)
$ErrorActionPreference = "Stop"
$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$ExperimentRoot = Split-Path -Parent $ScriptRoot
$Cypher = Join-Path $ExperimentRoot "实验结果\neo4j_import.cypher"
$Neo4jBin = "E:\tools\WindowsDomainJail\neo4j-community-2026.02.2-windows\neo4j-community-2026.02.2\bin"
$JavaHome = "E:\game\MCmod\bkm\java21"
$Shell = Join-Path $Neo4jBin "cypher-shell.bat"
if (!(Test-Path $Shell)) { throw "cypher-shell.bat not found: $Shell" }
$env:JAVA_HOME = $JavaHome
$env:PATH = "$JavaHome\bin;$env:PATH"
if (!(Test-Path $Cypher)) {
  Write-Host "Cypher file not found; running experiments first..."
  & (Join-Path $ScriptRoot ".venv\Scripts\python.exe") (Join-Path $ScriptRoot "run_experiments.py")
}
Write-Host "Importing $Cypher into $Address as $User"
& $Shell -a $Address -u $User -p $Password -f $Cypher
exit $LASTEXITCODE

