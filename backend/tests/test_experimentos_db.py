"""Laboratórios, experimentos e participantes contra o Postgres."""
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from redenb4.api.schemas import ExperimentoCriar
from redenb4.db.models import Experimento, experimento_participantes
from redenb4.db.repos import experimentos as repo
from redenb4.db.repos import laboratorios as repo_lab
from redenb4.db.repos import pesquisadores as repo_pesq

AGORA = datetime.now(UTC)
HORA = timedelta(hours=1)


async def _cenario(s):
    lab = await repo_lab.cadastrar(s, "Laboratório de Biologia", "Sala 3")
    bia = await repo_pesq.cadastrar(s, "Bia", "bia@cnpem.br")
    ana = await repo_pesq.cadastrar(s, "Ana", "ana@cnpem.br")
    return lab, ana, bia


async def test_criar_com_participantes(fabrica):
    async with fabrica() as s:
        lab, ana, bia = await _cenario(s)
        e = await repo.criar(s, lab.id, "  Teste de esforço ", AGORA - HORA, "Esteira",
                             participantes=[bia.id, ana.id, ana.id])
        assert e.nome == "Teste de esforço"
        assert e.laboratorio.nome == "Laboratório de Biologia"
        assert [p.nome for p in e.participantes] == ["Ana", "Bia"]       # em ordem de nome, sem repetir
        assert repo.situacao(e) == "em_andamento"
        assert [x.id for x in await repo.listar(s, laboratorio_id=lab.id)] == [e.id]


async def test_editar_substitui_participantes_e_omitir_mantem(fabrica):
    async with fabrica() as s:
        lab, ana, bia = await _cenario(s)
        e = await repo.criar(s, lab.id, "Exp", AGORA, participantes=[ana.id])
        e = await repo.atualizar(s, e.id, participantes=[bia.id])
        assert [p.nome for p in e.participantes] == ["Bia"]
        e = await repo.atualizar(s, e.id, nome="Exp 2")
        assert e.nome == "Exp 2" and [p.nome for p in e.participantes] == ["Bia"]
        e = await repo.atualizar(s, e.id, participantes=[])
        assert e.participantes == []


async def test_periodo_invalido(fabrica):
    async with fabrica() as s:
        lab, _, _ = await _cenario(s)
        lab_id = lab.id
        with pytest.raises(repo.ExperimentoInvalido, match="fim deve ser depois"):
            await repo.criar(s, lab_id, "Exp", AGORA, fim=AGORA)
        s.add(Experimento(laboratorio_id=lab_id, nome="Direto", inicio=AGORA, fim=AGORA - HORA))
        with pytest.raises(IntegrityError, match="ck_experimentos_periodo"):
            await s.commit()
    with pytest.raises(ValidationError, match="fim deve ser depois"):
        ExperimentoCriar(laboratorio_id=1, nome="X", inicio=AGORA, fim=AGORA - HORA)


async def test_laboratorio_ou_pesquisador_inexistente(fabrica):
    async with fabrica() as s:
        lab, _, _ = await _cenario(s)
        with pytest.raises(repo.ExperimentoInvalido, match="Laboratório"):
            await repo.criar(s, 9999, "Exp", AGORA)
        with pytest.raises(repo.ExperimentoInvalido, match="Pesquisador"):
            await repo.criar(s, lab.id, "Exp", AGORA, participantes=[9999])


async def test_mesmo_pesquisador_em_experimentos_simultaneos(fabrica):
    async with fabrica() as s:
        lab, ana, _ = await _cenario(s)
        outro = await repo_lab.cadastrar(s, "Laboratório de Física")
        await repo.criar(s, lab.id, "A", AGORA - HORA, participantes=[ana.id])
        await repo.criar(s, outro.id, "B", AGORA - HORA, participantes=[ana.id])
        assert len(await repo.listar(s, situacao_="em_andamento")) == 2


async def test_situacao_e_filtro(fabrica):
    async with fabrica() as s:
        lab, _, _ = await _cenario(s)
        agendado = await repo.criar(s, lab.id, "Agendado", AGORA + 24 * HORA)
        andamento = await repo.criar(s, lab.id, "Em andamento", AGORA - HORA, fim=AGORA + HORA)
        encerrado = await repo.criar(s, lab.id, "Encerrado", AGORA - 3 * HORA, fim=AGORA - HORA)
        assert [repo.situacao(e) for e in (agendado, andamento, encerrado)] == \
            ["agendado", "em_andamento", "encerrado"]
        for sit, esperado in (("agendado", agendado), ("em_andamento", andamento), ("encerrado", encerrado)):
            assert [e.id for e in await repo.listar(s, situacao_=sit)] == [esperado.id]


async def test_encerrar(fabrica):
    async with fabrica() as s:
        lab, _, _ = await _cenario(s)
        e = await repo.criar(s, lab.id, "Exp", AGORA - HORA)
        e = await repo.encerrar(s, e.id)
        assert repo.situacao(e) == "encerrado"
        with pytest.raises(repo.ExperimentoJaEncerrado):
            await repo.encerrar(s, e.id)
        futuro = await repo.criar(s, lab.id, "Futuro", AGORA + HORA)
        with pytest.raises(repo.ExperimentoNaoIniciado):
            await repo.encerrar(s, futuro.id)


async def test_excluir_experimento_leva_os_participantes(fabrica):
    async with fabrica() as s:
        lab, ana, bia = await _cenario(s)
        e = await repo.criar(s, lab.id, "Exp", AGORA, participantes=[ana.id, bia.id])
        await repo.remover(s, e.id)
        assert await s.scalar(select(func.count()).select_from(experimento_participantes)) == 0
        with pytest.raises(repo.ExperimentoNaoEncontrado):
            await repo.obter(s, e.id)


async def test_laboratorio_com_experimentos_nao_e_excluido(fabrica):
    async with fabrica() as s:
        lab, _, _ = await _cenario(s)
        vazio = await repo_lab.cadastrar(s, "Vazio")
        await repo.criar(s, lab.id, "Exp", AGORA)
        with pytest.raises(repo_lab.LaboratorioComExperimentos):
            await repo_lab.remover(s, lab.id)
        await repo_lab.remover(s, vazio.id)
        assert [(lab.nome, total) for lab, total in await repo_lab.listar(s)] == [("Laboratório de Biologia", 1)]
        with pytest.raises(repo_lab.LaboratorioDuplicado):
            await repo_lab.cadastrar(s, "Laboratório de Biologia")


async def test_participante_nao_pode_ser_excluido(fabrica):
    async with fabrica() as s:
        lab, ana, bia = await _cenario(s)
        await repo.criar(s, lab.id, "Exp", AGORA, participantes=[ana.id])
        with pytest.raises(repo_pesq.PesquisadorComHistorico, match="participa de experimento"):
            await repo_pesq.remover(s, ana.id)
        await repo_pesq.remover(s, bia.id)
