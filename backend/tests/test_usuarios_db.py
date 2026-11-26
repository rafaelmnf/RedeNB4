"""Senhas, usuários e as proteções contra ficar sem administrador."""
import pytest

from redenb4.db.repos import usuarios as repo
from redenb4.dominio import senhas

SENHA = "senha-boa-123"


def test_hash_de_senha():
    h1, h2 = senhas.gerar_hash(SENHA), senhas.gerar_hash(SENHA)
    assert h1 != h2                                    # sal aleatório
    assert senhas.conferir(h1, SENHA) and not senhas.conferir(h1, "outra-senha")
    assert not senhas.conferir("lixo", SENHA)


async def test_criar_autenticar_e_email_unico(fabrica):
    async with fabrica() as s:
        u = await repo.criar(s, "  Ana@CNPEM.br ", "Ana", SENHA, "admin")
        assert u.email == "ana@cnpem.br" and u.versao_sessao == 1
        with pytest.raises(repo.UsuarioDuplicado):
            await repo.criar(s, "ana@cnpem.br", "Outra", SENHA)
        with pytest.raises(repo.SenhaFraca):
            await repo.criar(s, "bia@cnpem.br", "Bia", "curta")
        assert (await repo.autenticar(s, "ANA@cnpem.br", SENHA)).ultimo_login is not None
        assert await repo.autenticar(s, "ana@cnpem.br", "errada") is None
        assert await repo.autenticar(s, "ninguem@cnpem.br", SENHA) is None


async def test_ultimo_admin_e_auto_desativacao(fabrica):
    async with fabrica() as s:
        ana = await repo.criar(s, "ana@cnpem.br", "Ana", SENHA, "admin")
        leitor = await repo.criar(s, "leo@cnpem.br", "Leo", SENHA, "leitor")
        with pytest.raises(repo.AutoDesativacao):
            await repo.atualizar(s, ana.id, ana, ativo=False)
        with pytest.raises(repo.UltimoAdmin):
            await repo.atualizar(s, ana.id, ana, papel="leitor")
        # com outro admin, rebaixar a Ana passa a ser possível
        await repo.atualizar(s, leitor.id, ana, papel="admin")
        assert (await repo.atualizar(s, ana.id, ana, papel="leitor")).papel == "leitor"
        with pytest.raises(repo.UltimoAdmin):          # agora o Leo é o único admin
            await repo.atualizar(s, leitor.id, ana, ativo=False)


async def test_versao_da_sessao_aumenta_ao_cortar_acesso(fabrica):
    async with fabrica() as s:
        ana = await repo.criar(s, "ana@cnpem.br", "Ana", SENHA, "admin")
        leo = await repo.criar(s, "leo@cnpem.br", "Leo", SENHA, "leitor")
        assert (await repo.definir_senha(s, leo.id, "nova-senha-123")).versao_sessao == 2
        assert (await repo.encerrar_sessoes(s, leo.id)).versao_sessao == 3
        assert (await repo.atualizar(s, leo.id, ana, ativo=False)).versao_sessao == 4
        assert (await repo.atualizar(s, leo.id, ana, nome="Leonardo")).versao_sessao == 4    # editar não derruba
        assert await repo.autenticar(s, "leo@cnpem.br", "nova-senha-123") is None           # desativado
