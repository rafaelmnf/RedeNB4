# RedeNB4

Monitoramento de frequência cardíaca (BPM) das pulseiras **Polar Verity Sense**, usando um AP Aruba (InstantOS 8.10) como receptor BLE. O AP encaminha os advertisements da Polar via WebSocket para o servidor, que decodifica os frames, grava as leituras no PostgreSQL e serve um site para cadastro e acompanhamento em tempo real.

```
Pulseira Polar ──BLE adv──► AP Aruba ──WebSocket :8765──► redenb4 ──► PostgreSQL (Docker)
                                                              │
                                              navegador ◄─────┘  site + API :8000
```

- **Backend** (`backend/`): Python, FastAPI, SQLAlchemy async, Alembic. Gerenciado com **uv**.
- **Frontend** (`frontend/`): React, TypeScript e Vite, com Mantine. O build gera arquivos estáticos que o próprio backend serve. Funciona **offline**, sem CDN.
- **Banco**: PostgreSQL 17 no Docker (só o banco; a aplicação roda direto com `uv run`).

## Pré-requisitos

- [uv](https://docs.astral.sh/uv/)
- Docker Desktop
- Node.js (só na máquina onde o frontend é compilado)

## Primeira execução

```powershell
# 1. Configuração (troque as senhas)
Copy-Item .env.example .env

# 2. Banco
docker compose up -d db

# 3. Backend: dependências e tabelas
cd backend
uv sync
uv run alembic upgrade head

# 4. Frontend: compila o site (gera frontend/dist)
cd ..\frontend
npm ci
npm run build

# 5. Sobe tudo (AP na 8765, site em http://127.0.0.1:8000)
cd ..\backend
uv run redenb4
```

> A porta do banco no host é a **5433** (`DB_PORTA`), para não conflitar com um PostgreSQL instalado no Windows.

## Cadastrar a primeira pulseira

1. Abra http://127.0.0.1:8000/pulseiras e clique em **Cadastrar pulseira**.
2. Informe o MAC. São aceitos `AA:BB:CC:DD:EE:FF`, `aa-bb-…`, `aabb.ccdd.eeff` e `aabbccddeeff`, e tudo é salvo como `AA:BB:CC:DD:EE:FF`. O apelido é opcional.
3. Pronto: a partir desse momento o servidor aceita os dados dela, **sem reiniciar**.

Desativar ou remover a pulseira faz o servidor parar de aceitar os dados dela. Se a pulseira tiver leituras gravadas, a remoção só a arquiva e o histórico é preservado. Cadastrar o mesmo MAC de novo restaura o registro.

Se você já tinha um `device_macs.json` do servidor antigo, importe-o com:

```powershell
uv run redenb4 importar-macs            # lê ..\device_macs.json
```

### Token do AP

O AP envia o `endpointToken` do perfil IoT dentro de cada frame. Para o servidor recusar frames de qualquer outro computador da rede, coloque o mesmo valor em `TOKEN_AP` no `.env` e reinicie o servidor. Use um valor forte (ex.: `python -c "import secrets; print(secrets.token_urlsafe(24))"`) e troque também no AP: `iot transportProfile Polar-WebSocket` → `endpointToken <valor>`. O simulador usa o `TOKEN_AP` do `.env` automaticamente.

### Pulseira não cadastrada

Se o AP enviar uma Polar cujo MAC não está cadastrado, o log mostra `Pulseira Polar NÃO cadastrada detectada: <MAC>`. Basta cadastrar esse MAC.

### Como a allowlist funciona

O AP já filtra pelo perfil IoT (`companyIdentifierFilter 006B` + `perFrameFiltering`) e envia só os advertisements da Polar. O servidor é a segunda camada: aceita apenas os MACs cadastrados e ativos. Cada alteração na tabela `pulseiras` dispara um `NOTIFY` no Postgres (trigger), e o servidor, que está em `LISTEN`, recarrega a lista na hora. Isso vale até para edições feitas direto no `psql`. Nada é enviado ao AP.

## Simulador (testar sem o hardware)

O simulador gera frames no mesmo formato do AP e os envia para a porta 8765, então passa pelo parser real:

```powershell
cd backend
uv run redenb4 simular --n 5 --cadastrar      # cria 5 pulseiras fake e cadastra os MACs
uv run redenb4 simular --n 3 --alto 2         # pulseira 2 com BPM subindo para ~170
uv run redenb4 simular --n 3 --baixo 1 --sumir 3 --fora 2
```

| opção | efeito |
|---|---|
| `--alto N…` / `--baixo N…` | BPM vai para ~170 / ~40 |
| `--sumir N…` | para de enviar (simula falta de sinal) |
| `--fora N…` | BPM 0 (pulseira fora do braço) |
| `--intervalo S` | segundos entre frames (padrão 1) |

## Desenvolvimento

```powershell
# Backend
cd backend
uv run pytest                  # testes (os de banco precisam do docker compose up -d db)
uv run ruff check src tests

# Frontend com recarga automática: abra http://127.0.0.1:5173
# (o Vite repassa /api e /ws para o backend na 8000, que precisa estar rodando)
cd frontend
npm run dev

# Depois de mudar a API, regere os tipos TypeScript
npm run gerar-api
```

Diagnóstico com o AP real:

```powershell
uv run redenb4 servidor --dump   # imprime a árvore protobuf das 3 primeiras entradas Polar
uv run redenb4 servidor --raw    # grava os frames em raw_frames.bin
```

Os scripts experimentais antigos (scan BLE, GATT direto, dump do AP) estão em `scripts/diagnostico/`. O servidor original `App/servidor_ws.py` continua funcionando até a validação do novo com o AP real.

## Estrutura

```
backend/src/redenb4/
  dominio/      regras puras (MAC, leitura, RSSI/distância, seletor)
  ingestao/     parser do protobuf do Aruba, servidor WS do AP, allowlist dinâmica
  servicos/     pipeline de processamento, gravação em lote (COPY)
  db/           modelos SQLAlchemy e repositórios
  api/          FastAPI (rotas REST, serve o frontend)
backend/alembic/  migrações do banco
frontend/src/     React (api/, componentes/, paginas/, util/)
deploy/initdb/    scripts executados na criação do volume do Postgres
```

## Backup

```powershell
docker compose exec -T db pg_dump -U redenb4 -Fc redenb4 > backup_redenb4.dump
# restaurar:
docker compose exec -T db pg_restore -U redenb4 -d redenb4 --clean < backup_redenb4.dump
```

## Relógio

Os horários das leituras são os do servidor (gravados em UTC e exibidos em America/Sao_Paulo). Numa rede isolada, sem NTP, o relógio do Windows deriva com o tempo. Configure um servidor NTP local ou ajuste a hora periodicamente.
