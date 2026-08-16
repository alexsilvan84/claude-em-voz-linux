#!/usr/bin/env bash
# ============================================================
#  O MESMO Claude em Voz, mas preso a este terminal, mostrando
#  o que ele esta lendo e entendendo. Serve para diagnosticar -
#  no dia a dia use ./ligar.sh
#
#  ATENCAO: aqui o terminal E o programa. Fechar esta janela,
#  ou apertar Ctrl+C, desliga tudo.
#
#  Nao adianta abrir os dois: o segundo percebe que ja existe
#  um rodando e encerra sozinho. Desligue o outro antes, com
#  ./desligar.sh
# ============================================================
cd "$(dirname "$(readlink -f "$0")")" || exit 1

PY="${PYTHON:-python3}"
exec "$PY" -X utf8 -u claude_em_voz.py "$@"
