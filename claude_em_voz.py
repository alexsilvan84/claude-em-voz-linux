# -*- coding: utf-8 -*-
"""
=============================================================================
 CLAUDE EM VOZ  -  conversa por voz com o Claude Code, 100% local e offline
=============================================================================

Um programa so, com as duas metades da conversa:

    OUVIR   o Claude fala as respostas novas em voz alta, inclusive as
            perguntas de multipla escolha, com as opcoes, assim que elas
            aparecem - e nao so depois de voce escolher.

    FALAR   voce segura o Ctrl da esquerda, espera o bipe, fala, e solta.
            As palavras vao sendo escritas na janela do Claude enquanto
            voce ainda esta falando, como a digitacao por voz do celular.

Ele nunca aperta Enter sozinho: a frase fica na linha esperando voce ler e
enviar. Ditado erra, e mandar sozinho seria pedir para o Claude executar
uma frase errada.

Como as duas metades convivem:
    - A leitura em voz alta espera a sua fala terminar. Sem isso as duas
      vozes se atropelariam, e o microfone ouviria o proprio leitor.
    - A voz e uma so, numa fila unica: respostas, perguntas e avisos saem
      na ordem, nunca por cima uns dos outros.
    - Nada de escutar o tempo todo: fosse assim, o microfone captaria a
      voz do leitor e transcreveria o Claude para dentro do Claude.

Esta e a versao para LINUX. A irma dela, para Windows, fica em ClaudeEmVoz.
As duas fazem a mesma coisa e compartilham toda a logica; o que muda e a
camada de baixo, e ela esta reunida na secao "O SISTEMA" para nao ficar
espalhada pelo programa:

    falar        espeak-ng, ou o piper, ou o speech-dispatcher
    digitar      xdotool (X11), wtype ou ydotool (Wayland), ou o pynput
    janelas      xdotool
    bipe         um tom gerado na hora e tocado pela placa de som
    instancia    trava de arquivo (flock), que o sistema solta sozinho

Por dentro, em uma linha cada:
    - As conversas ficam em .claude/projects/<projeto>/<sessao>.jsonl, uma
      linha por mensagem; so as linhas "assistant" interessam, e delas so o
      texto explicativo e as perguntas de escolha.
    - A leitura dos arquivos e incremental, estilo "tail -f": o historico
      antigo nunca e relido.
    - O ditado transcreve a fala em andamento a cada instante e so escreve
      as palavras que se repetiram em duas passadas seguidas; ao soltar a
      tecla, um reconhecedor melhor rele tudo e corrige o que saiu errado.

Requisitos:
    pip install faster-whisper sounddevice numpy pynput
    e, pelo gerenciador de pacotes do seu Linux:
        espeak-ng          a voz
        espeak-ng-data     a voz em portugues do Brasil (as vezes ja vem junto)
        portaudio          para o microfone (libportaudio2 no Debian/Ubuntu)
        xdotool            para escrever na janela e saber qual esta na frente

    Instalando num computador novo? A receita completa esta em
    INSTALAR_DO_ZERO.txt, e o instalar.sh faz tudo sozinho.

Uso:
    ./ligar.sh       liga tudo, sem terminal preso
    ./desligar.sh    desliga

    Pelo terminal, para diagnosticar:
        python3 claude_em_voz.py                 liga mostrando tudo
        python3 claude_em_voz.py --diagnostico   confere tudo e DIZ o resultado
        python3 claude_em_voz.py --teste-voz     fala tres frases
        python3 claude_em_voz.py --teste-pronuncia  ouve a tabela de pronuncia
        python3 claude_em_voz.py --vozes         lista as vozes instaladas
        python3 claude_em_voz.py --teste-ditado  grava 5s e so mostra o texto
        python3 claude_em_voz.py --dispositivos  lista os microfones
        python3 claude_em_voz.py --descobrir-tecla  mostra o que cada tecla manda
        python3 claude_em_voz.py --baixar        so baixa os reconhecedores
        python3 claude_em_voz.py --so-leitor     liga so a metade que fala
        python3 claude_em_voz.py --so-ditado     liga so a metade que escreve
=============================================================================
"""

import os
import re
import sys
import json
import math
import time
import queue
import atexit
import tempfile
import threading
import collections


ARQUIVO_REGISTRO = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "registro.txt"
)


def preparar_saida():
    """
    Deixa impressao de texto inofensiva, aconteca o que acontecer.

    Normalmente este programa roda solto, sem terminal preso a ele - e a
    unica forma de nao depender de uma janela que alguem fecha sem querer,
    derrubando tudo junto. Sem terminal a saida de texto pode nao existir, e
    um print comum levantaria erro; como as threads imprimem antes de falar
    e de escrever, esse erro mataria a thread e o programa ficaria ligado
    porem inutil. Entao a saida vai para um arquivo, refeito a cada partida.
    """
    if getattr(sys, "stdout", None) is None or getattr(sys, "stderr", None) is None:
        try:
            registro = open(ARQUIVO_REGISTRO, "w", encoding="utf-8",
                            errors="replace", buffering=1)
        except OSError:
            try:
                registro = open(os.devnull, "w", encoding="utf-8")
            except OSError:
                return
        sys.stdout = registro
        sys.stderr = registro
        return

    for nome in ("stdout", "stderr"):
        try:
            getattr(sys, nome).reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError, ValueError):
            pass


preparar_saida()

try:
    import numpy as np
    import sounddevice as sd
    from pynput import keyboard
    from faster_whisper import WhisperModel
except ImportError as erro:
    print("Falta uma biblioteca:", erro)
    print("Instale tudo com:")
    print("    pip install faster-whisper sounddevice numpy pynput")
    print()
    print("Se o erro falar em PortAudio, o que falta nao e do Python: e a")
    print("biblioteca de audio do sistema. No Debian ou Ubuntu:")
    print("    sudo apt install libportaudio2")
    sys.exit(1)


# =============================================================================
# CONFIGURACOES
# =============================================================================

# ---------- a metade que FALA (leitura das respostas) ----------

# Velocidade em palavras por minuto. O espeak entende esse numero direto;
# o padrao dele e 175, e 230 e um pouco mais rapido que a fala comum.
VELOCIDADE = 230
VOLUME = 1.0              # 0.0 a 1.0
INTERVALO = 0.6           # de quantos em quantos segundos checar os arquivos

# A voz do espeak. "pt-br" e o portugues do Brasil; "pt" e o de Portugal.
# Para ver todas:  espeak-ng --voices=pt
VOZ_DO_ESPEAK = "pt-br"

# Voz neural, muito mais natural que a do espeak - e o unico jeito de ouvir
# respostas longas sem cansar. Nao vem em nenhuma distribuicao: e preciso
# instalar o piper e baixar um modelo em portugues. Enquanto isto for uma
# string vazia, o programa usa o espeak.
#
# Para ter: instale o piper (pip install piper-tts) e baixe um modelo pt-BR
# em https://huggingface.co/rhasspy/piper-voices/tree/main/pt/pt_BR
# Depois aponte o arquivo .onnx aqui. Exemplo:
#     MODELO_DO_PIPER = os.path.expanduser("~/vozes/pt_BR-faber-medium.onnx")
MODELO_DO_PIPER = ""

# Ler tambem as perguntas de multipla escolha, com as opcoes. Sem isto o
# leitor fica mudo justamente na hora de decidir, que e quando ouvir mais
# ajuda.
LER_PERGUNTAS = True
LER_DESCRICAO_DAS_OPCOES = True

# Caixa de entrada das perguntas, preenchida por um gancho do Claude Code.
#
# Ela existe porque o arquivo da conversa chega TARDE: a pergunta so e
# gravada la depois que voce escolhe. Vigiando so aquele arquivo, o programa
# lia a pergunta quando ela ja nao servia mais de nada.
#
# O gancho "PreToolUse" dispara ANTES de a pergunta ser mostrada na tela e
# despeja o conteudo dela aqui; o programa le e fala na hora. Instrucoes de
# como instalar o gancho estao no PERGUNTAS_E_RESPOSTAS.txt.
ARQUIVO_DE_PERGUNTAS = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "perguntas_pendentes.jsonl"
)

# Como falar as palavras que a voz brasileira leria errado.
#
# A voz do sistema le tudo com sotaque de portugues, e as respostas do Claude
# vem cheias de termo em ingles. "Claude" saia "clau-de", "PowerShell" saia
# soletrado - e uma palavra lida errado no meio da frase custa mais atencao
# do que parece: quem ouve para para decifrar e perde o resto.
#
# A troca e so na hora de FALAR. O texto na tela e o registro continuam
# escritos do jeito certo.
#
# Para acrescentar, escreva a palavra do jeito que se ESCREVE de um lado, e do
# jeito que se PRONUNCIA em portugues do outro. Depois ouca com:
#     python claude_em_voz.py --teste-pronuncia
# Ouvido e o unico juiz aqui: se ficar estranho, mude a grafia da direita.
PRONUNCIAS = {
    "Claude Code": "Clôd Côud",
    "Claude": "Clôd",
    "Anthropic": "Antrópic",
    "PowerShell": "páuer chél",
    "Python": "páiton",
    "GitHub": "guit rábi",
    "Git": "guit",
    "bash": "béch",
    "JSON": "jêissón",
    "markdown": "márk dáun",
    "commit": "cómit",
    "deploy": "diplói",
    "backup": "béquiap",
    "software": "sófit uér",
    "hardware": "rárd uér",
    "cache": "quéchi",
    "Whisper": "uísper",
    "Windows": "uíndous",
    "byte": "báite",
    "bytes": "báites",
}

# Ouvir so as conversas de uma pasta (parte do nome). None = todas.
FILTRAR_PROJETO = None

# Nao ler respostas absurdamente longas por inteiro (0 = sem limite).
LIMITE_CARACTERES = 0

# Frase falada assim que o programa liga.
FRASE_DE_ABERTURA = "Claude em voz iniciado."

# ---------- a metade que ESCREVE (ditado) ----------

# Tecla que aciona o ditado. Use um nome do pynput ("ctrl_l", "f9", "f8",
# "scroll_lock", "pause") ou o numero cru da tecla ("vk:120").
# Nao sabe qual e a sua? Rode:  ./descobrir_tecla.sh
#
# O padrao e o Ctrl da ESQUERDA, e nao o F9, por um motivo medido neste
# notebook: a tecla marcada F9, apertada sozinha, nao manda F9 nenhum - ela
# manda Windows+L, o atalho de bloquear a tela, que o Windows trata num nivel
# que nenhum programa comum alcanca. So com o Fn junto ela vira F9, e ai sao
# duas maos. Este teclado tambem nao tem Ctrl da direita.
TECLA_DE_FALA = "ctrl_l"

# "segurar"  -> grava enquanto a tecla estiver pressionada (padrao). O gesto
#               completo fica: segure, espere o bipe, fale, solte.
# "alternar" -> um toque comeca, outro toque termina.
MODO_DE_ESCUTA = "segurar"

# Quanto tempo a tecla precisa ficar apertada, SOZINHA, para acionar.
# E o que permite usar o Ctrl sem atrapalhar nada: ninguem segura o Ctrl por
# tres segundos num Ctrl+C. Se outra tecla chegar nesse meio tempo, a
# contagem morre na hora e o atalho acontece normalmente.
SEGUNDOS_PARA_ACIONAR = 3.0

# Modelo usado AO VIVO, enquanto voce fala. Precisa ser rapido, nao certeiro.
# Medido aqui: "tiny" leva 0,45 s por passada e "base" leva 1,1 s.
MODELO_AO_VIVO = "base"

# Modelo que rele tudo e corrige quando a fala termina. Aqui vale o
# contrario: pode ser lento, tem que acertar. "small" leva ~3,9 s.
# None desliga a revisao.
MODELO_FINAL = "small"

# De quantos em quantos segundos reprocessar a fala em andamento.
CADENCIA = 0.7

# Nucleos usados no reconhecimento. Medido nesta maquina de 8 nucleos: 4 e o
# melhor; com 8 fica MAIS lento, porque as passadas brigam pela memoria.
FIOS_DO_PROCESSADOR = 4

IDIOMA = "pt"

# Palavras que o reconhecedor deve esperar ouvir.
#
# Um reconhecedor pequeno erra justamente o que nao e portugues corrente:
# nome de programa, termo tecnico, nome de arquivo. Esta lista e entregue a
# ele como pista antes de cada transcricao - ele passa a preferir estas
# grafias quando o som for parecido.
#
# E a mesma vantagem que o ditado da propria Anthropic tem sobre este, e que
# a documentacao reconhece: la o servidor conhece vocabulario de programacao.
# Aqui a lista e sua, e por isso pode ser melhor: ponha o que VOCE fala.
#
# Nao exagere. Lista comprida dilui a dica e o reconhecedor comeca a enxergar
# essas palavras onde elas nao estao - vinte ou trinta termos e o ponto certo.
# Lista vazia desliga a dica.
VOCABULARIO = [
    "Claude", "Claude Code", "Anthropic",
    "Python", "PowerShell", "Git", "GitHub", "bash",
    "gancho", "ganchos", "ditado", "interruptor", "reconhecedor",
    "diagnóstico", "vocabulário", "pronúncia",
    "arquivo bat", "pasta", "registro", "histórico",
    "markdown", "commit", "backup",
]

# O reconhecedor recebe a lista como um texto so.
DICA_DE_VOCABULARIO = ", ".join(VOCABULARIO)

# Escrever na janela que estava na frente quando a fala comecou, e trazer
# essa janela de volta se voce tiver clicado em outra no meio.
ESCREVER_NA_TELA = True
DEVOLVER_O_FOCO = True

# Por qual caminho o texto e digitado. "auto" decide sozinho conforme a sua
# area de trabalho; os outros valores forcam um deles, para quando o
# automatico errar: "pynput", "xdotool", "wtype", "ydotool".
COMO_ESCREVER = "auto"

# Preferir o xdotool ao pynput no X11. Vale tentar se o texto sair
# incompleto, ou nao sair, em algum programa que filtre teclas sinteticas.
PREFERIR_XDOTOOL = False

# So obedecer a tecla quando o Claude Code estiver na frente. Em qualquer
# outro programa ela volta a ser o que sempre foi.
SO_NO_CLAUDE = True

# Como reconhecer o Claude Code entre os processos. No Linux ele costuma
# rodar como "node" com o caminho do claude na linha de comando, e nao como
# um programa de nome proprio - por isso a procura olha tambem a linha de
# comando, e nao so o nome.
PROGRAMAS_DO_CLAUDE = ["claude"]
PROGRAMAS_DE_TERMINAL = [
    "bash", "sh", "zsh", "fish", "dash", "tmux", "screen",
    "gnome-terminal-", "konsole", "xterm", "alacritty", "kitty", "wezterm",
    "wezterm-gui", "terminator", "tilix", "xfce4-terminal", "lxterminal",
    "mate-terminal", "urxvt", "rxvt", "st", "foot", "ptyxis", "guake",
    "code", "codium", "node",
]
TITULOS_DO_CLAUDE = []

# Guardar tudo o que voce ditar num arquivo, ao lado deste programa.
GUARDAR_HISTORICO = True
ARQUIVO_HISTORICO = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "historico_de_voz.txt"
)

# Tempo maximo de uma fala, contra tecla travada ou esquecida.
LIMITE_DE_SEGUNDOS = 300

# Fala mais curta que isso e considerada aperto sem querer.
MINIMO_DE_SEGUNDOS = 0.35

# Guarda esta fracao de segundo ANTERIOR ao bipe, para nao perder o comeco
# de quem comeca a falar junto com o sinal.
PRE_ROLL = 0.35

# Volume abaixo disto e silencio. Medido nesta maquina: sala em silencio bate
# 0,011 e fala normal passa de 0,1. Se ele disser "so silencio" quando voce
# falou, baixe este numero.
VOLUME_MINIMO = 0.02

# ---------- avisos ----------

# Bipes curtos quando a gravacao comeca e termina.
AVISO_SONORO = True

# Lembrete de como usar, falado e numa faixa na tela. Acontece ao ligar e
# toda vez que um Claude Code novo e aberto.
AVISO_FALADO = True
AVISO_NA_TELA = True
SEGUNDOS_DO_AVISO = 7
FRASE_DO_LEMBRETE = ("Para digitar por voz, segure o Control da esquerda. "
                     "Depois do bipe, fale, e solte a tecla quando terminar.")
FRASE_NA_TELA = ("Digitar por voz: segure o Ctrl da esquerda, espere o bipe,\n"
                 "fale, e solte a tecla para terminar")
INTERVALO_DA_RONDA = 3.0

# Mostrar no terminal (ou no registro) o que esta sendo falado e escrito.
MOSTRAR_NO_TERMINAL = True

