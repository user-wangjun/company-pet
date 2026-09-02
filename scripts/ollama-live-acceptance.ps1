[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string] $RuntimeExe,

    [string[]] $Models = @("qwen3.5:0.8b", "qwen3.5:2b"),

    [string] $Label = "runtime",

    [string] $ModelRoot = "",

    [switch] $CleanModelRoot
)

$ErrorActionPreference = "Stop"

function Write-Marker([string] $Name, [string] $Value) {
    Write-Output ("{0}={1}" -f $Name, $Value)
}

function Get-PropertyValue($Object, [string] $Name) {
    if ($null -eq $Object) { return $null }
    $property = $Object.PSObject.Properties[$Name]
    if ($null -eq $property) { return $null }
    return $property.Value
}

function Write-RunLog([string] $Line) {
    if ($script:LogPath) {
        Add-Content -LiteralPath $script:LogPath -Value $Line -Encoding utf8
    }
}

function Get-OwnedProcessIds([int] $RootPid) {
    $processes = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Select-Object ProcessId, ParentProcessId, ExecutablePath)
    if (-not ($processes | Where-Object { [int] $_.ProcessId -eq $RootPid })) {
        return @()
    }
    $owned = [System.Collections.Generic.HashSet[int]]::new()
    [void] $owned.Add($RootPid)
    $changed = $true
    while ($changed) {
        $changed = $false
        foreach ($process in $processes) {
            $processId = [int] $process.ProcessId
            $parentPid = [int] $process.ParentProcessId
            if (-not $owned.Contains($processId) -and $owned.Contains($parentPid)) {
                [void] $owned.Add($processId)
                $changed = $true
            }
        }
    }
    return @($owned | Sort-Object)
}

function Stop-OwnedProcessTree([System.Diagnostics.Process] $Process) {
    if ($null -eq $Process) { return @() }
    try { $rootPid = [int] $Process.Id } catch { return @() }
    if ($rootPid -le 0) { return @() }
    $ownedBeforeStop = @(Get-OwnedProcessIds -RootPid $rootPid)
    if ($ownedBeforeStop.Count -eq 0) { $ownedBeforeStop = @($rootPid) }
    $taskkill = Join-Path $env:SystemRoot "System32\taskkill.exe"
    if (Test-Path -LiteralPath $taskkill) {
        & $taskkill /PID $rootPid /T /F *> $null
    } else {
        try { $Process.Kill($true) } catch { }
    }
    try { [void] $Process.WaitForExit(15000) } catch { }
    Start-Sleep -Milliseconds 250
    $livePids = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        ForEach-Object { [int] $_.ProcessId })
    return @($ownedBeforeStop | Where-Object { $livePids -contains $_ })
}

function Read-JsonResponse(
    [System.Net.Http.HttpClient] $Client,
    [string] $Url
) {
    $request = [System.Net.Http.HttpRequestMessage]::new(
        [System.Net.Http.HttpMethod]::Get,
        $Url
    )
    [void] $request.Headers.Accept.Add("application/json")
    $response = $Client.SendAsync(
        $request,
        [System.Net.Http.HttpCompletionOption]::ResponseContentRead
    ).GetAwaiter().GetResult()
    $body = $response.Content.ReadAsStringAsync().GetAwaiter().GetResult()
    Write-RunLog ("GET {0} status={1} body={2}" -f $Url, [int] $response.StatusCode, $body)
    $payload = $null
    if ($body.Trim()) {
        try { $payload = $body | ConvertFrom-Json } catch { $payload = $null }
    }
    $result = [pscustomobject]@{
        Status = [int] $response.StatusCode
        Body = $body
        Payload = $payload
    }
    $response.Dispose()
    $request.Dispose()
    return $result
}

