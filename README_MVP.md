# Concert Ticket Assistant (M1 Scaffold)

This repository now includes a compliant multi-platform MVP scaffold under:

- `concert_ticket_assistant/core`: models, policy, orchestrator
- `concert_ticket_assistant/platforms`: platform adapters
- `concert_ticket_assistant/notify`: notification providers
- `tests`: unit tests for policy and orchestration behavior

## Run tests

```powershell
py -m unittest discover -s tests -p "test_*.py"
```

## Run monitor entry

```powershell
py -m concert_ticket_assistant.main --event-id 123 --session-id A --price-tier 480 --audience Alice --interval-seconds 1 --max-cycles 3
```

Current Damai adapter supports official subpage signal parsing for:
- `ON_SALE` (e.g. "立即购买", "选座购买")
- `SOLD_OUT` (e.g. "缺货登记")
- `UNKNOWN` (e.g. "即将开抢" and fallback)

No payment automation or anti-risk-control logic is implemented.

Monitoring runtime flags:
- `--interval-seconds`: polling interval
- `--max-cycles`: stop after N cycles (0 means run forever)
- `--dedupe-window-seconds`: suppress duplicate notifications in a time window

