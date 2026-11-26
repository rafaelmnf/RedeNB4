"""Cadastro de pesquisadores (Postgres) e validação dos dados de entrada."""
from datetime import date, timedelta

import pytest
from pydantic import ValidationError

from redenb4.api.schemas import PesquisadorCriar
from redenb4.db.repos import atribuicoes as repo_atr
from redenb4.db.repos import pesquisadores as repo
from redenb4.db.repos import pulseiras as repo_puls


async def test_email_unico_sem_diferenciar_maiusculas(fabrica):
    async with fabrica() as s:
        p = await repo.cadastrar(s, "Ana", "  Ana.Silva@CNPEM.br ")
        assert p.email == "ana.silva@cnpem.br"
        with pytest.raises(repo.PesquisadorDuplicado):
            await repo.cadastrar(s, "Outra Ana", "ana.silva@cnpem.br")


async def test_trocar_email_para_um_existente_e_recusado(fabrica):
    async with fabrica() as s:
        await repo.cadastrar(s, "Ana", "ana@cnpem.br")
        bia = await repo.cadastrar(s, "Bia", "bia@cnpem.br")
        with pytest.raises(repo.PesquisadorDuplicado):
            await repo.atualizar(s, bia.id, email="ANA@cnpem.br")


async def test_remover_so_quem_nunca_usou_pulseira(fabrica):
    async with fabrica() as s:
        nunca = await repo.cadastrar(s, "Nunca usou", "nunca@cnpem.br")
        usou = await repo.cadastrar(s, "Já usou", "usou@cnpem.br")
        p = await repo_puls.cadastrar(s, "A0:9E:1A:00:00:01", None)
        a = await repo_atr.criar(s, p.id, usou.id)
        await repo_atr.encerrar(s, a.id)

        await repo.remover(s, nunca.id)
        with pytest.raises(repo.PesquisadorComHistorico):
            await repo.remover(s, usou.id)
        assert [x.nome for x in await repo.listar(s)] == ["Já usou"]


async def test_listar_filtra_por_ativo(fabrica):
    async with fabrica() as s:
        ana = await repo.cadastrar(s, "Ana", "ana@cnpem.br")
        await repo.cadastrar(s, "Bia", "bia@cnpem.br")
        await repo.atualizar(s, ana.id, ativo=False)
        assert [x.nome for x in await repo.listar(s, ativo=True)] == ["Bia"]
        assert [x.nome for x in await repo.listar(s, ativo=False)] == ["Ana"]


@pytest.mark.parametrize("email", ["fulano@cnpem.br", "Fulano@LNLS.CNPEM.BR"])
def test_email_institucional_aceito(email):
    assert PesquisadorCriar(nome="Fulano", email=email).email == email.lower()


@pytest.mark.parametrize("email", ["fulano@gmail.com", "fulano@cnpem.br.com", "fulanocnpem.br", "a@xcnpem.br"])
def test_email_fora_do_dominio_recusado(email):
    with pytest.raises(ValidationError):
        PesquisadorCriar(nome="Fulano", email=email)


def test_nome_vazio_e_nascimento_futuro_recusados():
    with pytest.raises(ValidationError):
        PesquisadorCriar(nome="   ", email="a@cnpem.br")
    with pytest.raises(ValidationError):
        PesquisadorCriar(nome="A", email="a@cnpem.br", data_nascimento=date.today() + timedelta(days=1))
