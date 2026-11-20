#requires -Version 7.0
param(
    [string]$ModelsDirectory,
    [ValidateRange(1024, 65535)][int]$Port = 11437
)

$ErrorActionPreference = 'Stop'
if (-not $ModelsDirectory) {
    $ModelsDirectory = $env:OLLAMA_MODELS
}
if (-not $ModelsDirectory) {
    $ModelsDirectory = Join-Path $env:USERPROFILE '.ollama/models'
}

$library = Join-Path (Split-Path -Parent (Get-Command ollama.exe).Source) 'lib/ollama'
$rocm = Join-Path $library 'rocm_v7_1'
$hip = Join-Path $rocm 'ggml-hip.dll'
$server = Join-Path $library 'llama-server.exe'
if (-not (Test-Path -LiteralPath $hip) -or -not (Test-Path -LiteralPath $server)) {
    throw 'Ta instalacja Ollamy musi zawierać llama-server.exe oraz biblioteki ROCm w lib/ollama.'
}

$manifestPath = Join-Path $ModelsDirectory 'manifests/registry.ollama.ai/library/gemma4/e4b'
if (-not (Test-Path -LiteralPath $manifestPath)) {
    throw 'Pobierz model poleceniem ollama pull gemma4:e4b lub wskaż folder modeli przez -ModelsDirectory.'
}
$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
$weights = @($manifest.layers | Where-Object mediaType -EQ 'application/vnd.ollama.image.model')
if ($weights.Count -ne 1 -or $weights[0].digest -notmatch '^sha256:[0-9a-f]{64}$') {
    throw 'Nie znaleziono pliku wag Gemmy E4B w tym manifeście.'
}
$model = Join-Path $ModelsDirectory ('blobs/' + ($weights[0].digest -replace ':', '-'))
if (-not (Test-Path -LiteralPath $model)) {
    throw 'Brakuje pliku wag. Ponów ollama pull gemma4:e4b.'
}

$previousPath = $env:Path
$previousBackend = $env:GGML_BACKEND_PATH
try {
    $env:Path = "$library;$rocm;$previousPath"
    $env:GGML_BACKEND_PATH = $hip
    $options = @(
        '-m', $model, '--alias', 'gemma4:e4b', '--host', '127.0.0.1', '--port', "$Port",
        '-c', '4096', '-np', '1', '-ngl', 'all', '-ot', '^.*$=ROCm0',
        '--reasoning', 'on', '--reasoning-budget', '256', '--no-mmproj', '--no-webui', '--offline'
    )
    & $server @options
    exit $LASTEXITCODE
} finally {
    $env:Path = $previousPath
    $env:GGML_BACKEND_PATH = $previousBackend
}
