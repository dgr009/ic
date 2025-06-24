import importlib
import sys
from types import ModuleType

_SUB_PKGS = [
    "common",
    "aws",
    "cf",
    "oci_module",
    "ssh",
]

for _sub in _SUB_PKGS:
    try:
        sys.modules[_sub] = importlib.import_module(_sub)
    except ImportError:
        continue

def main():
    """console_scripts 진입점용 래퍼. 내부적으로 ic.cli.main 실행"""
    from importlib import import_module

    cli_mod = import_module("ic.cli")
    cli_mod.main() 