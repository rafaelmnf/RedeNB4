"""Exporta o schema OpenAPI para gerar os tipos TypeScript do frontend.

    uv run python -m redenb4.api.openapi ../frontend/src/api/openapi.json
"""
import json
import sys
from pathlib import Path

from .app import criar_app


def main() -> None:
    destino = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("openapi.json")
    schema = criar_app(iniciar_ingestao=False).openapi()
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"OpenAPI salvo em {destino}")


if __name__ == "__main__":
    main()
