"""Telegram delivery via OpenClaw CLI."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass

from .config import TelegramConfig


@dataclass
class SendResult:
    ok: bool
    output: str = ""


class TelegramSender:
    def __init__(
        self,
        cfg: TelegramConfig,
        *,
        openclaw_bin: str = "openclaw",
        dry_run: bool = False,
    ) -> None:
        self.cfg = cfg
        self.openclaw_bin = openclaw_bin
        self.dry_run = dry_run
        self.sent: list[str] = []

    def send(self, message: str) -> SendResult:
        message = message.strip()
        if not message:
            return SendResult(ok=True, output="")
        self.sent.append(message)
        if self.dry_run:
            return SendResult(ok=True, output="dry-run")
        if not self.cfg.target:
            return SendResult(ok=False, output="telegram.target is not configured")
        cmd = [
            self.openclaw_bin,
            "message",
            "send",
            "--channel",
            self.cfg.channel,
            "--target",
            self.cfg.target,
            "--message",
            message,
        ]
        try:
            proc = subprocess.run(
                cmd,
                check=False,
                capture_output=True,
                text=True,
                timeout=60,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return SendResult(ok=False, output=str(exc))
        out = (proc.stdout or proc.stderr or "").strip()
        return SendResult(ok=proc.returncode == 0, output=out)
