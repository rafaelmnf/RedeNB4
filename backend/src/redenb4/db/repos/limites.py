"""Limites globais dos alertas (linha única, id = 1)."""
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from ...config import Config
from ...dominio.alertas import Limites as LimitesDominio
from ..models import Limites


def limites_do_config(config: Config) -> LimitesDominio:
    """Valores do .env, usados até a linha do banco ser lida (ou se o banco estiver fora)."""
    return LimitesDominio(config.bpm_min, config.bpm_max, config.alerta_duracao_s, config.sem_sinal_alerta_s,
                          config.fora_do_braco_alerta_s)


def para_dominio(lim: Limites) -> LimitesDominio:
    return LimitesDominio(lim.bpm_min, lim.bpm_max, lim.duracao_s, lim.sem_sinal_s, lim.fora_do_braco_s)


async def obter_ou_criar(sessao: AsyncSession, config: Config) -> Limites:
    """Devolve a linha de limites, criando-a com os valores do .env na primeira vez."""
    await sessao.execute(
        insert(Limites)
        .values(id=1, bpm_min=config.bpm_min, bpm_max=config.bpm_max, duracao_s=config.alerta_duracao_s,
                sem_sinal_s=config.sem_sinal_alerta_s, fora_do_braco_s=config.fora_do_braco_alerta_s)
        .on_conflict_do_nothing(index_elements=[Limites.id])
    )
    await sessao.commit()
    return await sessao.get(Limites, 1, populate_existing=True)


async def atualizar(sessao: AsyncSession, config: Config, **campos) -> Limites:
    lim = await obter_ou_criar(sessao, config)
    for nome, valor in campos.items():
        setattr(lim, nome, valor)
    lim.atualizado_em = func.now()
    await sessao.commit()
    await sessao.refresh(lim)
    return lim
