#!/usr/bin/env bash
# ============================================================
#  Instala as bibliotecas do Python e os reconhecedores de fala.
#
#  Quer instalar TUDO de uma vez - inclusive os programas do
#  sistema e os ganchos? Use ./INSTALAR_TUDO.sh
#  Este arquivo aqui e so a parte do Python, e serve para
#  reinstalar essa parte sozinha, sem mexer no resto.
#
#  Nenhum dos dois instala o Claude Code: ele ja e seu e fica
#  como esta.
#
#  Os reconhecedores sao uns 600 MB, baixados uma vez so.
#  Depois disso o programa nunca mais precisa de internet.
# ============================================================
set -u
cd "$(dirname "$(readlink -f "$0")")" || exit 1

PY="${PYTHON:-python3}"
SEM_PAUSA="${SEM_PAUSA:-}"

echo
echo " =========================================================="
echo "  Bibliotecas e reconhecedores de fala"
echo " =========================================================="
echo

if ! command -v "$PY" >/dev/null 2>&1; then
    echo " Nao encontrei o $PY."
    echo " Instale o Python 3 pelo gerenciador de pacotes do seu Linux."
    exit 1
fi

echo " Python encontrado:"
"$PY" --version
echo

# ------------------------------------------------------------
#  As bibliotecas
# ------------------------------------------------------------
echo " > Instalando as bibliotecas..."
echo

# --user, e nao no sistema: instalar como root em cima dos pacotes da
# distribuicao e o caminho mais curto para quebrar outra coisa. Se estivermos
# dentro de um ambiente virtual, o --user nao vale e nem e preciso.
OPCOES_DO_PIP=""
if [ -z "${VIRTUAL_ENV:-}" ]; then
    OPCOES_DO_PIP="--user"
fi

if ! "$PY" -m pip install $OPCOES_DO_PIP -r requirements.txt; then
    echo
    echo " A instalacao das bibliotecas falhou."
    echo
    echo " Se a mensagem falar em 'externally-managed-environment', o seu"
    echo " Linux esta protegendo os pacotes do sistema. Dois caminhos:"
    echo
    echo "   1. Um ambiente so para este programa (recomendado):"
    echo "        $PY -m venv ~/.venv-claude-em-voz"
    echo "        source ~/.venv-claude-em-voz/bin/activate"
    echo "        ./instalar.sh"
    echo
    echo "   2. Pelo gerenciador de pacotes, se ele tiver os pacotes:"
    echo "        sudo apt install python3-numpy python3-sounddevice"
    echo
    exit 1
fi

# ------------------------------------------------------------
#  Os reconhecedores
# ------------------------------------------------------------
echo
echo " > Baixando e conferindo os reconhecedores de fala..."
echo "   Sao uns 600 MB na primeira vez. Depois disso, nunca mais."
echo

if ! "$PY" -X utf8 -u claude_em_voz.py --baixar; then
    echo
    echo " Nao consegui preparar os reconhecedores. Se ele estava baixando,"
    echo " confira a internet e rode de novo: o que ja baixou nao se perde."
    exit 1
fi

echo
echo " Bibliotecas e reconhecedores prontos."

if [ -n "$SEM_PAUSA" ]; then
    exit 0
fi

echo
echo " =========================================================="
echo "  Falta o que depende do sistema:"
echo
echo "   - o espeak (a voz) e o xdotool (para escrever na janela)"
echo "   - os quatro ganchos do Claude Code"
echo
echo "  Os dois estao explicados no INSTALAR_DO_ZERO.txt, e o"
echo "  ./INSTALAR_TUDO.sh faz tudo sozinho. Os ganchos tambem"
echo "  saem prontos com:"
echo "      $PY configurar_ganchos.py"
echo
echo "  Para conferir tudo de uma vez:  ./diagnostico.sh"
echo " =========================================================="
echo
