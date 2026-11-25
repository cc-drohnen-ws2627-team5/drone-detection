$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..')
$env:DB_PASSWORD = [guid]::NewGuid().ToString('N')
$env:MINIO_ROOT_USER = 'task3-test'
$env:MINIO_ROOT_PASSWORD = [guid]::NewGuid().ToString('N')
$env:MQTT_PASSWORD = [guid]::NewGuid().ToString('N')
$env:MQTT_FIXTURE_SENSOR = [guid]::NewGuid().ToString('N')
$env:API_TOKEN = [guid]::NewGuid().ToString('N')
if (-not $env:API_PORT) { $env:API_PORT = '18000' }
if (-not $env:MQTT_PUBLISHED_PORT) { $env:MQTT_PUBLISHED_PORT = '18883' }
$project = 'task3-test-' + [guid]::NewGuid().ToString('N').Substring(0, 8)
$compose = @('compose', '-p', $project, '-f', 'docker-compose.yml', '-f', 'compose.test.yml')

function Invoke-Compose {
    & docker @compose @args
    if ($LASTEXITCODE -ne 0) { throw "Compose failed: $args" }
}

try {
    Invoke-Compose config --quiet
    Invoke-Compose up --build -d
    Invoke-Compose exec -T api python -m unittest -v tests.test_events tests.test_compose
    Invoke-Compose stop minio
    Invoke-Compose exec -T api python -m tests.recovery publish
    $observed = $false
    for ($attempt = 0; $attempt -lt 20; $attempt++) {
        if ((Invoke-Compose logs --no-color ingestion | Out-String) -match "leaving event unacknowledged") {
            $observed = $true
            break
        }
        Start-Sleep -Seconds 1
    }
    if (-not $observed) { throw "Worker did not encounter the MinIO outage" }
    Invoke-Compose start minio
    Invoke-Compose exec -T api python -m tests.recovery verify
} catch {
    & docker @compose logs --tail 50
    throw
} finally {
    & docker @compose down --volumes
}
