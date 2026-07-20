# 每日重大新闻汇总与微信公众号发布

这是一个可直接部署的 Python 项目，每天自动抓取国内外新闻、筛选去重、调用 AI 编辑公众号文章，并上传微信公众号草稿箱或按条件自动发布。

## 已配置的中转站

项目已经写入：

```dotenv
OPENAI_BASE_URL=https://token.yiliao.hb.cn/v1
OPENAI_API_MODE=auto
```

已确认该站点的 `/v1/models` 是 OpenAI 兼容接口路径。你只需要打开 `.env` 填写：

```dotenv
OPENAI_API_KEY=你的中转站密钥
OPENAI_MODEL=gpt-5.5
```

如果中转站没有 `gpt-5.5`，可以在安装后运行模型检查，从返回列表中选择实际可用的模型。

`OPENAI_API_MODE=auto` 会优先调用 Responses API；如果中转站不支持该接口，会自动改用 Chat Completions。也可以手动设置为 `responses` 或 `chat_completions`。

## 一键安装

在项目目录打开 PowerShell：

```powershell
.\setup.ps1
```

脚本会创建 `.venv` 虚拟环境并安装依赖。也可以手动安装：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## 检查中转站

没有填写密钥时，检查接口地址：

```powershell
.\.venv\Scripts\python.exe -m wechat_news check
```

填写密钥后，验证鉴权、模型名称并显示模型列表：

```powershell
.\.venv\Scripts\python.exe -m wechat_news check --show-models
```

程序不会打印你的密钥。

## 生成本地测试稿

调用中转站 AI 编辑，但不连接公众号：

```powershell
.\.venv\Scripts\python.exe -m wechat_news run --dry-run
```

完全不调用 AI，只测试新闻抓取和本地编辑：

```powershell
.\.venv\Scripts\python.exe -m wechat_news run --dry-run --no-ai
```

结果保存在 `data/runs/日期/`：

- `article.html`：公众号 HTML 正文
- `article.md`：标题和摘要
- `news.json`：入选新闻、时间和原始链接
- `result.json`：编辑模式、草稿 ID、发布 ID及质量检查结果
- `cover.jpg`：自动生成的公众号封面（连接公众号时生成）

日志保存在 `logs/publisher.log`。

## 连接微信公众号

在 `.env` 填写：

```dotenv
WECHAT_APP_ID=你的AppID
WECHAT_APP_SECRET=你的AppSecret
WECHAT_AUTHOR=每日要闻编辑部
WECHAT_AUTO_PUBLISH=false
```

公众号还需要具备素材、草稿和发布接口权限，并在微信公众平台配置运行电脑或服务器的公网出口 IP 白名单。

上传草稿箱但不自动发布：

```powershell
.\.venv\Scripts\python.exe -m wechat_news run
```

人工明确确认后立即提交发布：

```powershell
.\.venv\Scripts\python.exe -m wechat_news run --publish
```

建议先保持 `WECHAT_AUTO_PUBLISH=false`。即使开启自动发布，AI 编辑失败、国内或国际新闻数量不足时，程序也只上传草稿，不会无人审核发布。

## 每天自动运行

安装每天 07:30 执行的 Windows 计划任务：

```powershell
.\install_windows_task.ps1 -RunTime "07:30"
```

也可以使用 Python 常驻调度器：

```powershell
.\.venv\Scripts\python.exe -m wechat_news schedule --run-now
```

运行时间可在 `.env` 修改：

```dotenv
RUN_TIME=07:30
TIMEZONE=Asia/Shanghai
```

## 新闻源和安全说明

新闻源位于 `config/sources.yml`。程序会：

- 只接受最近时间窗口内、能够确认发布日期的新闻；
- 按时效、来源权重和重大事件关键词评分；
- 去除重复标题并维持国内、国际新闻配额；
- 单个新闻源失效时跳过，不发布空文章；
- 过滤 AI 输出中的脚本、危险链接和不适合公众号的标签；
- 保存全部原始链接，便于发布前核查。

