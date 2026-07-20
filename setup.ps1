$ErrorActionPreference = "Stop"
$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvPython = Join-Path $ProjectDir ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $VenvPython)) {
    $SystemPython = (Get-Command python -ErrorAction Stop).Source
    & $SystemPython -m venv (Join-Path $ProjectDir ".venv")
}

& $VenvPython -m pip install -r (Join-Path $ProjectDir "requirements.txt") -i https://pypi.tuna.tsinghua.edu.cn/simple

Write-Host "安装完成。下一步：编辑 .env 填写 OPENAI_API_KEY，然后运行："
Write-Host ".\.venv\Scripts\python.exe -m wechat_news check --show-models"

