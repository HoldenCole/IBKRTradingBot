<#
Remove the scheduled tasks. Leaves the venv and code in place.
#>

$ErrorActionPreference = "Stop"

foreach ($name in @("IBKRBot", "IBKRBot-EodPush")) {
    if (Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $name -Confirm:$false
        Write-Host "[uninstall] removed scheduled task: $name" -ForegroundColor Cyan
    } else {
        Write-Host "[uninstall] no task named $name" -ForegroundColor Yellow
    }
}
Write-Host "[uninstall] done. .venv and code left in place; delete by hand if desired."
