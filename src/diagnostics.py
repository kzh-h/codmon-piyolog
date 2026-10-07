# src/diagnostics.py

import asyncio
import json
import logging
import os
import platform
import re
import sys
import time
import traceback
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from typing import Any

from playwright.async_api import (
    Browser,
    BrowserContext,
    ConsoleMessage,
    Dialog,
    Frame,
    Page,
    Request,
    Response,
)

from src.gcs import upload_directory_to_gcs
from src.utils import JST

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent
CLOUD_RUN_ENV_KEYS = (
    "CLOUD_RUN_JOB",
    "CLOUD_RUN_EXECUTION",
    "CLOUD_RUN_TASK_INDEX",
    "K_REVISION",
)

FORM_STATE_JS = """() => {
    const text = el => (el ? el.textContent.trim() : null);
    const id = el => el.name || el.id || el.className || el.tagName;
    return {
        selects: [...document.querySelectorAll('select')]
            .map((el, i) => ({
                index: i,
                id: id(el),
                value: el.value,
                text: text(el.selectedOptions[0]),
            })),
        textareas: [...document.querySelectorAll('textarea')].map(
            (el, i) => ({ index: i, id: id(el), value: el.value })
        ),
        checked: [...document.querySelectorAll(
            'input[type=radio]:checked, input[type=checkbox]:checked'
        )].map(el => ({ type: el.type, id: id(el), value: el.value })),
    };
}"""

ENV_JS = """() => ({
    userAgent: navigator.userAgent,
    webdriver: navigator.webdriver,
    language: navigator.language,
    timeZone: Intl.DateTimeFormat().resolvedOptions().timeZone,
    dateString: new Date().toString(),
    innerWidth: window.innerWidth,
    innerHeight: window.innerHeight,
    devicePixelRatio: window.devicePixelRatio,
})"""


def resolve_artifacts_base(gcp: bool) -> Path:
    override = os.environ.get("ARTIFACTS_DIR")
    if override:
        return Path(override).resolve()
    return Path("/tmp") if gcp else REPO_ROOT / "tmp"


def build_run_id(gcp: bool, now: datetime | None = None) -> str:
    run_id = (
        (now or datetime.now(JST)).astimezone(JST).strftime("%Y%m%d-%H%M%S")
    )
    if gcp:
        execution = os.environ.get("CLOUD_RUN_EXECUTION")
        if execution:
            run_id += f"-{execution}"
        task_index = os.environ.get("CLOUD_RUN_TASK_INDEX")
        if task_index:
            run_id += f"-task{task_index}"
    return run_id


_current_run_id = ""


def set_run_id(run_id: str) -> None:
    global _current_run_id
    _current_run_id = run_id


class JsonLogFormatter(logging.Formatter):
    """Cloud Logging が severity を解釈できる1行JSON。"""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "severity": record.levelname,
            "message": record.getMessage(),
            "run_id": _current_run_id,
            "logger": record.name,
        }
        if record.exc_info:
            exc_text = record.exc_text or self.formatException(record.exc_info)
            payload["message"] += "\n" + exc_text
        return json.dumps(payload, ensure_ascii=False)


def setup_logging(gcp: bool) -> None:
    handler = logging.StreamHandler(sys.stdout)
    if gcp:
        handler.setFormatter(JsonLogFormatter())
        handler.setLevel(logging.INFO)
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
        )
    logging.basicConfig(level=logging.DEBUG, handlers=[handler], force=True)


def attach_file_log(path: Path) -> None:
    handler = logging.FileHandler(path, encoding="utf-8")
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    )
    logging.getLogger().addHandler(handler)


class SecretRedactFilter(logging.Filter):
    """ログ出力から認証情報などを伏せ字にする。"""

    def __init__(self, secrets: list[str]):
        super().__init__()
        self.secrets = [s for s in secrets if s]

    def redact(self, text: str) -> str:
        for secret in self.secrets:
            text = text.replace(secret, "***")
        return text

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = self.redact(record.getMessage())
        record.args = None
        if record.exc_info and not record.exc_text:
            record.exc_text = self.redact(
                logging.Formatter().formatException(record.exc_info)
            )
        return True


def add_redaction(secrets: list[str]) -> SecretRedactFilter:
    redactor = SecretRedactFilter(secrets)
    for handler in logging.getLogger().handlers:
        handler.addFilter(redactor)
    return redactor


def _slug(name: str) -> str:
    return re.sub(r"[^\w-]+", "-", name).strip("-")[:60] or "checkpoint"


