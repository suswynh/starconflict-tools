# ============================================================================
# Noesis 批量 MSH → FBX 导出脚本 (PowerShell)
# 命名规则：plasma_gun_mod1.mdl-msh000 → plasma_gun_mod1h000.fbx
# 输出保持多层级目录结构
#
# 用法：
#   .\batch_noesis_fbx.ps1 -DryRun
#   .\batch_noesis_fbx.ps1 -InputDir "models\weapons" -OutputDir "fbx_output\weapons"
# ============================================================================

param(
    [string]$NoesisExe = "",
    [string]$InputDir = "",
    [string]$OutputDir = "",
    [switch]$DryRun,
    [switch]$Force,
    [int]$Limit = 0,
    [string]$LogFile = ""
)

$ErrorActionPreference = "Stop"
$script:StartTime = Get-Date

# ----------------------------------------------------------------------------
# 默认路径
# ----------------------------------------------------------------------------
$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $ScriptRoot) { $ScriptRoot = Get-Location }

if (-not $NoesisExe)  { $NoesisExe  = Join-Path $ScriptRoot "NOESIS\Noesis64.exe" }
if (-not $InputDir)   { $InputDir   = Join-Path $ScriptRoot "quickbms_unpacksource" }
if (-not $OutputDir)  { $OutputDir  = Join-Path $ScriptRoot "fbx_output" }
if (-not $LogFile)    { $LogFile    = Join-Path $ScriptRoot "batch_noesis_fbx.log" }

# ----------------------------------------------------------------------------
# 验证
# ----------------------------------------------------------------------------
if (-not (Test-Path $NoesisExe)) {
    Write-Error "未找到 Noesis: $NoesisExe"
    exit 1
}
if (-not (Test-Path $InputDir)) {
    Write-Error "输入目录不存在: $InputDir"
    exit 1
}

