#!/usr/bin/env bash
# ============================================================
#  PACOTE DE INSTALACAO DO CLAUDE EM VOZ  (Linux)
#
#  Rode isto e ele instala tudo sozinho, na ordem:
#
#      1. os programas do sistema (a voz, o microfone, o xdotool)
#      2. as bibliotecas do Python
#      3. os reconhecedores de fala
#      4. os quatro ganchos, com os caminhos deste computador
#
#  O CLAUDE CODE NAO E INSTALADO AQUI, de proposito: quem vai
#  usar este programa ja tem o Claude funcionando, e reinstalar
#  por cima trocaria a versao dele e poderia estragar o que ja
#  funcionava. Este arquivo apenas confere que ele existe.
#
#  Pula sozinho o que ja estiver instalado, entao pode ser
#  rodado de novo sem medo.
#
#  A parte 1 pede a sua senha: instalar programa do sistema
#  exige permissao de administrador. As outras tres nao.
# ============================================================
set -u
cd "$(dirname "$(readlink -f "$0")")" || exit 1

PY="${PYTHON:-python3}"
FALTOU=""

echo
echo " =========================================================="
echo "                    CLAUDE EM VOZ"
echo "              pacote de instalacao completo"
echo " =========================================================="
echo
echo "   Vou instalar, um por vez:"
echo
echo "     1. os programas do sistema (voz, audio, janelas)"
echo "     2. as bibliotecas do Python"
echo "     3. os reconhecedores de fala"
echo "     4. os quatro ganchos do Claude Code"
echo
echo "   O que ja estiver instalado sera pulado."
echo "   Leva uns 10 minutos, quase tudo esperando."
echo
echo "   NAO vou mexer no seu Claude Code: voce ja o tem instalado,"
echo "   e reinstalar por cima poderia trocar a versao dele. Apenas"
echo "   confiro se ele esta ai."
echo
echo " ----------------------------------------------------------"
read -r -p "   Para comecar, aperte Enter. Para desistir, Ctrl+C. " _
echo

# ------------------------------------------------------------
#  Descobrir qual e o gerenciador de pacotes
# ------------------------------------------------------------
GERENCIADOR=""
if command -v apt-get >/dev/null 2>&1; then
    GERENCIADOR="apt"
elif command -v dnf >/dev/null 2>&1; then
    GERENCIADOR="dnf"
elif command -v pacman >/dev/null 2>&1; then
    GERENCIADOR="pacman"
elif command -v zypper >/dev/null 2>&1; then
    GERENCIADOR="zypper"
fi

instalar_pacotes() {
    case "$GERENCIADOR" in
        apt)    sudo apt-get install -y "$@" ;;
        dnf)    sudo dnf install -y "$@" ;;
        pacman) sudo pacman -S --needed --noconfirm "$@" ;;
        zypper) sudo zypper install -y "$@" ;;
        *)      return 1 ;;
    esac
}

# ------------------------------------------------------------
#  1) OS PROGRAMAS DO SISTEMA
# ------------------------------------------------------------
echo " =========================================================="
echo "  [1 de 4] Programas do sistema"
echo " =========================================================="
echo

if [ -z "$GERENCIADOR" ]; then
    echo " Nao reconheci o gerenciador de pacotes deste Linux."
    echo " Instale a mao estes tres, e rode este arquivo de novo:"
    echo "     espeak-ng      a voz"
    echo "     portaudio      o microfone (libportaudio2 no Debian/Ubuntu)"
    echo "     xdotool        escrever na janela e saber qual esta na frente"
    FALTOU="1"
else
    echo " Gerenciador de pacotes: $GERENCIADOR"
    echo " Vou pedir a sua senha para instalar os programas do sistema."
    echo

    case "$GERENCIADOR" in
        apt)    PACOTES="espeak-ng libportaudio2 xdotool" ;;
        dnf)    PACOTES="espeak-ng portaudio xdotool" ;;
        pacman) PACOTES="espeak-ng portaudio xdotool" ;;
        zypper) PACOTES="espeak-ng portaudio xdotool" ;;
    esac

    if instalar_pacotes $PACOTES; then
        echo
        echo " Instalados."
    else
        echo
        echo " Alguma coisa nao instalou. Continuo mesmo assim - o"
        echo " diagnostico no fim vai dizer exatamente o que faltou."
        FALTOU="1"
    fi
fi

