"""Linha de comando.

    uv run redenb4                      # servidor (ingestão do AP + site/API)
    uv run redenb4 servidor --dump      # mostra a árvore protobuf das 3 primeiras entradas Polar
    uv run redenb4 servidor --raw       # grava frames em raw_frames.bin
    uv run redenb4 importar-macs [arquivo]   # importa device_macs.json para o banco
    uv run redenb4 simular --n 5 --cadastrar # simulador de pulseiras
    uv run redenb4 criar-usuario --admin --email fulano@cnpem.br --nome "Fulano"
    uv run redenb4 redefinir-senha --email fulano@cnpem.br
"""
import argparse
import asyncio
import logging
import sys
from pathlib import Path

from .config import RAIZ_REPO, obter_config


def _configurar_log() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
                        datefmt="%H:%M:%S")
    logging.getLogger("websockets").setLevel(logging.WARNING)


def cmd_servidor(args) -> None:
    import uvicorn

    from .api.app import criar_app

    config = obter_config()
    app = criar_app(config, dump=args.dump, arquivo_raw=Path("raw_frames.bin") if args.raw else None)
    print(f"Site e API: http://127.0.0.1:{config.porta_web}   |   AP: ws://{config.host}:{config.porta_ap}")
    uvicorn.run(app, host=config.host, port=config.porta_web, log_config=None)


async def _importar(caminho: Path) -> None:
    sys.path.insert(0, str(RAIZ_REPO))
    from device_config import load_polar_devices

    from .db.repos import pulseiras as repo
    from .db.sessao import criar_engine, criar_fabrica_sessoes

    dispositivos = load_polar_devices(caminho)
    engine = criar_engine(obter_config().database_url)
    try:
        async with criar_fabrica_sessoes(engine)() as sessao:
            for nome, mac in dispositivos:
                try:
                    await repo.cadastrar(sessao, mac, nome)
                    print(f"  + {mac}  {nome}")
                except repo.PulseiraDuplicada:
                    await sessao.rollback()
                    print(f"  = {mac}  já cadastrada")
    finally:
        await engine.dispose()


def cmd_importar_macs(args) -> None:
    asyncio.run(_importar(Path(args.arquivo)))


def _pedir_senha() -> str:
    import getpass

    from .dominio.senhas import TAMANHO_MINIMO

    while True:
        senha = getpass.getpass("Senha: ")
        if len(senha) < TAMANHO_MINIMO:
            print(f"  A senha precisa ter pelo menos {TAMANHO_MINIMO} caracteres.")
            continue
        if getpass.getpass("Repita a senha: ") != senha:
            print("  As senhas não conferem.")
            continue
        return senha


async def _com_sessao(funcao):
    from .db.sessao import criar_engine, criar_fabrica_sessoes

    engine = criar_engine(obter_config().database_url)
    try:
        async with criar_fabrica_sessoes(engine)() as sessao:
            return await funcao(sessao)
    finally:
        await engine.dispose()


def cmd_criar_usuario(args) -> None:
    from .api.schemas import validar_email
    from .db.repos import auditoria, usuarios

    try:
        email = validar_email(args.email)
    except ValueError as exc:
        raise SystemExit(f"E-mail inválido: {exc}") from None
    senha = args.senha or _pedir_senha()
    papel = "admin" if args.admin else "leitor"

    async def criar(sessao):
        u = await usuarios.criar(sessao, email, args.nome, senha, papel)
        await auditoria.registrar(sessao, None, "usuario.criar", "usuario", u.id,
                                  {"email": u.email, "papel": u.papel, "origem": "linha de comando"})
        return u

    try:
        u = asyncio.run(_com_sessao(criar))
    except usuarios.UsuarioDuplicado:
        raise SystemExit(f"Já existe um usuário com o e-mail {email}") from None
    except usuarios.SenhaFraca as exc:
        raise SystemExit(str(exc)) from None
    print(f"Usuário criado: {u.nome} <{u.email}> ({u.papel})")


