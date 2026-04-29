#!/usr/bin/env python3
"""
Compat wrapper para manter o comando antigo do projeto.

Encaminha para scripts/analisar_vaga.py, que agora e o ponto de entrada
principal para o pipeline de analise.
"""

import sys

from scripts.analise.analisar_vaga import main


if __name__ == "__main__":
    sys.exit(main())
