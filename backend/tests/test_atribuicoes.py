"""Vínculos pulseira ↔ pesquisador contra o Postgres (constraints EXCLUDE e CHECK),
efeitos na allowlist e no atribuicao_id das leituras gravadas."""
from datetime import UTC, datetime, timedelta

import asyncpg
import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from redenb4.db.models import Atribuicao, LeituraBpm
from redenb4.db.repos import atribuicoes as repo
from redenb4.db.repos import pesquisadores as repo_pesq
from redenb4.db.repos import pulseiras as repo_puls
from redenb4.db.sessao import dsn_asyncpg
from redenb4.dominio.mac import mac_para_bytes
from redenb4.ingestao.allowlist import Allowlist
from redenb4.servicos.gravador import GravadorLote

MAC1, MAC2 = "A0:9E:1A:00:00:01", "A0:9E:1A:00:00:02"


async def _cenario(s):
    """Duas pulseiras e duas pessoas."""
    p1 = await repo_puls.cadastrar(s, MAC1, "Pulseira 01")
    p2 = await repo_puls.cadastrar(s, MAC2, "Pulseira 02")
    ana = await repo_pesq.cadastrar(s, "Ana", "ana@cnpem.br")
    bia = await repo_pesq.cadastrar(s, "Bia", "bia@cnpem.br")
    return p1, p2, ana, bia


async def test_pulseira_nao_pode_ter_duas_pessoas(fabrica):
    async with fabrica() as s:
        p1, _, ana, bia = await _cenario(s)
        await repo.criar(s, p1.id, ana.id)
        with pytest.raises(repo.AtribuicaoConflito, match="já está com Ana"):
            await repo.criar(s, p1.id, bia.id)


async def test_pessoa_nao_pode_ter_duas_pulseiras(fabrica):
    async with fabrica() as s:
        p1, p2, ana, _ = await _cenario(s)
        await repo.criar(s, p1.id, ana.id)
        with pytest.raises(repo.AtribuicaoConflito, match="Ana já está com a pulseira Pulseira 01"):
            await repo.criar(s, p2.id, ana.id)


async def test_encerrar_e_reatribuir(fabrica):
    async with fabrica() as s:
        p1, _, ana, bia = await _cenario(s)
        a = await repo.criar(s, p1.id, ana.id)
        assert a.fim is None and a.pesquisador.nome == "Ana"
        encerrada = await repo.encerrar(s, a.id)
        assert encerrada.fim is not None and encerrada.fim >= encerrada.inicio
        with pytest.raises(repo.AtribuicaoJaEncerrada):
            await repo.encerrar(s, a.id)
        b = await repo.criar(s, p1.id, bia.id)
        assert [x.id for x in await repo.listar(s, pulseira_id=p1.id)] == [b.id, a.id]
        assert [x.id for x in await repo.listar(s, ativa=True)] == [b.id]


async def test_exclude_bloqueia_sobreposicao_no_historico(fabrica):
    """Mesmo inserindo direto (sem passar pelo repositório), o banco recusa períodos sobrepostos."""
    async with fabrica() as s:
        p1, _, ana, bia = await _cenario(s)
        pid, ana_id, bia_id = p1.id, ana.id, bia.id     # objetos expiram no rollback
        agora = datetime.now(UTC)
        s.add(Atribuicao(pulseira_id=pid, pesquisador_id=ana_id,
                         inicio=agora - timedelta(hours=3), fim=agora - timedelta(hours=1)))
        await s.commit()
        s.add(Atribuicao(pulseira_id=pid, pesquisador_id=bia_id,
                         inicio=agora - timedelta(hours=2), fim=agora - timedelta(minutes=30)))
        with pytest.raises(IntegrityError) as exc:
            await s.commit()
        assert "ex_atribuicoes_pulseira" in str(exc.value)
        await s.rollback()
        # Encostado (fim de um = início do outro) é permitido: intervalo [inicio, fim).
        s.add(Atribuicao(pulseira_id=pid, pesquisador_id=bia_id,
                         inicio=agora - timedelta(hours=1), fim=agora))
        await s.commit()