# Numero do microfone (veja com --dispositivos). None = o padrao do sistema.
MICROFONE = None

# O Whisper inventa frases de legenda quando recebe silencio.
FRASES_INVENTADAS = [
    "legendas pela comunidade amara.org",
    "legendas pela comunidade",
    "amara.org",
    "obrigado por assistir",
    "obrigado por assistirem",
    "inscreva-se no canal",
    "ate o proximo video",
    "subtitles by",
]

TAXA = 16000        # o Whisper trabalha em 16 kHz


# =============================================================================
# 0) INSTANCIA UNICA
# =============================================================================

ARQUIVO_DO_CADEADO = os.path.join(tempfile.gettempdir(), "claude_em_voz.trava")
ARQUIVO_PID = os.path.join(tempfile.gettempdir(), "claude_em_voz.pid")

# Global so para o cadeado viver enquanto o programa viver: fechado o arquivo,
# a trava se solta.
_cadeado = None


def ja_esta_rodando():
    """
    Ha outra copia no ar? Uma trava de arquivo responde.

    E flock, e nao "existe um arquivo de trava?". A diferenca importa: a trava
    do flock e do PROCESSO, e o proprio sistema a solta quando ele termina -
    inclusive se for morto a forca, e inclusive se o computador desligar no
    tombo. Um arquivo comum ficaria para tras nesse caso, e o programa nunca
    mais ligaria, dizendo que ja esta rodando.
    """
    global _cadeado
    try:
        import fcntl
        _cadeado = open(ARQUIVO_DO_CADEADO, "w")
        try:
            fcntl.flock(_cadeado, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            _cadeado.close()
            _cadeado = None
            return True         # a trava e de outro: ele chegou primeiro
        return False
    except Exception:
        # Sem trava, o pior que acontece e subirem dois. Melhor isso do que
        # nao subir nenhum por causa da conferencia.
        return False


def registrar_pid():
    try:
        with open(ARQUIVO_PID, "w", encoding="utf-8") as f:
            f.write(str(os.getpid()))
        atexit.register(apagar_pid)
    except OSError:
        pass


def apagar_pid():
    try:
        os.remove(ARQUIVO_PID)
    except OSError:
        pass


def bipar(frequencia, duracao_ms):
    """
    Toca um bipe sem segurar o programa.

    O tom e gerado na hora e tocado pela mesma biblioteca que grava o
    microfone - a que ja esta instalada. Foi o caminho escolhido para nao
    depender de mais um programa de fora so para fazer bipe: nem todo Linux
    tem beep, nem todo terminal deixa o caractere de campainha soar, e o
    alto-falante do gabinete costuma estar desligado nas maquinas novas.

    Numa thread propria porque tocar segura quem toca, e esperar pelo bipe
    antes de gravar comeria o comeco da fala.
    """
    if not AVISO_SONORO:
        return

    def tocar():
        try:
            duracao = duracao_ms / 1000.0
            tempo = np.linspace(0, duracao, int(TAXA * duracao), endpoint=False)
            onda = 0.25 * np.sin(2 * np.pi * frequencia * tempo)

            # Sobe e desce o volume nas pontas: sem isso o corte seco do sinal
            # sai como um estalo, mais alto que o proprio bipe.
            beirada = max(1, int(0.008 * TAXA))
            rampa = np.linspace(0.0, 1.0, beirada)
            onda[:beirada] *= rampa
            onda[-beirada:] *= rampa[::-1]

            sd.play(onda.astype(np.float32), TAXA)
            sd.wait()
        except Exception:
            pass

    threading.Thread(target=tocar, daemon=True).start()


# =============================================================================
# 1) ESTADO COMPARTILHADO ENTRE AS DUAS METADES
# =============================================================================

# Ligado enquanto voce esta ditando. A leitura em voz alta espera este sinal
# baixar: as duas vozes se atropelariam, e o microfone ouviria o leitor.
_gravando = threading.Event()

# Ligado enquanto o programa esta digitando. Serve para nao confundir as
# proprias teclas com as suas.
_estamos_escrevendo = threading.Event()

# Ligado enquanto a tecla de falar esta fisicamente apertada.
_tecla_presa = threading.Event()

# As duas metades podem ser desligadas em separado, sem fechar o programa:
# as vezes voce quer so ler em paz, sem ninguem falando, e as vezes so
# escutar, sem correr o risco de a tecla disparar no meio de outra coisa.
# Comecam sempre ligadas - ver VigiaDoInterruptor, logo abaixo.
_leitura_ligada = threading.Event()
_ditado_ligado = threading.Event()
_leitura_ligada.set()
_ditado_ligado.set()


# =============================================================================
# 1b) O INTERRUPTOR  -  ligar e desligar cada metade sem fechar o programa
# =============================================================================
#
# Voce digita  voz 1  na janela do Claude Code e a leitura para. Quem escuta
# o que voce digita e o gancho UserPromptSubmit, que chama o comando_de_voz.py:
# ele nao deixa a linha chegar ao Claude (nao vira pergunta, nao gasta nada) e
# anota a escolha AQUI, neste arquivo. Este programa apenas o vigia.
#
# Um arquivo, e nao um recado direto, porque sao dois processos diferentes: o
# gancho nasce e morre a cada linha que voce digita, e nao tem como falar com
# quem ja esta rodando. Arquivo os dois enxergam.
#
# Na partida ele e REESCRITO com tudo ligado, de proposito: desligar vale para
# o momento, e abrir o Claude de novo devolve o programa inteiro. Foi a escolha
# do usuario, e evita o pior caso - alguem desliga, esquece, e meses depois
# acha que o programa quebrou.

ARQUIVO_DO_INTERRUPTOR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "interruptor.json"
)

INTERVALO_DO_INTERRUPTOR = 0.3

# A ultima resposta lida em voz alta, guardada para o "ler de novo".
#
# Existe por um caso real: a pessoa sai da sala esperando a resposta, o
# programa le para ninguem, e quando ela volta nao ha mais como ouvir. O
# texto ja passou; sem guardar, so restaria pedir ao Claude que repetisse,
# gastando outra resposta para dizer o mesmo.
_ultima_resposta = ""


def guardar_para_repetir(texto):
    """
    So respostas do Claude entram aqui.

    Avisos do programa - "leitura desligada", o lembrete da tecla, a frase de
    abertura - ficam de fora de proposito: repetir tem que devolver o que voce
    perdeu, e nao o ultimo ruido que o programa fez sozinho.
    """
    global _ultima_resposta
    if texto and texto.strip():
        _ultima_resposta = texto


def enfileirar_resposta(fila, texto):
    guardar_para_repetir(texto)
    fila.put(texto)


def escrever_interruptor(leitura, ditado, repeticoes=0):
    """Anota a escolha em disco. Devolve se conseguiu."""
    try:
        with open(ARQUIVO_DO_INTERRUPTOR, "w", encoding="utf-8") as arquivo:
            json.dump({"leitura": bool(leitura), "ditado": bool(ditado),
                       "repetir": int(repeticoes)},
                      arquivo, ensure_ascii=False)
        return True
    except OSError:
        return False


def ler_interruptor():
    """
    Devolve (leitura, ditado, repeticoes), ou None se nao der para ler.

    Arquivo pela metade nao e erro: o gancho pode estar escrevendo neste
    exato instante. Nesse caso devolvemos None e a proxima volta le de novo -
    trezentos milissegundos depois, ja inteiro.

    "repetir" e um contador, e nao um sim ou nao: pedir para repetir duas
    vezes seguidas tem que valer duas vezes, e um sim ficaria indistinguivel
    do sim anterior.
    """
    try:
        with open(ARQUIVO_DO_INTERRUPTOR, "r", encoding="utf-8") as arquivo:
            dados = json.load(arquivo)
    except (OSError, ValueError):
        return None
    if not isinstance(dados, dict):
        return None
    try:
        repeticoes = int(dados.get("repetir", 0))
    except (TypeError, ValueError):
        repeticoes = 0
    return (bool(dados.get("leitura", True)),
            bool(dados.get("ditado", True)),
            repeticoes)


class VigiaDoInterruptor(object):
    """
    Fica de olho no arquivo do interruptor e aplica o que voce escolheu.

    Ele tambem AVISA por voz o que mudou - menos quando o que foi desligado
    e justamente a leitura, ai o aviso e o proprio silencio. Ligar de volta
    sempre fala, senao voce nao teria como saber que voltou.
    """

    def __init__(self, fila_da_voz, parar, controle_do_ditado=None):
        self.fila = fila_da_voz
        self.parar = parar
        self.controle = controle_do_ditado
        self.marca = None
        self.repeticoes = None

    def rodar(self):
        while not self.parar.is_set():
            time.sleep(INTERVALO_DO_INTERRUPTOR)
            try:
                marca = os.path.getmtime(ARQUIVO_DO_INTERRUPTOR)
            except OSError:
                continue
            if marca == self.marca:
                continue

            estado = ler_interruptor()
            if estado is None:
                continue        # escrita pela metade; tentamos na proxima
            self.marca = marca
            leitura, ditado, repeticoes = estado

            self.aplicar(leitura, ditado)

            # Na primeira volta so anotamos onde o contador esta. Sem isso o
            # programa comecaria repetindo sozinho a resposta anterior.
            if self.repeticoes is None:
                self.repeticoes = repeticoes
            elif repeticoes != self.repeticoes:
                self.repeticoes = repeticoes
                self.repetir()

    def repetir(self):
        if self.fila is None:
            return
        if _ultima_resposta:
            if MOSTRAR_NO_TERMINAL:
                try:
                    print("\n[repetir] lendo a ultima resposta de novo.")
                except Exception:
                    pass
            # Entra como resposta comum: pode ser interrompida, e nao
            # atropela o que estiver sendo falado agora.
            self.fila.put(_ultima_resposta)
        else:
            self.anunciar("Ainda nao li nenhuma resposta desde que liguei.")

    # O que ele diz em cada caso. Duas metades mudando de uma vez viram UMA
    # frase, e nao duas seguidas: "leitura desligada, ditado desligado" e
    # justamente o tipo de despejo que este programa existe para evitar.
    AVISOS = {
        (True, None): "Leitura em voz alta ligada.",
        (False, None): "Leitura em voz alta desligada.",
        (None, True): "Ditado ligado. Segure a tecla para falar.",
        (None, False): "Ditado desligado.",
        (True, True): "Leitura e ditado ligados.",
        (False, False): "Leitura e ditado desligados.",
    }

    def aplicar(self, leitura, ditado):
        antes_leitura = _leitura_ligada.is_set()
        antes_ditado = _ditado_ligado.is_set()

        mudou_leitura = leitura != antes_leitura
        mudou_ditado = ditado != antes_ditado
        if not mudou_leitura and not mudou_ditado:
            return

        if mudou_leitura:
            if leitura:
                _leitura_ligada.set()
            else:
                _leitura_ligada.clear()
                # Antes do aviso, senao ele proprio seria jogado fora junto.
                self.esvaziar_a_fila()
            self.mostrar("leitura em voz alta", leitura)

        if mudou_ditado:
            if ditado:
                _ditado_ligado.set()
            else:
                _ditado_ligado.clear()
                # Se voce desligou no meio de uma fala, ela termina agora.
                if self.controle is not None and self.controle.ativo:
                    try:
                        self.controle.parar()
                    except Exception:
                        pass
            self.mostrar("ditado", ditado)

        # A confirmacao falada e o que separa "ele obedeceu" de "ele quebrou".
        # Desligar a leitura sem dizer nada deixaria voce diante de um silencio
        # de significado duvidoso; assim, a ultima coisa que se ouve e o aviso
        # de que ele vai calar. Ela sai mesmo com a leitura ja desligada, e
        # nao pode ser interrompida - por isso vai marcada.
        #
        # Excecao: leitura desligada antes E depois. Ai voce ja esta em
        # silencio por escolha propria, e mexer so no ditado nao e motivo
        # para quebra-lo.
        if not antes_leitura and not leitura:
            return

        chave = (leitura if mudou_leitura else None,
                 ditado if mudou_ditado else None)
        self.anunciar(self.AVISOS.get(chave, ""))

    def esvaziar_a_fila(self):
        """
        Joga fora o que estava esperando para ser falado.

        Sem isto, desligar a leitura no meio de uma resposta comprida so
        adiantaria o problema: ele calaria agora e despejaria tudo depois,
        ao ser religado.
        """
        if self.fila is None:
            return
        while True:
            try:
                self.fila.get_nowait()
            except queue.Empty:
                return
            else:
                self.fila.task_done()

    def anunciar(self, frase):
        """
        Diz o que mudou, mesmo com a leitura ja desligada.

        Vai marcado com "fale de qualquer jeito" porque e exatamente a frase
        que precisa atravessar o desligamento: e ela que transforma o silencio
        seguinte em resposta ao seu pedido, e nao em suspeita de defeito.
        """
        if frase and self.fila is not None:
            self.fila.put((frase, True))

    @staticmethod
    def mostrar(nome, ligado):
        if not MOSTRAR_NO_TERMINAL:
            return
        try:
            print("\n[interruptor] %s: %s" % (nome, "ligada" if ligado else "desligada"))
        except Exception:
            pass


# =============================================================================
# 2) A METADE QUE FALA  -  onde estao as conversas
# =============================================================================

def achar_pasta_sessoes():
    """Devolve a pasta onde o Claude Code guarda as conversas."""
    candidatos = []

    casa = os.environ.get("HOME") or os.path.expanduser("~")
    candidatos.append(os.path.join(casa, ".claude", "projects"))

    config = os.environ.get("CLAUDE_CONFIG_DIR")
    if config:
        candidatos.append(os.path.join(config, "projects"))

    # Quem segue o padrao de pastas do XDG pode ter mandado para ca.
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        candidatos.append(os.path.join(xdg, "claude", "projects"))

    for caminho in candidatos:
        if os.path.isdir(caminho):
            return caminho
    return None


def listar_sessoes(pasta):
    """Todos os arquivos de conversa, varrendo as subpastas de projeto."""
    encontrados = []
    try:
        for projeto in os.listdir(pasta):
            if FILTRAR_PROJETO and FILTRAR_PROJETO.lower() not in projeto.lower():
                continue
            sub = os.path.join(pasta, projeto)
            if not os.path.isdir(sub):
                continue
            try:
                for arquivo in os.listdir(sub):
                    if arquivo.endswith(".jsonl"):
                        encontrados.append(os.path.join(sub, arquivo))
            except OSError:
                continue
    except OSError:
        pass
    return encontrados


# =============================================================================
# 3) A METADE QUE FALA  -  limpeza do texto
# =============================================================================

RE_BLOCO_CODIGO = re.compile(r"(?:```|~~~).*?(?:```|~~~|\Z)", re.S)
RE_LINHA_INDENTADA = re.compile(r"^(?: {4,}|\t).*$", re.M)
RE_TAG_SISTEMA = re.compile(r"<([a-z-]+)>.*?</\1>", re.S | re.I)
RE_LINK = re.compile(r"\[([^\]\n]+)\]\([^)\n]*\)")
RE_IMAGEM = re.compile(r"!\[[^\]\n]*\]\([^)\n]*\)")
RE_CODIGO_INLINE = re.compile(r"`([^`\n]+)`")
RE_TITULO = re.compile(r"^\s{0,3}#{1,6}\s*", re.M)
RE_LISTA = re.compile(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)", re.M)
RE_CITACAO = re.compile(r"^\s*>+\s?", re.M)
RE_LINHA_HORIZONTAL = re.compile(r"^\s*(?:-{3,}|\*{3,}|_{3,})\s*$", re.M)
RE_TABELA = re.compile(r"^\s*\|.*\|\s*$", re.M)
RE_ENFASE = re.compile(r"(\*\*|__|\*|_|~~)")
RE_HTML = re.compile(r"<[^>\n]{1,80}>")
RE_EMOJI = re.compile(
    "[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF←-⇿⬀-⯿]"
)
RE_CAMINHO = re.compile(r"(?:[A-Za-z]:[\\/][^\s`\"']{3,}|(?:\./|/)[\w./-]{6,})")
RE_ESPACOS = re.compile(r"[ \t]{2,}")
RE_QUEBRAS = re.compile(r"\n{2,}")


def encurtar_caminho(achado):
    """De um caminho inteiro, so o nome final - a unica parte util de ouvir."""
    caminho = achado.group(0).rstrip(".,;:)")
    nome = re.split(r"[\\/]", caminho)[-1]
    return nome if nome else " "


