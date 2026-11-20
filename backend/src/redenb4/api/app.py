"""Aplicação FastAPI. O lifespan sobe, no mesmo processo, a ingestão do AP (porta
PORTA_AP), a allowlist dinâmica e o gravador em lote."""
import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from ..config import Config, obter_config
from ..db.sessao import criar_engine, criar_fabrica_sessoes, dsn_asyncpg
from ..ingestao.allowlist import Allowlist
from ..ingestao.servidor_ap import ServidorAP
from ..servicos.gravador import GravadorLote
from ..servicos.pipeline import Pipeline
from .routers import atribuicoes, pesquisadores, pulseiras

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

        app.state.config = config
        app.state.fabrica_sessoes = fabrica
        app.state.allowlist = allowlist
        app.state.pipeline = pipeline

        tarefas = []
        servidor_ws = None
        if iniciar_ingestao:
            try:
                await allowlist.recarregar()
            except Exception as exc:
                log.error("Banco indisponível ao iniciar (%s); a allowlist será carregada quando voltar", exc)
            tarefas.append(asyncio.create_task(allowlist.escutar(dsn, parar), name="allowlist"))
            tarefas.append(asyncio.create_task(gravador.executar(parar), name="gravador"))
            servidor_ap = ServidorAP(allowlist, pipeline.processar, fabrica, dump=dump,
                                     arquivo_raw=arquivo_raw, token=config.token_ap)
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
    app.include_router(pulseiras.router)
    app.include_router(pesquisadores.router)
    app.include_router(atribuicoes.router)
    _montar_frontend(app, config.frontend_dist)
    return app


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
