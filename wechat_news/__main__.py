from __future__ import annotations

import argparse
import json
import logging
from logging.handlers import RotatingFileHandler
import sys
from datetime import datetime
from pathlib import Path

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from .config import load_settings
from .diagnostics import check_openai_connection
from .pipeline import run_pipeline


def configure_logging() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8")
            except OSError:
                pass
    log_dir = Path.cwd() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    log_file = RotatingFileHandler(
        log_dir / "publisher.log", maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    log_file.setFormatter(formatter)
    logging.basicConfig(
        level=logging.INFO,
        handlers=[console, log_file],
    )


def run_once(args: argparse.Namespace) -> int:
    settings = load_settings()
    result = run_pipeline(
        settings,
        dry_run=args.dry_run,
        no_ai=args.no_ai,
        force_publish=args.publish,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def run_scheduler(args: argparse.Namespace) -> int:
    settings = load_settings()
    hour, minute = (int(part) for part in settings.run_time.split(":"))
    scheduler = BlockingScheduler(timezone=settings.timezone)

    def job() -> None:
        try:
            result = run_pipeline(settings, dry_run=args.dry_run, no_ai=args.no_ai)
            logging.getLogger(__name__).info("每日任务完成：%s", result)
        except Exception:
            logging.getLogger(__name__).exception("每日任务失败")

    scheduler.add_job(
        job,
        CronTrigger(hour=hour, minute=minute, timezone=settings.timezone),
        id="daily-wechat-news",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=3600,
    )
    logging.getLogger(__name__).info(
        "调度器已启动，每天 %s (%s) 运行。按 Ctrl+C 停止。", settings.run_time, settings.timezone
    )
    if args.run_now:
        job()
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        return 0
    return 0


def run_check(args: argparse.Namespace) -> int:
    settings = load_settings()
    result = check_openai_connection(settings, show_models=args.show_models)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("endpoint_reachable") else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="每日重大新闻汇总与微信公众号发布")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run = subparsers.add_parser("run", help="立即运行一次")
    run.add_argument("--dry-run", action="store_true", help="只生成本地稿件，不调用微信接口")
    run.add_argument("--no-ai", action="store_true", help="不调用 OpenAI，使用本地简版编辑")
    run.add_argument("--publish", action="store_true", help="上传草稿后立即提交发布")
    run.set_defaults(func=run_once)

    schedule = subparsers.add_parser("schedule", help="启动常驻每日调度器")
    schedule.add_argument("--run-now", action="store_true", help="启动时先立即运行一次")
    schedule.add_argument("--dry-run", action="store_true", help="每天只生成本地稿件")
    schedule.add_argument("--no-ai", action="store_true", help="每天使用本地简版编辑")
    schedule.set_defaults(func=run_scheduler)

    check = subparsers.add_parser("check", help="检查中转站地址、鉴权和模型配置")
    check.add_argument("--show-models", action="store_true", help="鉴权成功后显示全部可用模型")
    check.set_defaults(func=run_check)
    return parser


def main() -> int:
    configure_logging()
    parser = build_parser()
    args = parser.parse_args()
    try:
        return int(args.func(args))
    except Exception as exc:
        logging.getLogger(__name__).exception("运行失败：%s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