class RunDiagnostics:
    """1回の実行の成果物 (trace/スクリーンショット/ログ等) を管理する。

    トレースは「ログイン時のパスワード」を残さないため、untraced() の
    前後でチャンクを分割し trace-01.zip, trace-02.zip, ... と出力する。
    診断処理の失敗は握りつぶし、本来の処理や例外には影響させない。
    """

    def __init__(
        self,
        run_id: str,
        run_dir: Path,
        bucket: str | None,
        redactor: SecretRedactFilter | None = None,
    ):
        self.redactor = redactor
        self.run_id = run_id
        self.run_dir = run_dir
        self.bucket = bucket
        self.page: Page | None = None
        self.context: BrowserContext | None = None
        self.steps: list[dict[str, Any]] = []
        self._checkpoint_n = 0
        self._trace_n = 0
        self._tracing = False
        self._request_started: dict[Request, float] = {}
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self._events_path = run_dir / "events.jsonl"
        self._checkpoint_dir = run_dir / "checkpoints"

    def _event(
        self, kind: str, level: int, summary: str, **fields: Any
    ) -> None:
        try:
            record = {
                "ts": datetime.now(JST).isoformat(timespec="milliseconds"),
                "kind": kind,
                **fields,
            }
            with self._events_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
            logger.log(level, f"[{kind}] {summary}")
        except Exception as e:
            logger.warning(f"Failed to record event {kind}: {e}")

    # --- tracing ---

    async def start_tracing(self, context: BrowserContext, title: str) -> None:
        self.context = context
        try:
            await context.tracing.start(
                screenshots=True,
                snapshots=True,
                sources=True,
                title=title,
            )
            self._tracing = True
            logger.info("Tracing started")
        except Exception as e:
            logger.warning(f"Failed to start tracing: {e}")

    def _next_trace_path(self) -> Path:
        self._trace_n += 1
        return self.run_dir / f"trace-{self._trace_n:02d}.zip"

    @asynccontextmanager
    async def untraced(self, label: str) -> AsyncIterator[None]:
        """この間の操作をトレースに残さない (機密入力用)。"""
        ctx = self.context if self._tracing else None
        if ctx is not None:
            try:
                await ctx.tracing.stop_chunk(path=self._next_trace_path())
            except Exception as e:
                logger.warning(f"Failed to stop trace chunk: {e}")
        logger.info(f"Trace paused ({label})")
        try:
            yield
        finally:
            if ctx is not None:
                try:
                    await ctx.tracing.start_chunk()
                    logger.info(f"Trace resumed ({label})")
                except Exception as e:
                    self._tracing = False
                    logger.warning(f"Failed to resume tracing: {e}")

    async def stop_tracing(self) -> None:
        if not self._tracing or self.context is None:
            return
        self._tracing = False
        try:
            path = self._next_trace_path()
            await self.context.tracing.stop(path=path)
            logger.info(f"Trace saved: {path}")
        except Exception as e:
            logger.warning(f"Failed to stop tracing: {e}")

    # --- page listeners ---

    def attach_page(self, page: Page) -> None:
        self.page = page
        try:
            page.on("console", self._on_console)
            page.on("pageerror", self._on_pageerror)
            page.on("request", self._on_request)
            page.on("requestfailed", self._on_requestfailed)
            page.on("response", self._on_response)
            page.on("dialog", self._on_dialog)
            page.on("framenavigated", self._on_framenavigated)
        except Exception as e:
            logger.warning(f"Failed to attach page listeners: {e}")

    def _on_console(self, msg: ConsoleMessage) -> None:
        text = msg.text
        level = logging.WARNING if msg.type == "error" else logging.DEBUG
        self._event(
            "console",
            level,
            f"{msg.type}: {text[:200]}",
            type=msg.type,
            text=text,
            location=msg.location,
        )

    def _on_pageerror(self, error: Any) -> None:
        self._event(
            "pageerror", logging.WARNING, str(error), message=str(error)
        )

    def _on_request(self, request: Request) -> None:
        if request.method == "GET":
            return
        self._request_started[request] = time.monotonic()
        self._event(
            "request",
            logging.INFO,
            f"{request.method} {request.url}",
            method=request.method,
            url=request.url,
        )

    def _on_requestfailed(self, request: Request) -> None:
        self._request_started.pop(request, None)
        self._event(
            "requestfailed",
            logging.WARNING,
            f"{request.method} {request.url} {request.failure}",
            method=request.method,
            url=request.url,
            failure=request.failure,
        )

    def _on_response(self, response: Response) -> None:
        request = response.request
        started = self._request_started.pop(request, None)
        if request.method == "GET" and response.status < 400:
            return
        elapsed = None if started is None else time.monotonic() - started
        level = logging.WARNING if response.status >= 400 else logging.INFO
        self._event(
            "response",
            level,
            f"{request.method} {response.url} -> {response.status}",
            method=request.method,
            url=response.url,
            status=response.status,
            elapsed_sec=None if elapsed is None else round(elapsed, 3),
        )

    async def _on_dialog(self, dialog: Dialog) -> None:
        self._event(
            "dialog",
            logging.WARNING,
            f"{dialog.type}: {dialog.message}",
            type=dialog.type,
            message=dialog.message,
        )
        try:
            await dialog.dismiss()
        except Exception as e:
            logger.warning(f"Failed to dismiss dialog: {e}")

    def _on_framenavigated(self, frame: Frame) -> None:
        if self.page is not None and frame == self.page.main_frame:
            self._event("navigated", logging.INFO, frame.url, url=frame.url)

    # --- checkpoints / environment ---

    async def checkpoint(self, name: str) -> None:
        """スクリーンショット・HTML・URL・フォーム状態を保存する。"""
        if self.page is None:
            return
        self._checkpoint_n += 1
        base = self._checkpoint_dir / f"{self._checkpoint_n:02d}-{_slug(name)}"
        info: dict[str, Any] = {"name": name}
        try:
            self._checkpoint_dir.mkdir(parents=True, exist_ok=True)
            info["url"] = self.page.url
            info["form"] = await self.page.evaluate(FORM_STATE_JS)
        except Exception as e:
            info["form_error"] = str(e)
        try:
            await self.page.screenshot(
                path=base.with_suffix(".png"), full_page=True
            )
        except Exception as e:
            info["screenshot_error"] = str(e)
        try:
            html = await self.page.content()
            base.with_suffix(".html").write_text(html, encoding="utf-8")
        except Exception as e:
            info["html_error"] = str(e)
        try:
            base.with_suffix(".json").write_text(
                json.dumps(info, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            logger.info(f"Checkpoint {base.name}: {info.get('url')}")
        except Exception as e:
            logger.warning(f"Failed to write checkpoint {name}: {e}")

    async def write_environment(
        self,
        browser: Browser,
        pattern_name: str,
        headless: bool,
        launch_args: list[str],
        context_options: dict[str, Any],
    ) -> None:
        try:
            now = datetime.now(JST)
            env: dict[str, Any] = {
                "pattern_name": pattern_name,
                "headless": headless,
                "launch_args": launch_args,
                "context_options": context_options,
                "browser_version": browser.version,
                "python": sys.version,
                "platform": platform.platform(),
                "playwright": version("playwright"),
                "process_tz_env": os.environ.get("TZ"),
                "now_jst": now.isoformat(),
                "now_utc": datetime.now(UTC).isoformat(),
                "cloud_run": {
                    k: os.environ.get(k)
                    for k in CLOUD_RUN_ENV_KEYS
                    if os.environ.get(k) is not None
                },
            }
            if self.page is not None:
                env["page"] = await self.page.evaluate(ENV_JS)
            (self.run_dir / "environment.json").write_text(
                json.dumps(env, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            logger.warning(f"Failed to write environment.json: {e}")

    # --- steps / summary / upload ---

    @contextmanager
    def step(self, name: str) -> Iterator[None]:
        started = time.monotonic()
        try:
            yield
        finally:
            self.steps.append(
                {"name": name, "seconds": round(time.monotonic() - started, 3)}
            )

    def _files(self) -> list[str]:
        return sorted(
            p.relative_to(self.run_dir).as_posix()
            for p in self.run_dir.rglob("*")
            if p.is_file()
        )

    @property
    def gcs_prefix(self) -> str | None:
        if not self.bucket:
            return None
        return f"gs://{self.bucket}/runs/{self.run_id}"

    def _redact(self, text: str) -> str:
        return self.redactor.redact(text) if self.redactor else text

    def write_summary(
        self, error: BaseException | None, extra: dict[str, Any]
    ) -> None:
        try:
            files = sorted({*self._files(), "summary.json"})
            prefix = self.gcs_prefix
            summary: dict[str, Any] = {
                "run_id": self.run_id,
                "status": "failed" if error else "success",
                "error": None
                if error is None
                else {
                    "type": type(error).__name__,
                    "message": self._redact(str(error)),
                    "traceback": self._redact(
                        "".join(traceback.format_exception(error))
                    ),
                },
                "steps": self.steps,
                "files": files,
                "gcs_uris": [f"{prefix}/{f}" for f in files] if prefix else [],
                **extra,
            }
            (self.run_dir / "summary.json").write_text(
                json.dumps(summary, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            logger.warning(f"Failed to write summary.json: {e}")

    async def upload(self) -> None:
        if not self.bucket:
            logger.info("GCS_TRACE_BUCKET is not set. Skipping upload.")
            return
        try:
            for h in logging.getLogger().handlers:
                h.flush()
            uris = await asyncio.to_thread(
                upload_directory_to_gcs,
                self.run_dir,
                f"runs/{self.run_id}",
                self.bucket,
            )
            logger.info(f"Uploaded {len(uris)} files to {self.gcs_prefix}")
            logger.info(
                "Cloud Console: https://console.cloud.google.com/storage/"
                f"browser/{self.bucket}/runs/{self.run_id}"
            )
        except Exception as e:
            logger.warning(f"Failed to upload artifacts: {e}")