def _montar_regex_das_pronuncias():
    """
    Uma expressao so para todas as trocas de pronuncia.

    Do termo mais longo para o mais curto, senao "Claude" casaria antes e
    "Claude Code" nunca seria alcancado. As bordas de palavra evitam o
    estrago classico: sem elas, "Git" seria trocado dentro de "GitHub", e o
    nome de arquivo claude_em_voz sairia com pedaco em ingles no meio.
    """
    if not PRONUNCIAS:
        return None
    termos = sorted(PRONUNCIAS, key=len, reverse=True)
    return re.compile(r"\b(?:%s)\b" % "|".join(re.escape(t) for t in termos),
                      re.IGNORECASE)


RE_PRONUNCIAS = _montar_regex_das_pronuncias()
_PRONUNCIAS_MINUSCULAS = {termo.lower(): fala
                          for termo, fala in PRONUNCIAS.items()}


def ajustar_pronuncia(texto):
    """Troca os termos que a voz brasileira leria errado, so na hora de falar."""
    if not RE_PRONUNCIAS or not texto:
        return texto
    return RE_PRONUNCIAS.sub(
        lambda achado: _PRONUNCIAS_MINUSCULAS[achado.group(0).lower()], texto)


def parece_codigo(linha):
    """Rede de seguranca: sobrou da limpeza mas ainda cheira a codigo."""
    if len(linha) < 3:
        return True
    simbolos = sum(1 for c in linha if c in "{}[]()<>=;|&$#%^*/\\+`")
    if simbolos > max(4, len(linha) * 0.25):
        return True
    if re.match(r"^(?:\$|>|PS |cd |npm |pip |git |python |node |sudo |curl )", linha):
        return True
    return False


def limpar_texto(texto):
    """
    Transforma o markdown numa frase limpa, pronta para ser falada.

    A ordem importa: tags de sistema e blocos de codigo saem antes de tudo,
    senao o conteudo deles vaza para as etapas seguintes.
    """
    t = texto

    t = RE_TAG_SISTEMA.sub(" ", t)
    t = RE_BLOCO_CODIGO.sub(" ", t)
    t = RE_IMAGEM.sub(" ", t)
    t = RE_LINK.sub(r"\1", t)
    t = RE_TABELA.sub(" ", t)
    t = RE_LINHA_HORIZONTAL.sub(" ", t)
    t = RE_LINHA_INDENTADA.sub(" ", t)
    t = RE_CODIGO_INLINE.sub(r"\1", t)
    t = RE_TITULO.sub("", t)
    t = RE_CITACAO.sub("", t)
    t = RE_LISTA.sub("", t)
    t = RE_ENFASE.sub("", t)
    t = RE_HTML.sub(" ", t)
    t = RE_EMOJI.sub(" ", t)
    t = RE_CAMINHO.sub(encurtar_caminho, t)

    linhas = []
    for linha in t.splitlines():
        linha = linha.strip()
        if not linha:
            continue
        if parece_codigo(linha):
            continue
        if linha[-1] not in ".!?:;,":
            linha += "."
        linhas.append(linha)

    t = " ".join(linhas)
    t = RE_ESPACOS.sub(" ", t)
    t = RE_QUEBRAS.sub(" ", t)
    t = t.strip()

    # Por ultimo, e nao antes: as etapas acima trabalham em cima do texto
    # como ele foi escrito. Trocar a grafia no meio do caminho faria as
    # regras seguintes procurarem palavras que ja nao existem mais.
    t = ajustar_pronuncia(t)

    if LIMITE_CARACTERES and len(t) > LIMITE_CARACTERES:
        t = t[:LIMITE_CARACTERES].rsplit(" ", 1)[0] + "..."

    return t


def texto_da_pergunta(entrada):
    """
    Transforma uma pergunta de multipla escolha em frase falada.

    Estas perguntas nao vem como texto: elas chegam dentro de uma chamada de
    ferramenta, que o leitor ignora por padrao - e por isso ele ficava calado
    exatamente na hora de escolher. Aqui esse caso e aberto e lido.
    """
    if not isinstance(entrada, dict):
        return ""

    perguntas = entrada.get("questions")
    if not isinstance(perguntas, list):
        return ""

    partes = []
    for pergunta in perguntas:
        if not isinstance(pergunta, dict):
            continue

        enunciado = (pergunta.get("question") or "").strip()
        if enunciado:
            partes.append("Pergunta: " + enunciado)

        opcoes = pergunta.get("options")
        if not isinstance(opcoes, list):
            continue

        for numero, opcao in enumerate(opcoes, start=1):
            if not isinstance(opcao, dict):
                continue
            rotulo = (opcao.get("label") or "").strip()
            if not rotulo:
                continue
            linha = "Opção %d: %s." % (numero, rotulo)
            if LER_DESCRICAO_DAS_OPCOES:
                explicacao = (opcao.get("description") or "").strip()
                if explicacao:
                    linha += " " + explicacao
            partes.append(linha)

    if partes:
        partes.append("Você também pode escrever uma resposta própria.")

    return "\n".join(partes)


# Perguntas ja faladas pela caixa de entrada. O arquivo da conversa vai
# trazer a MESMA pergunta minutos depois, quando ela for finalmente gravada
# la; sem esta lista, voce ouviria tudo duas vezes.
_perguntas_faladas = set()
_trava_das_perguntas = threading.Lock()


def marcar_pergunta_falada(texto):
    with _trava_das_perguntas:
        _perguntas_faladas.add(texto)
        # Nao deixa a lista crescer para sempre; 50 perguntas de memoria e
        # muito mais do que a distancia entre as duas vias.
        if len(_perguntas_faladas) > 50:
            _perguntas_faladas.clear()
            _perguntas_faladas.add(texto)


def pergunta_ja_falada(texto):
    with _trava_das_perguntas:
        return texto in _perguntas_faladas


class VigiaDePerguntas(object):
    """
    Le a caixa de entrada preenchida pelo gancho do Claude Code e manda as
    perguntas para a voz na hora em que elas aparecem na tela.

    E a unica via que chega a tempo: o arquivo da conversa so recebe a
    pergunta depois que voce escolhe.
    """

    def __init__(self, fila, parar):
        self.fila = fila
        self.parar = parar
        self.posicao = 0
        self.resto = ""

        # Comeca do zero: o que estiver na caixa e de antes de ligar, e
        # perguntas velhas nao interessam a ninguem.
        try:
            if os.path.exists(ARQUIVO_DE_PERGUNTAS):
                os.remove(ARQUIVO_DE_PERGUNTAS)
        except OSError:
            try:
                self.posicao = os.path.getsize(ARQUIVO_DE_PERGUNTAS)
            except OSError:
                self.posicao = 0

    def rodar(self):
        while not self.parar.is_set():
            try:
                self.ler_novidades()
            except Exception as erro:
                print("[perguntas] aviso:", erro)
            self.parar.wait(0.25)      # mais miudo que o resto: e ao vivo

    def ler_novidades(self):
        try:
            tamanho = os.path.getsize(ARQUIVO_DE_PERGUNTAS)
        except OSError:
            return

        if tamanho < self.posicao:     # arquivo recriado
            self.posicao = 0
            self.resto = ""
        if tamanho == self.posicao:
            return

        try:
            with open(ARQUIVO_DE_PERGUNTAS, "rb") as f:
                f.seek(self.posicao)
                bruto = f.read(tamanho - self.posicao)
        except OSError:
            return

        self.posicao = tamanho
        texto = self.resto + bruto.decode("utf-8", errors="ignore")

        if texto.endswith("\n"):
            self.resto = ""
            linhas = texto.splitlines()
        else:
            linhas = texto.splitlines()
            self.resto = linhas.pop() if linhas else texto

        for linha in linhas:
            falado = self.pergunta_da_linha(linha)
            if not falado:
                continue
            marcar_pergunta_falada(falado)
            print("[perguntas] pergunta nova; lendo agora.")
            enfileirar_resposta(self.fila, limpar_texto(falado))

    @staticmethod
    def pergunta_da_linha(linha):
        """
        O gancho entrega o pedido inteiro da ferramenta. A pergunta pode vir
        em "tool_input" ou "input", dependendo da versao - por isso os dois
        sao tentados antes de desistir.
        """
        linha = linha.strip()
        if not linha:
            return ""
        try:
            obj = json.loads(linha)
        except (ValueError, TypeError):
            return ""
        if not isinstance(obj, dict):
            return ""

        for chave in ("tool_input", "input", "arguments"):
            entrada = obj.get(chave)
            if isinstance(entrada, dict) and entrada.get("questions"):
                return texto_da_pergunta(entrada)

        if obj.get("questions"):
            return texto_da_pergunta(obj)
        return ""


def extrair_resposta(linha_json):
    """
    De uma linha bruta do arquivo de conversa, devolve (id, texto_falado).

    So interessam as linhas do tipo "assistant", e dentro delas o texto
    explicativo e as perguntas de escolha. Raciocinio interno, chamadas de
    ferramenta e conversas de subagentes ficam de fora.
    """
    linha_json = linha_json.strip()
    if not linha_json:
        return None, None

    try:
        obj = json.loads(linha_json)
    except (ValueError, TypeError):
        return None, None      # linha ainda incompleta ou corrompida

    if not isinstance(obj, dict) or obj.get("type") != "assistant":
        return None, None

    if obj.get("isSidechain"):
        return None, None

    mensagem = obj.get("message") or {}
    conteudo = mensagem.get("content")
    if not isinstance(conteudo, list):
        return None, None

    # Cada pedaco vai marcado com "isto e explicacao?", porque a explicacao
    # pode ter de ser descartada depois - veja o corte logo abaixo.
    pedacos = []
    pergunta_ja_lida_na_hora = False

    for bloco in conteudo:
        if not isinstance(bloco, dict):
            continue
        tipo = bloco.get("type")

        if tipo == "text":
            texto = bloco.get("text") or ""
            if texto.strip():
                pedacos.append((True, texto))

        elif (LER_PERGUNTAS and tipo == "tool_use"
                and bloco.get("name") == "AskUserQuestion"):
            pergunta = texto_da_pergunta(bloco.get("input"))
            if not pergunta:
                continue
            # Esta e a via LENTA: a pergunta so chega aqui depois que voce
            # escolheu. Se a caixa de entrada ja tiver falado esta mesma
            # pergunta na hora certa, nao se repete.
            if pergunta_ja_falada(pergunta):
                pergunta_ja_lida_na_hora = True
            else:
                pedacos.append((False, pergunta))

    # A explicacao que vem ANTES de uma pergunta chega tarde demais para ser
    # util. Medido nesta maquina: o gancho entregou a pergunta aos 7 segundos
    # e o Claude Code so gravou a mensagem inteira - explicacao junto - aos 86,
    # no instante em que a escolha foi feita. Ou seja, a explicacao seria lida
    # DEPOIS da pergunta que ela explicava, e depois de voce ja ter escolhido.
    # Ler assim confunde mais do que ajuda, entao ela e descartada; continua na
    # tela, e a explicacao que importa vai dentro da propria pergunta.
    if pergunta_ja_lida_na_hora:
        pedacos = [(e_texto, texto) for (e_texto, texto) in pedacos
                   if not e_texto]

    partes = [texto for (_, texto) in pedacos]

    if not partes:
        return None, None

    identificador = (
        mensagem.get("id")
        or obj.get("uuid")
        or obj.get("requestId")
        or str(hash("\n".join(partes)))
    )

    limpo = limpar_texto("\n\n".join(partes))
    if not limpo:
        return None, None

    return identificador, limpo


# =============================================================================
# 4) A METADE QUE FALA  -  vigia dos arquivos
# =============================================================================

class VigiaDeSessoes(object):
    """
    Percorre a pasta de conversas de tempos em tempos e entrega na fila da voz
    apenas o que e novo.

    Por polling, e nao por aviso do sistema de arquivos, para ser imune a
    arquivo trocado, recriado ou aberto por outro programa.
    """

    def __init__(self, pasta, fila, parar):
        self.pasta = pasta
        self.fila = fila
        self.parar = parar
        self.posicoes = {}        # caminho -> bytes ja lidos
        self.restos = {}          # caminho -> pedaco de linha incompleta
        self.ja_falados = set()   # ids ja enviados para a voz

    def preparar(self):
        """
        Marca os arquivos que JA existem como lidos ate o fim. E isto que
        garante que o historico antigo nunca seja relido.
        """
        for caminho in listar_sessoes(self.pasta):
            try:
                self.posicoes[caminho] = os.path.getsize(caminho)
            except OSError:
                self.posicoes[caminho] = 0
            self.restos[caminho] = ""

    def rodar(self):
        while not self.parar.is_set():
            try:
                for caminho in listar_sessoes(self.pasta):
                    self.ler_novidades(caminho)
            except Exception as erro:
                print("[vigia] aviso:", erro)
            self.parar.wait(INTERVALO)

    def ler_novidades(self, caminho):
        """
        Le so os bytes acrescentados desde a ultima checagem. Arquivo novo
        comeca do inicio (tudo nele e novo); arquivo que encolheu foi
        recriado e volta ao zero.
        """
        try:
            tamanho = os.path.getsize(caminho)
        except OSError:
            return

        if caminho not in self.posicoes:
            self.posicoes[caminho] = 0
            self.restos[caminho] = ""
            print("[vigia] nova conversa detectada:", os.path.basename(caminho))

        anterior = self.posicoes[caminho]

        if tamanho < anterior:
            anterior = 0
            self.restos[caminho] = ""

        if tamanho == anterior:
            return

        try:
            with open(caminho, "rb") as f:
                f.seek(anterior)
                bruto = f.read(tamanho - anterior)
        except OSError:
            return

        self.posicoes[caminho] = tamanho
        texto = self.restos.get(caminho, "") + bruto.decode("utf-8", errors="ignore")

        # A ultima parte pode ser uma linha pela metade: guarda para depois.
        if texto.endswith("\n"):
            self.restos[caminho] = ""
            linhas = texto.splitlines()
        else:
            linhas = texto.splitlines()
            self.restos[caminho] = linhas.pop() if linhas else texto

        for linha in linhas:
            identificador, falado = extrair_resposta(linha)
            if not falado:
                continue
            if identificador in self.ja_falados:
                continue          # nao ler a mesma coisa duas vezes
            self.ja_falados.add(identificador)
            enfileirar_resposta(self.fila, falado)


# =============================================================================
# 5) A METADE QUE FALA  -  a voz
# =============================================================================

def tem_o_programa(nome):
    """O programa esta instalado e ao alcance? Usado o tempo todo aqui."""
    import shutil
    return shutil.which(nome) is not None


