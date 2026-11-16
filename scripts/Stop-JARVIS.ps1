$ErrorActionPreference = 'Continue'
foreach ($port in @(8787,5173)) {
  $connections = Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue
  foreach ($connection in $connections) {
    $processId = $connection.OwningProcess
    if ($processId -gt 0) { Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue; Write-Host "Stopped listener on port $port (PID $processId)" }
  }
}
