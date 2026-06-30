# Documentation

Per-layer documentation for the Market Advisory Dashboard.

The architecture source-of-truth is `../Claude code building guide/Advisory_Dashboard_Architecture_v7.md` (and `_v7_lite.md` for the extension). These docs translate them into developer-facing reference material and walk through how the code enforces each invariant.

| File | Audience | What it covers |
|---|---|---|
| [01_overview.md](01_overview.md) | new contributor | system purpose, the Layer 0 invariant, the five sign-off criteria |
| [02_architecture.md](02_architecture.md) | new contributor | data flow, layer dependencies, sign-off chain, persistent state |
| [03_invariants.md](03_invariants.md) | reviewer | the seven architectural invariants and the code locations that enforce them |
| [04_layers.md](04_layers.md) | implementer | per-layer public API reference |
| [05_running.md](05_running.md) | operator | install, bootstrap, seed, test, debug recipes |
| [06_developing.md](06_developing.md) | implementer | house style, adding a layer/feature, common pitfalls |
| [07_dashboard.md](07_dashboard.md) | operator / trader | Streamlit pages (legacy UI), sign-off gate behaviour, session state, components |
| [08_llm.md](08_llm.md) | operator | optional LLM layer — what it can/cannot do, enabling it, cache + TTL |
| [09_v7_lite.md](09_v7_lite.md) | operator / reviewer | V7_lite (Scanner+) extension — the three modes, eight new invariants, locked layers |
| [10_web_stack.md](10_web_stack.md) | operator / implementer | React + Vite frontend + FastAPI API — payload contract, live-vs-representative wiring, the data pipeline |

A reader who wants the shortest path to understanding should read 01 → 03 → 05 → 10. A reader who is reviewing a PR should read 03 + 09 first. An operator picking the free vs paid data tier should jump straight to 09. Anyone running or extending the **current** UI (React web app + HTTP API) should read 10; 07 documents the legacy Streamlit UI it supersedes.
