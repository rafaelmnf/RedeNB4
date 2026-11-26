"""Ajudantes dos testes que usam o app com login."""
SENHA_TESTE = "senha-de-teste-123"


async def criar_usuario_teste(fabrica, email: str = "admin@cnpem.br", papel: str = "admin", nome: str = "Admin Teste"):
    from redenb4.db.repos import usuarios

    async with fabrica() as s:
        return await usuarios.criar(s, email, nome, SENHA_TESTE, papel)


def entrar(cliente, email: str = "admin@cnpem.br", senha: str = SENHA_TESTE) -> None:
    """Faz login no TestClient (o cookie fica guardado nele)."""
    r = cliente.post("/api/auth/login", json={"email": email, "senha": senha})
    assert r.status_code == 200, r.text