class VozDoLinux(object):
    """
    Fala chamando o programa de fala do sistema.

    Um processo por frase, e nao uma biblioteca presa ao programa. Parece
    desperdicio, mas e o que da o comportamento mais importante da leitura:
    para CALAR NA HORA basta encerrar esse processo. No Windows isso exigiu
    fala assincrona com sondagem de estado; aqui sai de graca.

    Qual programa usar e decidido uma vez, na partida, do melhor para o mais
    comum:

      piper       voz neural, de longe a mais natural. So se estiver
                  instalado E com um modelo em portugues apontado em
                  MODELO_DO_PIPER - ele nao vem em nenhuma distribuicao.
      espeak-ng   robotica, mas existe em todo lugar, fala portugues do
                  Brasil sem ajuste e obedece velocidade e volume direto.
      spd-say     a fala que o proprio sistema ja usa para acessibilidade.
                  Fica por ultimo porque e uma camada a mais: ela costuma
                  chamar o espeak por baixo, e responde pior a comandos.
    """

    def __init__(self):
        import shutil, subprocess           # noqa: E401
        self.subprocess = subprocess
        self.processo = None
        self.calamos = False
        self.motor = None

        if MODELO_DO_PIPER and tem_o_programa("piper") and tocador_de_audio():
            if os.path.isfile(MODELO_DO_PIPER):
                self.motor = "piper"
            else:
                print("[voz] MODELO_DO_PIPER aponta para um arquivo que nao"
                      " existe; usando o espeak.")
        if self.motor is None:
            for candidato in ("espeak-ng", "espeak"):
                if tem_o_programa(candidato):
                    self.motor = candidato
                    break
        if self.motor is None and tem_o_programa("spd-say"):
            self.motor = "spd-say"

        if self.motor is None:
            raise RuntimeError("nenhum programa de fala instalado")

        print("[voz] usando:", self.descricao())

    def descricao(self):
        if self.motor == "piper":
            return "piper (%s)" % os.path.basename(MODELO_DO_PIPER)
        if self.motor == "spd-say":
            return "spd-say (fala do sistema)"
        return "%s, voz %s" % (self.motor, VOZ_DO_ESPEAK)

    def _comando(self, texto):
        """A linha de comando que fala este texto, ja com voz e velocidade."""
        if self.motor == "piper":
            # O piper escreve o audio cru na saida, e quem toca e o programa
            # de audio. Vai como uma linha so de shell porque e um cano entre
            # dois programas; encerrar o grupo inteiro cala os dois.
            return ("piper --model %s --output_raw 2>/dev/null | %s"
                    % (aspas(MODELO_DO_PIPER), tocador_de_audio()))

        if self.motor == "spd-say":
            # -w espera terminar; sem isso ele devolve o comando na hora e
            # nao haveria como saber quando a frase acabou.
            return ["spd-say", "-w", "-l", "pt-BR",
                    "-r", "%d" % max(-100, min(100, int((VELOCIDADE - 175) / 3))),
                    texto]

        # espeak: -s ja e em palavras por minuto, igualzinho a VELOCIDADE.
        return [self.motor, "-v", VOZ_DO_ESPEAK,
                "-s", "%d" % max(80, min(450, int(VELOCIDADE))),
                "-a", "%d" % max(0, min(200, int(round(VOLUME * 100)))),
                "--stdin"]

    def falar(self, texto, desistir_se=None):
        """
        Fala uma frase. Se desistir_se() virar verdade no meio, cala na hora.

        O processo nasce em sessao propria para que encerra-lo alcance
        tambem o programa de audio do outro lado do cano - sem isso, com o
        piper, o texto pararia de ser gerado mas o que ja estava na fila da
        placa de som continuaria saindo.
        """
        if not texto or not texto.strip():
            return

        comando = self._comando(texto)
        e_shell = isinstance(comando, str)
        self.calamos = False

        try:
            self.processo = self.subprocess.Popen(
                comando, shell=e_shell,
                stdin=self.subprocess.PIPE,
                stdout=self.subprocess.DEVNULL,
                # A reclamacao do programa de fala e GUARDADA, e nao jogada
                # fora. Sem isso, um espeak que nao consegue abrir o som
                # falharia em silencio: o programa acharia que falou, o
                # registro diria "falando", e nao sairia som nenhum - a pior
                # especie de defeito, porque nada aponta para ele.
                stderr=self.subprocess.PIPE,
                start_new_session=True)
        except Exception as erro:
            print("[voz] nao consegui falar:", erro)
            self.processo = None
            raise

        try:
            # O texto vai pela entrada, e nao como argumento: assim nenhuma
            # aspa, acento ou cifrao do meio da frase e interpretado como
            # parte do comando.
            if self.motor != "spd-say":
                self.processo.stdin.write(texto.encode("utf-8", "replace"))
            self.processo.stdin.close()
        except Exception:
            pass

        while True:
            codigo = self.processo.poll()
            if codigo is not None:
                processo = self.processo
                self.processo = None
                self._conferir_o_fim(processo, codigo)
                return
            if desistir_se is not None and desistir_se():
                self.calar()
                return
            time.sleep(0.05)

    def _conferir_o_fim(self, processo, codigo):
        """Terminou bem? Se nao, levanta o erro com o que o programa disse."""
        if self.calamos or codigo == 0:
            return
        reclamacao = ""
        try:
            reclamacao = (processo.stderr.read() or b"").decode(
                "utf-8", "replace").strip()
        except Exception:
            pass
        raise RuntimeError(
            "%s terminou com erro %d%s"
            % (self.motor, codigo, (": " + reclamacao) if reclamacao else ""))

    def calar(self):
        """Encerra a fala em andamento, com o programa de audio junto."""
        processo = self.processo
        self.processo = None
        self.calamos = True          # o fim veio de nos: nao e defeito
        if processo is None:
            return
        try:
            os.killpg(os.getpgid(processo.pid), 15)      # o grupo inteiro
        except Exception:
            try:
                processo.kill()
            except Exception:
                pass
        try:
            processo.wait(timeout=2)
        except Exception:
            pass


def tocador_de_audio():
    """
    Quem toca o audio cru que o piper produz.

    Tres candidatos porque nenhum esta em todo lugar: paplay vem com o
    PulseAudio, pw-play com o PipeWire, aplay com o ALSA.
    """
    if tem_o_programa("pw-play"):
        return "pw-play --rate 22050 --channels 1 --format s16 -"
    if tem_o_programa("paplay"):
        return "paplay --raw --rate=22050 --channels=1 --format=s16le"
    if tem_o_programa("aplay"):
        return "aplay -q -r 22050 -c 1 -f S16_LE -t raw -"
    return None


def aspas(caminho):
    """Protege um caminho para entrar numa linha de shell."""
    import shlex
    return shlex.quote(caminho)


def montar_voz():
    """
    Se isto falhar, o programa continua vivo e escrevendo o que voce dita -
    so nao fala. E uma falha silenciosa por natureza, entao ela precisa
    deixar no registro o comando exato que resolve, e nao so o erro cru.
    """
    try:
        return VozDoLinux()
    except RuntimeError:
        print("[voz] nao ha nenhum programa de fala instalado.")
        print("[voz] resolva com um destes, conforme o seu Linux:")
        print("      sudo apt install espeak-ng          (Debian, Ubuntu)")
        print("      sudo dnf install espeak-ng          (Fedora)")
        print("      sudo pacman -S espeak-ng            (Arch)")
        print("[voz] o resto do programa continua funcionando, mas mudo.")
        return None
    except Exception as erro:
        print("[voz] nao consegui preparar a fala:", erro)
        print("[voz] confira o que existe com:")
        print("      python3 claude_em_voz.py --vozes")
        return None


def locutor(fila, parar):
    """
    Thread unica da voz: respostas, perguntas e avisos saem em fila, na
    ordem, nunca por cima uns dos outros.

    Antes de cada frase ela espera voce terminar de ditar. Duas vozes ao
    mesmo tempo nao se entendem, e o microfone ouviria esta aqui.
    """
    voz = montar_voz()

    while not parar.is_set():
        try:
            item = fila.get(timeout=0.4)
        except queue.Empty:
            continue

        if item is None:
            break

        # Ou o texto puro, ou o texto marcado como "fale de qualquer jeito".
        # A marca e usada pelos avisos do interruptor - "leitura desligada" -,
        # que precisam ser ouvidos justamente quando a leitura esta caindo.
        if isinstance(item, tuple):
            texto, de_qualquer_jeito = item
        else:
            texto, de_qualquer_jeito = item, False

        try:
            # Leitura desligada: a resposta e simplesmente descartada. Nao
            # fica guardada para depois - religar e para voltar a ouvir o que
            # vem a seguir, nao para receber de uma vez tudo o que perdeu.
            if not de_qualquer_jeito and not _leitura_ligada.is_set():
                continue

            # Espera a sua fala terminar. Fica em espera indefinidamente de
            # proposito: a resposta continua na fila e sera lida depois.
            while _gravando.is_set() and not parar.is_set():
                time.sleep(0.15)

            if MOSTRAR_NO_TERMINAL:
                try:
                    print("\n[falando] " + texto[:300]
                          + ("..." if len(texto) > 300 else ""))
                except Exception:
                    pass

            if voz is None:
                voz = montar_voz()
            if voz is not None:
                # Cala na hora se a leitura for desligada no meio da frase -
                # menos os avisos do proprio interruptor, que sao curtos e
                # existem para ser ouvidos ate o fim.
                voz.falar(texto, None if de_qualquer_jeito
                          else (lambda: not _leitura_ligada.is_set()))

        except Exception as erro:
            # Uma frase perdida e melhor que a thread morrer e o programa
            # seguir ligado porem mudo.
            print("[voz] erro ao falar:", erro)
            try:
                voz = montar_voz()
            except Exception as outro:
                print("[voz] nao consegui recriar a voz:", outro)
        finally:
            fila.task_done()


# =============================================================================
# 6) A METADE QUE ESCREVE  -  uma fala
# =============================================================================

class Fala(object):
    """
    Tudo o que diz respeito a UMA fala: o audio, o texto que ela ja escreveu,
    a janela de destino e se voce digitou no meio.

    Existir como pacote separado e o que permite comecar a proxima fala
    enquanto a anterior ainda esta sendo revisada, sem uma atrapalhar a
    outra - antes, a revisao de uma caia em cima do texto da seguinte e o
    apagava.

    O audio fica em dois lugares: "aberto" encolhe a cada palavra escrita,
    para as passadas nao ficarem cada vez mais lentas; "completo" guarda a
    fala inteira, que a revisao final precisa.
    """

    def __init__(self, inicio_do_audio, janela):
        self.aberto = list(inicio_do_audio)
        self.completo = list(inicio_do_audio)
        self.gravando = True
        self.trava = threading.Lock()

        self.janela = janela
        self.digitado = ""
        self.hipotese = []
        self.usuario_digitou = False

    def guardar(self, pedaco):
        with self.trava:
            if not self.gravando:
                return
            self.aberto.append(pedaco)
            self.completo.append(pedaco)

    def encerrar(self):
        with self.trava:
            self.gravando = False

    def trecho_aberto(self):
        with self.trava:
            if not self.aberto:
                return np.zeros(0, dtype=np.float32)
            return np.concatenate(self.aberto)

    def audio_completo(self):
        with self.trava:
            if not self.completo:
                return np.zeros(0, dtype=np.float32)
            return np.concatenate(self.completo)

    def descartar(self, amostras):
        """Joga fora o comeco do trecho aberto, ja escrito em definitivo."""
        if amostras <= 0:
            return
        with self.trava:
            if not self.aberto:
                return
            inteiro = np.concatenate(self.aberto)
            self.aberto = [inteiro[amostras:]] if amostras < len(inteiro) else []

    def duracao(self):
        with self.trava:
            return sum(len(p) for p in self.completo) / float(TAXA)


# =============================================================================
# 7) A METADE QUE ESCREVE  -  microfone
# =============================================================================

class Microfone(object):
    """
    Mantem o microfone aberto o tempo todo, mas so entrega audio para a fala
    em andamento. Abrir e fechar a cada aperto custaria uma fracao de segundo
    - justamente a fracao da primeira silaba.

    Sem fala em andamento, o audio vai para um anel curto e e descartado; ao
    comecar, esse anel entra junto, para nao perder o comeco de quem fala um
    instante antes do sinal.
    """

    def __init__(self):
        self.taxa = TAXA
        self.fala = None
        self.trava = threading.Lock()
        self.stream = None
        self.anel = collections.deque(maxlen=max(1, int(PRE_ROLL * TAXA / 1024) + 1))

    def abrir(self):
        try:
            self.stream = sd.InputStream(
                samplerate=TAXA, channels=1, dtype="float32",
                blocksize=1024, device=MICROFONE, callback=self._chegou_audio,
            )
            self.stream.start()
            self.taxa = TAXA
            return
        except Exception as erro:
            print("[microfone] 16 kHz recusado (%s); usando a taxa nativa." % erro)

        info = sd.query_devices(
            MICROFONE if MICROFONE is not None else sd.default.device[0], "input"
        )
        self.taxa = int(info["default_samplerate"])
        self.stream = sd.InputStream(
            samplerate=self.taxa, channels=1, dtype="float32",
            blocksize=1024, device=MICROFONE, callback=self._chegou_audio,
        )
        self.stream.start()

    def _chegou_audio(self, dados, quadros, tempo, estado):
        pedaco = dados[:, 0].copy()
        if self.taxa != TAXA:
            pedaco = reamostrar(pedaco, self.taxa, TAXA)
        with self.trava:
            fala = self.fala
        if fala is not None and fala.gravando:
            fala.guardar(pedaco)
        else:
            self.anel.append(pedaco)

    def comecar(self, janela):
        with self.trava:
            inicio = list(self.anel)
            self.anel.clear()
            self.fala = Fala(inicio, janela)
            return self.fala

    def parar(self):
        """Fecha a fala em andamento sem jogar o audio dela fora."""
        with self.trava:
            fala = self.fala
            self.fala = None
        if fala is not None:
            fala.encerrar()
        return fala

    def fechar(self):
        try:
            if self.stream is not None:
                self.stream.stop()
                self.stream.close()
        except Exception:
            pass


def reamostrar(audio, de_taxa, para_taxa):
    """
    Reamostragem simples por interpolacao. Fala humana tem pouca energia nos
    agudos, entao o resultado e indistinguivel para o reconhecedor - e nao
    acrescenta biblioteca nenhuma.
    """
    if de_taxa == para_taxa or len(audio) == 0:
        return audio
    quantidade = int(round(len(audio) * para_taxa / float(de_taxa)))
    if quantidade <= 1:
        return audio
    origem = np.linspace(0.0, 1.0, num=len(audio), endpoint=False)
    destino = np.linspace(0.0, 1.0, num=quantidade, endpoint=False)
    return np.interp(destino, origem, audio).astype(np.float32)


# =============================================================================
# 8) A METADE QUE ESCREVE  -  reconhecimento
# =============================================================================

def carregar_modelo(tamanho):
    """
    Carrega um reconhecedor. Na primeira vez ele BAIXA (uma vez so, fica
    guardado no computador); depois disso funciona sem internet nenhuma.

    "int8" e a versao compacta: ocupa menos memoria e roda varias vezes mais
    rapido no processador comum, com perda que nao se percebe em fala ditada
    de perto.
    """
    print("[reconhecimento] carregando o modelo '%s'..." % tamanho)
    inicio = time.time()
    modelo = WhisperModel(
        tamanho, device="cpu", compute_type="int8",
        cpu_threads=FIOS_DO_PROCESSADOR,
    )
    print("[reconhecimento] '%s' pronto em %.1f s." % (tamanho, time.time() - inicio))
    return modelo


def palavras_de(modelo, audio, feixe=1):
    """
    Devolve as palavras com o instante em que cada uma comeca e termina - sao
    esses instantes que permitem jogar fora o audio ja escrito.

    condition_on_previous_text=False de proposito: sem isso o Whisper usa a
    frase anterior como contexto e, num ditado de frases soltas, entra em
    circulo repetindo o que ja disse.

    O vocabulario vai por "hotwords", e nao por "initial_prompt": os dois
    servem de pista, mas o initial_prompt entra como se fosse fala anterior -
    justamente o que se desligou na linha de cima, e pelo mesmo motivo.
    """
    segmentos, _info = modelo.transcribe(
        audio,
        language=IDIOMA,
        beam_size=feixe,
        vad_filter=True,
        word_timestamps=True,
        condition_on_previous_text=False,
        hotwords=DICA_DE_VOCABULARIO or None,
        no_speech_threshold=0.6,
    )
    saida = []
    for segmento in segmentos:
        for palavra in (segmento.words or []):
            saida.append({
                "texto": palavra.word,
                "inicio": palavra.start,
                "fim": palavra.end,
            })
    return saida


def comparavel(texto):
    """Compara palavras ignorando pontuacao, maiuscula e espaco em volta."""
    return re.sub(r"[^\wÀ-ÿ]", "", texto).lower()


def limpar_transcricao(texto):
    """Tira os cacoetes do reconhecedor e deixa tudo numa linha so."""
    if not texto:
        return ""

    # Quebra de linha no prompt do Claude Code enviaria a mensagem no meio.
    texto = re.sub(r"\s*[\r\n]+\s*", " ", texto)
    texto = re.sub(r"[ \t]{2,}", " ", texto).strip()

    comparando = texto.lower().strip(" .!?,")
    for lixo in FRASES_INVENTADAS:
        if lixo in comparando:
            return ""

    if len(re.sub(r"[^\wÀ-ÿ]", "", texto)) < 2:
        return ""

    return texto


# =============================================================================
# 9) A METADE QUE ESCREVE  -  janelas e teclado
# =============================================================================

_teclado = keyboard.Controller()

# Ligado enquanto ESTE programa esta digitando. Veja evento_e_nosso().
_evento_injetado = False        # sem uso aqui; existe para a versao Windows
_filtro_funcionando = False


def evento_e_nosso():
    """
    Diz se o evento de teclado atual foi criado por nos, e nao pelo seu dedo.

    Sem isto o programa se sabota: para escrever, ele avisa o sistema de que
    o Ctrl esta solto - senao cada letra viraria atalho. So que ele tambem
    ESCUTA o teclado, e escutava o proprio aviso. Como soltar o Ctrl encerra
    a fala, ele encerrava a si mesmo na primeira leva de palavras, e falas
    longas paravam no meio.

    No Windows da para perguntar ao proprio evento quem o criou. Aqui nao ha
    essa marca, entao vale a regra simples: toda tecla que chega enquanto
    estamos escrevendo e nossa. E por isso que escrever() e apagar() marcam
    o sinal ANTES de encostar no teclado, e so o desmarcam 50 ms depois do
    ultimo caractere - tempo dos eventos em transito chegarem.
    """
    return _estamos_escrevendo.is_set()


