#!/usr/bin/env bash
# ============================================================
#  Mostra o que cada tecla do seu teclado manda.
#
#  Util quando voce quer trocar a tecla de falar, e obrigatorio
#  em notebook: a fileira de cima costuma vir trocada, e a
#  tecla marcada F9 quase nunca manda "f9" sozinha.
#
#  Aperte as teclas que quiser testar, e ESC para sair. Ele
#  mostra o nome, o numero, e ja escreve a receita pronta para
#  a linha TECLA_DE_FALA.
#
#  Se apertar uma tecla e nao aparecer NADA, aquele comando e
#  resolvido dentro do proprio teclado e nunca chega ao
#  sistema: nao ha como usar essa tecla.
# ============================================================
cd "$(dirname "$(readlink -f "$0")")" || exit 1

PY="${PYTHON:-python3}"
exec "$PY" -X utf8 -u claude_em_voz.py --descobrir-tecla
