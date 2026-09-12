"""Telegram delivery via Cabinet (OpenClaw / Bot API)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass
class SendResult:
    ok: bool
    output: str = ""


def _cabinet_send(message: str) -> bool:
    from cabinet import telegram as cabinet_telegram

    return bool(cabinet_telegram(message, is_quiet=True))


class TelegramSender:
    """
    Record and deliver diary Telegram messages.

    Production sends go through ``cabinet.telegram`` so chat id / OpenClaw live
    in Cabinet. Tests pass ``dry_run=True`` or a fake ``send_fn``.
    """

    def __init__(
        self,
        *,
        dry_run: bool = False,
        send_fn: Callable[[str], bool] | None = None,
    ) -> None:
        self.dry_run = dry_run
        self.send_fn = send_fn
        self.sent: list[str] = []

    def send(self, message: str) -> SendResult:
        message = message.strip()
        if not message:
            return SendResult(ok=True, output="")
        self.sent.append(message)
        if self.dry_run:
            return SendResult(ok=True, output="dry-run")
        fn = self.send_fn or _cabinet_send
        try:
            ok = fn(message)
        except Exception as exc:  # noqa: BLE001 - surface to workflow
            return SendResult(ok=False, output=str(exc))
        if ok:
            return SendResult(ok=True, output="")
        return SendResult(ok=False, output="cabinet.telegram failed")
