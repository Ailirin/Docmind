param(
    [int]$Count = 30,
    [int]$DelayMs = 200,
    [string]$BaseUrl = "http://127.0.0.1:8000",
    [string]$PdfPath = "samples\test_discharge.pdf"
)

if (-not (Test-Path $PdfPath)) {
    throw "PDF not found: $PdfPath"
}

$fullPdf = (Resolve-Path $PdfPath).Path
$url = "$BaseUrl/api/v1/documents"
$tmpBody = Join-Path $env:TEMP "docmind_load_body.json"

Write-Host "Uploading $Count files to $url"
Write-Host "File: $fullPdf"
Write-Host "Delay: ${DelayMs}ms"
Write-Host ""

$ok = 0
$fail = 0

for ($i = 1; $i -le $Count; $i++) {
    $code = curl.exe -s -o $tmpBody -w "%{http_code}" `
        -X POST $url `
        -F "file=@${fullPdf};type=application/pdf"

    $body = ""
    if (Test-Path $tmpBody) {
        $body = Get-Content $tmpBody -Raw -ErrorAction SilentlyContinue
    }

    if ($LASTEXITCODE -ne 0) {
        $fail++
        Write-Host "[$i/$Count] FAIL curl exit=$LASTEXITCODE" -ForegroundColor Red
    }
    elseif ($code -eq "202") {
        $ok++
        Write-Host "[$i/$Count] OK $body"
    }
    else {
        $fail++
        Write-Host "[$i/$Count] FAIL HTTP $code $body" -ForegroundColor Red
    }

    Start-Sleep -Milliseconds $DelayMs
}

Write-Host ""
Write-Host "Done. OK=$ok FAIL=$fail"