#!/usr/bin/env python3
"""
GitHub Actions progress helper.

Provides live progress tracking for long-running batch jobs by:
  - Updating $GITHUB_STEP_SUMMARY with a progress table (visible on mobile)
  - Emitting workflow annotations (::notice) that show in the Actions UI
  - Writing a progress.json file for external monitoring

Outside GitHub Actions, simply prints progress to stdout.
"""

import json
import os
import time
from datetime import datetime, timezone


SUMMARY_FILE = os.environ.get("GITHUB_STEP_SUMMARY", "")
IS_CI = bool(os.environ.get("GITHUB_ACTIONS"))


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%S UTC")


def emit_notice(message: str) -> None:
    """Emit a GitHub Actions annotation (visible in the job log sidebar)."""
    if IS_CI:
        print(f"::notice ::{message}")
    print(f"📢 {message}")


def emit_progress_group(title: str, body: str) -> None:
    """Print a collapsible group in the Actions log."""
    if IS_CI:
        print(f"::group::{title}")
        print(body)
        print("::endgroup::")
    else:
        print(f"\n{'─'*50}")
        print(f"  {title}")
        print(body)


def update_summary(
    title: str,
    current: int,
    total: int,
    updated: int = 0,
    failed: int = 0,
    extra_lines: list[str] | None = None,
) -> None:
    """Rewrite $GITHUB_STEP_SUMMARY with a live progress table.

    This file is rendered as Markdown in the Actions run summary page,
    which is accessible on mobile via the GitHub app notifications.
    """
    pct = (current / total * 100) if total else 0
    bar_len = 20
    filled = int(bar_len * current / total) if total else 0
    bar = "█" * filled + "░" * (bar_len - filled)

    lines = [
        f"## {title}",
        "",
        f"**Progression** : `{current}` / `{total}`  ({pct:.1f} %)",
        f"```",
        f"[{bar}]",
        f"```",
        f"| Métrique | Valeur |",
        f"|----------|--------|",
        f"| ✅ Traités | {current} |",
        f"| 📝 Mis à jour | {updated} |",
        f"| ❌ Échoués / ignorés | {failed} |",
        f"| 🕐 Dernier refresh | {_ts()} |",
    ]
    if extra_lines:
        lines.append("")
        lines.extend(extra_lines)

    text = "\n".join(lines) + "\n"

    if SUMMARY_FILE:
        try:
            with open(SUMMARY_FILE, "w") as f:
                f.write(text)
        except OSError:
            pass


def write_progress_json(
    path: str,
    current: int,
    total: int,
    updated: int = 0,
    failed: int = 0,
    phase: str = "",
) -> None:
    """Write a machine-readable progress.json (useful for external polling)."""
    data = {
        "phase": phase,
        "current": current,
        "total": total,
        "updated": updated,
        "failed": failed,
        "pct": round(current / total * 100, 1) if total else 0,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
    except OSError:
        pass


class BatchProgress:
    """Track progress of a batch operation and emit updates.

    Usage:
        bp = BatchProgress("PDF Processing", total=7043, save_interval=100)
        for i, item in enumerate(items, 1):
            ... process item ...
            bp.tick(updated=True/False)
        bp.finish()
    """

    def __init__(
        self,
        title: str,
        total: int,
        save_interval: int = 100,
        progress_json_path: str | None = None,
    ):
        self.title = title
        self.total = total
        self.save_interval = save_interval
        self.progress_json_path = progress_json_path
        self.current = 0
        self.updated = 0
        self.failed = 0
        self.start_time = time.monotonic()
        self._last_summary_at = 0

        # Initial summary
        update_summary(title, 0, total)
        if IS_CI:
            emit_notice(f"{title} — démarrage ({total} à traiter)")

    def tick(self, updated: bool = False, failed: bool = False) -> bool:
        """Record one processed item. Returns True if a checkpoint was reached."""
        self.current += 1
        if updated:
            self.updated += 1
        if failed:
            self.failed += 1

        is_checkpoint = (self.current % self.save_interval == 0)

        # Update summary every save_interval items or at the end
        if is_checkpoint or self.current == self.total:
            elapsed = time.monotonic() - self.start_time
            rate = self.current / elapsed if elapsed > 0 else 0
            eta_s = (self.total - self.current) / rate if rate > 0 else 0
            eta_m = int(eta_s / 60)

            extra = [
                f"⏱️ Vitesse : {rate:.1f} élus/s — ETA : ~{eta_m} min",
            ]

            update_summary(
                self.title, self.current, self.total,
                self.updated, self.failed, extra_lines=extra,
            )

            if self.progress_json_path:
                write_progress_json(
                    self.progress_json_path,
                    self.current, self.total,
                    self.updated, self.failed,
                    phase=self.title,
                )

            if IS_CI:
                emit_notice(
                    f"{self.title} — {self.current}/{self.total} "
                    f"({self.updated} mis à jour, ~{eta_m} min restant)"
                )

            self._last_summary_at = self.current

        return is_checkpoint

    def finish(self) -> None:
        elapsed = time.monotonic() - self.start_time
        elapsed_m = int(elapsed / 60)
        elapsed_s = int(elapsed % 60)

        extra = [
            f"⏱️ Durée totale : {elapsed_m}m {elapsed_s}s",
        ]

        update_summary(
            f"{self.title} — ✅ Terminé",
            self.current, self.total,
            self.updated, self.failed,
            extra_lines=extra,
        )

        if self.progress_json_path:
            write_progress_json(
                self.progress_json_path,
                self.current, self.total,
                self.updated, self.failed,
                phase=f"{self.title} — done",
            )

        if IS_CI:
            emit_notice(
                f"{self.title} — ✅ Terminé : {self.current}/{self.total} traités, "
                f"{self.updated} mis à jour en {elapsed_m}m {elapsed_s}s"
            )
