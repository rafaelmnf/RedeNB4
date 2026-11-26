"""Login, papéis (admin/leitor), cookie de sessão e auditoria pela API de verdade."""
import pytest
from ajudantes import SENHA_TESTE, criar_usuario_teste, entrar
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from redenb4.api import routers
from redenb4.api.app import criar_app
from redenb4.api.sessao import NOME_COOKIE
from redenb4.config import Config
from redenb4.db.repos import auditoria as repo_aud
from redenb4.db.repos import usuarios as repo_usu

MAC = "A0:9E:1A:00:00:01"


def _usar_cookie(cliente, valor: str) -> None:
    """Troca o cookie de sessão do TestClient (como se fosse outro navegador)."""
    cliente.cookies.clear()
    cliente.cookies.set(NOME_COOKIE, valor)


@pytest.fixture
async def app(fabrica, url_banco_teste):
    await criar_usuario_teste(fabrica, "admin@cnpem.br", "admin", "Admin")
    await criar_usuario_teste(fabrica, "leitor@cnpem.br", "leitor", "Leitor")
    routers.auth._falhas.clear()
    return criar_app(Config(database_url=url_banco_teste, segredo_sessao="segredo-dos-testes"),
                     iniciar_ingestao=False)


def test_sem_login_nada_abre(app):
    with TestClient(app) as c:
        for rota in ("/api/pulseiras", "/api/status", "/api/alertas", "/api/limites", "/api/auth/eu"):
            assert c.get(rota).status_code == 401, rota
        assert c.post("/api/pulseiras", json={"mac": MAC}).status_code == 401
        with pytest.raises(WebSocketDisconnect) as exc, c.websocket_connect("/ws/ao-vivo") as ws:
            ws.receive_json()
        assert exc.value.code == 4401
        assert c.get("/").status_code in (200, 404)     # o site (tela de login) continua acessível


def test_leitor_ve_tudo_mas_nao_edita(app):
    with TestClient(app) as c:
        entrar(c, "leitor@cnpem.br")
        assert c.get("/api/auth/eu").json()["papel"] == "leitor"
        for rota in ("/api/pulseiras", "/api/pesquisadores", "/api/experimentos", "/api/alertas", "/api/limites",
                     "/api/status"):
            assert c.get(rota).status_code == 200, rota
        assert c.post("/api/pulseiras", json={"mac": MAC}).status_code == 403
        assert c.patch("/api/pulseiras/1", json={"apelido": "x"}).status_code == 403
        assert c.delete("/api/pesquisadores/1").status_code == 403
        assert c.put("/api/limites", json={"bpm_min": 50, "bpm_max": 150, "duracao_s": 10, "sem_sinal_s": 30,
                                           "fora_do_braco_s": 60}).status_code == 403
        assert c.get("/api/usuarios").status_code == 403
        assert c.get("/api/auditoria").status_code == 403
        with c.websocket_connect("/ws/ao-vivo") as ws:
            assert ws.receive_json()["tipo"] == "snapshot"


async def test_admin_edita_e_fica_na_auditoria(app, fabrica):
    with TestClient(app) as c:
        entrar(c, "admin@cnpem.br")
        r = c.post("/api/pulseiras", json={"mac": MAC, "apelido": "Pulseira 01"})
        assert r.status_code == 201
        pid = r.json()["id"]
        assert c.patch(f"/api/pulseiras/{pid}", json={"apelido": "P1"}).status_code == 200
        assert c.post("/api/pulseiras", json={"mac": MAC}).status_code == 409        # erro não é auditado
        r = c.post("/api/usuarios", json={"email": "novo@cnpem.br", "nome": "Novo", "senha": "senha-nova-123"})
        assert r.status_code == 201 and r.json()["papel"] == "leitor"
        registros = c.get("/api/auditoria").json()
    acoes = [r["acao"] for r in reversed(registros)]
    assert acoes == ["login", "pulseira.criar", "pulseira.editar", "usuario.criar"]
    assert all(r["email"] == "admin@cnpem.br" for r in registros)
    editar = next(r for r in registros if r["acao"] == "pulseira.editar")
    assert (editar["entidade"], editar["entidade_id"], editar["detalhes"]) == ("pulseira", pid, {"apelido": "P1"})
    criar_usuario = next(r for r in registros if r["acao"] == "usuario.criar")
    assert "senha" not in (criar_usuario["detalhes"] or {})