function Pull-Model(
    [System.Net.Http.HttpClient] $Client,
    [string] $BaseUrl,
    [string] $Model
) {
    $request = [System.Net.Http.HttpRequestMessage]::new(
        [System.Net.Http.HttpMethod]::Post,
        "$BaseUrl/api/pull"
    )
    [void] $request.Headers.Accept.Add("application/x-ndjson")
    $json = @{ model = $Model; stream = $true } | ConvertTo-Json -Compress
    $request.Content = [System.Net.Http.StringContent]::new(
        $json,
        [System.Text.Encoding]::UTF8,
        "application/json"
    )
    Write-RunLog ("POST {0}/api/pull model={1} body={2}" -f $BaseUrl, $Model, $json)
    $response = $Client.SendAsync(
        $request,
        [System.Net.Http.HttpCompletionOption]::ResponseHeadersRead
    ).GetAwaiter().GetResult()
    if (-not $response.IsSuccessStatusCode) {
        $body = $response.Content.ReadAsStringAsync().GetAwaiter().GetResult()
        Write-RunLog ("PULL_ERROR model={0} status={1} body={2}" -f $Model, [int] $response.StatusCode, $body)
        $response.Dispose()
        $request.Dispose()
        throw "Model pull failed for $Model (HTTP $([int] $response.StatusCode))."
    }

    $stream = $response.Content.ReadAsStreamAsync().GetAwaiter().GetResult()
    $reader = [System.IO.StreamReader]::new($stream)
    $done = $false
    $lastReportedPercent = -1
    $lastReportedStatus = ""
    try {
        while ($null -ne ($line = $reader.ReadLine())) {
            if (-not $line.Trim()) { continue }
            Write-RunLog ("PULL model={0} line={1}" -f $Model, $line)
            try { $event = $line | ConvertFrom-Json } catch { throw "Invalid pull event for $Model." }
            $eventError = Get-PropertyValue $event "error"
            if ($eventError -and "$eventError".Trim()) {
                throw "Model pull failed for ${Model}: $eventError"
            }
            $status = "$(Get-PropertyValue $event "status")".Trim()
            $completed = Get-PropertyValue $event "completed"
            $total = Get-PropertyValue $event "total"
            if ($completed -and $total) {
                $percent = [math]::Floor(([double] $completed / [double] $total) * 100)
                if ($percent -ge $lastReportedPercent + 5 -or $status -ne $lastReportedStatus -or $percent -ge 100) {
                    Write-Output ("PULL_PROGRESS={0} percent={1} completed={2} total={3} status={4}" -f $Model, $percent, $completed, $total, $status)
                    $lastReportedPercent = $percent
                    $lastReportedStatus = $status
                }
            } elseif ($status -and $status -ne $lastReportedStatus) {
                Write-Output ("PULL_PROGRESS={0} status={1}" -f $Model, $status)
                $lastReportedStatus = $status
            }
            if ((Get-PropertyValue $event "done") -eq $true -or $status -ieq "success") {
                $done = $true
                break
            }
        }
    } finally {
        $reader.Dispose()
        $stream.Dispose()
        $response.Dispose()
        $request.Dispose()
    }
    if (-not $done) { throw "Model pull ended without a completion event for $Model." }
}

function Get-ModelNames($Payload) {
    $models = Get-PropertyValue $Payload "models"
    if ($null -eq $models) { return @() }
    return @($models | ForEach-Object {
        $name = Get-PropertyValue $_ "name"
        if (-not $name) { $name = Get-PropertyValue $_ "model" }
        if ($name) { "$name" }
    })
}

function Assert-ModelPresent($Payload, [string] $Model) {
    $names = @(Get-ModelNames $Payload)
    if (-not ($names -contains $Model)) {
        throw "Model $Model was not present in /api/tags after pull."
    }
}

function New-ChatRequest([string] $Model, [string] $Nonce) {
    return @{
        model = $Model
        messages = @(
            @{
                role = "user"
                content = "Reply with one short sentence containing nonce $Nonce and the model name $Model."
            }
        )
        stream = $false
        think = $false
        chat_template_kwargs = @{ enable_thinking = $false }
        reasoning_effort = "none"
    } | ConvertTo-Json -Depth 8 -Compress
}

function Invoke-Chat(
    [System.Net.Http.HttpClient] $Client,
    [string] $BaseUrl,
    [string] $Model,
    [string] $Nonce
) {
    $request = [System.Net.Http.HttpRequestMessage]::new(
        [System.Net.Http.HttpMethod]::Post,
        "$BaseUrl/v1/chat/completions"
    )
    [void] $request.Headers.Accept.Add("application/json")
    $json = New-ChatRequest -Model $Model -Nonce $Nonce
    $request.Content = [System.Net.Http.StringContent]::new(
        $json,
        [System.Text.Encoding]::UTF8,
        "application/json"
    )
    Write-RunLog ("POST {0}/v1/chat/completions model={1} nonce={2} body={3}" -f $BaseUrl, $Model, $Nonce, $json)
    $started = [System.Diagnostics.Stopwatch]::StartNew()
    $response = $Client.SendAsync(
        $request,
        [System.Net.Http.HttpCompletionOption]::ResponseContentRead
    ).GetAwaiter().GetResult()
    $body = $response.Content.ReadAsStringAsync().GetAwaiter().GetResult()
    $started.Stop()
    Write-RunLog ("CHAT_RESPONSE model={0} nonce={1} status={2} body={3}" -f $Model, $Nonce, [int] $response.StatusCode, $body)
    if (-not $response.IsSuccessStatusCode) {
        $statusCode = [int] $response.StatusCode
        $response.Dispose()
        $request.Dispose()
        throw "Chat failed for $Model (HTTP $statusCode)."
    }
    try { $payload = $body | ConvertFrom-Json } catch { $payload = $null }
    $choices = Get-PropertyValue $payload "choices"
    $firstChoice = if ($choices) { @($choices)[0] } else { $null }
    $message = Get-PropertyValue $firstChoice "message"
    $content = Get-PropertyValue $message "content"
    if ($content -isnot [string] -or -not $content.Trim()) {
        throw "Chat response for $Model did not contain a non-empty choices[0].message.content string."
    }
    $trimmed = $content.Trim()
    if ($trimmed -match "^<think>[\s\S]*</think>$") {
        throw "Chat response for $Model contained only reasoning in message.content."
    }
    return [pscustomobject]@{
        Content = $trimmed
        ElapsedMs = [int64] $started.ElapsedMilliseconds
        Status = [int] $response.StatusCode
    }
}