async def test_check_fim_depois_do_inicio(fabrica):
    async with fabrica() as s:
        p1, _, ana, _ = await _cenario(s)
        agora = datetime.now(UTC)
        s.add(Atribuicao(pulseira_id=p1.id, pesquisador_id=ana.id, inicio=agora, fim=agora))
        with pytest.raises(IntegrityError, match="ck_atribuicoes_periodo"):
            await s.commit()


async def test_nao_vincula_pulseira_ou_pessoa_desativada(fabrica):
    async with fabrica() as s:
        p1, p2, ana, bia = await _cenario(s)
        await repo_puls.atualizar(s, p1.id, ativa=False)
        with pytest.raises(repo.AtribuicaoInvalida, match="desativada"):
            await repo.criar(s, p1.id, ana.id)
        await repo_pesq.atualizar(s, bia.id, ativo=False)
        with pytest.raises(repo.AtribuicaoInvalida, match="desativad"):
            await repo.criar(s, p2.id, bia.id)


@pytest.mark.parametrize("acao", ["desativar_pulseira", "remover_pulseira", "desativar_pessoa"])
async def test_desativar_ou_remover_encerra_o_vinculo(fabrica, acao):
    async with fabrica() as s:
        p1, _, ana, _ = await _cenario(s)
        a_id = (await repo.criar(s, p1.id, ana.id)).id
        if acao == "desativar_pulseira":
            await repo_puls.atualizar(s, p1.id, ativa=False)
        elif acao == "remover_pulseira":
            assert await repo_puls.remover(s, p1.id) == "arquivada"   # tem vínculo = tem histórico
        else:
            await repo_pesq.atualizar(s, ana.id, ativo=False)
        s.expire_all()
        assert (await repo.obter(s, a_id)).fim is not None
        assert await repo.listar(s, ativa=True) == []


async def test_allowlist_traz_quem_esta_usando(fabrica):
    async with fabrica() as s:
        p1, _, ana, _ = await _cenario(s)
        a = await repo.criar(s, p1.id, ana.id)
    al = Allowlist(fabrica)
    await al.recarregar()
    assert al.obter(mac_para_bytes(MAC1)).atribuicao_id == a.id
    assert al.obter(mac_para_bytes(MAC1)).pesquisador == "Ana"
    assert al.obter(mac_para_bytes(MAC2)).atribuicao_id is None

    async with fabrica() as s:
        await repo.encerrar(s, a.id)
    await al.recarregar()
    assert al.obter(mac_para_bytes(MAC1)).atribuicao_id is None
    assert al.obter(mac_para_bytes(MAC1)).pesquisador is None


async def test_leitura_gravada_com_atribuicao_id(fabrica, url_banco_teste):
    async with fabrica() as s:
        p1, p2, ana, _ = await _cenario(s)
        a = await repo.criar(s, p1.id, ana.id)
    agora = datetime.now(UTC)
    gravador = GravadorLote(dsn_asyncpg(url_banco_teste))
    gravador.adicionar(agora, p1.id, 72, -60.0, None, a.id)
    gravador.adicionar(agora, p2.id, 80, -70.0, None, None)
    conn = await asyncpg.connect(dsn_asyncpg(url_banco_teste))
    try:
        await gravador._gravar(conn)
    finally:
        await conn.close()
    async with fabrica() as s:
        linhas = (await s.execute(select(LeituraBpm.pulseira_id, LeituraBpm.atribuicao_id)
                                  .order_by(LeituraBpm.pulseira_id))).all()
    assert [tuple(x) for x in linhas] == [(p1.id, a.id), (p2.id, None)]


async def test_trigger_notifica_mudanca_de_vinculo(fabrica, url_banco_teste):
    """A allowlist escuta 'atribuicoes_alteradas'; o trigger precisa disparar no INSERT/UPDATE."""
    recebidos = []
    conn = await asyncpg.connect(dsn_asyncpg(url_banco_teste))
    try:
        await conn.add_listener("atribuicoes_alteradas", lambda *args: recebidos.append(args[3]))
        async with fabrica() as s:
            p1, _, ana, _ = await _cenario(s)
            a = await repo.criar(s, p1.id, ana.id)
            await repo.encerrar(s, a.id)
            await s.execute(text("SELECT 1"))
        await conn.execute("SELECT 1")   # dá tempo de o asyncpg entregar as notificações
    finally:
        await conn.close()
    assert "INSERT" in recebidos and "UPDATE" in recebidos
