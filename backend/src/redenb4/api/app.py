"""Aplicação FastAPI. O lifespan sobe, no mesmo processo, a ingestão do AP (porta
PORTA_AP), a allowlist dinâmica e o gravador em lote."""
import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse

from ..config import Config, obter_config
from ..db.repos import limites as repo_limites
from ..db.repos import usuarios as repo_usuarios
from ..db.repos.leituras import nomes_aps
from ..db.sessao import criar_engine, criar_fabrica_sessoes, dsn_asyncpg
from ..dominio.alertas import MotorAlertas
from ..ingestao.allowlist import Allowlist
from ..ingestao.servidor_ap import ServidorAP
from ..servicos.alertas import ServicoAlertas
from ..servicos.broadcaster import Broadcaster
from ..servicos.gravador import GravadorLote
from ..servicos.limpeza import LimpezaLeituras
from ..servicos.pipeline import Pipeline
from ..servicos.vigia import Vigia
from .ao_vivo import montar_cartao
from .routers import (
    alertas,
    ao_vivo,
    atribuicoes,
    auditoria,
    auth,
    experimentos,
    laboratorios,
    leituras,
    limites,
    pesquisadores,
    pulseiras,
    usuarios,
)
from .schemas import AlertaSaida
from .sessao import SEGREDOS_PADRAO

log = logging.getLogger(__name__)


def criar_app(config: Config | None = None, iniciar_ingestao: bool = True, dump: bool = False,
              arquivo_raw: Path | None = None) -> FastAPI:
    config = config or obter_config()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        engine = criar_engine(config.database_url)
        fabrica = criar_fabrica_sessoes(engine)
        dsn = dsn_asyncpg(config.database_url)
        parar = asyncio.Event()

        allowlist = Allowlist(fabrica)
        gravador = GravadorLote(dsn)
        pipeline = Pipeline(allowlist, gravador, config)
        allowlist.ao_mudar(pipeline.esquecer_removidas)

        # Tempo real: eventos do pipeline e do vigia viram mensagens para os navegadores.
        broadcaster = Broadcaster()

        def publicar_cartao(tipo: str, st) -> None:
            aceita = allowlist.por_id.get(st.pulseira_id)
            if aceita is None:
                return
            msg = {"tipo": tipo,
                   "cartao": montar_cartao(aceita, st, config, pipeline.nomes_aps).model_dump(mode="json")}
            if tipo == "leitura":
                msg.update(ts=st.ultima_leitura, bpm=st.ultimo_bpm)
            broadcaster.publicar(msg)

        pipeline.ao_evento(publicar_cartao)
        allowlist.ao_mudar(lambda: broadcaster.publicar({"tipo": "cadastro"}))

        # Alertas: o motor recebe leituras (pipeline), o tempo (vigia) e as mudanças de
        # vínculo (allowlist); o serviço grava e publica.
        motor = MotorAlertas(repo_limites.limites_do_config(config))

        def publicar_alerta(evento: str, alerta) -> None:
            broadcaster.publicar({"tipo": "alerta", "evento": evento,
                                  "alerta": AlertaSaida.model_validate(alerta).model_dump(mode="json")})

        servico_alertas = ServicoAlertas(fabrica, motor, publicar_alerta)

        def alertas_do_pipeline(tipo: str, st) -> None:
            if tipo == "leitura":
                servico_alertas.tratar(motor.leitura(st.pulseira_id, st.atribuicao_id, st.ultimo_bpm,
                                                     st.ultima_leitura))
            elif tipo == "status" and st.fora_do_braco:
                servico_alertas.tratar(motor.fora_do_braco(st.pulseira_id, st.atribuicao_id, st.ultimo_contato))

        def alertas_no_tempo(agora) -> None:
            contatos = {pid: (st.atribuicao_id, st.ultimo_contato) for pid, st in pipeline.status.items()}
            servico_alertas.tratar(motor.verificar(agora, contatos))

        def alertas_dos_vinculos() -> None:
            vinculos = {p.pulseira_id: p.atribuicao_id for p in allowlist.ativas()}
            servico_alertas.tratar(motor.sincronizar_vinculos(vinculos, datetime.now(UTC)))

        pipeline.ao_evento(alertas_do_pipeline)
        allowlist.ao_mudar(alertas_dos_vinculos)
        vigia = Vigia(pipeline, config.offline_apos_s, lambda st: publicar_cartao("status", st),
                      ao_verificar=alertas_no_tempo)

        app.state.config = config
        app.state.broadcaster = broadcaster
        app.state.fabrica_sessoes = fabrica
        app.state.allowlist = allowlist
        app.state.pipeline = pipeline
        app.state.alertas = servico_alertas

        tarefas = []
        servidor_ws = None
        try:
            await allowlist.recarregar()
            async with fabrica() as sessao:
                pipeline.nomes_aps.update(await nomes_aps(sessao))
                motor.definir_limites(repo_limites.para_dominio(await repo_limites.obter_ou_criar(sessao, config)))
            await servico_alertas.iniciar()
            async with fabrica() as sessao:
                if await repo_usuarios.total(sessao) == 0:
                    log.warning("Nenhum usuário cadastrado: ninguém consegue entrar no site. Crie o primeiro com "
                                "'uv run redenb4 criar-usuario --admin --email <e-mail> --nome <nome>'")
        except Exception as exc:
            log.error("Banco indisponível ao iniciar (%s); a allowlist será carregada quando voltar", exc)
        tarefas.append(asyncio.create_task(servico_alertas.executar(parar), name="alertas"))
        if iniciar_ingestao:
            tarefas.append(asyncio.create_task(allowlist.escutar(dsn, parar), name="allowlist"))
            tarefas.append(asyncio.create_task(vigia.executar(parar), name="vigia"))
            tarefas.append(asyncio.create_task(gravador.executar(parar), name="gravador"))
            if config.retencao_leituras_dias > 0:
                limpeza = LimpezaLeituras(fabrica, config.retencao_leituras_dias)
                tarefas.append(asyncio.create_task(limpeza.executar(parar), name="limpeza"))
                log.info("Leituras com mais de %g dia(s) são apagadas a cada hora", config.retencao_leituras_dias)
            servidor_ap = ServidorAP(allowlist, pipeline.processar, fabrica, dump=dump,
                                     arquivo_raw=arquivo_raw, token=config.token_ap,
                                     ao_novo_ap=pipeline.nomes_aps.__setitem__)
            app.state.servidor_ap = servidor_ap
            servidor_ws = await servidor_ap.servir(config.host, config.porta_ap)
            log.info("Ingestão do AP em ws://%s:%d  (%d pulseiras na allowlist)",
                     config.host, config.porta_ap, len(allowlist))
        try:
            yield
        finally:
            parar.set()
            if servidor_ws is not None:
                servidor_ws.close()
                await servidor_ws.wait_closed()
            await asyncio.gather(*tarefas, return_exceptions=True)
            await engine.dispose()

    app = FastAPI(title="RedeNB4", version="0.1.0", lifespan=lifespan)
    _avisar_segredo(config)
    app.middleware("http")(_conferir_origem)
    app.include_router(auth.router)
    app.include_router(usuarios.router)
    app.include_router(auditoria.router)
    app.include_router(pulseiras.router)
    app.include_router(pesquisadores.router)
    app.include_router(atribuicoes.router)
    app.include_router(laboratorios.router)
    app.include_router(experimentos.router)
    app.include_router(leituras.router)
    app.include_router(ao_vivo.router)
    app.include_router(limites.router)
    app.include_router(alertas.router)
    _montar_frontend(app, config.frontend_dist)
    return app


