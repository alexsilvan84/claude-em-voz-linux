# -*- coding: utf-8 -*-
"""
"O som esta ocupado" nao pode parecer "a voz quebrou" - e falhar em silencio
e pior ainda.

O primeiro caso aconteceu de verdade na versao para Windows: o usuario pediu um
teste de voz logo depois de uma resposta comprida, o proprio leitor estava
falando e segurando a saida de som, e o teste despejou um erro tecnico. A voz
estava perfeita - mas quem lesse aquilo iria procurar defeito onde nao havia.

O segundo caso e proprio daqui: a fala sai por um programa de fora, e a
reclamacao dele era jogada fora. Um espeak que nao conseguisse abrir o som
falharia calado - o programa acharia que falou, o registro diria "falando", e
nao sairia som nenhum. Este arquivo protege as duas coisas.
"""

TITULO = "Som ocupado, e falha que nao pode ser calada"


class VozQueRecusa(object):
    """Uma voz que diz "som ocupado" nas primeiras vezes e depois fala."""

    def __init__(self, recusas, erro):
        self.faltam = recusas
        self.erro = erro
        self.falou = []

    def falar(self, texto, desistir_se=None):
        if self.faltam > 0:
            self.faltam -= 1
            raise self.erro
        self.falou.append(texto)


class ProcessoFalso(object):
    """Imita o programa de fala: um codigo de saida e uma reclamacao."""

    def __init__(self, codigo, reclamacao=b""):
        self.codigo = codigo
        self.stderr = _Leitura(reclamacao)
        self.pid = 424242

    def poll(self):
        return self.codigo


class _Leitura(object):
    def __init__(self, dados):
        self.dados = dados

    def read(self):
        return self.dados


def rodar(p, comum):
    voz = comum.carregar("claude_em_voz")

    # =====================================================================
    # Reconhecer "som ocupado" entre as varias formas de reclamar
    # =====================================================================
    # Cada camada de audio do Linux diz a sua: o ALSA, o PulseAudio e o
    # PipeWire nao usam as mesmas palavras.
    for reclamacao in (
            "ALSA lib pcm.c: Device or resource busy",
            "audio open error: Device or resource busy",
            "cannot open audio device",
            "Connection refused",
            "pw-play: failed to create stream"):
        p.certo("reconhece: %s" % reclamacao[:34],
                voz.som_esta_ocupado(RuntimeError(reclamacao)))

    # ---------- o que NAO pode ser confundido ----------

    p.certo("voz inexistente nao e som ocupado",
            not voz.som_esta_ocupado(
                RuntimeError("espeak-ng: unknown voice 'pt-br'")))

    p.certo("erro comum nao e som ocupado",
            not voz.som_esta_ocupado(ValueError("qualquer outra coisa")))

    p.certo("erro vazio nao quebra a conferencia",
            not voz.som_esta_ocupado(Exception()))

    p.certo("None nao quebra", not voz.som_esta_ocupado(None))

    # =====================================================================
    # Esperar a vez
    # =====================================================================
    ocupado = RuntimeError("audio open error: Device or resource busy")

    falsa = VozQueRecusa(recusas=2, erro=ocupado)
    with comum.Silencio():
        deu_certo = voz.falar_esperando_a_vez(falsa, "oi", tentativas=5,
                                              espera=0.01)
    p.certo("depois de o som liberar, a frase e falada", deu_certo)
    p.igual("e falada uma vez so", falsa.falou, ["oi"])

    teimosa = VozQueRecusa(recusas=99, erro=ocupado)
    with comum.Silencio() as silencio:
        deu_certo = voz.falar_esperando_a_vez(teimosa, "oi", tentativas=3,
                                              espera=0.01)
    p.certo("som ocupado o tempo todo devolve falso, sem estourar",
            deu_certo is False)
    p.contem("e o programa explica que nao e defeito",
             silencio.texto, "NAO e")

    # Esta e a parte que mantem o conserto honesto: engolir todo erro faria a
    # voz quebrada passar por "som ocupado", e o teste nunca acusaria nada.
    quebrada = VozQueRecusa(recusas=99,
                            erro=RuntimeError("espeak-ng: unknown voice"))
    estourou = False
    try:
        with comum.Silencio():
            voz.falar_esperando_a_vez(quebrada, "oi", tentativas=3, espera=0.01)
    except Exception:
        estourou = True
    p.certo("erro de verdade continua subindo, e nao vira espera", estourou)

    # =====================================================================
    # A fala nao pode falhar calada
    # =====================================================================
    # Este e o defeito proprio desta versao: o programa de fala termina com
    # erro e ninguem fica sabendo. Silencio sem explicacao e o pior modo de
    # falhar num programa cuja unica funcao e falar.
    falador = voz.VozDoLinux.__new__(voz.VozDoLinux)
    falador.motor = "espeak-ng"
    falador.calamos = False
    falador.processo = None

    estourou = False
    try:
        falador._conferir_o_fim(
            ProcessoFalso(1, b"audio open error: Device or resource busy"), 1)
    except Exception as erro:
        estourou = True
        p.contem("o erro carrega o que o programa de fala reclamou",
                 str(erro), "Device or resource busy")
        p.certo("e esse erro e reconhecido como som ocupado",
                voz.som_esta_ocupado(erro))
    p.certo("terminar com erro levanta aviso, e nao passa calado", estourou)

    # Terminar bem nao pode virar erro.
    deu_erro = False
    try:
        falador._conferir_o_fim(ProcessoFalso(0), 0)
    except Exception:
        deu_erro = True
    p.certo("terminar bem nao levanta nada", not deu_erro)

    # E quando fomos NOS que encerramos - o usuario digitou /voz 1 no meio da
    # frase -, o fim brusco e esperado: nao e defeito nenhum.
    falador.calamos = True
    deu_erro = False
    try:
        falador._conferir_o_fim(ProcessoFalso(-15), -15)
    except Exception:
        deu_erro = True
    p.certo("calar a fala de proposito nao vira erro", not deu_erro)
