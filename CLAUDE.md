# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Reads heart rate (BPM) for Polar Verity Sense armbands using an Aruba access point (InstantOS 8.10) as the BLE receiver. The AP streams BLE telemetry over WebSocket to the backend, which decodes it, stores readings in PostgreSQL, and serves a React dashboard. Code, comments, UI, and console output are in Portuguese; keep that convention. `manual AP aruba.pdf` is only the 330-series install guide.

The AP is already filtered on its side (IoT profile: `companyIdentifierFilter 006B` + `perFrameFiltering`), so it forwards only Polar advertisements. The server never sends commands to the AP (no GATT / bleConnect); registering a MAC in the database is all it takes for the server to accept it.

## Commands

Windows. Backend uses **uv** (don't use pip/venv directly); DB-only Docker (host port **5434**: a native Windows Postgres holds 5432 and another project's container holds 5433; use 127.0.0.1, not localhost). Config comes from `.env` at the repo root (`.env.example` is the template).

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

- **`ingestao/aruba_parser.py`**: schema-less protobuf parser (moved from `App/servidor_ws.py`). `achar_nos_com_macs()` walks the frame once and finds submessages directly containing an allowlisted MAC (6 raw bytes); `extrair_bpm()` reads the Polar manufacturer data (AD `0xFF`, company `0x006B`, BPM = payload byte 15); `achar_rssi()` reads field 4 (sint32 ZigZag, confirmed on the real AP) and falls back to the old heuristic. Real entry layout: [1] MAC, [2] 0, [3] advertisement, [4] RSSI, [5] 0, [6] AP BLE radio MAC (`radio_ap`); the docstring and `tests/test_parser.py` (real captures) document it. The non-strict parse tolerates frames the AP truncates at ~4096 bytes.
- **`ingestao/allowlist.py`**: in-memory MAC → `PulseiraAceita` (pulseira + active `atribuicao_id` + pesquisador name) loaded by `repos/pulseiras.listar_ativas()` (outer join on the active atribuição). Triggers `NOTIFY` `pulseiras_alteradas` (pulseiras) and `atribuicoes_alteradas` (atribuicoes, pesquisadores); `Allowlist.escutar()` holds a `LISTEN` connection (auto-reconnect, plus a 60 s periodic reload).
- **`ingestao/servidor_ap.py`**: `websockets` server; the AP is identified by the BLE radio MAC in entry field [6] (`aps.identificador`, auto-row on first sight, cached; `processar_frame` is async). Old IP-identified rows remain as history. Real AP: `endpointURL ws://192.168.50.10:8765/telemetry`, `transportInterval 2`, `endpointToken` travels inside every frame (header [1] meta → [2] text), not in the WS handshake; it is validated against `TOKEN_AP` (empty = disabled) and a mismatch closes with 1008. Frame top level: [1] meta, [2] AP info (MAC, IP, model, firmware, clock ~6 months off, so server time is used), [6] one entry per device. Unregistered Polars seen by the AP are logged (`ServidorAP.nao_cadastradas`).
- **`servicos/pipeline.py`**: `Seletor` (pass-through now; later dedup by MAC + window and zone by best RSSI for a second AP) → in-memory `StatusPulseira` → `GravadorLote`. Every advertisement updates last contact; only identical payloads skip storage; BPM 0 = "fora do braço" (status only, not stored). Each stored reading carries the allowlist's current `atribuicao_id`.
- **`servicos/gravador.py`**: buffered `COPY` into `leituras_bpm` through a dedicated asyncpg connection.
- **`servicos/limpeza.py`**: retention. `LimpezaLeituras` deletes `leituras_bpm` rows older than `RETENCAO_LEITURAS_DIAS` (default 2; 0 = keep all) on startup and every hour, in batches by `ctid` (`repos/leituras.apagar_antigas`), using the BRIN index on `ts` (migration `0005`). Only readings are deleted; so any history/export (stage e) only reaches back that far.
- **`dominio/`**: pure rules (`mac.py` normalization, `sinal.py` EMA RSSI + log-distance).
- **DB**: `timestamptz` everywhere, `macaddr UNIQUE`, `leituras_bpm` PK `(id, ts)` (TimescaleDB-compatible). Removing a pulseira with history (readings or atribuições) soft-deletes it (`removida_em`); re-registering the MAC restores the row.
- **Pesquisadores / atribuições** (migration `0002`): `pesquisadores.email` unique, lowercase, domain checked by `DOMINIO_EMAIL` in `api/schemas.py`. `atribuicoes` = who wears which pulseira, `inicio` always `now()` (no backdating), `fim NULL` = active; `btree_gist` `EXCLUDE` on `tstzrange(inicio, fim, '[)')` per pulseira and per pesquisador, so one person per pulseira and vice versa, with no historical overlap. Only INSERT and `UPDATE fim` (`repos/atribuicoes.py`, which maps SQLSTATE 23P01 to `AtribuicaoConflito` → 409). Deactivating/removing a pulseira or deactivating a pesquisador closes the active atribuição in the same transaction (`encerrar_ativas`). A pesquisador with any atribuição can't be deleted, only deactivated. UI: Pesquisadores page; vincular/desvincular/histórico on the Pulseiras page.
- **Laboratórios / experimentos** (migration `0003`): `experimentos` (laboratorio FK, nome, descricao, `inicio NOT NULL`, `fim` optional and may be in the future, `CHECK fim > inicio`) + `experimento_participantes` N:N (CASCADE on experiment delete; no overlap rule, one person can be in many). Not linked to pulseiras. `situacao` (agendado/em_andamento/encerrado) is computed (`repos/experimentos.situacao`, SQL filter in `listar`). `participantes` in POST/PATCH replaces the whole list. Lab with experiments → 409; pesquisador in any experiment can't be deleted. UI: Experimentos page (grouped by lab, filters, labs modal).
- **Live** (stage c): `servicos/broadcaster.py` fans out JSON to one bounded `asyncio.Queue` per browser (full queue → `DESCONECTAR`, client reconnects and gets a snapshot). `servicos/vigia.py` ticks every 1 s and publishes only online↔offline transitions (`StatusPulseira.esta_online`, `OFFLINE_APOS_S`). `api/app.py` wires `pipeline.ao_evento` + vigia → `publicar_cartao`, and `allowlist.ao_mudar` → `{"tipo":"cadastro"}` (the allowlist only notifies when its content actually changed). `api/ao_vivo.py` builds `CartaoSaida` (one per active pulseira, never-seen ones as `sem_dados`), shared by `GET /api/status`, `WS /ws/ao-vivo` (`api/routers/ao_vivo.py`: snapshot on connect and on client `{"tipo":"snapshot"}`; then `leitura`/`status`/`cadastro`) and the Pulseiras status. AP names live in `pipeline.nomes_aps` (loaded at startup, updated by `ServidorAP(ao_novo_ap=...)`). Charts: `GET /api/leituras/recentes` (raw, ≤60 min) and `GET /api/leituras` (`date_bin` avg/min/max, auto step ≤ ~720 points, `repos/leituras.py`).
- **Alertas** (stage d, migration `0004`): `limites` is a single row (`id = 1`), seeded from `.env` on startup (`repos/limites.obter_ou_criar`), editable via `PUT /api/limites` (applies to the motor immediately). `dominio/alertas.py` `MotorAlertas` is pure (time comes from readings and `verificar(agora, contatos)`): bpm_alto/bpm_baixo after `duracao_s` consecutive out-of-range readings (start = first one; one in-range reading resets/ends; extreme tracked), sem_sinal after `sem_sinal_s` without any advertisement (uses status `ultimo_contato`, so repeated payloads count), fora_do_braco after `fora_do_braco_s` of BPM 0; only for pulseiras with an atribuição; no BPM data (sem sinal/fora) closes BPM alerts; vínculo change closes all (`sincronizar_vinculos`). `servicos/alertas.py` `ServicoAlertas` queues motor events, persists them in order (`repos/alertas.py`; unique open alert per `(atribuicao_id, tipo)`), keeps open ones in memory for the snapshot and publishes `{"tipo":"alerta","evento":inicio|atualizacao|fim|reconhecido}`. Wired in `api/app.py`: pipeline events → `leitura`/`fora_do_braco`, `Vigia(ao_verificar=...)` → `verificar`, `allowlist.ao_mudar` → `sincronizar_vinculos`. Open alerts are closed on startup. Alerts are never deleted. UI: `BannerAlertas` (in `Layout`, all pages), red card, Alertas and Limites pages; no sound (user's choice).
- **`simulador.py`**: builds AP-format frames; the parser tests reuse its encoders. `--sumir N --sumir-apos S` makes pulseira N stop after S seconds (tests sem sinal on a pulseira that had contact).
- **Frontend**: React Router + TanStack Query + Mantine. Types come from `src/api/schema.d.ts`. FastAPI serves `frontend/dist` with SPA fallback for non-`/api`, non-`/ws` paths. Live state lives outside React in `src/aoVivo/armazenar.ts` (`useSyncExternalStore`; cards map + one `BufferCircular` per pulseira), fed by `src/aoVivo/conexao.ts` (single WS, backoff reconnect, refills buffers from `/api/leituras/recentes`, `cadastro` → `invalidarCadastros`); `AoVivoProvider` sits in `main.tsx`. uPlot charts (`componentes/GraficoBpm.tsx`) subscribe to buffer points and redraw via `requestAnimationFrame`, not React state. `frontend/.npmrc` sets `legacy-peer-deps` (openapi-typescript's peer is TS 5; we use TS 6).

Legacy: `device_config.py` and `App/servidor_ws.py` (old CSV server) remain until the new server is validated on real hardware. `scripts/diagnostico/` holds the old experiment scripts.

## Roadmap (staged commits on branch `dashboard`)

(a) pulseiras + dynamic allowlist ✔ · (b1) pesquisadores + atribuições ✔ · (b2) laboratórios + experimentos ✔ · (c) live dashboard (WS `/ws/ao-vivo`, uPlot, detail page) ✔ · (d) alertas (global limits + duration, sem sinal, fora do braço, acknowledge) ✔ · (e) history and CSV export (incl. BPM per experiment = participants' atribuições within the experiment period) · (f) auth (roles admin/leitor, 12 h session, auditoria).