async def test_cookie_falso_desativado_ou_senha_trocada_nao_vale(app, fabrica):
    with TestClient(app) as c:
        entrar(c, "leitor@cnpem.br")
        cookie = c.cookies.get(NOME_COOKIE)
        _usar_cookie(c, cookie[:-2] + "xx")                         # assinatura adulterada
        assert c.get("/api/auth/eu").status_code == 401
        _usar_cookie(c, cookie)
        assert c.get("/api/auth/eu").status_code == 200

        async with fabrica() as s:                                    # admin redefine a senha do leitor
            leitor = await repo_usu.por_email(s, "leitor@cnpem.br")
            await repo_usu.definir_senha(s, leitor.id, "outra-senha-123")
        assert c.get("/api/auth/eu").status_code == 401             # o cookie antigo caiu
        entrar(c, "leitor@cnpem.br", "outra-senha-123")
        assert c.get("/api/auth/eu").status_code == 200

        async with fabrica() as s:
            admin = await repo_usu.por_email(s, "admin@cnpem.br")
            await repo_usu.atualizar(s, leitor.id, admin, ativo=False)
        assert c.get("/api/auth/eu").status_code == 401


def test_troca_da_propria_senha_mantem_este_navegador(app):
    with TestClient(app) as c:
        entrar(c, "leitor@cnpem.br")
        cookie_de_outro_navegador = c.cookies.get(NOME_COOKIE)
        r = c.post("/api/auth/senha", json={"senha_atual": "errada", "nova_senha": "nova-senha-123"})
        assert r.status_code == 400
        r = c.post("/api/auth/senha", json={"senha_atual": SENHA_TESTE, "nova_senha": "nova-senha-123"})
        assert r.status_code == 204
        assert c.get("/api/auth/eu").status_code == 200             # este navegador continua
        _usar_cookie(c, cookie_de_outro_navegador)
        assert c.get("/api/auth/eu").status_code == 401             # o cookie anterior não vale mais


def test_logout_e_bloqueio_por_tentativas(app):
    with TestClient(app) as c:
        entrar(c, "leitor@cnpem.br")
        assert c.post("/api/auth/logout").status_code == 204
        assert c.get("/api/auth/eu").status_code == 401
        for _ in range(5):
            r = c.post("/api/auth/login", json={"email": "leitor@cnpem.br", "senha": "errada"})
            assert r.status_code == 401 and r.json()["detail"] == "E-mail ou senha inválidos"
        r = c.post("/api/auth/login", json={"email": "leitor@cnpem.br", "senha": SENHA_TESTE})
        assert r.status_code == 429                                  # bloqueado mesmo com a senha certa


def test_outra_origem_nao_altera_nada(app):
    with TestClient(app) as c:
        entrar(c, "admin@cnpem.br")
        r = c.post("/api/pulseiras", json={"mac": MAC}, headers={"Origin": "http://site-malicioso.example"})
        assert r.status_code == 403
        r = c.post("/api/pulseiras", json={"mac": MAC}, headers={"Origin": "http://testserver"})
        assert r.status_code == 201


async def test_ultimo_admin_pela_api(app, fabrica):
    with TestClient(app) as c:
        entrar(c, "admin@cnpem.br")
        async with fabrica() as s:
            admin = await repo_usu.por_email(s, "admin@cnpem.br")
            assert len(await repo_aud.listar(s)) == 1                 # o login
        r = c.patch(f"/api/usuarios/{admin.id}", json={"papel": "leitor"})
        assert r.status_code == 409 and "último administrador" in r.json()["detail"]
        assert c.patch(f"/api/usuarios/{admin.id}", json={"ativo": False}).status_code == 409