def _chamar(comando, entrada=None, limite=3.0):
    """
    Roda um programa curto e devolve a saida, ou None se nao der certo.

    Todo dialogo com o sistema de janelas passa por aqui: sao comandos de
    milissegundos, e o limite de tempo existe para o programa nunca ficar
    preso esperando um deles.
    """
    import subprocess
    try:
        resultado = subprocess.run(
            comando, timeout=limite, capture_output=True, text=True,
            input=entrada)
    except Exception:
        return None
    if resultado.returncode != 0:
        return None
    return (resultado.stdout or "").strip()


_avisou_do_wayland = [False]


def usando_wayland():
    return bool(os.environ.get("WAYLAND_DISPLAY")) and not os.environ.get("DISPLAY")


def janela_da_frente():
    """
    Qual janela esta na frente agora.

    E um numero do X11, obtido pelo xdotool. No Wayland nao ha resposta: o
    proprio sistema impede que um programa saiba qual janela e do outro, e
    isso e de proposito, por seguranca. A leitura em voz alta continua igual;
    quem sente e o ditado, que perde a garantia de escrever na janela certa.
    """
    saida = _chamar(["xdotool", "getactivewindow"])
    if saida:
        return saida.strip()
    if usando_wayland() and not _avisou_do_wayland[0]:
        _avisou_do_wayland[0] = True
        print("[janela] sessao Wayland: nao da para saber qual janela esta na"
              " frente.")
        print("[janela] a leitura funciona normalmente; para o ditado, veja o")
        print("         PERGUNTAS_E_RESPOSTAS.txt, secao sobre Wayland.")
    return None


def nome_da_janela(janela):
    if janela is None:
        return "?"
    return _chamar(["xdotool", "getwindowname", str(janela)]) or "?"


def nossa_propria_janela():
    """
    O terminal onde este programa esta rodando, quando ha um.

    Serve para recusar a gravacao se ele estiver na frente - escrever ali nao
    serviria para nada. A maioria dos terminais anota o proprio numero de
    janela nesta variavel de ambiente; quando nao anota, ficamos sem saber, e
    o pior que acontece e o texto sair no lugar errado uma vez.
    """
    return os.environ.get("WINDOWID") or None


def focar(janela):
    """
    Traz a janela escolhida para a frente.

    Alguns gerenciadores de janelas recusam, por seguranca contra programas
    que roubam o foco; nesse caso escrevemos onde estiver, porque perder o
    texto seria pior do que escreve-lo no lugar errado.
    """
    if janela is None:
        return False
    if _chamar(["xdotool", "getactivewindow"]) == str(janela):
        return True
    if _chamar(["xdotool", "windowactivate", "--sync", str(janela)],
               limite=2.0) is None:
        return False
    time.sleep(0.05)
    return _chamar(["xdotool", "getactivewindow"]) == str(janela)


_cache_do_claude = {}
VALIDADE_DO_CACHE = 4.0


def _arvore_de_processos():
    """
    Nome, linha de comando e parentesco de cada processo, lidos em /proc.

    A linha de comando entra junto porque no Linux o Claude Code costuma
    rodar como "node": procurar so pelo nome do processo nao acharia nada.
    """
    nomes, filhos = {}, {}
    try:
        entradas = os.listdir("/proc")
    except OSError:
        return {}, {}

    for entrada in entradas:
        if not entrada.isdigit():
            continue
        pid = int(entrada)
        try:
            with open("/proc/%d/comm" % pid, "r") as arquivo:
                nome = arquivo.read().strip().lower()
        except OSError:
            continue

        linha_de_comando = ""
        try:
            with open("/proc/%d/cmdline" % pid, "rb") as arquivo:
                linha_de_comando = (arquivo.read()
                                    .replace(b"\x00", b" ")
                                    .decode("utf-8", "ignore").strip().lower())
        except OSError:
            pass

        pai = 0
        try:
            with open("/proc/%d/status" % pid, "r") as arquivo:
                for linha in arquivo:
                    if linha.startswith("PPid:"):
                        pai = int(linha.split()[1])
                        break
        except (OSError, ValueError, IndexError):
            pass

        nomes[pid] = (nome, linha_de_comando)
        filhos.setdefault(pai, []).append(pid)

    return nomes, filhos


def _e_o_claude(dados, procurados):
    """
    O processo e o Claude Code? Vale pelo nome ou pela linha de comando.

    A linha de comando entra porque no Linux ele costuma rodar como "node",
    com o caminho do claude como argumento - procurar so pelo nome do
    processo nao acharia nada.

    E a procura e por PEDACO INTEIRO do caminho, e nao pelo texto solto.
    Procurando o texto, uma pasta chamada "claudeteca" faria qualquer
    programa passar por Claude Code, e a tecla de falar comecaria a valer
    onde nao devia. E o mesmo engano que a versao para Windows ja teve com um
    navegador, documentado la.
    """
    nome, linha = dados
    if nome in procurados:
        return True

    for palavra in (linha or "").split():
        for pedaco in palavra.split("/"):
            for procurado in procurados:
                # "claude" exato, ou o comeco de um nome com traco, como em
                # "claude-code" - que e a pasta do pacote instalado por npm.
                if pedaco == procurado or pedaco.startswith(procurado + "-"):
                    return True
    return False


def dono_da_janela(janela):
    if janela is None:
        return None
    saida = _chamar(["xdotool", "getwindowpid", str(janela)])
    try:
        return int(saida)
    except (TypeError, ValueError):
        return None


def janela_e_do_claude(janela):
    """
    Diz se a janela dada e a do Claude Code.

    O titulo nao serve de identificacao: ele muda a cada conversa. O que nao
    muda e o programa que roda dentro - o claude fica pendurado no processo
    do terminal.

    Com uma exigencia a mais: a janela precisa ser de um terminal, e o
    caminho ate o claude so pode passar por terminais. Sem isso, um navegador
    que um dia abriu um terminal continua com um claude pendurado na arvore
    dele e vira "o Claude" - aconteceu de verdade na versao para Windows.
    """
    if not SO_NO_CLAUDE:
        return True
    if janela is None:
        return False

    if TITULOS_DO_CLAUDE:
        titulo = (nome_da_janela(janela) or "").lower()
        if any(t.lower() in titulo for t in TITULOS_DO_CLAUDE):
            return True

    pid = dono_da_janela(janela)
    if not pid:
        return False

    guardado = _cache_do_claude.get(pid)
    if guardado and (time.time() - guardado[1]) < VALIDADE_DO_CACHE:
        return guardado[0]

    procurados = [p.lower() for p in PROGRAMAS_DO_CLAUDE]
    terminais = [p.lower() for p in PROGRAMAS_DE_TERMINAL]
    try:
        nomes, filhos = _arvore_de_processos()
    except Exception:
        return True          # na duvida, obedece

    achou = False
    dono = nomes.get(pid, ("", ""))
    if _e_o_claude(dono, procurados):
        achou = True
    elif dono[0] in terminais:
        pilha, vistos = [pid], set()
        while pilha and not achou:
            atual = pilha.pop()
            if atual in vistos:
                continue
            vistos.add(atual)
            for filho in filhos.get(atual, []):
                dados = nomes.get(filho, ("", ""))
                if _e_o_claude(dados, procurados):
                    achou = True
                    break
                if dados[0] in terminais:
                    pilha.append(filho)

    _cache_do_claude[pid] = (achou, time.time())
    return achou


# Teclas que, presas, transformam o que digitamos em atalho. O Shift fica de
# fora: ele so muda a letra, nao dispara comando.
MODIFICADORAS_A_SOLTAR = ("ctrl_l", "ctrl_r", "alt_l", "alt_gr", "cmd_l", "cmd_r")
ESPERA_PELA_TECLA = 3.0


def liberar_o_teclado():
    """
    Garante que nenhuma tecla de atalho esteja valendo antes de escrevermos.

    No modo "segurar" voce esta com o dedo no Ctrl de proposito, entao nao ha
    o que esperar: avisamos o Windows de que ele esta solto e escrevemos. No
    modo "alternar" vale esperar um instante, porque a tecla logo sera solta.

    Esse aviso volta para nos como um evento de teclado; e por isso que
    filtro_de_eventos() existe.
    """
    if MODO_DE_ESCUTA == "alternar" and _tecla_presa.is_set():
        limite = time.time() + ESPERA_PELA_TECLA
        while _tecla_presa.is_set() and time.time() < limite:
            time.sleep(0.03)

    for nome in MODIFICADORAS_A_SOLTAR:
        tecla = getattr(keyboard.Key, nome, None)
        if tecla is None:
            continue
        try:
            _teclado.release(tecla)
        except Exception:
            pass


def escolher_como_escrever():
    """
    Decide por qual caminho o texto sera digitado.

    Sao tres, e a ordem nao e gosto, e sim o que funciona onde:

      pynput    fala direto com o X11 e e o mais rapido. So serve no X11.
      xdotool   tambem so no X11, mas as vezes acerta onde o pynput erra,
                em programas que filtram eventos sinteticos.
      wtype     o equivalente para Wayland. Nem toda area de trabalho
                Wayland aceita: o GNOME, por exemplo, recusa.

    Nao havendo nenhum, o programa continua lendo em voz alta e guardando o
    que voce dita no historico - so nao digita.
    """
    if COMO_ESCREVER != "auto":
        return COMO_ESCREVER

    if usando_wayland():
        if tem_o_programa("wtype"):
            return "wtype"
        if tem_o_programa("ydotool"):
            return "ydotool"
        return "pynput"          # tentativa: XWayland as vezes salva
    return "pynput" if not PREFERIR_XDOTOOL and _teclado else "xdotool"


_como_escrever = None


def como_escrever():
    global _como_escrever
    if _como_escrever is None:
        _como_escrever = escolher_como_escrever()
        print("[escrita] digitando por:", _como_escrever)
    return _como_escrever


def _digitar(texto):
    modo = como_escrever()
    if modo == "xdotool":
        # O "--" separa o texto das opcoes: sem ele, uma fala que comece com
        # tracinho seria lida como opcao do proprio xdotool.
        _chamar(["xdotool", "type", "--clearmodifiers", "--delay", "1",
                 "--", texto], limite=20.0)
    elif modo == "wtype":
        _chamar(["wtype", "--", texto], limite=20.0)
    elif modo == "ydotool":
        _chamar(["ydotool", "type", "--", texto], limite=20.0)
    else:
        _teclado.type(texto)


def _apagar_letras(quantidade):
    modo = como_escrever()
    if modo == "xdotool":
        _chamar(["xdotool", "key", "--clearmodifiers", "--repeat",
                 str(quantidade), "--delay", "4", "BackSpace"], limite=20.0)
    elif modo in ("wtype", "ydotool"):
        for _ in range(quantidade):
            if modo == "wtype":
                _chamar(["wtype", "-k", "BackSpace"])
            else:
                _chamar(["ydotool", "key", "14:1", "14:0"])
    else:
        for _ in range(quantidade):
            _teclado.press(keyboard.Key.backspace)
            _teclado.release(keyboard.Key.backspace)
            time.sleep(0.004)


def escrever(texto):
    """Digita o texto na janela que estiver na frente, acento e tudo."""
    if not texto:
        return
    # A marca entra ANTES de liberar o teclado: soltar as modificadoras ja
    # gera eventos nossos, que nao podem ser confundidos com os seus.
    _estamos_escrevendo.set()
    try:
        liberar_o_teclado()
        _digitar(texto)
    except Exception as erro:
        print("[escrita] nao consegui escrever:", erro)
    finally:
        # Uma folga para os eventos que acabamos de mandar chegarem antes de
        # voltarmos a considerar as teclas como suas.
        time.sleep(0.05)
        _estamos_escrevendo.clear()


def apagar(quantidade):
    """Apaga N letras ja escritas, para a correcao do fim da fala."""
    if quantidade <= 0:
        return
    _estamos_escrevendo.set()
    try:
        liberar_o_teclado()
        _apagar_letras(quantidade)
    except Exception as erro:
        print("[escrita] nao consegui apagar:", erro)
    finally:
        time.sleep(0.05)
        _estamos_escrevendo.clear()


def guardar_no_historico(texto):
    if not GUARDAR_HISTORICO or not texto:
        return
    try:
        with open(ARQUIVO_HISTORICO, "a", encoding="utf-8") as f:
            f.write("[%s] %s\n" % (time.strftime("%d/%m/%Y %H:%M:%S"), texto))
    except OSError as erro:
        print("[historico] nao consegui guardar:", erro)


# =============================================================================
# 10) A METADE QUE ESCREVE  -  o ditado ao vivo
# =============================================================================

class DitadoAoVivo(object):
    """
    Enquanto voce fala, transcreve o que ja foi dito e escreve so o que ja
    esta firme.

    A regra do "firme" e a do acordo local: uma palavra so vai para a tela
    quando aparece IGUAL em duas passadas seguidas. Palavra que ainda pode
    mudar espera. E por isso que o texto nunca precisa ser apagado no meio da
    fala - o que aparece, aparece para ficar.

    A ultima palavra de cada passada nunca e escrita na hora, mesmo que
    combine: enquanto voce fala ela esta cortada no meio.
    """

    def __init__(self, modelo_vivo, modelo_final):
        self.modelo_vivo = modelo_vivo
        self.modelo_final = modelo_final
        self.em_curso = None

        # Se ja existe texto escrito por voz na linha. E consultado na hora de
        # ESCREVER, e nao no aperto da tecla: falando de novo antes de a
        # revisao anterior terminar, no aperto a resposta ainda seria "nao" e
        # as duas frases sairiam grudadas.
        self.ja_escreveu = False

    def registrar_tecla_do_usuario(self):
        """Chamado quando VOCE digita: cancela a correcao automatica."""
        if evento_e_nosso():
            return
        fala = self.em_curso
        if fala is not None:
            fala.usuario_digitou = True

    # ---- uma passada ao vivo ----

    def passada(self, fala):
        audio = fala.trecho_aberto()
        if len(audio) < int(0.7 * TAXA):
            return
        if float(np.max(np.abs(audio))) < VOLUME_MINIMO:
            return

        try:
            atual = palavras_de(self.modelo_vivo, audio, feixe=1)
        except Exception as erro:
            print("[ao vivo] erro na passada:", erro)
            return

        if not atual:
            return

        firmes = self.quantas_combinam(fala.hipotese, atual, deixar_de_fora=1)

        if firmes > 0:
            self.entregar(fala, atual[:firmes])
            corte = atual[firmes - 1]["fim"]
            fala.descartar(int(corte * TAXA))
            fala.hipotese = [
                {"texto": p["texto"], "inicio": p["inicio"] - corte,
                 "fim": p["fim"] - corte}
                for p in atual[firmes:]
            ]
        else:
            fala.hipotese = atual

    @staticmethod
    def quantas_combinam(anterior, atual, deixar_de_fora=0):
        limite = min(len(anterior), len(atual) - deixar_de_fora)
        n = 0
        while n < limite and comparavel(anterior[n]["texto"]) == comparavel(atual[n]["texto"]):
            n += 1
        return n

    def entregar(self, fala, palavras):
        """Escreve na tela as palavras que ja estao firmes."""
        pedaco = "".join(p["texto"] for p in palavras)
        if not fala.digitado:
            # O Whisper devolve as palavras com um espaco na frente. No comeco
            # de tudo esse espaco e lixo; continuando um texto que ja existe,
            # ele e justamente o que separa uma fala da outra.
            pedaco = (" " + pedaco.strip()) if self.ja_escreveu else pedaco.lstrip()
        if not pedaco.strip():
            return

        if MOSTRAR_NO_TERMINAL:
            try:
                print(pedaco, end="", flush=True)
            except Exception:
                pass

        fala.digitado += pedaco
        self.ja_escreveu = True
        if ESCREVER_NA_TELA:
            if DEVOLVER_O_FOCO:
                focar(fala.janela)
            escrever(pedaco)

    # ---- o fim da fala ----

    def finalizar(self, fala, ha_outra_fala=None):
        """
        Escreve o que ficou pendente e, se der, deixa o modelo bom corrigir a
        frase inteira.

        Se voce ja comecou a falar de novo, a revisao e PULADA: ela leva
        alguns segundos e, enquanto roda, a fala nova espera na fila. Entre
        acompanhar voce falando e caprichar numa frase ja escrita, acompanhar
        vale mais.
        """
        audio = fala.trecho_aberto()
        if len(audio) > int(0.2 * TAXA) and float(np.max(np.abs(audio))) >= VOLUME_MINIMO:
            try:
                self.entregar(fala, palavras_de(self.modelo_vivo, audio, feixe=1))
            except Exception as erro:
                print("[ao vivo] erro no fecho:", erro)

        if MOSTRAR_NO_TERMINAL:
            try:
                print()
            except Exception:
                pass

        pular = bool(ha_outra_fala and ha_outra_fala())
        if pular and MOSTRAR_NO_TERMINAL:
            print("[revisao] pulada: voce ja comecou a falar de novo.")

        final = None
        if self.modelo_final is not None and not pular:
            final = self.reler_com_calma(fala)

        guardar_no_historico(final or limpar_transcricao(fala.digitado))

        if final:
            # O espaco que separa esta fala da anterior ja faz parte do que
            # foi escrito; o texto revisado precisa dele tambem, senao a
            # correcao acha que o comeco mudou e reescreve a frase inteira.
            separador = " " if fala.digitado.startswith(" ") else ""
            self.corrigir(fala, separador + final)

    def reler_com_calma(self, fala):
        completo = fala.audio_completo()
        if len(completo) < int(MINIMO_DE_SEGUNDOS * TAXA):
            return None
        if float(np.max(np.abs(completo))) < VOLUME_MINIMO:
            return None
        try:
            inicio = time.time()
            palavras = palavras_de(self.modelo_final, completo, feixe=5)
            texto = limpar_transcricao("".join(p["texto"] for p in palavras))
            if MOSTRAR_NO_TERMINAL and texto:
                print("[revisao em %.1fs] %s" % (time.time() - inicio, texto))
            return texto or None
        except Exception as erro:
            print("[revisao] erro ao reler:", erro)
            return None

    @staticmethod
    def onde_muda(atual, certo):
        """
        A partir de que ponto vale a pena reescrever - ou None se nao compensa.

        A conta e por PALAVRA, e nao por letra, de proposito. Letra por letra,
        um "Quero" contra "quero" no comeco da frase obrigava a apagar tudo o
        que veio depois: medido, 166 letras reescritas por uma maiuscula.
        """
        no_atual = list(re.finditer(r"\S+", atual))
        no_certo = list(re.finditer(r"\S+", certo))

        n = 0
        while (n < len(no_atual) and n < len(no_certo)
               and comparavel(no_atual[n].group()) == comparavel(no_certo[n].group())):
            n += 1

        if n < len(no_atual) or n < len(no_certo):
            # O corte fica DEPOIS da ultima palavra que combinou. Cortando no
            # comeco da palavra nova, o espaco entre as duas ficava de fora e
            # o texto saia grudado ("crie a pastanova").
            return (no_atual[n - 1].end() if n else 0,
                    no_certo[n - 1].end() if n else 0)

        # Todas as palavras batem: so vale mexer se a ULTIMA estiver
        # literalmente diferente - e o caso da pontuacao final.
        if not no_atual or not no_certo:
            return None
        if no_atual[-1].group() == no_certo[-1].group():
            return None
        return no_atual[-1].start(), no_certo[-1].start()

    def corrigir(self, fala, texto_certo):
        """
        Troca o que ESTA fala escreveu pelo texto revisado, apagando so do
        ponto que mudou para a frente.

        Duas travas, as duas por seguranca do que ja esta na tela: so mexe no
        que a propria fala escreveu, e nao mexe em nada se voce comecou a
        digitar - apagar por cima do que voce escreveu seria pior que o erro.
        """
        if not ESCREVER_NA_TELA:
            return
        if fala.usuario_digitou:
            print("[revisao] voce ja estava digitando; deixei como estava.")
            return

        atual = fala.digitado
        mudanca = self.onde_muda(atual, texto_certo)
        if mudanca is None:
            if MOSTRAR_NO_TERMINAL:
                print("[revisao] nada que valha reescrever.")
            return

        sobra = len(atual) - mudanca[0]
        acrescimo = texto_certo[mudanca[1]:]
        if not sobra and not acrescimo:
            return

        if DEVOLVER_O_FOCO:
            focar(fala.janela)

        if fala.usuario_digitou:
            print("[revisao] voce comecou a digitar; deixei como estava.")
            return

        apagar(sobra)
        escrever(acrescimo)
        # O comeco que ficou na tela e o do texto AO VIVO, nao o do revisado -
        # podem diferir numa maiuscula que nao valeu a pena reescrever.
        fala.digitado = atual[:mudanca[0]] + acrescimo
        if MOSTRAR_NO_TERMINAL:
            print("[revisao] corrigido (%d letras apagadas)." % sobra)


