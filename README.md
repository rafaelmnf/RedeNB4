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

> A porta do banco no host é a **5434** (`DB_PORTA`), porque a 5432 é do PostgreSQL instalado no Windows e a 5433 é usada por outro projeto no Docker. Nas URLs use `127.0.0.1`, não `localhost` (no Windows o `localhost` pode ir para o IPv6 e cair em outro serviço).

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

## Pesquisadores e vínculo com a pulseira

1. Em http://127.0.0.1:8000/pesquisadores, cadastre quem vai usar as pulseiras.
   - O **nome** e o **e-mail CNPEM** são obrigatórios.
   - Nascimento e observações são opcionais.
   - O e-mail é único e salvo em minúsculas. O domínio exigido vem de `DOMINIO_EMAIL` no `.env` (padrão `cnpem.br`, e subdomínios também valem). Deixe vazio para aceitar qualquer domínio.
2. Em **Pulseiras**, clique em **Vincular** (ícone de pessoa) e escolha quem está com a pulseira.
   - O vínculo começa na hora do clique.
   - A partir daí, cada leitura de BPM é gravada com o vínculo (`leituras_bpm.atribuicao_id`).
3. **Desvincular** encerra o uso, e a pulseira volta a "Não vinculada". O ícone de relógio mostra quem já usou cada pulseira e quando.

Regras:
- Uma pulseira fica com no máximo uma pessoa por vez, e uma pessoa com no máximo uma pulseira. Isso é garantido no banco por constraints `EXCLUDE` sobre o período, inclusive no histórico.
- Desativar ou remover a pulseira, ou desativar a pessoa, **encerra o vínculo automaticamente**.
- Só é possível excluir um pesquisador que nunca usou pulseira. Quem já tem histórico deve ser desativado.
- Vínculos nunca são apagados: só recebem o horário de fim.

## Dashboard (tempo real)

