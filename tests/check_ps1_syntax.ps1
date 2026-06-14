Set-Location (Join-Path $PSScriptRoot "..")
$script = "scripts\quickstart.ps1"
$errors = $null
$tokens = $null
[void][System.Management.Automation.Language.Parser]::ParseFile($script, [ref]$tokens, [ref]$errors)
if ($errors -and $errors.Count -gt 0) {
    Write-Host "[FAIL] PS1 syntax errors:" -ForegroundColor Red
    foreach ($err in $errors) {
        Write-Host ("  line " + $err.Extent.StartLineNumber + ": " + $err.Message)
    }
    exit 1
} else {
    Write-Host "[OK] PS1 syntax clean (quickstart.ps1)" -ForegroundColor Green
}
