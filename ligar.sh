#!/usr/bin/env bash
# ============================================================
#  Liga o Claude em Voz, solto do terminal.
#
#  Rode isto e feche o terminal a vontade: o programa continua.
#
#  Ele faz as duas metades da conversa:
#    - fala as respostas novas do Claude, inclusive as
#      perguntas de escolha, com as opcoes;
#    - escreve o que voce falar (segure o Ctrl da esquerda,
#      espere o bipe, fale, e solte).
#
#  Dois bipes subindo avisam que ficou pronto.
#
#  Para desligar: ./desligar.sh
#  Deu problema?  ./diagnostico.sh , ou leia o registro.txt
# ============================================================
cd "$(dirname "$(readlink -f "$0")")" || exit 1

PY="${PYTHON:-python3}"

# setsid solta o programa do terminal: sem isso, fechar a janela levaria o
# programa junto - exatamente o tipo de morte sem explicacao que este
# projeto ja teve na versao para Windows.
setsid nohup "$PY" -X utf8 -u claude_em_voz.py > registro.txt 2>&1 &

# Nao da para conferir pelo numero do processo que acabou de sair daqui: o
# setsid entrega o programa a um filho e sai na hora, entao esse numero ja
# nao existe. Perguntamos ao sistema quem esta rodando o programa.
sleep 1
if pgrep -f "claude_em_voz\.py" >/dev/null 2>&1; then
    echo "Claude em Voz ligado."
    echo "Espere os dois bipes subindo: os reconhecedores levam alguns"
    echo "segundos para carregar, e antes disso a tecla nao responde."
else
    echo "Ele nao subiu. O motivo costuma estar nas ultimas linhas do"
    echo "registro.txt:"
    echo
    tail -n 15 registro.txt 2>/dev/null
    echo
    echo "Para uma conferencia completa:  ./diagnostico.sh"
    exit 1
fi
