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

## Run demo entry

```powershell
py -m concert_ticket_assistant.main --event-id 123 --session-id A --price-tier 480 --audience Alice
```

Current Damai adapter is a stub and only returns official purchase URL guidance.
No payment automation or anti-risk-control logic is implemented.

