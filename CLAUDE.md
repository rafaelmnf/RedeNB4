# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Reads heart rate (BPM) for Polar Verity Sense armbands using an Aruba access point (InstantOS 8.10) as the BLE receiver. The AP streams BLE telemetry over WebSocket to the backend, which decodes it, stores readings in PostgreSQL, and serves a React dashboard. Code, comments, UI, and console output are in Portuguese; keep that convention. `manual AP aruba.pdf` is only the 330-series install guide.

The AP is already filtered on its side (IoT profile: `companyIdentifierFilter 006B` + `perFrameFiltering`), so it forwards only Polar advertisements. The server never sends commands to the AP (no GATT / bleConnect); registering a MAC in the database is all it takes for the server to accept it.

## Commands

Windows. Backend uses **uv** (don't use pip/venv directly); DB-only Docker (host port **5433**, because a native Windows Postgres holds 5432). Config comes from `.env` at the repo root (`.env.example` is the template).

```powershell
docker compose up -d db
cd backend
uv sync
uv run alembic upgrade head
uv run redenb4                         # AP ingest ws :8765 + site/API http :8000 (one process)
uv run redenb4 servidor --dump|--raw   # protobuf dump of first 3 Polar entries / save frames
uv run redenb4 simular --n 5 --cadastrar [--alto N] [--baixo N] [--sumir N] [--fora N]
uv run redenb4 importar-macs           # legacy device_macs.json -> DB
uv run pytest                          # DB tests use TEST_DATABASE_URL (redenb4_test, auto-created by deploy/initdb); skipped if DB down
uv run pytest tests/test_parser.py::test_frame_truncado_ainda_entrega_entradas_completas
uv run ruff check src tests alembic

cd frontend
npm run build                          # tsc + vite -> frontend/dist (served by FastAPI)
npm run dev                            # :5173, proxies /api and /ws to :8000
npm run gerar-api                      # regenerate src/api/schema.d.ts from FastAPI OpenAPI
```

TypeScript is pinned to 6.x: openapi-typescript needs the JS compiler API that TS 7 dropped. On Windows a running `uv run redenb4` locks `redenb4.exe`, so stop it before `uv sync` or a pyproject change.

## Architecture

Single process (`api/app.py` lifespan) hosting layered modules, so ingest can later be split into its own process:

- **`ingestao/aruba_parser.py`**: schema-less protobuf parser (moved from `App/servidor_ws.py`). `achar_nos_com_macs()` walks the frame once and finds submessages directly containing an allowlisted MAC (6 raw bytes); `extrair_bpm()` reads the Polar manufacturer data (AD `0xFF`, company `0x006B`, BPM = payload byte 15); `achar_rssi()` is a heuristic (first varint in -120..-20 dBm). The non-strict parse tolerates frames the AP truncates at ~4096 bytes.
- **`ingestao/allowlist.py`**: in-memory MAC → pulseira map loaded from active rows. A DB trigger `NOTIFY`s `pulseiras_alteradas`, and `Allowlist.escutar()` holds a `LISTEN` connection (auto-reconnect, plus a 60 s periodic reload).
- **`ingestao/servidor_ap.py`**: `websockets` server; the AP is identified by peer IP (auto-row in `aps`).
- **`servicos/pipeline.py`**: `Seletor` (pass-through now; later dedup by MAC + window and zone by best RSSI for a second AP) → in-memory `StatusPulseira` → `GravadorLote`. Every advertisement updates last contact; only identical payloads skip storage; BPM 0 = "fora do braço" (status only, not stored).
- **`servicos/gravador.py`**: buffered `COPY` into `leituras_bpm` through a dedicated asyncpg connection.
- **`dominio/`**: pure rules (`mac.py` normalization, `sinal.py` EMA RSSI + log-distance).
- **DB**: `timestamptz` everywhere, `macaddr UNIQUE`, `leituras_bpm` PK `(id, ts)` (TimescaleDB-compatible). Removing a pulseira with history soft-deletes it (`removida_em`); re-registering the MAC restores the row.
- **`simulador.py`**: builds AP-format frames; the parser tests reuse its encoders.
- **Frontend**: React Router + TanStack Query + Mantine. Types come from `src/api/schema.d.ts`. FastAPI serves `frontend/dist` with SPA fallback for non-`/api`, non-`/ws` paths.

Legacy: `device_config.py` and `App/servidor_ws.py` (old CSV server) remain until the new server is validated on real hardware. `scripts/diagnostico/` holds the old experiment scripts.

## Roadmap (staged commits on branch `dashboard`)

(a) pulseiras + dynamic allowlist ✔ · (b) pesquisadores + atribuições (EXCLUDE constraints on `tstzrange`) · (c) live dashboard (WS `/ws/ao-vivo`, uPlot) · (d) alertas (limits + duration, sem sinal, acknowledge) · (e) history and CSV export · (f) auth (roles admin/leitor, 12 h session, auditoria).
