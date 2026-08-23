param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectDir,

    [Parameter(Mandatory = $true)]
    [double]$PlainAt,

    [double]$CardAt = -1,

    [Parameter(Mandatory = $true)]
    [double]$EndAt
)

$ErrorActionPreference = 'Stop'
$resolvedProject = (Resolve-Path -LiteralPath $ProjectDir).Path
$publicDir = Join-Path $resolvedProject 'public'
$captions = Join-Path $resolvedProject 'captions.json'
$timeline = Join-Path $resolvedProject 'production-timeline.json'
$validator = Join-Path $PSScriptRoot 'validate_package.py'
$portableValidator = Join-Path $PSScriptRoot 'portable_project.py'
$visualValidator = Join-Path $PSScriptRoot 'validate_portable_visuals.py'
$skillRoot = Split-Path -Parent $PSScriptRoot
$cli = Join-Path $skillRoot 'assets/runtime/node_modules/hyperframes/bin/hyperframes.mjs'

foreach ($required in @($publicDir, $captions, $timeline, $validator, $portableValidator, $visualValidator, $cli)) {
    if (-not (Test-Path -LiteralPath $required)) {
        throw "Missing required preflight input: $required"
    }
}

& python $portableValidator validate $resolvedProject
if ($LASTEXITCODE -ne 0) {
    throw 'Portable project validation failed.'
}

& python $visualValidator $resolvedProject
if ($LASTEXITCODE -ne 0) {
    throw 'Portable visual validation failed.'
}

& python $validator --captions $captions --timeline $timeline --strict
if ($LASTEXITCODE -ne 0) {
    throw 'Strict package validation failed.'
}

$runner = @('node', $cli)

Push-Location $resolvedProject
try {
    & $runner[0] $runner[1] check $publicDir --json
    if ($LASTEXITCODE -ne 0) {
        throw 'HyperFrames check failed.'
    }

    $times = @($PlainAt)
    if ($CardAt -ge 0) {
        $times += $CardAt
    }
    $times += $EndAt
    $at = ($times | ForEach-Object { $_.ToString('0.###', [Globalization.CultureInfo]::InvariantCulture) }) -join ','
    $output = Join-Path $resolvedProject 'qa/smoke-preflight'

    & $runner[0] $runner[1] snapshot $publicDir --at $at --no-end --output $output --describe false
    if ($LASTEXITCODE -ne 0) {
        throw 'Three-frame smoke snapshot failed.'
    }

    Write-Output "FAST_PREFLIGHT_OK=$output"
} finally {
    Pop-Location
}
