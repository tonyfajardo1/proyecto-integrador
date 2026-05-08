"""
Validacion rapida de conectividad y token ODIN API.

Uso:
  python validar_odin_api.py
"""
import os
import sys
from pathlib import Path


def load_env(env_path: Path) -> None:
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding='utf-8', errors='ignore').splitlines():
        s = line.strip()
        if not s or s.startswith('#') or '=' not in s:
            continue
        k, v = s.split('=', 1)
        os.environ[k.strip()] = v.strip()


def main() -> int:
    root = Path(__file__).resolve().parent
    load_env(root / '.env')

    sys.path.insert(0, str(root / 'condimensa_project'))
    from custom.odin_api_client import odin_get

    estado = os.getenv('ODIN_ESTADO', 'PENDIENTE')

    print('[ODIN] Probando endpoint sales...')
    sales = odin_get('sales', 'Sales', {'estado': estado, 'from': 0, 'skip': 2})
    print(f"  status={sales.get('status')} total={sales.get('message')}")

    print('[ODIN] Probando endpoint produccion...')
    prod = odin_get('produccion', 'Sales', {'estado': estado, 'from': 0, 'skip': 2})
    print(f"  status={prod.get('status')} total={prod.get('message')}")

    print('[ODIN] OK: API accesible con token')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
