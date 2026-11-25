[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$composeFile = Join-Path $repositoryRoot 'infra/compose.pg17-test.yml'
$image = 'postgres:17.12-alpine3.24@sha256:34261f594522cf41dfcb76aefd42b9d201098b0e6b23c9c68733f169e4218b6f'
$hostPort = 55436
$project = 'drip-pg17-' + [guid]::NewGuid().ToString('N')
$containerId = $null
$networkId = $null
$started = $false
$originalEnvironment = @{}

function Invoke-DockerChecked {
    param([Parameter(Mandatory)][string[]]$Arguments)
    & docker @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Docker command failed with exit code $LASTEXITCODE."
    }
}

function Get-ProjectContainers {
    param([Parameter(Mandatory)][string]$ProjectName)
    $ids = @(& docker ps -aq --filter "label=com.docker.compose.project=$ProjectName")
    if ($LASTEXITCODE -ne 0) {
        throw 'Unable to inspect the task-scoped Docker project.'
    }
    return @($ids | Where-Object { $_ })
}

function Get-ProjectNetworks {
    param([Parameter(Mandatory)][string]$ProjectName)
    $ids = @(& docker network ls -q --filter "label=com.docker.compose.project=$ProjectName")
    if ($LASTEXITCODE -ne 0) {
        throw 'Unable to inspect task-scoped Docker networks.'
    }
    return @($ids | Where-Object { $_ })
}

function Set-TaskEnvironment {
    param([Parameter(Mandatory)][string]$Name, [AllowNull()][string]$Value)
    if (-not $originalEnvironment.ContainsKey($Name)) {
        $originalEnvironment[$Name] = [Environment]::GetEnvironmentVariable($Name, 'Process')
    }
    [Environment]::SetEnvironmentVariable($Name, $Value, 'Process')
}