A página inicial (http://127.0.0.1:8000) mostra um card para cada pulseira ativa. Tudo se atualiza sozinho por WebSocket (`/ws/ao-vivo`), sem recarregar a página.

Cada card mostra:
- quem está usando a pulseira, ou "Não vinculada";
- o BPM em destaque e um gráfico da janela escolhida (1, 5 ou 15 min);
- RSSI, distância estimada, AP e há quanto tempo foi o último contato.

O card muda de aparência conforme o estado:
- **cinza** ("sem sinal"): sem nenhum advertisement há mais de `OFFLINE_APOS_S` segundos (padrão 15);
- **amarelo**: fora do braço (BPM 0);
- "sem dados": a pulseira ainda não mandou nada desde que o servidor subiu.

O selo no topo mostra **Ao vivo** ou **Reconectando…**. Se o servidor cair, o site reconecta sozinho e completa os gráficos com os últimos minutos gravados no banco.

Clique em um card para abrir o **detalhe da pulseira**, que mostra:
- o gráfico ao vivo dos últimos 15 min;
- o histórico de 1 h ou 24 h (média, com uma faixa de mínimo e máximo);
- quem já usou a pulseira e quando.

A tela Pulseiras também recebe o status ao vivo pelo WebSocket. Ela não consulta mais o servidor a cada 5 s.

O botão no canto superior direito alterna entre o tema claro e o escuro.

## Alertas

Os alertas valem só para **pulseiras vinculadas a alguém**.

| alerta | dispara quando | termina quando |
|---|---|---|
| **BPM alto** | o BPM fica acima do máximo por *tempo fora da faixa* segundos seguidos | chega uma leitura dentro da faixa |
| **BPM baixo** | o BPM fica abaixo do mínimo pelo mesmo tempo (BPM 0 não conta) | chega uma leitura dentro da faixa |
| **Sem sinal** | a pulseira passa *sem sinal* segundos sem enviar nada | a pulseira volta a enviar |
| **Fora do braço** | a pulseira marca BPM 0 por *fora do braço* segundos | chega um BPM maior que zero |

Um BPM que volta à faixa por um instante zera a contagem. Para BPM alto e baixo, o alerta guarda o pico (ou o vale) atingido.

Na tela:
- o alerta aparece num **banner vermelho no topo de todas as páginas**, e o card da pulseira fica vermelho;
- **Reconhecer** tira o alerta do destaque. Ele continua registrado e aberto até a condição acabar;
- desvincular a pulseira encerra os alertas dela.

Os limites são globais e ficam na tela **Limites**. Os valores iniciais vêm do `.env`:
- `BPM_MIN` e `BPM_MAX`;
- `ALERTA_DURACAO_S`;
- `SEM_SINAL_ALERTA_S`;
- `FORA_DO_BRACO_ALERTA_S`.

Uma mudança feita na tela vale na hora, sem reiniciar o servidor.

A tela **Alertas** lista os alertas em andamento ou todos. Cada alerta também sai no log do servidor.

Se o servidor reiniciar, os alertas que estavam abertos são encerrados, e os que continuarem valendo são abertos de novo quando a pulseira voltar a enviar dados.

Para testar sem hardware:

```powershell
# alto na 1, baixo na 2, fora do braço na 3; a 4 envia por 30 s e depois some
uv run redenb4 simular --n 4 --cadastrar --alto 1 --baixo 2 --fora 3 --sumir 4 --sumir-apos 30
```

Vincule as 4 pulseiras a pesquisadores. Só pulseiras vinculadas geram alerta.

## Laboratórios e experimentos

Na aba **Experimentos** ficam os experimentos de cada laboratório, com descrição, período e as pessoas envolvidas.

1. Clique em **Laboratórios** e cadastre os laboratórios.
2. Clique em **Novo experimento** e preencha:
   - laboratório e nome;
   - descrição;
   - início e fim (o fim é opcional);
   - pessoas envolvidas.
3. A situação é calculada pelas datas: *agendado* (ainda não começou), *em andamento* ou *encerrado*. **Encerrar** (ícone de bandeira) grava o fim como agora.
4. Use os filtros por laboratório e por situação. A lista sai agrupada por laboratório.

Regras:
- O experimento **não se liga à pulseira**. Um pesquisador pode estar em vários experimentos e salas ao mesmo tempo, e a pulseira fica com quem a está usando (aba Pulseiras). O BPM de um experimento sai do cruzamento entre participantes, período e as pulseiras que essas pessoas usavam no período (etapa de histórico).
- Excluir um experimento apaga só a lista de participantes. Pesquisadores e leituras não são afetados.
- Um laboratório com experimentos não pode ser excluído.
- Um pesquisador que participa de algum experimento não pode ser excluído, só desativado.

### Identificação do AP

O AP é identificado pelo **MAC do rádio BLE** que ouviu cada pulseira. Ele vem no campo [6] de cada entrada do frame, não muda com DHCP e é diferente em cada AP. Cada rádio novo vira uma linha em `aps` na primeira leitura. As linhas antigas, identificadas por IP, ficam só como histórico.

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

O servidor original `App/servidor_ws.py` fica como teste básico, sem banco: ele imprime o BPM e grava um CSV. Use o ambiente do backend para rodá-lo, sem `.venv` na raiz. Pare o `redenb4` antes, porque os dois usam a porta 8765.

```powershell
cd backend
uv run --no-sync python ..\App\servidor_ws.py          # ou --dump / --raw
```

Os scripts experimentais antigos (scan BLE, GATT direto, dump do AP) estão em `scripts/diagnostico/`. Os que falam BLE direto com a pulseira precisam do `bleak`, que o `uv` instala só para aquela execução:

```powershell
cd backend
uv run --no-sync --with bleak python ..\scripts\diagnostico\discover_polar.py
```

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

## Retenção das leituras

As leituras de BPM (`leituras_bpm`) com mais de **2 dias** são apagadas automaticamente. O prazo vem de `RETENCAO_LEITURAS_DIAS` no `.env`, e `0` guarda tudo.

A limpeza roda quando o servidor sobe e depois a cada hora. Ela apaga em lotes, sem atrapalhar a gravação das leituras novas.

Só as leituras são apagadas: pulseiras, pesquisadores, vínculos, experimentos e alertas ficam. O Postgres reaproveita o espaço liberado, então a tabela para de crescer. Ela não encolhe no disco sozinha; para devolver o espaço ao sistema, rode `VACUUM FULL leituras_bpm` com o servidor parado.

> Com 2 dias, os gráficos e a exportação só alcançam os últimos 2 dias. Para guardar mais, aumente `RETENCAO_LEITURAS_DIAS` e reinicie o servidor.

## Backup

```powershell
docker compose exec -T db pg_dump -U redenb4 -Fc redenb4 > backup_redenb4.dump
# restaurar:
docker compose exec -T db pg_restore -U redenb4 -d redenb4 --clean < backup_redenb4.dump
```

## Relógio

Os horários das leituras são os do servidor (gravados em UTC e exibidos em America/Sao_Paulo). Numa rede isolada, sem NTP, o relógio do Windows deriva com o tempo. Configure um servidor NTP local ou ajuste a hora periodicamente.
