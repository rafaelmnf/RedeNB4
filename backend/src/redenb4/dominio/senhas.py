"""Hash de senhas com argon2 (argon2-cffi)."""
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

TAMANHO_MINIMO = 8
_hasher = PasswordHasher()


def gerar_hash(senha: str) -> str:
    return _hasher.hash(senha)


def conferir(senha_hash: str, senha: str) -> bool:
    try:
        return _hasher.verify(senha_hash, senha)
    except (VerificationError, InvalidHashError):
        return False


def precisa_rehash(senha_hash: str) -> bool:
    """Verdadeiro se os parâmetros do argon2 mudaram desde que o hash foi gerado."""
    return _hasher.check_needs_rehash(senha_hash)