def trabalhador(ditado, falas, parar):
    """
    Cuida de uma fala por vez, do comeco ao fim: passadas ao vivo enquanto a
    tecla esta apertada, depois o fecho e a revisao.

    Uma por vez, sempre. Se voce comecar a falar de novo antes da revisao
    anterior terminar, a fala nova espera aqui - o microfone continua
    gravando, entao nada se perde na espera.
    """
    while not parar.is_set():
        try:
            fala = falas.get(timeout=0.3)
        except queue.Empty:
            continue

        if fala is None:
            break

        ditado.em_curso = fala
        try:
            proxima = time.time()
            while fala.gravando and not parar.is_set():
                agora = time.time()
                if agora < proxima:
                    time.sleep(min(0.05, proxima - agora))
                    continue
                ditado.passada(fala)
                # A proxima passada e marcada a partir da HORA PREVISTA, e nao
                # de agora: contando do fim do calculo, o atraso de cada
                # passada se somaria e o texto ficaria cada vez mais atras.
                proxima = max(time.time(), proxima + CADENCIA)

            ditado.finalizar(fala, ha_outra_fala=lambda: not falas.empty())
        except Exception as erro:
            print("[ao vivo] erro:", erro)
        finally:
            ditado.em_curso = None
            falas.task_done()


# =============================================================================
# 11) A METADE QUE ESCREVE  -  a tecla
# =============================================================================

MODIFICADORAS = ("ctrl", "alt", "shift", "cmd")

APELIDOS = {
    "ctrl_r": "Ctrl da direita", "ctrl_l": "Ctrl da esquerda", "ctrl": "Ctrl",
    "alt_r": "Alt da direita", "alt_l": "Alt da esquerda", "alt_gr": "AltGr",
    "shift_r": "Shift da direita", "shift_l": "Shift da esquerda",
    "cmd_r": "Windows da direita", "cmd_l": "Windows da esquerda",
    "scroll_lock": "Scroll Lock", "caps_lock": "Caps Lock",
    "pause": "Pause", "insert": "Insert", "menu": "Menu",
}


def e_modificadora(tecla):
    nome = getattr(tecla, "name", "") or ""
    return nome.split("_")[0] in MODIFICADORAS


def descobrir_tecla(nome):
    """
    Converte o nome da configuracao na tecla que o pynput entende. Aceita
    "f9", uma letra solta, ou "vk:120" para teclado que mande algo fora do
    comum (descubra o seu com --descobrir-tecla).
    """
    nome = (nome or "").strip().lower()

    if nome.startswith("vk:"):
        try:
            return keyboard.KeyCode.from_vk(int(nome[3:]))
        except ValueError:
            print("[tecla] numero invalido em '%s'; usando Ctrl da esquerda." % nome)
            return keyboard.Key.ctrl_l

    especial = getattr(keyboard.Key, nome, None)
    if especial is not None:
        return especial
    if len(nome) == 1:
        return keyboard.KeyCode.from_char(nome)
    print("[tecla] nome '%s' desconhecido; usando Ctrl da esquerda." % nome)
    return keyboard.Key.ctrl_l


def apelido_da_tecla(tecla):
    """Como chamar a tecla nas mensagens - que sao lidas em voz alta."""
    nome = getattr(tecla, "name", None)
    if nome:
        return APELIDOS.get(nome, nome.upper())
    caractere = getattr(tecla, "char", None)
    if caractere:
        return "tecla %s" % caractere.upper()
    return "a tecla numero %s" % getattr(tecla, "vk", "?")


def mesma_tecla(tecla, alvo):
    if tecla == alvo:
        return True
    try:
        return (getattr(tecla, "vk", None) is not None
                and tecla.vk == getattr(alvo, "vk", None))
    except Exception:
        return False


class ControleDeFala(object):
    """Liga e desliga a gravacao conforme a tecla."""

    def __init__(self, microfone, ditado, falas):
        self.microfone = microfone
        self.ditado = ditado
        self.falas = falas
        self.alvo = descobrir_tecla(TECLA_DE_FALA)
        self.ativo = False
        self.vigia_do_limite = None
        self.nossa_janela = nossa_propria_janela()

        # A espera de SEGUNDOS_PARA_ACIONAR e o que permite usar o Ctrl sem
        # atrapalhar atalho nenhum.
        self.apertada_em = 0.0
        self.teve_companhia = False
        self.gatilho = None

        if e_modificadora(self.alvo) and SEGUNDOS_PARA_ACIONAR <= 0:
            print("[tecla] atencao: %s e tecla de atalho e esta configurada"
                  % apelido_da_tecla(self.alvo))
            print("        para acionar na hora. Todo atalho com ela vai")
            print("        ligar o ditado. Use SEGUNDOS_PARA_ACIONAR.")

    def cancelar_gatilho(self):
        if self.gatilho is not None:
            self.gatilho.cancel()
            self.gatilho = None

    def ao_pressionar(self, tecla):
        # Teclas que nos mesmos criamos nao contam para nada: e o programa
        # digitando, nao voce.
        if evento_e_nosso():
            return

        if not mesma_tecla(tecla, self.alvo):
            self.ditado.registrar_tecla_do_usuario()
            if self.apertada_em:
                self.teve_companhia = True
                self.cancelar_gatilho()
            # Enter significa que a mensagem foi enviada e a linha esta limpa:
            # a proxima fala recomeca do zero, sem espaco na frente.
            if tecla in (keyboard.Key.enter, keyboard.Key.esc):
                self.ditado.ja_escreveu = False
            return

        # Ditado desligado: a tecla de acionar volta a ser uma tecla comum,
        # sem contagem e sem bipe. O Ctrl continua sendo Ctrl para tudo o
        # mais - inclusive era isso que ele era antes de existirmos.
        if not _ditado_ligado.is_set():
            return

        # O Windows repete o evento enquanto a tecla esta presa: so o
        # primeiro aperto conta, senao a contagem reiniciaria sem parar.
        if self.apertada_em:
            return

        self.apertada_em = time.time()
        self.teve_companhia = False
        _tecla_presa.set()

        if SEGUNDOS_PARA_ACIONAR > 0:
            self.gatilho = threading.Timer(SEGUNDOS_PARA_ACIONAR, self.acionar)
            self.gatilho.daemon = True
            self.gatilho.start()
            return

        if MODO_DE_ESCUTA == "alternar":
            self.acionar()
        else:
            self.comecar()

    def acionar(self):
        """Comeca a gravar, quando a espera na tecla se completa."""
        if SEGUNDOS_PARA_ACIONAR > 0 and (not self.apertada_em or self.teve_companhia):
            return          # soltou antes, ou veio outra tecla junto
        self.gatilho = None
        if MODO_DE_ESCUTA == "alternar":
            self.parar() if self.ativo else self.comecar()
        elif not self.ativo:
            self.comecar()

    def ao_soltar(self, tecla):
        if evento_e_nosso():
            return          # foi o programa soltando o Ctrl para escrever
        if not mesma_tecla(tecla, self.alvo):
            return

        self.cancelar_gatilho()
        self.apertada_em = 0.0
        _tecla_presa.clear()

        # No modo segurar, soltar e o fim da fala - e o melhor momento
        # possivel: a tecla acabou de sair do caminho, entao o texto que vem
        # a seguir nao corre risco de virar atalho.
        if MODO_DE_ESCUTA != "alternar" and self.ativo:
            self.parar()

    def comecar(self):
        # Rede de seguranca: a contagem de tres segundos pode ter comecado
        # antes de voce desligar o ditado, e ela dispara sozinha depois.
        if not _ditado_ligado.is_set():
            return

        janela = janela_da_frente()

        # Fora do Claude a tecla nao e nossa: ela continua valendo para o
        # programa que estiver na frente. Sai calado - um bipe a cada atalho
        # do trabalho seria um tormento.
        if not janela_e_do_claude(janela):
            if MOSTRAR_NO_TERMINAL:
                print("[tecla] ignorada: '%s' nao e o Claude."
                      % (nome_da_janela(janela) or "janela sem nome"))
            return

        if self.nossa_janela and janela == self.nossa_janela:
            print("\n[atencao] a janela do programa esta na frente; o texto")
            print("          iria para ca. Clique na janela do Claude.")
            bipar(300, 200)
            return

        self.ativo = True
        _gravando.set()
        fala = self.microfone.comecar(janela)
        bipar(880, 90)
        if MOSTRAR_NO_TERMINAL:
            print("\n[falando -> %s] " % (nome_da_janela(janela) or "janela ativa"),
                  end="", flush=True)
        self.falas.put(fala)

        self.vigia_do_limite = threading.Timer(LIMITE_DE_SEGUNDOS, self.estourou)
        self.vigia_do_limite.daemon = True
        self.vigia_do_limite.start()

    def estourou(self):
        if self.ativo:
            print("\n[limite de %d segundos atingido; encerrando a fala.]"
                  % LIMITE_DE_SEGUNDOS)
            self.parar()

    def parar(self):
        if not self.ativo:
            return
        self.ativo = False
        _gravando.clear()
        if self.vigia_do_limite is not None:
            self.vigia_do_limite.cancel()
            self.vigia_do_limite = None

        fala = self.microfone.parar()
        bipar(660, 90)

        if fala is not None and fala.duracao() < MINIMO_DE_SEGUNDOS:
            if MOSTRAR_NO_TERMINAL:
                print("(aperto curto demais)")


# =============================================================================
# 12) O LEMBRETE
# =============================================================================

def mostrar_na_tela(texto, segundos):
    """
    Faixa discreta no canto da tela, que some sozinha.

    Sem borda e sem barra de tarefas de proposito: assim ela nao rouba o foco
    de onde voce esta digitando e nao vira mais uma janela para fechar sem
    querer - erro que ja custou caro neste projeto.

    Se o tkinter nao estiver instalado, a faixa simplesmente nao aparece e o
    resto continua: e um lembrete, nao uma parte do funcionamento. Em varias
    distribuicoes ele vem separado, no pacote python3-tk.
    """
    try:
        import tkinter as tk
        raiz = tk.Tk()
        raiz.overrideredirect(True)
        raiz.attributes("-topmost", True)
        raiz.configure(bg="#202020")
        tk.Label(
            raiz, text=texto, fg="#f0f0f0", bg="#202020",
            # Uma familia generica: a fonte da Microsoft nao existe aqui, e
            # pedir uma fonte inexistente faria o Tk escolher qualquer coisa.
            font=("sans-serif", 11), padx=20, pady=14,
        ).pack()
        raiz.update_idletasks()
        largura, altura = raiz.winfo_width(), raiz.winfo_height()
        canto_x = raiz.winfo_screenwidth() - largura - 30
        canto_y = raiz.winfo_screenheight() - altura - 100
        raiz.geometry("+%d+%d" % (max(0, canto_x), max(0, canto_y)))
        raiz.after(int(segundos * 1000), raiz.destroy)
        raiz.mainloop()
    except Exception as erro:
        print("[aviso] nao consegui mostrar na tela:", erro)


def lembrar_do_ditado(fila_da_voz):
    """
    O lembrete nas duas formas. A fala entra na fila da voz, e nao numa voz
    propria: assim ela nunca sai por cima de uma resposta sendo lida.
    """
    if AVISO_NA_TELA:
        threading.Thread(
            target=mostrar_na_tela, args=(FRASE_NA_TELA, SEGUNDOS_DO_AVISO),
            daemon=True,
        ).start()
    if AVISO_FALADO and fila_da_voz is not None:
        fila_da_voz.put(FRASE_DO_LEMBRETE)


def rondar_o_claude(parar, fila_da_voz):
    """
    Fica de olho em Claude Code recem-abertos para repetir o lembrete.

    A primeira rodada so anota quem ja estava aberto: o lembrete da partida
    ja foi dado, e repeti-lo aqui seria falar duas vezes.
    """
    procurados = [p.lower() for p in PROGRAMAS_DO_CLAUDE]
    vistos = None
    while not parar.is_set():
        try:
            nomes, _filhos = _arvore_de_processos()
            agora = set(pid for pid, nome in nomes.items() if nome in procurados)
        except Exception:
            agora = set()

        if vistos is not None and (agora - vistos):
            print("[aviso] Claude Code novo detectado; lembrando do ditado.")
            lembrar_do_ditado(fila_da_voz)
        vistos = agora
        parar.wait(INTERVALO_DA_RONDA)


# =============================================================================
# 13) MODOS AUXILIARES
# =============================================================================