# Wayland: o wtype e o unico jeito de o ditado escrever la.
if [ -n "${WAYLAND_DISPLAY:-}" ] && [ -z "${DISPLAY:-}" ]; then
    echo
    echo " Voce esta numa sessao Wayland. Vou tentar instalar o wtype,"
    echo " que e o que permite o ditado escrever nas outras janelas."
    instalar_pacotes wtype >/dev/null 2>&1 \
        && echo " wtype instalado." \
        || echo " O wtype nao esta disponivel aqui; o diagnostico explica as opcoes."
fi

# ------------------------------------------------------------
#  Conferencia: o Claude Code (nao instalamos, so olhamos)
# ------------------------------------------------------------
echo
echo " ----------------------------------------------------------"
echo "  Conferindo o Claude Code (nao vou mexer nele)"
echo " ----------------------------------------------------------"
echo

if claude --version >/dev/null 2>&1; then
    echo " Encontrado:"
    claude --version
else
    echo " Nao encontrei o comando claude neste terminal."
    echo
    echo " Se voce ja usa o Claude Code, provavelmente e so isto: a"
    echo " pasta dele nao esta no PATH deste terminal. Confira com"
    echo "     claude --version"
    echo
    echo " Nao vou instalar nem atualizar o Claude por aqui, para nao"
    echo " mexer numa instalacao que ja funciona. Sem ele, o resto"
    echo " instala normalmente, mas nao havera com quem falar."
    FALTOU="1"
fi

# ------------------------------------------------------------
#  2 e 3) BIBLIOTECAS E RECONHECEDORES
# ------------------------------------------------------------
echo
echo " =========================================================="
echo "  [2 e 3 de 4] Bibliotecas e reconhecedores de fala"
echo " =========================================================="

if ! SEM_PAUSA=1 ./instalar.sh; then
    echo
    echo " A instalacao das bibliotecas nao terminou. Resolva o que"
    echo " ele apontou e rode este arquivo de novo - ele pula o que"
    echo " ja estiver pronto."
    exit 1
fi

# ------------------------------------------------------------
#  4) OS GANCHOS
# ------------------------------------------------------------
echo
echo " =========================================================="
echo "  [4 de 4] Ganchos do Claude Code"
echo " =========================================================="
echo
echo " Sao eles que ligam e desligam o programa junto com o Claude,"
echo " e que fazem as perguntas de escolha serem faladas na hora."
echo

chmod +x ./*.sh 2>/dev/null

if ! "$PY" -X utf8 configurar_ganchos.py; then
    echo
    echo " Nao consegui escrever os ganchos. O passo a passo para"
    echo " faze-lo a mao esta no INSTALAR_DO_ZERO.txt, PASSO 6."
    FALTOU="1"
fi

# ------------------------------------------------------------
#  CONFERENCIA FINAL
# ------------------------------------------------------------
echo
echo " =========================================================="
echo "  Conferindo"
echo " =========================================================="
echo

# A bateria de testes vale como prova da instalacao: ela so passa inteira se
# as bibliotecas estiverem no lugar e o programa carregar.
if "$PY" -X utf8 testes/testar.py >/dev/null 2>&1; then
    echo " [x] Programa conferido: a bateria de testes passou inteira."
else
    echo " [!] A bateria de testes acusou alguma coisa."
    echo "     Nao impede de usar, mas vale olhar. Rode ./testar.sh"
fi

echo
echo " Agora a conferencia completa, que fala em voz alta o que"
echo " encontrou:"
echo
"$PY" -X utf8 -u claude_em_voz.py --diagnostico || FALTOU="1"

echo
echo " =========================================================="
if [ -n "$FALTOU" ]; then
    echo "  QUASE LA. Resolva os itens marcados acima."
else
    echo "  PRONTO. Esta tudo instalado."
fi
echo " =========================================================="
echo
echo "   Para experimentar agora:"
echo
echo "     1. Feche o Claude Code, se estiver aberto, e abra de"
echo "        novo. Ele deve falar \"Claude em voz iniciado\"."
echo "     2. Pergunte qualquer coisa: a resposta e lida em voz alta."
echo "     3. Para ditar, clique na janela do Claude, SEGURE o Ctrl"
echo "        da esquerda, espere o bipe, fale, e solte a tecla."
echo
echo "   Duvidas: COMO_USAR.txt (o dia a dia) e"
echo "            PERGUNTAS_E_RESPOSTAS.txt (o porque de cada coisa)."
echo