def cmd_redefinir_senha(args) -> None:
    from .db.repos import auditoria, usuarios

    senha = args.senha or _pedir_senha()

    async def redefinir(sessao):
        u = await usuarios.por_email(sessao, args.email)
        if u is None:
            raise SystemExit(f"Nenhum usuário com o e-mail {args.email}")
        u = await usuarios.definir_senha(sessao, u.id, senha)
        await auditoria.registrar(sessao, None, "usuario.redefinir_senha", "usuario", u.id,
                                  {"origem": "linha de comando"})
        return u

    u = asyncio.run(_com_sessao(redefinir))
    print(f"Senha de {u.email} redefinida. As sessões abertas dessa pessoa foram encerradas.")


def cmd_simular(args) -> None:
    from .simulador import executar

    executar(args)


def main(argv=None) -> None:
    _configurar_log()
    parser = argparse.ArgumentParser(prog="redenb4")
    sub = parser.add_subparsers(dest="comando")

    p = sub.add_parser("servidor", help="ingestão do AP + site/API (padrão)")
    p.add_argument("--dump", action="store_true", help="imprime a árvore protobuf das 3 primeiras entradas")
    p.add_argument("--raw", action="store_true", help="grava frames em raw_frames.bin")
    p.set_defaults(func=cmd_servidor)

    p = sub.add_parser("importar-macs", help="importa device_macs.json para o banco")
    p.add_argument("arquivo", nargs="?", default=str(RAIZ_REPO / "device_macs.json"))
    p.set_defaults(func=cmd_importar_macs)

    config = obter_config()
    p = sub.add_parser("simular", help="simula pulseiras enviando frames no formato do AP")
    p.add_argument("--n", type=int, default=3, help="quantidade de pulseiras (padrão 3)")
    p.add_argument("--url", default=f"ws://127.0.0.1:{config.porta_ap}")
    p.add_argument("--api", default=f"http://127.0.0.1:{config.porta_web}")
    p.add_argument("--intervalo", type=float, default=1.0, help="segundos entre frames")
    p.add_argument("--token", default=config.token_ap, help="endpointToken (padrão: TOKEN_AP do .env)")
    p.add_argument("--cadastrar", action="store_true", help="cadastra os MACs simulados no banco")
    for modo, ajuda in (("alto", "BPM sobe para ~170"), ("baixo", "BPM desce para ~40"),
                        ("sumir", "para de enviar (sem sinal)"), ("fora", "BPM 0 (fora do braço)")):
        p.add_argument(f"--{modo}", type=int, nargs="*", metavar="N", help=f"pulseiras (1..n): {ajuda}")
    p.add_argument("--sumir-apos", type=float, default=0, metavar="S",
                   help="com --sumir: envia normalmente por S segundos e só depois para (testa o alerta de sem sinal)")
    p.set_defaults(func=cmd_simular)

    p = sub.add_parser("criar-usuario", help="cria um usuário do site (o primeiro deve ser --admin)")
    p.add_argument("--email", required=True, help="e-mail CNPEM (é o login)")
    p.add_argument("--nome", required=True)
    p.add_argument("--admin", action="store_true", help="papel admin (padrão: leitor)")
    p.add_argument("--senha", help="a senha; se omitida, é pedida sem aparecer na tela (recomendado)")
    p.set_defaults(func=cmd_criar_usuario)

    p = sub.add_parser("redefinir-senha", help="define uma senha nova para um usuário")
    p.add_argument("--email", required=True)
    p.add_argument("--senha", help="a senha; se omitida, é pedida sem aparecer na tela (recomendado)")
    p.set_defaults(func=cmd_redefinir_senha)

    args = parser.parse_args(argv)
    if args.comando is None:
        args = parser.parse_args(["servidor", *(argv or sys.argv[1:])])
    args.func(args)


if __name__ == "__main__":
    main()