def listar_vozes():
    """As vozes em portugues que o espeak conhece, e o que mais esta ao alcance."""
    programa = None
    for candidato in ("espeak-ng", "espeak"):
        if tem_o_programa(candidato):
            programa = candidato
            break

    if programa is None:
        print("O espeak nao esta instalado. Sem ele nao ha vozes para listar.")
        print("Instale com um destes, conforme o seu Linux:")
        print("    sudo apt install espeak-ng          (Debian, Ubuntu)")
        print("    sudo dnf install espeak-ng          (Fedora)")
        print("    sudo pacman -S espeak-ng            (Arch)")
        return

    print("Vozes em portugues do %s:\n" % programa)
    saida = _chamar([programa, "--voices=pt"], limite=10.0)
    print(saida or "  (nenhuma; falta o pacote de dados do espeak)")

    print("\nA que este programa vai usar:  %s" % VOZ_DO_ESPEAK)
    print("Para trocar, mude VOZ_DO_ESPEAK no topo do claude_em_voz.py.")

    print("\nOutros programas de fala neste computador:")
    for nome, para_que in (("piper", "voz neural, a mais natural"),
                           ("spd-say", "a fala de acessibilidade do sistema")):
        print("  %-10s %s" % (nome, "sim - " + para_que if tem_o_programa(nome)
                              else "nao instalado"))
    if not MODELO_DO_PIPER:
        print("\nQuer uma voz bem mais natural? Instale o piper e aponte um")
        print("modelo em portugues na constante MODELO_DO_PIPER.")


# Sinais de "a saida de som esta ocupada por outro programa". Isto aparece o
# tempo todo em uso normal: rodando um teste logo depois de uma resposta
# comprida, o proprio leitor esta falando e segurando o som. Sem tratar, o
# teste despeja um erro tecnico - e quem le conclui que a voz quebrou, quando
# ela esta perfeita.
#
# Sao varias frases porque cada camada de audio reclama com as suas palavras:
# o ALSA, o PulseAudio e o PipeWire nao dizem a mesma coisa.
SINAIS_DE_SOM_OCUPADO = (
    "device or resource busy",
    "resource busy",
    "audio open error",
    "cannot open audio device",
    "connection refused",          # servidor de audio fora do ar
    "failed to create stream",
    "no such device",
)


def som_esta_ocupado(erro):
    """O erro e "a saida de som esta ocupada", e nao um defeito de verdade?"""
    texto = str(erro or "").lower()
    return any(sinal in texto for sinal in SINAIS_DE_SOM_OCUPADO)


def falar_esperando_a_vez(voz, texto, tentativas=5, espera=4.0):
    """
    Fala, e se o som estiver ocupado, espera a vez em vez de desistir.

    Quem ocupa quase sempre e o proprio leitor deste programa, falando a
    resposta anterior - entao esperar resolve sozinho em poucos segundos.
    """
    for tentativa in range(1, tentativas + 1):
        try:
            voz.falar(texto)
            return True
        except Exception as erro:
            if not som_esta_ocupado(erro):
                raise
            if tentativa == tentativas:
                return False
            if tentativa == 1:
                print("\n[voz] A saida de som esta ocupada agora - o leitor")
                print("      deve estar falando uma resposta. Isto NAO e")
                print("      defeito: vou esperar a vez.")
            print("      tentando de novo em %d s... (%d de %d)"
                  % (int(espera), tentativa, tentativas - 1))
            time.sleep(espera)
    return False


def testar_voz():
    """
    Fala tres frases seguidas de proposito: uma so nao testaria nada - o
    defeito classico deste tipo de programa aparece da segunda em diante.
    """
    voz = montar_voz()
    if voz is None:
        print("Nao consegui falar.")
        return 1

    frases = (
        "Primeira frase. O Claude em voz esta funcionando.",
        "Segunda frase. Se voce esta ouvindo isto, a fala nao emudeceu.",
        "Terceira frase. Teste concluido.",
    )

    for numero, frase in enumerate(frases, start=1):
        try:
            if falar_esperando_a_vez(voz, frase):
                continue
        except Exception as erro:
            print("\nA voz falhou na frase %d de 3:" % numero)
            print("   ", erro)
            print("\nConfira o que existe instalado com:")
            print("    python3 claude_em_voz.py --vozes")
            return 1

        print("\nO som continuou ocupado o tempo todo, entao o teste nao")
        print("chegou a acontecer. Nao ha defeito nenhum apontado ate aqui.")
        print("\nO que fazer: espere o leitor terminar de falar e rode de")
        print("novo. Se quiser silencio na hora, digite  /voz 1  na janela")
        print("do Claude Code, faca o teste, e religue com  /voz 4 .")
        return 1

    print("\nAs tres frases foram faladas.")
    print("Ouviu as TRES? Se ouviu so a primeira, e justamente o defeito que")
    print("este teste existe para pegar - a fala emudece da segunda em diante.")
    return 0


def testar_pronuncia(termos=None):
    """
    Fala cada termo do jeito escrito e do jeito corrigido, um par por vez.

    Ouvido e o unico juiz de uma tabela de pronuncia: uma grafia que parece
    obvia no papel pode sair pior que a original. Ouvindo os dois lados na
    sequencia, da para decidir em dois segundos se a troca melhorou.
    """
    voz = montar_voz()
    if voz is None:
        print("Nao consegui falar.")
        return 1

    escolhidos = [t.strip() for t in (termos or []) if t.strip()]
    tabela = ([(t, ajustar_pronuncia(t)) for t in escolhidos] if escolhidos
              else sorted(PRONUNCIAS.items()))

    if not tabela:
        print("A tabela PRONUNCIAS esta vazia; nao ha o que ouvir.")
        return 0

    print("=" * 62)
    print(" COMO CADA TERMO E FALADO")
    print("=" * 62)
    print(" Para cada um: primeiro como se escreve, depois como ficou.")
    print(" Se a segunda versao soar pior, mude a grafia em PRONUNCIAS,")
    print(" no topo do claude_em_voz.py.")
    print("-" * 62)

    for escrito, falado in tabela:
        print("  %-16s ->  %s" % (escrito, falado))
        if not falar_esperando_a_vez(voz, "Escrito: %s." % escrito):
            print("\nO som ficou ocupado o tempo todo. Espere o leitor")
            print("terminar de falar, ou digite  /voz 1  antes, e rode de novo.")
            return 1
        falar_esperando_a_vez(voz, "Falado: %s." % falado)

    print("-" * 62)
    return 0


def listar_dispositivos():
    print("Entradas de audio deste computador:\n")
    for numero, aparelho in enumerate(sd.query_devices()):
        if aparelho["max_input_channels"] > 0:
            padrao = "  <- padrao" if numero == sd.default.device[0] else ""
            print("  %d. %s%s" % (numero, aparelho["name"], padrao))
    print("\nPara fixar um deles, coloque o numero em MICROFONE, no topo.")


def descobrir_qual_tecla():
    """
    Mostra o nome e o numero de cada tecla apertada.

    Serve para teclado de notebook, onde a fileira de cima vem trocada: a
    tecla marcada F9 manda, sozinha, um comando da maquina, e so vira F9 de
    verdade com o Fn junto. Se apertar e nao aparecer nada, aquele comando e
    resolvido dentro do teclado e nunca chega ao Windows.
    """
    print("=" * 62)
    print(" DESCOBRIR A TECLA")
    print("=" * 62)
    print("Aperte as teclas que voce quer testar. Aperte ESC para sair.\n")

    vistas = []

    def ao_pressionar(tecla):
        if tecla == keyboard.Key.esc:
            return False
        nome = getattr(tecla, "name", None)
        caractere = getattr(tecla, "char", None)
        numero = getattr(tecla, "vk", None)
        if nome:
            receita = '"%s"' % nome
        elif caractere:
            receita = '"%s"' % caractere
        else:
            receita = '"vk:%s"' % numero
        print("  tecla: %-14s numero: %-6s  ->  TECLA_DE_FALA = %s"
              % (nome or caractere or "?", numero, receita))
        if receita not in vistas:
            vistas.append(receita)

    with keyboard.Listener(on_press=ao_pressionar) as ouvinte:
        ouvinte.join()

    print("\nEscreva a receita escolhida na linha TECLA_DE_FALA, no topo de")
    print("claude_em_voz.py.")
    if vistas:
        print("Teclas que apareceram: " + ", ".join(vistas))
    else:
        print("Nenhuma tecla chegou ate aqui.")


def testar_ditado(segundos=5):
    """
    Grava alguns segundos e MOSTRA o que cada reconhecedor entendeu, sem
    escrever em lugar nenhum.
    """
    vivo = carregar_modelo(MODELO_AO_VIVO)
    bom = carregar_modelo(MODELO_FINAL) if MODELO_FINAL else None

    microfone = Microfone()
    microfone.abrir()
    print("\nFale agora - gravando %d segundos..." % segundos)
    bipar(880, 90)
    microfone.comecar(None)
    time.sleep(segundos)
    fala = microfone.parar()
    bipar(660, 90)
    audio = fala.audio_completo()
    microfone.fechar()

    if len(audio) == 0:
        print("Nao veio audio nenhum do microfone.")
        return

    print("Volume maximo captado: %.4f (silencio fica perto de zero)"
          % float(np.max(np.abs(audio))))

    inicio = time.time()
    texto = limpar_transcricao("".join(p["texto"] for p in palavras_de(vivo, audio, 1)))
    print("\nAo vivo  (%s, %.1fs): %s"
          % (MODELO_AO_VIVO, time.time() - inicio, texto or "(nada reconhecivel)"))

    if bom is not None:
        inicio = time.time()
        texto = limpar_transcricao("".join(p["texto"] for p in palavras_de(bom, audio, 5)))
        print("Revisado (%s, %.1fs): %s"
              % (MODELO_FINAL, time.time() - inicio, texto or "(nada reconhecivel)"))


# =============================================================================
# 13b) O DIAGNOSTICO  -  o programa dizendo o que ha de errado com ele mesmo
# =============================================================================

# Cada gancho e reconhecido por um arquivo que so ele menciona. E por aqui que
# se descobre a armadilha mais provavel do futuro: mover a pasta do programa de
# lugar deixa os quatro ganchos apontando para o vazio, e tudo para de
# funcionar em silencio, sem nenhuma pista na tela.
GANCHOS_ESPERADOS = (
    ("SessionStart", "claude_em_voz.py", "ligar sozinho com o Claude Code"),
    ("SessionEnd", "parar.sh", "desligar sozinho ao sair"),
    ("PreToolUse", "perguntas_pendentes.jsonl",
     "falar as perguntas de escolha na hora"),
    ("UserPromptSubmit", "comando_de_voz.py", "atender o comando de voz"),
)

RE_CAMINHO_NO_GANCHO = re.compile(r'/[^"\'<>|\s]+?\.(?:py|sh)')


def caminho_comparavel(texto):
    """
    Deixa dois caminhos comparaveis.

    So colapsa barras repetidas - "/casa//ana" e "/casa/ana" sao o mesmo
    lugar. Maiuscula NAO e uniformizada, ao contrario da versao para Windows:
    aqui duas pastas podem se chamar "Voz" e "voz" e serem diferentes, e
    ignorar isso faria o diagnostico dizer que esta tudo certo quando os
    ganchos apontam para outro lugar.
    """
    return re.sub(r"/+", "/", texto or "")


class Conferencia(object):
    """Junta o que foi conferido, para a tela e para a fala."""

    def __init__(self):
        self.itens = []          # (situacao, titulo, detalhe)

    def anotar(self, situacao, titulo, detalhe=""):
        self.itens.append((situacao, titulo, detalhe))

    def ok(self, titulo, detalhe=""):
        self.anotar("ok", titulo, detalhe)

    def problema(self, titulo, detalhe=""):
        self.anotar("problema", titulo, detalhe)

    def aviso(self, titulo, detalhe=""):
        self.anotar("aviso", titulo, detalhe)

    def de(self, situacao):
        return [item for item in self.itens if item[0] == situacao]

    def mostrar(self):
        marcas = {"ok": "[x]", "problema": "[ ] PROBLEMA:", "aviso": "[!] "}
        for situacao, titulo, detalhe in self.itens:
            print(" %s %s" % (marcas[situacao], titulo))
            for linha in (detalhe or "").splitlines():
                if linha.strip():
                    print("       %s" % linha)


def _pasta_de_configuracao_do_claude():
    config = os.environ.get("CLAUDE_CONFIG_DIR")
    if config:
        return config
    casa = os.environ.get("HOME") or os.path.expanduser("~")
    return os.path.join(casa, ".claude")


def _conferir_ganchos(conferencia, pasta_do_programa):
    caminho = os.path.join(_pasta_de_configuracao_do_claude(), "settings.json")

    if not os.path.isfile(caminho):
        conferencia.problema(
            "Os ganchos nao estao instalados.",
            "Nao existe settings.json em %s\n"
            "Rode configurar_ganchos.py para criar." % caminho)
        return

    try:
        # utf-8-sig: o Bloco de Notas carimba uma marca invisivel ao salvar, e
        # sem isso um arquivo que voce so abriu para olhar pareceria corrompido.
        with open(caminho, "r", encoding="utf-8-sig") as arquivo:
            configuracao = json.load(arquivo)
    except (OSError, ValueError) as erro:
        conferencia.problema("Nao consegui ler o settings.json.",
                             "%s\n%s" % (caminho, erro))
        return

    ganchos = (configuracao or {}).get("hooks") or {}
    nosso = caminho_comparavel(pasta_do_programa)
    faltando, fora_do_lugar, sumidos = [], [], []

    for evento, marca, para_que in GANCHOS_ESPERADOS:
        comandos = []
        for entrada in ganchos.get(evento) or []:
            for gancho in (entrada or {}).get("hooks") or []:
                comando = (gancho or {}).get("command") or ""
                if marca in comando:
                    comandos.append(comando)

        if not comandos:
            faltando.append(para_que)
            continue

        for comando in comandos:
            if nosso not in caminho_comparavel(comando):
                fora_do_lugar.append(para_que)
                break
            for achado in RE_CAMINHO_NO_GANCHO.findall(comando):
                if not os.path.isfile(achado):
                    sumidos.append(achado)

    if faltando:
        conferencia.problema(
            "Faltam ganchos: %d de 4." % len(faltando),
            "Sem eles, o programa nao consegue: " + "; ".join(faltando) + ".\n"
            "Rode configurar_ganchos.py.")
    if fora_do_lugar:
        conferencia.problema(
            "Os ganchos apontam para OUTRA pasta.",
            "A pasta do programa mudou de lugar depois da instalacao.\n"
            "Isto faz tudo parar de funcionar sem nenhum aviso.\n"
            "Rode configurar_ganchos.py aqui desta pasta para corrigir.")
    if sumidos:
        conferencia.problema(
            "Um gancho aponta para arquivo que nao existe.",
            "\n".join(sorted(set(sumidos))) +
            "\nRode configurar_ganchos.py para refazer os caminhos.")

    if not (faltando or fora_do_lugar or sumidos):
        conferencia.ok("Os quatro ganchos estao instalados e apontam para ca.")

    barra = os.path.join(_pasta_de_configuracao_do_claude(), "commands", "voz.md")
    if os.path.isfile(barra):
        conferencia.ok("O comando /voz aparece na lista de comandos.")
    else:
        conferencia.aviso(
            "O /voz nao aparece na lista ao digitar a barra.",
            "Sem gravidade: digitando  voz  sem barra funciona igual.\n"
            "Para ter os dois, rode configurar_ganchos.py.")


def _conferir_voz(conferencia):
    voz = montar_voz()
    if voz is None:
        conferencia.problema(
            "Nao ha programa de fala instalado.",
            "Sem ele o programa fica mudo. Instale conforme o seu Linux:\n"
            "    sudo apt install espeak-ng          (Debian, Ubuntu)\n"
            "    sudo dnf install espeak-ng          (Fedora)\n"
            "    sudo pacman -S espeak-ng            (Arch)")
        return None

    conferencia.ok("Fala disponivel.", voz.descricao())

    if voz.motor in ("espeak-ng", "espeak"):
        vozes = _chamar([voz.motor, "--voices=pt"], limite=10.0) or ""
        if VOZ_DO_ESPEAK in vozes:
            conferencia.ok("Voz em portugues do Brasil encontrada.",
                           VOZ_DO_ESPEAK)
        else:
            conferencia.problema(
                "O espeak nao conhece a voz '%s'." % VOZ_DO_ESPEAK,
                "Falta o pacote de dados de idiomas dele:\n"
                "    sudo apt install espeak-ng-data     (Debian, Ubuntu)\n"
                "Veja as que existem com:  %s --voices=pt" % voz.motor)

        if not MODELO_DO_PIPER:
            conferencia.aviso(
                "A voz do espeak e robotica.",
                "Funciona bem, mas cansa em respostas longas. Para uma voz\n"
                "natural, instale o piper e aponte um modelo em portugues na\n"
                "constante MODELO_DO_PIPER. O PERGUNTAS_E_RESPOSTAS explica.")

    return voz


