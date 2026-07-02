param(
  [switch]$Visible,
  [switch]$Console
)
$ErrorActionPreference = "Stop"
$Neo4jBin = "E:\tools\WindowsDomainJail\neo4j-community-2026.02.2-windows\neo4j-community-2026.02.2\bin"
$JavaHome = "E:\game\MCmod\bkm\java21"
$Neo4jBat = Join-Path $Neo4jBin "neo4j.bat"
if (!(Test-Path $Neo4jBat)) { throw "neo4j.bat not found: $Neo4jBat" }
if (!(Test-Path $JavaHome)) { throw "JAVA_HOME not found: $JavaHome" }
$env:JAVA_HOME = $JavaHome
$env:PATH = "$JavaHome\bin;$env:PATH"
Write-Host "JAVA_HOME=$env:JAVA_HOME"
Write-Host "Neo4j=$Neo4jBat"
if ($Console) {
  & $Neo4jBat console
  exit $LASTEXITCODE
}
$arg = "/c `"$Neo4jBat`" console"
if ($Visible) {
  Start-Process -FilePath "cmd.exe" -ArgumentList $arg -WorkingDirectory $Neo4jBin
} else {
  Start-Process -FilePath "cmd.exe" -ArgumentList $arg -WorkingDirectory $Neo4jBin -WindowStyle Hidden
}
Write-Host "Neo4j console process launched. Browser: http://localhost:7474 ; Bolt: bolt://localhost:7687"
