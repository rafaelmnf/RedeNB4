"""Cadastro de pulseiras. Toda alteração dispara NOTIFY no banco (trigger), que
atualiza a allowlist da ingestão sem reiniciar o servidor."""
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.repos import pulseiras as repo
from ..deps import obter_pipeline, obter_sessao
from ..schemas import PulseiraAtualizar, PulseiraCriar, PulseiraSaida, RemocaoSaida, StatusSaida

router = APIRouter(prefix="/api/pulseiras", tags=["pulseiras"])


def _status(pipeline, pulseira_id: int) -> StatusSaida | None:
    st = pipeline.status.get(pulseira_id) if pipeline is not None else None
    if st is None:
        return None
    limite = pipeline.config.offline_apos_s
    online = st.ultimo_contato is not None and (
        (datetime.now(UTC) - st.ultimo_contato).total_seconds() <= limite
    )
    return StatusSaida(
        online=online,
        ultimo_contato=st.ultimo_contato,
        ultimo_bpm=st.ultimo_bpm,
        ultima_leitura=st.ultima_leitura,
        rssi=st.rssi,
        distancia_m=st.distancia_m,
        ap_id=st.ap_id,
        fora_do_braco=st.fora_do_braco,
        bateria=st.bateria,
    )


def _saida(p, pipeline) -> PulseiraSaida:
    saida = PulseiraSaida.model_validate(p)
    saida.status = _status(pipeline, p.id)
    return saida


def _nao_encontrada(pulseira_id: int) -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, f"Pulseira {pulseira_id} não encontrada")


@router.get("", response_model=list[PulseiraSaida])
async def listar(sessao: AsyncSession = Depends(obter_sessao), pipeline=Depends(obter_pipeline)):
    return [_saida(p, pipeline) for p in await repo.listar(sessao)]


@router.get("/{pulseira_id}", response_model=PulseiraSaida)
async def obter(pulseira_id: int, sessao: AsyncSession = Depends(obter_sessao),
                pipeline=Depends(obter_pipeline)):
    try:
        return _saida(await repo.obter(sessao, pulseira_id), pipeline)
    except repo.PulseiraNaoEncontrada:
        raise _nao_encontrada(pulseira_id) from None


@router.post("", response_model=PulseiraSaida, status_code=status.HTTP_201_CREATED)
async def cadastrar(dados: PulseiraCriar, sessao: AsyncSession = Depends(obter_sessao),
                    pipeline=Depends(obter_pipeline)):
    try:
        p = await repo.cadastrar(sessao, dados.mac, dados.apelido)
    except repo.PulseiraDuplicada:
        raise HTTPException(status.HTTP_409_CONFLICT, f"O MAC {dados.mac} já está cadastrado") from None
    return _saida(p, pipeline)


@router.patch("/{pulseira_id}", response_model=PulseiraSaida)
async def atualizar(pulseira_id: int, dados: PulseiraAtualizar,
                    sessao: AsyncSession = Depends(obter_sessao), pipeline=Depends(obter_pipeline)):
    campos = dados.model_dump(exclude_unset=True)
    if campos.get("ativa") is None:
        campos.pop("ativa", None)
    try:
        return _saida(await repo.atualizar(sessao, pulseira_id, **campos), pipeline)
    except repo.PulseiraNaoEncontrada:
        raise _nao_encontrada(pulseira_id) from None


@router.delete("/{pulseira_id}", response_model=RemocaoSaida)
async def remover(pulseira_id: int, sessao: AsyncSession = Depends(obter_sessao)):
    try:
        return RemocaoSaida(resultado=await repo.remover(sessao, pulseira_id))
    except repo.PulseiraNaoEncontrada:
        raise _nao_encontrada(pulseira_id) from None