$resolvedRuntime = $null
$runtimeProcess = $null
$modelDirectory = $null
$createdRoot = $false
$script:LogPath = $null
$client = $null
$ownedProcessExit = $false
$cleanupPassed = $false

try {
    if (-not [System.IO.Path]::IsPathRooted($RuntimeExe)) {
        throw "RuntimeExe must be an absolute path."
    }
    $resolvedRuntime = (Resolve-Path -LiteralPath $RuntimeExe).Path
    if (-not (Test-Path -LiteralPath $resolvedRuntime -PathType Leaf)) {
        throw "Runtime executable does not exist: $resolvedRuntime"
    }
    $runtimeRoot = Split-Path -Parent $resolvedRuntime
    $serverPath = Join-Path $runtimeRoot "lib\ollama\llama-server.exe"
    if (-not (Test-Path -LiteralPath $serverPath -PathType Leaf)) {
        throw "Runtime is missing lib/ollama/llama-server.exe: $serverPath"
    }
    if (-not $Models -or $Models.Count -eq 0) { throw "At least one model is required." }
    foreach ($model in $Models) {
        if (-not $model.Trim() -or $model.Contains("..") -or $model.Contains("\") -or $model.Contains("/")) {
            throw "Unsafe model name: $model"
        }
    }

    if ($ModelRoot) {
        if (-not [System.IO.Path]::IsPathRooted($ModelRoot)) { throw "ModelRoot must be an absolute path." }
        $modelDirectory = [System.IO.Path]::GetFullPath($ModelRoot)
        New-Item -ItemType Directory -Path $modelDirectory -Force | Out-Null
    } else {
        $createdRoot = $true
        $modelDirectory = Join-Path ([System.IO.Path]::GetTempPath()) ("yuxin-ollama-acceptance-" + [guid]::NewGuid().ToString("N"))
        New-Item -ItemType Directory -Path $modelDirectory -Force | Out-Null
    }
    $script:LogPath = Join-Path $modelDirectory "acceptance.log"
    New-Item -ItemType File -Path $script:LogPath -Force | Out-Null

    $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 0)
    $listener.Start()
    $port = ([System.Net.IPEndPoint] $listener.LocalEndpoint).Port
    $listener.Stop()
    $hostValue = "127.0.0.1:$port"
    $baseUrl = "http://$hostValue"

    $startInfo = [System.Diagnostics.ProcessStartInfo]::new()
    $startInfo.FileName = $resolvedRuntime
    [void] $startInfo.ArgumentList.Add("serve")
    $startInfo.WorkingDirectory = $runtimeRoot
    $startInfo.UseShellExecute = $false
    $startInfo.CreateNoWindow = $true
    # The acceptance process must stay independent of PowerShell's async
    # runspace callbacks. HTTP evidence is written below; runtime stdout is
    # intentionally not redirected because a callback can outlive this
    # runspace on Windows PowerShell hosts.
    $startInfo.RedirectStandardOutput = $false
    $startInfo.RedirectStandardError = $false
    $startInfo.Environment["OLLAMA_HOST"] = $hostValue
    $startInfo.Environment["OLLAMA_MODELS"] = $modelDirectory
    $startInfo.Environment["OLLAMA_NO_CLOUD"] = "1"
    $startInfo.Environment["OLLAMA_KEEP_ALIVE"] = "5m"
    $runtimeProcess = [System.Diagnostics.Process]::new()
    $runtimeProcess.StartInfo = $startInfo
    Write-RunLog ("START label={0} exe={1} host={2} models={3} noCloud=1 keepAlive=5m" -f $Label, $resolvedRuntime, $hostValue, $modelDirectory)
    if (-not $runtimeProcess.Start()) { throw "Could not start bundled Ollama runtime." }

    $client = [System.Net.Http.HttpClient]::new()
    $client.Timeout = [System.TimeSpan]::FromMinutes(45)
    $health = $null
    $deadline = [System.DateTime]::UtcNow.AddSeconds(30)
    do {
        try { $health = Read-JsonResponse -Client $client -Url "$baseUrl/api/version" } catch { $health = $null }
        if ($health -and $health.Status -ge 200 -and $health.Status -lt 300) { break }
        Start-Sleep -Milliseconds 250
    } while ([System.DateTime]::UtcNow -lt $deadline -and -not $runtimeProcess.HasExited)
    $version = Get-PropertyValue $health.Payload "version"
    if ($health -and $health.Status -ge 200 -and $health.Status -lt 300 -and "$version".Trim()) {
        Write-Marker "BUNDLED_RUNTIME_HEALTH" ("PASS label={0} version={1} exe={2} host={3} models={4} noCloud=1" -f $Label, $version, $resolvedRuntime, $hostValue, $modelDirectory)
    } else {
        throw "Bundled runtime health check failed."
    }

    $tags = Read-JsonResponse -Client $client -Url "$baseUrl/api/tags"
    if ($tags.Status -lt 200 -or $tags.Status -ge 300) { throw "Initial /api/tags failed." }
    Write-Output ("TAGS_STATUS={0} label={1} models={2}" -f $tags.Status, $Label, ((Get-ModelNames $tags.Payload) -join ","))

    foreach ($model in $Models) {
        Write-Output ("PULL_START={0} label={1}" -f $model, $Label)
        Pull-Model -Client $client -BaseUrl $baseUrl -Model $model
        $tags = Read-JsonResponse -Client $client -Url "$baseUrl/api/tags"
        if ($tags.Status -lt 200 -or $tags.Status -ge 300) { throw "Post-pull /api/tags failed for $model." }
        Assert-ModelPresent -Payload $tags.Payload -Model $model
        Write-Marker "PULL_DONE" $model

        $chatResponses = @()
        $nonces = @(
            ("YUXIN" + [guid]::NewGuid().ToString("N").Substring(0, 12)),
            ("YUXIN" + [guid]::NewGuid().ToString("N").Substring(0, 12))
        )
        foreach ($nonce in $nonces) {
            $chatResponses += Invoke-Chat -Client $client -BaseUrl $baseUrl -Model $model -Nonce $nonce
        }
        $first = $chatResponses[0]
        $second = $chatResponses[1]
        $firstHash = [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData([Text.Encoding]::UTF8.GetBytes($first.Content)))
        $secondHash = [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData([Text.Encoding]::UTF8.GetBytes($second.Content)))
        if ($first.Content -eq "嗯，我听着。" -or $second.Content -eq "嗯，我听着。") {
            throw "Chat response matched the deterministic local fallback."
        }
        if ($first.Content -eq $second.Content -and -not ($first.Content.Contains($nonces[0]) -and $second.Content.Contains($nonces[1]))) {
            throw "Two nonce-varying chat prompts produced the same content without nonce evidence."
        }
        Write-Marker ("CHAT[{0}]" -f $model) ("PASS label={0} contentLength={1}/{2} contentSha256={3}/{4} elapsedMs={5}/{6}" -f $Label, $first.Content.Length, $second.Content.Length, $firstHash, $secondHash, $first.ElapsedMs, $second.ElapsedMs)
    }

    Write-Marker "REAL_GENERATION" ("PASS label={0} models={1}" -f $Label, ($Models -join ","))
} catch {
    Write-Marker "ACCEPTANCE_ERROR" ("label={0} message={1}" -f $Label, $_.Exception.Message)
    throw
} finally {
    if ($null -ne $client) { $client.Dispose() }
    $ownedAfterStop = Stop-OwnedProcessTree -Process $runtimeProcess
    $ownedProcessExit = ($ownedAfterStop.Count -eq 0)
    Write-Marker "OWNED_PROCESS_TREE_EXIT" ("{0} label={1} rootPid={2} remaining={3}" -f $(if ($ownedProcessExit) { "PASS" } else { "FAIL" }), $Label, $(if ($runtimeProcess) { $runtimeProcess.Id } else { "none" }), ($ownedAfterStop -join ","))
    $shouldCleanModelRoot = $createdRoot -or $CleanModelRoot
    if ($ownedProcessExit -and $shouldCleanModelRoot -and (Test-Path -LiteralPath $modelDirectory)) {
        [System.IO.Directory]::Delete($modelDirectory, $true)
    }
    $cleanupPassed = if ($shouldCleanModelRoot) {
        -not (Test-Path -LiteralPath $modelDirectory)
    } else {
        $true
    }
    $cleanupState = if ($shouldCleanModelRoot) {
        if ($cleanupPassed) { "PASS" } else { "FAIL" }
    } else {
        "SKIPPED_EXPLICIT_MODEL_ROOT"
    }
    Write-Marker "ACCEPTANCE_TEMP_CLEANUP" ("{0} label={1}" -f $cleanupState, $Label)
}

if (-not $ownedProcessExit -or -not $cleanupPassed) { exit 1 }
