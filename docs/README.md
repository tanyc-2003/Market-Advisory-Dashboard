# Documentation

Per-layer documentation for the Market Advisory Dashboard.

The architecture source-of-truth is `../Claude code building guide/Advisory_Dashboard_Architecture_v7.md`. These docs translate it into developer-facing reference material and walk through how the code enforces each invariant.

| File | Audience | What it covers |
|---|---|---|
| [01_overview.md](01_overview.md) | new contributor | system purpose, the Layer 0 invariant, the five sign-off criteria |
| [02_architecture.md](02_architecture.md) | new contributor | data flow, layer dependencies, sign-off chain, persistent state |
| [03_invariants.md](03_invariants.md) | reviewer | the seven architectural invariants and the code locations that enforce them |
| [04_layers.md](04_layers.md) | implementer | per-layer public API reference |
| [05_running.md](05_running.md) | operator | install, bootstrap, seed, test, debug recipes |
| [06_developing.md](06_developing.md) | implementer | house style, adding a layer/feature, common pitfalls |
| [07_dashboard.md](07_dashboard.md) | operator / trader | Streamlit pages, sign-off gate behaviour, session state, components |
| [08_llm.md](08_llm.md) | operator | optional LLM layer — what it can/cannot do, enabling it, cache + TTL |

A reader who wants the shortest path to understanding should read 01 → 03 → 05 → 07. A reader who is reviewing a PR should read 03 first.