try {
    if (-not (Test-Path -LiteralPath (Join-Path $repositoryRoot 'pnpm-workspace.yaml'))) {
        throw 'Repository root could not be confirmed.'
    }
    if (-not (Test-Path -LiteralPath $composeFile)) {
        throw 'The dedicated PG17 Compose file is missing.'
    }

    $engine = & docker info --format '{{.OSType}}|{{.ServerVersion}}' 2>$null
    if ($LASTEXITCODE -ne 0 -or $engine -notmatch '^linux\|.+$') {
        throw 'Docker Linux engine is unavailable; no PG17 service was created.'
    }

    $listeners = @(Get-NetTCPConnection -LocalPort $hostPort -State Listen -ErrorAction SilentlyContinue)
    if ($listeners.Count -gt 0) {
        throw 'The dedicated PG17 loopback port is already occupied.'
    }

    if ((Get-ProjectContainers -ProjectName $project).Count -ne 0 -or
        (Get-ProjectNetworks -ProjectName $project).Count -ne 0) {
        throw 'The unique task-scoped Docker project unexpectedly already exists.'
    }

    $pullOutput = & docker pull $image 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw 'The exact digest-pinned official PostgreSQL image could not be resolved.'
    }
    $resolvedDigests = & docker image inspect --format '{{json .RepoDigests}}' $image 2>$null
    if ($LASTEXITCODE -ne 0 -or $resolvedDigests -notmatch 'postgres@sha256:34261f594522cf41dfcb76aefd42b9d201098b0e6b23c9c68733f169e4218b6f') {
        throw 'The pulled PostgreSQL image digest did not match the approved pin.'
    }

    $passwordBytes = [byte[]]::new(32)
    $random = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try { $random.GetBytes($passwordBytes) } finally { $random.Dispose() }
    $password = [Convert]::ToHexString($passwordBytes).ToLowerInvariant()
    Set-TaskEnvironment -Name 'DRIP_PG17_TEST_USER' -Value 'drip_pg17_test'
    Set-TaskEnvironment -Name 'DRIP_PG17_TEST_PASSWORD' -Value $password

    Invoke-DockerChecked -Arguments @('compose', '-p', $project, '-f', $composeFile, 'config', '--quiet')
    Invoke-DockerChecked -Arguments @('compose', '-p', $project, '-f', $composeFile, 'up', '-d', '--wait', 'postgres-pg17')
    $started = $true

    $ids = @(Get-ProjectContainers -ProjectName $project)
    if ($ids.Count -ne 1) {
        throw 'The task-scoped project did not contain exactly one PostgreSQL container.'
    }
    $containerId = $ids[0]
    $networks = @(Get-ProjectNetworks -ProjectName $project)
    if ($networks.Count -ne 1) { throw 'The task-scoped project network inventory was unexpected.' }
    $networkId = $networks[0]
    $inspectJson = & docker inspect $containerId
    if ($LASTEXITCODE -ne 0) { throw 'Unable to attest the created PostgreSQL container.' }
    $container = ($inspectJson -join "`n") | ConvertFrom-Json
    $resolvedImageId = & docker image inspect --format '{{.Id}}' $image 2>$null
    if ($LASTEXITCODE -ne 0 -or $container.Image -ne $resolvedImageId) {
        throw 'The created container did not use the locally resolved digest-pinned image.'
    }
    if ($container.Config.Image -ne $image) {
        throw 'The created container image reference did not match the exact digest pin.'
    }
    if ($container.Config.Labels.'com.docker.compose.project' -ne $project -or
        $container.Config.Labels.'com.docker.compose.service' -ne 'postgres-pg17') {
        throw 'The created container ownership labels were unexpected.'
    }
    $tmpfsPaths = @($container.HostConfig.Tmpfs.PSObject.Properties.Name)
    if ($tmpfsPaths.Count -ne 1 -or $tmpfsPaths[0] -ne '/var/lib/postgresql/data' -or
        $container.Mounts.Count -ne 0) {
        throw 'The PostgreSQL data path was not exclusively mounted as task-scoped tmpfs.'
    }
    $binding = $container.NetworkSettings.Ports.'5432/tcp'
    if ($binding.Count -ne 1 -or $binding[0].HostIp -ne '127.0.0.1' -or
        $binding[0].HostPort -ne [string]$hostPort) {
        throw 'The PostgreSQL port was not bound exclusively to the approved loopback endpoint.'
    }
    $networkNames = @($container.NetworkSettings.Networks.PSObject.Properties.Name)
    if ($networkNames.Count -ne 1 -or $networkNames[0] -ne "${project}_default") {
        throw 'The PostgreSQL container network was not isolated to this Compose project.'
    }
    $network = (& docker network inspect $networkId | ConvertFrom-Json)[0]
    $networkContainerIds = @($network.Containers.PSObject.Properties.Name)
    $networkContainerIdMatches = $false
    if ($networkContainerIds.Count -eq 1) {
        $networkContainerId = [string]$networkContainerIds[0]
        $containerIdLength = $containerId.Length
        $networkContainerIdLength = $networkContainerId.Length
        $validIdLengths = $containerIdLength -ge 12 -and $containerIdLength -le 64 -and
            $networkContainerIdLength -ge 12 -and $networkContainerIdLength -le 64
        $networkContainerIdMatches = $validIdLengths -and (
            $containerId.StartsWith($networkContainerId, [StringComparison]::OrdinalIgnoreCase) -or
            $networkContainerId.StartsWith($containerId, [StringComparison]::OrdinalIgnoreCase)
        )
    }
    if ($LASTEXITCODE -ne 0 -or $network.Name -ne "${project}_default" -or
        $network.Labels.'com.docker.compose.project' -ne $project -or
        $network.Driver -ne 'bridge' -or $network.Scope -ne 'local' -or
        $networkContainerIds.Count -ne 1 -or
        -not $networkContainerIdMatches) {
        throw "The created Docker network was not task-scoped and local (name=$($network.Name); " +
            "project-label=$($network.Labels.'com.docker.compose.project'); driver=$($network.Driver); " +
            "scope=$($network.Scope); attached=$($networkContainerIds.Count); " +
            "container-id-match=$networkContainerIdMatches)."
    }

    $attestation = & docker exec $containerId psql -U drip_pg17_test -d drip_pg17_admin -At -c "SELECT current_database() || '|' || current_user || '|' || current_setting('server_version') || '|' || current_setting('server_encoding') || '|' || current_setting('block_size') || '|' || (SELECT system_identifier::text FROM pg_catalog.pg_control_system());"
    if ($LASTEXITCODE -ne 0 -or $attestation -notmatch '^drip_pg17_admin\|drip_pg17_test\|17\.\d+\|UTF8\|\d+\|\d+$') {
        throw 'PostgreSQL target attestation failed; the migration test suite was not started.'
    }
    Write-Output "Attested PostgreSQL target: $attestation"

    $passwordForUrl = $password
    $adminUrl = "postgresql+asyncpg://drip_pg17_test:${passwordForUrl}@127.0.0.1:55436/drip_pg17_admin"
    Set-TaskEnvironment -Name 'DRIP_PG17_TEST_ADMIN_URL' -Value $adminUrl
    Set-TaskEnvironment -Name 'ENVIRONMENT' -Value 'test'
    Set-TaskEnvironment -Name 'DRIP_ENV_FILE' -Value ''
    $inheritedPythonPath = [Environment]::GetEnvironmentVariable('PYTHONPATH', 'Process')
    $pythonPath = $repositoryRoot
    if ($inheritedPythonPath) {
        $pythonPath += [IO.Path]::PathSeparator + $inheritedPythonPath
    }
    Set-TaskEnvironment -Name 'PYTHONPATH' -Value $pythonPath

    Push-Location $repositoryRoot
    try {
        & uv run --project apps/api --locked --extra dev --python 3.14.7 pytest -c apps/api/pyproject.toml apps/api/database_tests/pg17 -o "addopts=" -m integration -v
        $testExitCode = $LASTEXITCODE
    } finally {
        Pop-Location
    }
    if ($testExitCode -ne 0) {
        throw "PG17 migration test suite failed with exit code $testExitCode."
    }
    Write-Output 'PG17 migration test suite completed successfully.'
} catch {
    Write-Error $_.Exception.Message
    exit 1
} finally {
    if ($started -and $containerId) {
        $remaining = @(Get-ProjectContainers -ProjectName $project)
        $remainingNetworks = @(Get-ProjectNetworks -ProjectName $project)
        if ($remaining.Count -eq 1 -and $remaining[0] -eq $containerId -and
            $remainingNetworks.Count -eq 1 -and $remainingNetworks[0] -eq $networkId) {
            & docker compose -p $project -f $composeFile down
            if ($LASTEXITCODE -ne 0) {
                Write-Error 'Task-scoped service shutdown failed; no broad cleanup was attempted.'
            } else {
                Write-Output 'Stopped and removed only the attested task-scoped PG17 container/network; no volume removal was requested.'
            }
        } else {
            Write-Error 'Cleanup ownership was ambiguous; no container or network removal was attempted.'
        }
    }
    foreach ($name in $originalEnvironment.Keys) {
        [Environment]::SetEnvironmentVariable($name, $originalEnvironment[$name], 'Process')
    }
    if ($password) { $password = $null; $passwordForUrl = $null; $adminUrl = $null }
}
