param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Args
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

function Add-ProjectVenvToPath {
    $venvScripts = Join-Path $ProjectRoot "venv\Scripts"
    if (Test-Path $venvScripts) {
        $env:PATH = "$venvScripts;$env:PATH"
    }
}

function Get-PythonCommand {
    $venvPython = Join-Path $ProjectRoot "venv\Scripts\python.exe"
    if (Test-Path $venvPython) {
        return @($venvPython)
    }

    if (Get-Command py -ErrorAction SilentlyContinue) {
        return @("py")
    }

    if (Get-Command python -ErrorAction SilentlyContinue) {
        return @("python")
    }

    throw "Unable to find Python. Activate the project virtual environment or make sure 'py' or 'python' is available on PATH."
}

function Invoke-DevPy {
    param(
        [string[]]$PythonCommand,
        [string[]]$CommandArgs
    )

    $launcher = $PythonCommand[0]
    $launcherArgs = @()

    if ($PythonCommand.Count -gt 1) {
        $launcherArgs = $PythonCommand[1..($PythonCommand.Count - 1)]
    }

    & $launcher @launcherArgs dev.py @CommandArgs
}

function Convert-LegacyArgs {
    param(
        [string[]]$InputArgs
    )

    $converted = New-Object System.Collections.Generic.List[string]

    foreach ($arg in $InputArgs) {
        if ($arg -eq "server:test") {
            $converted.Add("server")
            $converted.Add("--test")
            continue
        }

        if ($arg -eq "fe") {
            $converted.Add("front")
            continue
        }

        if ($arg.StartsWith("fe:")) {
            $converted.Add("front")
            $converted.Add($arg.Substring(3))
            continue
        }

        if ($arg.Contains(":")) {
            $parts = $arg -split ":", 2
            $converted.Add($parts[0])
            $converted.Add($parts[1])
            continue
        }

        $converted.Add($arg)
    }

    return $converted.ToArray()
}

$convertedArgs = Convert-LegacyArgs -InputArgs $Args
Add-ProjectVenvToPath
$pythonCommand = Get-PythonCommand

if ($convertedArgs.Count -eq 0) {
    Invoke-DevPy -PythonCommand $pythonCommand -CommandArgs @("--help")
    exit $LASTEXITCODE
}

Invoke-DevPy -PythonCommand $pythonCommand -CommandArgs $convertedArgs
exit $LASTEXITCODE
