#!/usr/bin/env bash
# ============================================================
#  O programa conferindo a si mesmo, e DIZENDO o resultado em
#  voz alta.
#
#  Rode isto quando alguma coisa parar de funcionar. Ele
#  confere, um por um: a fala, o microfone, a sua area de
#  trabalho e o jeito de digitar, os dois reconhecedores, os
#  quatro ganchos, o Claude Code, e se o programa esta no ar.
#
#  No fim ele FALA quantos problemas achou e quais sao. O que
#  fazer em cada caso fica escrito nesta tela.
#
#  Pode rodar com o programa ligado - alias, e o melhor jeito.
# ============================================================
cd "$(dirname "$(readlink -f "$0")")" || exit 1

PY="${PYTHON:-python3}"
"$PY" -X utf8 -u claude_em_voz.py --diagnostico
RESULTADO=$?

if [ "$RESULTADO" -eq 0 ]; then
    echo
    echo "  Nada a fazer. Se mesmo assim algo parece errado, o"
    echo "  registro.txt conta o que aconteceu na ultima partida."
fi

exit "$RESULTADO"