$InputDir  = (Resolve-Path $InputDir).Path.TrimEnd('\')
$OutputDir = $OutputDir.TrimEnd('\')

# ----------------------------------------------------------------------------
# 命名转换：.mdl-msh000 → h000.fbx
# ----------------------------------------------------------------------------
function ConvertTo-FbxName {
    param([string]$FileName)
    return $FileName -replace '\.mdl-msh(\d+)$', '$1.fbx'
}

# ----------------------------------------------------------------------------
# 日志
# ----------------------------------------------------------------------------
function Write-Log {
    param([string]$Message, [string]$Level = "INFO")
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[$timestamp] [$Level] $Message"
    Add-Content -Path $LogFile -Value $line
    switch ($Level) {
        "ERROR"   { Write-Host $line -ForegroundColor Red }
        "WARN"    { Write-Host $line -ForegroundColor Yellow }
        "SUCCESS" { Write-Host $line -ForegroundColor Green }
        default   { Write-Host $line }
    }
}

# ----------------------------------------------------------------------------
# Noesis 导出（注：命令行模式可能不可用，推荐 GUI Batch Process）
# ----------------------------------------------------------------------------
function Invoke-NoesisExport {
    param([string]$InputPath, [string]$OutputPath)

    $outDir = Split-Path -Parent $OutputPath
    if (-not (Test-Path $outDir)) {
        New-Item -ItemType Directory -Path $outDir -Force | Out-Null
    }
    try {
        $proc = Start-Process -FilePath $NoesisExe `
            -ArgumentList "?cmode `"$InputPath`" `"$OutputPath`"" `
            -NoNewWindow -Wait -PassThru
        if ($proc.ExitCode -ne 0) { return $false }
        if ((Test-Path $OutputPath) -and ((Get-Item $OutputPath).Length -gt 0)) {
            return $true
        }
        return $false
    } catch {
        Write-Log "异常: $_" "ERROR"
        return $false
    }
}

# ----------------------------------------------------------------------------
# 主流程
# ----------------------------------------------------------------------------
Write-Host ""
Write-Host "╔══════════════════════════════════════════════════════════╗"
Write-Host "║   Noesis 批量 MSH → FBX   (.mdl-msh000 → h000.fbx)      ║"
Write-Host "╚══════════════════════════════════════════════════════════╝"
Write-Host ""
Write-Host "Noesis:    $NoesisExe"
Write-Host "输入目录:  $InputDir"
Write-Host "输出目录:  $OutputDir"
if ($DryRun) { Write-Host "模式:      预演" -ForegroundColor Cyan }
Write-Host ""

Write-Log "=== 启动 ==="
Write-Log "输入: $InputDir  输出: $OutputDir"

# ----------------------------------------------------------------------------
# [1/3] 扫描
# ----------------------------------------------------------------------------
Write-Host "[1/3] 扫描模型文件..." -ForegroundColor Cyan
$mshFiles = @(Get-ChildItem -Path $InputDir -Recurse -File `
    | Where-Object { $_.Name -match '\.mdl-msh\d+$' })

$totalFiles = $mshFiles.Count
Write-Host "       找到 $totalFiles 个 .mdl-msh* 文件"
if ($totalFiles -eq 0) { Write-Host "无文件，退出。" -ForegroundColor Yellow; exit 0 }

# 扩展名统计
$extStats = $mshFiles | ForEach-Object {
    if ($_.Name -match '(\.mdl-msh\d+)$') { $matches[1] }
} | Group-Object | Sort-Object Count -Descending
Write-Host "       扩展名分布 (前10):"
$extStats | Select-Object -First 10 | ForEach-Object {
    Write-Host "         $($_.Name): $($_.Count)"
}

# 目录层级
$dirs = $mshFiles | ForEach-Object {
    $_.DirectoryName.Substring($InputDir.Length).TrimStart('\')
} | Select-Object -Unique | Sort-Object
Write-Host "       目录层级: $($dirs.Count) 个"

# ----------------------------------------------------------------------------
# 预演
# ----------------------------------------------------------------------------
if ($DryRun) {
    Write-Host ""
    Write-Host "[预演] 前20个文件命名:" -ForegroundColor Cyan
    $mshFiles | Select-Object -First 20 | ForEach-Object {
        $rel    = $_.FullName.Substring($InputDir.Length).TrimStart('\')
        $outName = ConvertTo-FbxName $_.Name
        $relDir  = Split-Path -Parent $rel
        if ($relDir) { $outRel = Join-Path $relDir $outName }
        else         { $outRel = $outName }
        Write-Host "  $rel  →  $outRel"
    }
    Write-Host ""
    Write-Host "目录层级预览 (前10):"
    $dirs | Select-Object -First 10 | ForEach-Object { Write-Host "  $_\" }
    if ($dirs.Count -gt 10) { Write-Host "  ... 共 $($dirs.Count) 个" }
    Write-Host ""
    Write-Host "预演完成。移除 -DryRun 执行导出。"
    exit 0
}

if ($Limit -gt 0) {
    $mshFiles = $mshFiles | Select-Object -First $Limit
    Write-Host "       限制: $Limit 个"
}

# ----------------------------------------------------------------------------
# [2/3] 导出
# ----------------------------------------------------------------------------
Write-Host ""
Write-Host "[2/3] 开始批量导出..." -ForegroundColor Cyan

$successCount = 0
$failCount    = 0
$skipCount    = 0
$totalFiles   = $mshFiles.Count
$failLogFile  = $LogFile -replace '\.log$', '_failed.log'

for ($i = 0; $i -lt $totalFiles; $i++) {
    $file = $mshFiles[$i]
    $idx  = $i + 1

    # 相对路径 + 命名转换（保持目录层级）
    $rel    = $file.FullName.Substring($InputDir.Length).TrimStart('\')
    $relDir = Split-Path -Parent $rel
    $outName = ConvertTo-FbxName $file.Name
    if ($relDir) { $outPath = Join-Path $OutputDir $relDir $outName }
    else         { $outPath = Join-Path $OutputDir $outName }

    # 断点续传
    if ((-not $Force) -and (Test-Path $outPath) -and ((Get-Item $outPath).Length -gt 0)) {
        $skipCount++
        if ($skipCount % 500 -eq 0) {
            Write-Host "  [$idx/$totalFiles] ... 已跳过 $skipCount" -ForegroundColor DarkGray
        }
        continue
    }

    if ($idx % 100 -eq 0 -or $idx -eq 1) {
        $elapsed = (Get-Date) - $script:StartTime
        Write-Host "  [$idx/$totalFiles] 成功:$successCount 失败:$failCount 跳过:$skipCount | $($elapsed.ToString('hh\:mm\:ss'))"
    }

    $result = Invoke-NoesisExport -InputPath $file.FullName -OutputPath $outPath
    if ($result) { $successCount++ }
    else {
        $failCount++
        Add-Content -Path $failLogFile -Value $rel
        Write-Log "失败: $rel" "ERROR"
    }
}

# ----------------------------------------------------------------------------
# [3/3] 结果
# ----------------------------------------------------------------------------
$totalElapsed = (Get-Date) - $script:StartTime
Write-Host ""
Write-Host "[3/3] 导出完成!" -ForegroundColor Green
Write-Host ""
Write-Host ("  命名规则: .mdl-msh000 → h000.fbx")
Write-Host ("  总文件:  {0,-8}  成功:  {1,-8}" -f $totalFiles, $successCount)
Write-Host ("  失败:    {0,-8}  跳过:  {1,-8}" -f $failCount, $skipCount)
Write-Host ("  耗时:    {0}" -f $totalElapsed.ToString('hh\:mm\:ss'))
Write-Host ""

Write-Log "=== 完成 === 总:$totalFiles 成功:$successCount 失败:$failCount 跳过:$skipCount"
if ($failCount -gt 0) { Write-Host "失败列表: $failLogFile" -ForegroundColor Yellow }
Write-Host "输出目录: $OutputDir"
