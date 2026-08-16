#!/usr/bin/env bash
# ============================================================
#  Desliga o Claude em Voz e diz o que aconteceu.
#
#  E o mesmo que o parar.sh faz, mas falando na tela. O outro
#  existe calado porque e chamado por um gancho, e gancho nao
#  pode escrever na tela do Claude Code.
# ============================================================
cd "$(dirname "$(readlink -f "$0")")" || exit 1

if ! pgrep -f "claude_em_voz\.py" >/dev/null 2>&1; then
    echo "O Claude em Voz nao estava rodando."
    exit 0
fi

./parar.sh

sleep 0.5
if pgrep -f "claude_em_voz\.py" >/dev/null 2>&1; then
    echo "Ele resistiu ao pedido de encerrar. Ainda esta rodando."
    exit 1
fi

echo "Claude em Voz desligado."
echo "Ele volta sozinho na proxima vez que voce abrir o Claude Code,"
echo "ou agora mesmo com  ./ligar.sh"
