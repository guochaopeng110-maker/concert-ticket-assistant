from __future__ import annotations

import argparse
import time

from concert_ticket_assistant.core.models import PurchaseIntent
from concert_ticket_assistant.core.orchestrator import TicketOrchestrator
from concert_ticket_assistant.notify.console import ConsoleNotifier
from concert_ticket_assistant.platforms.damai.adapter import DamaiAdapter, DamaiAdapterError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compliant multi-platform concert ticket assistant (MVP).")
    parser.add_argument("--event-id", required=True, help="Target event id")
    parser.add_argument("--session-id", required=True, help="Target session id")
    parser.add_argument("--price-tier", required=True, help="Target price tier text")
    parser.add_argument("--quantity", type=int, default=1, help="Ticket quantity")
    parser.add_argument("--audience", default="", help="Comma separated audience names")
    parser.add_argument("--backup-sessions", default="", help="Comma separated backup session ids")
    parser.add_argument("--backup-tiers", default="", help="Comma separated backup price tiers")
    parser.add_argument("--interval-seconds", type=float, default=1.0, help="Polling interval in seconds")
    parser.add_argument("--max-cycles", type=int, default=0, help="0 means run forever")
    parser.add_argument("--dedupe-window-seconds", type=float, default=30.0, help="Duplicate alert suppression window")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    audience_names = [name.strip() for name in args.audience.split(",") if name.strip()]
    backup_sessions = [value.strip() for value in args.backup_sessions.split(",") if value.strip()]
    backup_tiers = [value.strip() for value in args.backup_tiers.split(",") if value.strip()]

    intent = PurchaseIntent(
        event_id=args.event_id,
        session_id=args.session_id,
        price_tier=args.price_tier,
        quantity=args.quantity,
        audience_names=audience_names,
        backup_sessions=backup_sessions,
        backup_price_tiers=backup_tiers,
    )

    adapter = DamaiAdapter()
    notifier = ConsoleNotifier()
    orchestrator = TicketOrchestrator(notifier=notifier, dedupe_window_seconds=args.dedupe_window_seconds)

    cycle = 0
    try:
        while True:
            cycle += 1
            try:
                signal = adapter.poll_signal(event_id=args.event_id, session_id=args.session_id)
            except (DamaiAdapterError, OSError, ValueError) as exc:
                print(f"cycle={cycle} adapter_error={exc}")
            else:
                result = orchestrator.handle_signal(intent=intent, signal=signal)
                print(
                    f"cycle={cycle} signal={signal.signal_type.value} "
                    f"tiers={signal.price_tiers} notified={result.notified} reason={result.reason}"
                )

            if args.max_cycles > 0 and cycle >= args.max_cycles:
                break
            time.sleep(max(0.05, args.interval_seconds))
    except KeyboardInterrupt:
        print("stopped_by_user=true")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
