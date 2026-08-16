#!/usr/bin/env bash
# ============================================================
#  Desliga o Claude em Voz, em silencio.
#
#  E esta versao que o gancho de fim de sessao chama, entao ela
#  nao pode escrever nada nem esperar tecla nenhuma: um gancho
#  que fala na tela atrapalha a saida do Claude Code.
#
#  Para desligar na mao, com resposta, use ./desligar.sh
# ============================================================
ARQUIVO_PID="${TMPDIR:-/tmp}/claude_em_voz.pid"

if [ -f "$ARQUIVO_PID" ]; then
    PID="$(cat "$ARQUIVO_PID" 2>/dev/null)"
    if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null; then
        # TERM primeiro: o programa fecha o microfone, apaga o proprio
        # numero e sai limpo. So insiste se ele nao atender.
        kill "$PID" 2>/dev/null
        for _ in 1 2 3 4 5 6 7 8 9 10; do
            kill -0 "$PID" 2>/dev/null || exit 0
            sleep 0.2
        done
        kill -9 "$PID" 2>/dev/null
        exit 0
    fi
fi

# Sem numero anotado, procuramos pelo programa. Com o caminho inteiro no
# padrao, para nunca acertar outro Python que esteja rodando na maquina.
pkill -f "claude_em_voz\.py" 2>/dev/null
exit 0
