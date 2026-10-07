param(
    [int]$HealthCount = 30,
    [int]$UploadCount = 20,
    [string]$BaseUrl = "http://127.0.0.1:8000",
    [string]$PdfPath = "samples\test_discharge.pdf",
    [string]$ApiKey = $env:API_KEY
)

function Get-Percentile([double[]]$Values, [double]$P) {
    if ($Values.Count -eq 0) { return $null }
    $sorted = $Values | Sort-Object
    $idx = [math]::Floor(($sorted.Count - 1) * $P)
    return $sorted[$idx]
}

function Show-Stats([string]$Name, [double[]]$TimesSec) {
    if ($TimesSec.Count -eq 0) {
        Write-Host "$Name : no samples" -ForegroundColor Red
        return
    }
    $avg = ($TimesSec | Measure-Object -Average).Average
    $p50 = Get-Percentile $TimesSec 0.5
    $p95 = Get-Percentile $TimesSec 0.95
    $min = ($TimesSec | Measure-Object -Minimum).Minimum
    $max = ($TimesSec | Measure-Object -Maximum).Maximum
    Write-Host ("{0,-28} n={1,3}  p50={2,7:N1} ms  p95={3,7:N1} ms  avg={4,7:N1} ms  min={5,7:N1} ms  max={6,7:N1} ms" -f `
        $Name, $TimesSec.Count, ($p50 * 1000), ($p95 * 1000), ($avg * 1000), ($min * 1000), ($max * 1000))
}

function Measure-Get([string]$Url, [int]$Count) {
    $times = New-Object System.Collections.Generic.List[double]
    for ($i = 1; $i -le $Count; $i++) {
        $sec = curl.exe -s -o NUL -w "%{time_total}" $Url
        if ($LASTEXITCODE -eq 0) {
            [void]$times.Add([double]$sec)
        }
    }
    return , $times.ToArray()
}

Write-Host "DocMind latency measure"
Write-Host "BaseUrl=$BaseUrl"
Write-Host ""

Show-Stats "GET /health" (Measure-Get "$BaseUrl/api/v1/health" $HealthCount)
Show-Stats "GET /health/ready" (Measure-Get "$BaseUrl/api/v1/health/ready" $HealthCount)

if (-not $ApiKey -or -not $ApiKey.Trim()) {
    Write-Host ""
    Write-Host "Skip POST /documents: set API_KEY env or pass -ApiKey" -ForegroundColor Yellow
    exit 0
}

if (-not (Test-Path $PdfPath)) {
    Write-Host "PDF not found: $PdfPath" -ForegroundColor Red
    exit 1
}

$fullPdf = (Resolve-Path $PdfPath).Path
$uploadUrl = "$BaseUrl/api/v1/documents"
$tmpBody = Join-Path $env:TEMP "docmind_latency_body.json"
$uploadTimes = New-Object System.Collections.Generic.List[double]
$ok = 0
$fail = 0

Write-Host ""
Write-Host "Uploading $UploadCount files (202 Accepted only, not full worker processing)"

for ($i = 1; $i -le $UploadCount; $i++) {
    $out = curl.exe -s -o $tmpBody -w "%{http_code} %{time_total}" `
        -H "X-API-Key: $ApiKey" `
        -F "file=@${fullPdf};type=application/pdf" `
        $uploadUrl

    if ($LASTEXITCODE -ne 0) {
        $fail++
        continue
    }

    $parts = $out.Trim() -split "\s+"
    if ($parts.Count -lt 2) {
        $fail++
        continue
    }

    $code = $parts[0]
    $sec = [double]$parts[1]
    if ($code -eq "202") {
        $ok++
        [void]$uploadTimes.Add($sec)
    }
    else {
        $fail++
    }
}

Show-Stats "POST /documents (202)" $uploadTimes.ToArray()
Write-Host "Upload OK=$ok FAIL=$fail"
Write-Host ""
Write-Host "Note: upload time is API accept latency (enqueue), not full PDF/LLM processing."
