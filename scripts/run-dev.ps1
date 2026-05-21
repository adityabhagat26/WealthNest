param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Args
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

function Add-ProjectVenvToPath {
    $venvCandidates = @(
        (Join-Path $ProjectRoot "venv\Scripts"),
        (Join-Path $ProjectRoot ".venv\Scripts")
    )

    foreach ($venvScripts in $venvCandidates) {
        if (Test-Path $venvScripts) {
            $env:PATH = "$venvScripts;$env:PATH"
            break
        }
    }
}

function Get-PythonCommand {
    $venvPythonCandidates = @(
        (Join-Path $ProjectRoot "venv\Scripts\python.exe"),
        (Join-Path $ProjectRoot ".venv\Scripts\python.exe")
    )

    foreach ($venvPython in $venvPythonCandidates) {
        if (Test-Path $venvPython) {
            return @($venvPython)
        }
    }

    if (Get-Command py -ErrorAction SilentlyContinue) {
        try {
            & py -c "import sys" 2>$null | Out-Null
            if ($LASTEXITCODE -eq 0) {
                return @("py")
            }
        }
        catch {
            # fall through to other launchers
        }
    }

    if (Get-Command python -ErrorAction SilentlyContinue) {
        return @("python")
    }

    throw "Unable to find Python. Activate the project virtual environment or make sure 'py' or 'python' is available on PATH."
}

function Get-PythonVersion {
    param(
        [string[]]$PythonCommand
    )

    $launcher = $PythonCommand[0]
    $launcherArgs = @()
    if ($PythonCommand.Count -gt 1) {
        $launcherArgs = $PythonCommand[1..($PythonCommand.Count - 1)]
    }

    $versionRaw = & $launcher @launcherArgs -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
    if ($LASTEXITCODE -ne 0) {
        return $null
    }

    return $versionRaw.Trim()
}

function Is-SupportedPythonVersion {
    param(
        [string]$Version
    )

    if (-not $Version -or $Version -notmatch "^\d+\.\d+$") {
        return $false
    }

    $parts = $Version.Split(".")
    $major = [int]$parts[0]
    $minor = [int]$parts[1]

    return ($major -eq 3 -and $minor -ge 11 -and $minor -le 13)
}

function Resolve-SupportedPythonCommand {
    $candidates = @()

    $venvPythonCandidates = @(
        (Join-Path $ProjectRoot "venv\Scripts\python.exe"),
        (Join-Path $ProjectRoot ".venv\Scripts\python.exe")
    )

    foreach ($venvPython in $venvPythonCandidates) {
        if (Test-Path $venvPython) {
            $candidates += ,@($venvPython)
        }
    }

    if (Get-Command py -ErrorAction SilentlyContinue) {
        $candidates += ,@("py")
    }
    if (Get-Command python -ErrorAction SilentlyContinue) {
        $candidates += ,@("python")
    }

    foreach ($candidate in $candidates) {
        $version = Get-PythonVersion -PythonCommand $candidate
        if (Is-SupportedPythonVersion -Version $version) {
            return $candidate
        }
    }

    $defaultCandidate = Get-PythonCommand
    $detected = Get-PythonVersion -PythonCommand $defaultCandidate
    throw "Unsupported Python version detected ($detected). Use Python 3.11, 3.12, or 3.13 for this project."
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
$pythonCommand = Resolve-SupportedPythonCommand

if ($convertedArgs.Count -eq 0) {
    Invoke-DevPy -PythonCommand $pythonCommand -CommandArgs @("--help")
    exit $LASTEXITCODE
}

Invoke-DevPy -PythonCommand $pythonCommand -CommandArgs $convertedArgs
exit $LASTEXITCODE
