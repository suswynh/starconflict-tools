# 批量 quickbms 解包所有 Star Conflict PAK 文件
# ── 路径配置（可按需修改或通过环境变量覆盖） ──
$ScriptRoot = $PSScriptRoot
$ProjRoot   = Split-Path -Parent $ScriptRoot   # 项目根目录

# quickbms.exe — 外部工具，默认在项目根目录下，支持环境变量
$qbms  = if ($env:QUICKBMS_EXE) { $env:QUICKBMS_EXE } else { "$ProjRoot\quickbms\quickbms.exe" }
# clutch.bms — 与脚本同目录
$bms   = "$ScriptRoot\clutch.bms"
# 游戏 PAK 数据目录 — 必须由用户指定，支持环境变量
$pakDir = if ($env:SC_DATA_DIR) { $env:SC_DATA_DIR } else { "$ProjRoot\StarConflict\data" }
# 解包输出目录
$outDir = if ($env:QUICKBMS_OUT) { $env:QUICKBMS_OUT } else { "$ProjRoot\quickbms_unpacksource" }

New-Item -ItemType Directory -Force -Path $outDir | Out-Null

$paks = Get-ChildItem -LiteralPath $pakDir -Filter "*.pak" -File | Sort-Object Length
$total = $paks.Count
$succeeded = 0
$failed = 0
$totalSize = 0

Write-Host "=== 批量解包 $total 个 PAK 文件 ==="
Write-Host "输出目录: $outDir"
Write-Host ""

foreach ($i in 0..($paks.Count-1)) {
    $pak = $paks[$i]
    $name = $pak.Name
    $size = [math]::Round($pak.Length/1MB, 1)
    $totalSize += $pak.Length

    Write-Host "[$($i+1)/$total] $name ($size MB) ... " -NoNewline

    try {
        $proc = Start-Process -FilePath $qbms `
            -ArgumentList "`"$bms`" `"$($pak.FullName)`" `"$outDir`"" `
            -Wait -NoNewWindow -PassThru

        if ($proc.ExitCode -eq 0) {
            Write-Host "OK" -ForegroundColor Green
            $succeeded++
        } else {
            Write-Host "FAIL (exit=$($proc.ExitCode))" -ForegroundColor Red
            $failed++
        }
    } catch {
        Write-Host "ERROR: $_" -ForegroundColor Red
        $failed++
    }
}

Write-Host ""
Write-Host "=== 完成 ==="
Write-Host "成功: $succeeded  失败: $failed"
Write-Host "总 PAK 大小: $([math]::Round($totalSize/1GB, 1)) GB"

# 统计解包结果
$allFiles = Get-ChildItem -LiteralPath $outDir -Recurse -File -ErrorAction SilentlyContinue
$outSize = ($allFiles | Measure-Object Length -Sum).Sum
Write-Host "解出文件: $($allFiles.Count) 个, $([math]::Round($outSize/1MB, 0)) MB"

$byExt = $allFiles | Group-Object Extension | Sort-Object Count -Descending | Select-Object -First 20
Write-Host "`n文件类型分布:"
$byExt | ForEach-Object { Write-Host "  $($_.Name): $($_.Count)" }