def _conferir_microfone(conferencia):
    try:
        aparelho = sd.query_devices(MICROFONE, "input")
    except Exception as erro:
        conferencia.problema("Nao achei microfone nenhum.", str(erro))
        return

    nome = aparelho.get("name", "sem nome") if isinstance(aparelho, dict) else str(aparelho)

    try:
        gravado = sd.rec(int(0.5 * TAXA), samplerate=TAXA, channels=1,
                         dtype="float32", device=MICROFONE)
        sd.wait()
    except Exception as erro:
        conferencia.problema(
            "O microfone existe, mas nao consegui abrir.",
            "%s\n%s\n"
            "Confira se o seu usuario esta no grupo de audio:\n"
            "    groups | grep audio\n"
            "Se nao estiver:  sudo usermod -aG audio $USER  e entre de novo."
            % (nome, erro))
        return

    nivel = float(np.max(np.abs(gravado))) if len(gravado) else 0.0
    if nivel <= 0.0:
        # Silencio digital perfeito nao existe em microfone ligado: ou ele
        # esta mudo no mixer, ou a entrada escolhida nao e a certa.
        conferencia.problema(
            "O microfone abriu, mas so veio silencio absoluto.",
            "%s\nIsto costuma ser o microfone mudo ou a entrada errada, e\n"
            "nao defeito. Abra o controle de volume do sistema e confira a\n"
            "aba de entrada (pavucontrol, se estiver instalado).\n"
            "Para ver as entradas que existem:\n"
            "    python3 claude_em_voz.py --dispositivos" % nome)
    else:
        conferencia.ok("Microfone respondendo.",
                       "%s (ruido de fundo: %.4f)" % (nome, nivel))


def _conferir_area_de_trabalho(conferencia):
    """
    A parte que so o Linux tem: X11 ou Wayland, e com que ferramenta digitar.

    Vale um item proprio porque e a diferenca mais importante entre uma
    maquina e outra aqui. No Wayland o sistema impede, de proposito, que um
    programa saiba qual janela esta na frente e digite nela - e o ditado
    depende das duas coisas. A leitura em voz alta nao muda em nada.
    """
    if usando_wayland():
        conferencia.aviso(
            "Voce esta numa sessao Wayland.",
            "A leitura em voz alta funciona normalmente.\n"
            "O ditado depende de escrever na janela dos outros, e o Wayland\n"
            "impede isso por seguranca. Caminhos: instalar o wtype (funciona\n"
            "no KDE e no Sway, nao no GNOME), ou entrar na sessao com X11 na\n"
            "tela de login - onde tudo funciona sem ajuste.")
    else:
        conferencia.ok("Sessao grafica X11.", os.environ.get("DISPLAY", ""))

    if tem_o_programa("xdotool"):
        conferencia.ok("xdotool instalado.",
                       "e ele que descobre a janela da frente e devolve o foco")
    elif not usando_wayland():
        conferencia.problema(
            "Falta o xdotool.",
            "Sem ele o ditado nao sabe em qual janela escrever, e a tecla\n"
            "nao consegue valer so no Claude Code.\n"
            "    sudo apt install xdotool            (Debian, Ubuntu)\n"
            "    sudo dnf install xdotool            (Fedora)\n"
            "    sudo pacman -S xdotool              (Arch)")

    modo = como_escrever()
    disponivel = (modo == "pynput") or tem_o_programa(modo)
    if disponivel:
        conferencia.ok("Da para digitar o que voce ditar.", "usando %s" % modo)
    else:
        conferencia.problema(
            "Nao ha como digitar o texto ditado.",
            "O caminho escolhido foi '%s', que nao esta instalado.\n"
            "A leitura continua funcionando; o que voce ditar so vai para o\n"
            "historico_de_voz.txt." % modo)

    # A faixa de lembrete e enfeite util, nao requisito - por isso e aviso.
    if AVISO_NA_TELA:
        try:
            import tkinter                          # noqa: F401
        except Exception:
            conferencia.aviso(
                "A faixa de lembrete na tela nao vai aparecer.",
                "Falta o tkinter, que em varias distribuicoes vem separado:\n"
                "    sudo apt install python3-tk\n"
                "Nada mais depende dele. Para nao ver este aviso, ponha\n"
                "AVISO_NA_TELA = False no topo do programa.")


def _conferir_reconhecedores(conferencia):
    for papel, tamanho in (("ao vivo", MODELO_AO_VIVO),
                           ("da revisao", MODELO_FINAL)):
        if not tamanho:
            continue
        try:
            inicio = time.time()
            carregar_modelo(tamanho)
            conferencia.ok("Reconhecedor %s carregado." % papel,
                           "%s, em %.1f s" % (tamanho, time.time() - inicio))
        except Exception as erro:
            conferencia.problema(
                "O reconhecedor %s nao carregou." % papel,
                "%s\nRode ./instalar.sh, ou:  python3 claude_em_voz.py --baixar"
                % erro)


def _conferir_claude(conferencia):
    import subprocess
    try:
        resultado = subprocess.run(["claude", "--version"], timeout=30,
                                   capture_output=True, text=True)
    except Exception:
        conferencia.aviso(
            "Nao encontrei o comando claude por aqui.",
            "Se voce usa o Claude Code normalmente, e so isto: esta janela\n"
            "nao enxerga o caminho dele. Nada a fazer.\n"
            "Este programa nao instala nem atualiza o Claude, de proposito.")
        return
    if resultado.returncode != 0:
        conferencia.aviso("O comando claude respondeu com erro.",
                          (resultado.stderr or "").strip())
        return
    conferencia.ok("Claude Code encontrado.",
                   (resultado.stdout or "").strip().splitlines()[0]
                   if (resultado.stdout or "").strip() else "")


def _conferir_estado(conferencia):
    ligado = os.path.isfile(ARQUIVO_PID)
    if ligado:
        try:
            with open(ARQUIVO_PID, "r", encoding="utf-8") as arquivo:
                numero = arquivo.read().strip()
        except OSError:
            numero = "?"
        conferencia.ok("O programa esta no ar agora.", "numero %s" % numero)
    else:
        conferencia.aviso(
            "O programa nao parece estar rodando.",
            "Abra o Claude Code, que ele sobe junto - ou ./ligar.sh.")

    estado = ler_interruptor()
    if estado is None:
        return
    leitura, ditado, _ = estado
    if leitura and ditado:
        conferencia.ok("As duas metades estao ligadas.")
    else:
        conferencia.aviso(
            "Alguma metade esta desligada agora.",
            "leitura: %s / ditado: %s\n"
            "Isto vale so para esta sessao. Digite  /voz 4  para religar."
            % ("ligada" if leitura else "DESLIGADA",
               "ligado" if ditado else "DESLIGADO"))


def _resumo_falado(conferencia):
    """A frase que ele diz em voz alta no fim."""
    problemas = conferencia.de("problema")
    avisos = conferencia.de("aviso")

    if not problemas and not avisos:
        return "Diagnóstico concluído. Está tudo certo."

    partes = []
    if problemas:
        partes.append("Diagnóstico concluído. Encontrei %s."
                      % ("um problema" if len(problemas) == 1
                         else "%d problemas" % len(problemas)))
        for _, titulo, _detalhe in problemas:
            partes.append(titulo)
        partes.append("O que fazer em cada caso está escrito na tela.")
    else:
        partes.append("Diagnóstico concluído. Nada impedindo o funcionamento.")
        partes.append("%s para você olhar na tela."
                      % ("Um aviso" if len(avisos) == 1
                         else "%d avisos" % len(avisos)))
    return " ".join(partes)


def diagnosticar():
    """
    Confere tudo de uma vez e DIZ o resultado em voz alta.

    Falado, e nao so escrito, porque este programa nao tem janela: quando algo
    para de funcionar, o caminho ate aqui era abrir o registro e ler. Um
    programa que fala deveria saber dizer o que ha de errado com ele mesmo.

    A fala vem por ultimo de proposito: se a voz for justamente o que esta
    quebrado, tudo ja esta escrito na tela quando se descobre isso.
    """
    pasta_do_programa = os.path.dirname(os.path.abspath(__file__))

    print("=" * 62)
    print(" CLAUDE EM VOZ - diagnostico")
    print("=" * 62)
    print(" Pasta do programa: %s" % pasta_do_programa)
    print(" Python:            %s" % sys.executable)
    print("-" * 62)

    conferencia = Conferencia()
    voz = _conferir_voz(conferencia)
    _conferir_microfone(conferencia)
    _conferir_area_de_trabalho(conferencia)
    _conferir_reconhecedores(conferencia)
    _conferir_ganchos(conferencia, pasta_do_programa)
    _conferir_claude(conferencia)
    _conferir_estado(conferencia)

    print()
    conferencia.mostrar()
    print("-" * 62)

    problemas = conferencia.de("problema")
    if problemas:
        print(" %d problema(s) para resolver. O que fazer esta acima."
              % len(problemas))
    else:
        print(" Nada impedindo o funcionamento.")
    print("=" * 62)

    frase = _resumo_falado(conferencia)
    if voz is not None:
        try:
            if not falar_esperando_a_vez(voz, frase):
                print("\nO som esta ocupado (o leitor deve estar falando), entao")
                print("o resumo fica so escrito - o diagnostico acima vale igual:")
                print(" ", frase)
        except Exception as erro:
            print("\n(nao consegui falar o resumo: %s)" % erro)
            print(" ", frase)
    else:
        print("\nComo a voz nao respondeu, o resumo fica so escrito:")
        print(" ", frase)

    return 1 if problemas else 0


# =============================================================================
# 14) PROGRAMA PRINCIPAL
# =============================================================================

def main():
    # As opcoes vem ANTES da conferencia de instancia unica, de proposito:
    # conferir a voz ou diagnosticar tem que funcionar com o programa ligado,
    # que e justamente quando se costuma precisar disso.
    if "--diagnostico" in sys.argv:
        return diagnosticar()
    if "--vozes" in sys.argv:
        listar_vozes()
        return
    if "--teste-voz" in sys.argv:
        testar_voz()
        return
    if "--teste-pronuncia" in sys.argv:
        # O que vier depois da opcao sao termos avulsos para ouvir; sem nada,
        # ele percorre a tabela inteira.
        depois = sys.argv[sys.argv.index("--teste-pronuncia") + 1:]
        return testar_pronuncia([t for t in depois if not t.startswith("--")])
    if "--dispositivos" in sys.argv:
        listar_dispositivos()
        return
    if "--descobrir-tecla" in sys.argv:
        descobrir_qual_tecla()
        return
    if "--teste-ditado" in sys.argv:
        testar_ditado()
        return
    if "--baixar" in sys.argv:
        carregar_modelo(MODELO_AO_VIVO)
        if MODELO_FINAL:
            carregar_modelo(MODELO_FINAL)
        print("Reconhecedores prontos. A partir de agora funciona offline.")
        return

    com_leitor = "--so-ditado" not in sys.argv
    com_ditado = "--so-leitor" not in sys.argv

    if ja_esta_rodando():
        print("O Claude em voz ja esta rodando. Este encerrou.")
        return

    registrar_pid()

    # Toda partida comeca com as duas metades ligadas. Desligar vale para o
    # momento; fechar e abrir o Claude devolve o programa inteiro.
    _leitura_ligada.set()
    _ditado_ligado.set()
    escrever_interruptor(True, True)

    parar = threading.Event()
    fila_da_voz = queue.Queue()
    threads = []

    print("=" * 62)
    print(" CLAUDE EM VOZ")
    print("=" * 62)

    # ---------- a metade que fala ----------
    if com_leitor:
        pasta = achar_pasta_sessoes()
        if not pasta:
            print("Nao encontrei a pasta de conversas do Claude Code.")
            print("Ela costuma ficar em .claude\\projects dentro do seu usuario.")
            com_leitor = False
        else:
            if FRASE_DE_ABERTURA:
                fila_da_voz.put(FRASE_DE_ABERTURA)

            vigia = VigiaDeSessoes(pasta, fila_da_voz, parar)
            vigia.preparar()

            threads.append(threading.Thread(
                target=locutor, args=(fila_da_voz, parar), daemon=True))
            threads.append(threading.Thread(target=vigia.rodar, daemon=True))

            print("Falando as respostas novas (%d conversa(s) em andamento)."
                  % len(vigia.posicoes))

            if LER_PERGUNTAS:
                caixa = VigiaDePerguntas(fila_da_voz, parar)
                threads.append(threading.Thread(target=caixa.rodar, daemon=True))
                print("As perguntas de escolha sao lidas com as opcoes,")
                print("na hora em que aparecem (pelo gancho PreToolUse).")

    # ---------- a metade que escreve ----------
    microfone = None
    ouvinte = None
    controle = None
    if com_ditado:
        modelo_vivo = carregar_modelo(MODELO_AO_VIVO)
        modelo_final = carregar_modelo(MODELO_FINAL) if MODELO_FINAL else None

        microfone = Microfone()
        try:
            microfone.abrir()
        except Exception as erro:
            print("Nao consegui abrir o microfone:", erro)
            print("Veja os disponiveis com:  --dispositivos")
            com_ditado = False

        if com_ditado:
            falas = queue.Queue()
            ditado = DitadoAoVivo(modelo_vivo, modelo_final)
            controle = ControleDeFala(microfone, ditado, falas)

            threads.append(threading.Thread(
                target=trabalhador, args=(ditado, falas, parar), daemon=True))

            apelido = apelido_da_tecla(controle.alvo)
            if SEGUNDOS_PARA_ACIONAR > 0 and MODO_DE_ESCUTA != "alternar":
                print("Segure %s. Depois de %.0f segundos sai um bipe: fale."
                      % (apelido, SEGUNDOS_PARA_ACIONAR))
                print("Solte a tecla para terminar.")
            elif SEGUNDOS_PARA_ACIONAR > 0:
                print("Segure %s por %.0f segundos ate o bipe, e fale."
                      % (apelido, SEGUNDOS_PARA_ACIONAR))
                print("Para terminar, segure de novo pelo mesmo tempo.")
            else:
                print("Tecla do ditado: %s" % apelido)
            print("Atalhos com essa tecla continuam normais: a contagem morre")
            print("assim que outra tecla e apertada.")
            if SO_NO_CLAUDE:
                print("A tecla so vale com o Claude Code na frente.")
            print("O Enter nunca e apertado sozinho: confira antes de enviar.")

            # Sem filtro de eventos: no Linux nao ha como perguntar ao evento
            # quem o criou. Quem distingue as nossas teclas das suas e o sinal
            # _estamos_escrevendo - veja evento_e_nosso().
            ouvinte = keyboard.Listener(
                on_press=controle.ao_pressionar,
                on_release=controle.ao_soltar,
            )
            ouvinte.start()

    if not com_leitor and not com_ditado:
        print("Nada para fazer. Encerrando.")
        return

    # ---------- o interruptor ----------
    interruptor = VigiaDoInterruptor(
        fila_da_voz if com_leitor else None, parar, controle)
    threads.append(threading.Thread(target=interruptor.rodar, daemon=True))
    print("Para desligar ou religar sem fechar nada, digite  voz  na janela")
    print("do Claude Code e siga o menu que aparecer.")

    if nossa_propria_janela():
        print("Ctrl+C neste terminal para encerrar (ou ./desligar.sh).")
    else:
        print("Rodando solto. Para encerrar: ./desligar.sh")
    print("=" * 62)

    for thread in threads:
        thread.start()

    # Dois bipes subindo avisam que esta pronto. Sem janela, e o unico jeito
    # de saber que subiu - e os reconhecedores demoram alguns segundos.
    bipar(700, 90)
    time.sleep(0.13)
    bipar(1000, 110)

    if com_ditado:
        time.sleep(0.4)
        lembrar_do_ditado(fila_da_voz if com_leitor else None)
        ronda = threading.Thread(
            target=rondar_o_claude,
            args=(parar, fila_da_voz if com_leitor else None), daemon=True)
        ronda.start()

    try:
        while not parar.is_set():
            time.sleep(0.5)
            if ouvinte is not None and not ouvinte.is_alive():
                break
    except KeyboardInterrupt:
        print("\nEncerrando...")
    finally:
        parar.set()
        fila_da_voz.put(None)
        if ouvinte is not None:
            try:
                ouvinte.stop()
            except Exception:
                pass
        if microfone is not None:
            microfone.fechar()
        for thread in threads:
            thread.join(timeout=3)
        print("Claude em voz encerrado.")


if __name__ == "__main__":
    # O codigo de saida importa para o --diagnostico: assim um script consegue
    # saber se achou problema, em vez de so mostrar texto na tela.
    sys.exit(main() or 0)
