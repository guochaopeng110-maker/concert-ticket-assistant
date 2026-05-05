from __future__ import annotations

import argparse
import time

from concert_ticket_assistant.core.config import MonitorConfig, load_config
from concert_ticket_assistant.core.models import PurchaseIntent
from concert_ticket_assistant.core.monitoring import RunMetrics, save_error_snapshot
from concert_ticket_assistant.core.orchestrator import TicketOrchestrator
from concert_ticket_assistant.notify.console import ConsoleNotifier
from concert_ticket_assistant.platforms.damai.adapter import DamaiAdapter, DamaiAdapterError, DamaiErrorKind


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compliant multi-platform concert ticket assistant (MVP).")
    parser.add_argument("--config", default="", help="JSON config path")
    parser.add_argument("--event-id", default="", help="Target event id")
    parser.add_argument("--session-id", default="", help="Target session id")
    parser.add_argument("--price-tier", default="", help="Target price tier text")
    parser.add_argument("--quantity", type=int, default=1, help="Ticket quantity")
    parser.add_argument("--audience", default="", help="Comma separated audience names")
    parser.add_argument("--backup-sessions", default="", help="Comma separated backup session ids")
    parser.add_argument("--backup-tiers", default="", help="Comma separated backup price tiers")
    parser.add_argument("--interval-seconds", type=float, default=1.0, help="Polling interval in seconds")
    parser.add_argument("--max-cycles", type=int, default=0, help="0 means run forever")
    parser.add_argument("--dedupe-window-seconds", type=float, default=30.0, help="Duplicate alert suppression window")
    parser.add_argument("--breaker-fail-threshold", type=int, default=5, help="Consecutive failures to open breaker")
    parser.add_argument("--breaker-cooldown-seconds", type=float, default=10.0, help="Breaker cooldown seconds")
    parser.add_argument("--snapshot-dir", default=".omx/logs/snapshots", help="Directory for parse error payload snapshots")
    return parser


def _split_csv(value: str) -> list[str]:
    return [x.strip() for x in value.split(",") if x.strip()]


def resolve_config(args: argparse.Namespace) -> MonitorConfig:
    file_data = load_config(args.config or None)
    merged = {
        "event_id": file_data.get("event_id") or args.event_id,
        "session_id": file_data.get("session_id") or args.session_id,
        "price_tier": file_data.get("price_tier") or args.price_tier,
        "quantity": args.quantity if args.quantity != 1 or "quantity" not in file_data else file_data.get("quantity"),
        "audience": _split_csv(args.audience) if args.audience else file_data.get("audience", []),
        "backup_sessions": _split_csv(args.backup_sessions) if args.backup_sessions else file_data.get("backup_sessions", []),
        "backup_tiers": _split_csv(args.backup_tiers) if args.backup_tiers else file_data.get("backup_tiers", []),
        "interval_seconds": (
            args.interval_seconds if args.interval_seconds != 1.0 or "interval_seconds" not in file_data else file_data.get("interval_seconds")
        ),
        "max_cycles": args.max_cycles if args.max_cycles != 0 or "max_cycles" not in file_data else file_data.get("max_cycles"),
        "dedupe_window_seconds": (
            args.dedupe_window_seconds
            if args.dedupe_window_seconds != 30.0 or "dedupe_window_seconds" not in file_data
            else file_data.get("dedupe_window_seconds")
        ),
        "breaker_fail_threshold": (
            args.breaker_fail_threshold
            if args.breaker_fail_threshold != 5 or "breaker_fail_threshold" not in file_data
            else file_data.get("breaker_fail_threshold")
        ),
        "breaker_cooldown_seconds": (
            args.breaker_cooldown_seconds
            if args.breaker_cooldown_seconds != 10.0 or "breaker_cooldown_seconds" not in file_data
            else file_data.get("breaker_cooldown_seconds")
        ),
    }
    config = MonitorConfig.from_dict(merged)
    if not config.event_id or not config.session_id or not config.price_tier:
        raise ValueError("event_id, session_id, and price_tier are required via args or config file")
    return config


def main() -> int:
    args = build_parser().parse_args()
    try:
        cfg = resolve_config(args)
    except (ValueError, OSError) as exc:
        print(f'{{"event":"config_error","message":"{str(exc)}"}}')
        return 2

    intent = PurchaseIntent(
        event_id=cfg.event_id,
        session_id=cfg.session_id,
        price_tier=cfg.price_tier,
        quantity=cfg.quantity,
        audience_names=cfg.audience or [],
        backup_sessions=cfg.backup_sessions or [],
        backup_price_tiers=cfg.backup_tiers or [],
    )

    adapter = DamaiAdapter()
    notifier = ConsoleNotifier()
    orchestrator = TicketOrchestrator(notifier=notifier, dedupe_window_seconds=cfg.dedupe_window_seconds)
    metrics = RunMetrics()

    cycle = 0
    try:
        while True:
            cycle += 1
            now = time.monotonic()
            if metrics.breaker_open(now=now):
                metrics.log_event("breaker_open_skip", cycle=cycle, reopen_in_seconds=round(metrics.breaker_open_until - now, 3))
            else:
                try:
                    signal = adapter.poll_signal(event_id=cfg.event_id, session_id=cfg.session_id)
                except DamaiAdapterError as exc:
                    metrics.on_adapter_error(exc.kind.value)
                    snapshot_path = ""
                    if exc.kind == DamaiErrorKind.PARSE_ERROR and exc.raw_payload:
                        snapshot_path = save_error_snapshot(
                            base_dir=args.snapshot_dir,
                            platform="damai",
                            kind=exc.kind.value,
                            cycle=cycle,
                            event_id=cfg.event_id,
                            session_id=cfg.session_id,
                            payload=exc.raw_payload,
                        )
                    metrics.log_event(
                        "adapter_error",
                        cycle=cycle,
                        kind=exc.kind.value,
                        message=str(exc),
                        snapshot=snapshot_path,
                    )
                    if metrics.maybe_open_breaker(cfg.breaker_fail_threshold, cfg.breaker_cooldown_seconds, now=now):
                        metrics.log_event("breaker_opened", cycle=cycle, cooldown_seconds=cfg.breaker_cooldown_seconds)
                except OSError as exc:
                    metrics.on_adapter_error("os_error")
                    metrics.log_event("adapter_error", cycle=cycle, kind="os_error", message=str(exc))
                else:
                    result = orchestrator.handle_signal(intent=intent, signal=signal, now=now)
                    suppressed = result.reason == "Duplicate suppressed"
                    metrics.on_success(notified=result.notified, suppressed=suppressed)
                    if not result.notified and not suppressed:
                        metrics.orchestrator_skips += 1
                    metrics.log_event(
                        "cycle_result",
                        cycle=cycle,
                        signal=signal.signal_type.value,
                        tiers=signal.price_tiers,
                        notified=result.notified,
                        reason=result.reason,
                    )

            if cfg.max_cycles > 0 and cycle >= cfg.max_cycles:
                break
            time.sleep(max(0.05, cfg.interval_seconds))
    except KeyboardInterrupt:
        metrics.log_event("stopped_by_user")

    metrics.log_event(
        "run_summary",
        cycles=metrics.cycles,
        notified=metrics.notified,
        suppressed=metrics.suppressed,
        adapter_errors=metrics.adapter_errors,
        orchestrator_skips=metrics.orchestrator_skips,
        by_error_kind=metrics.by_error_kind,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