def _avisar_segredo(config: Config) -> None:
    if config.segredo_sessao in SEGREDOS_PADRAO:
        log.warning("SEGREDO_SESSAO está com o valor padrão: qualquer um pode forjar o login. Gere um com "
                    "'python -c \"import secrets; print(secrets.token_urlsafe(32))\"' e coloque no .env "
                    "(todos precisarão entrar de novo).")


async def _conferir_origem(request: Request, chamar):
    """Proteção extra contra CSRF: uma alteração vinda de outra página (Origin diferente
    do Host) é recusada. Navegadores sempre mandam Origin em POST/PUT/PATCH/DELETE."""
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        origem = request.headers.get("origin")
        if origem and origem.split("://", 1)[-1] != request.headers.get("host"):
            return JSONResponse({"detail": "Origem da requisição não permitida"}, status_code=403)
    return await chamar(request)


def _montar_frontend(app: FastAPI, dist: Path) -> None:
    """Serve o build do React (frontend/dist). Rotas desconhecidas devolvem o
    index.html para o React Router tratar."""
    dist = dist.resolve()

    @app.get("/{caminho:path}", include_in_schema=False)
    async def frontend(caminho: str):
        if caminho.startswith(("api/", "ws/")):
            raise HTTPException(404)
        indice = dist / "index.html"
        if not indice.exists():
            raise HTTPException(404, "Frontend não compilado: rode 'npm run build' em frontend/")
        arquivo = (dist / caminho).resolve()
        if caminho and arquivo.is_file() and arquivo.is_relative_to(dist):
            return FileResponse(arquivo)
        return FileResponse(indice)
