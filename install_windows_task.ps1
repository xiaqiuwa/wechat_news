param(
    [string]$TaskName = "Daily-WeChat-News",
    [string]$RunTime = "07:30"
)

$ErrorActionPreference = "Stop"
$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvPython = Join-Path $ProjectDir ".venv\Scripts\python.exe"
if (Test-Path -LiteralPath $VenvPython) {
    $Python = $VenvPython
} else {
    throw "未找到虚拟环境，请先运行 .\setup.ps1"
}
$Arguments = "-m wechat_news run"

$Action = New-ScheduledTaskAction -Execute $Python -Argument $Arguments -WorkingDirectory $ProjectDir
$Trigger = New-ScheduledTaskTrigger -Daily -At $RunTime
$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Description "每天汇总重大新闻并生成微信公众号草稿" `
    -Force

Write-Host "已创建计划任务：$TaskName，每天 $RunTime 运行。"
