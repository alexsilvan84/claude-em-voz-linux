# -*- coding: utf-8 -*-
"""
O ditado ao vivo, com o trabalhador de verdade rodando numa thread.

Nada aqui depende de microfone, de reconhecedor ou de janela: o audio e
inventado, o reconhecedor e uma funcao que devolve palavras conforme o trecho
de audio que recebe - do mesmo jeito que o de verdade -, e a "tela" e um texto
na memoria onde as escritas e as apagadas sao aplicadas.

O caso que este arquivo existe para impedir e um defeito real, relatado em
uso: comecar a falar de novo enquanto a revisao da fala anterior ainda rodava
fazia a correcao cair em cima do texto da fala NOVA e apaga-lo.
"""

import time
import queue

TITULO = "Ditado ao vivo e duas falas seguidas"


class Tela(object):
    """O que estaria na linha do Claude Code."""

    def __init__(self):
        self.texto = ""

    def escrever(self, pedaco):
        self.texto += pedaco

    def apagar(self, quantidade):
        if quantidade > 0:
            self.texto = self.texto[:-quantidade]


def fabricar_audio(np, segundos, marca):
    """
    Audio de teste com uma marca de identidade no proprio sinal.

    A marca e a altura do sinal: e por ela que o reconhecedor de mentira sabe
    de qual fala aquele trecho veio, sem precisar de estado guardado - se
    precisasse, o teste deixaria de valer justamente no caso das duas falas ao
    mesmo tempo, que e o que ele existe para conferir.
    """
    return np.full(int(segundos * 16000), marca, dtype=np.float32)


class Roteiro(object):
    """
    Um reconhecedor de mentira, mas com o comportamento que importa.

    Ele devolve as palavras a partir do TRECHO de audio que recebeu, e nao de
    um contador de chamadas. Isso e o que reproduz o programa de verdade: o
    trecho aberto encolhe a cada palavra ja escrita, entao o que sobra e
    exatamente o que ainda nao foi dito.
    """

    def __init__(self, np, marca, palavras, duracao_por_palavra=0.5):
        self.np = np
        self.marca = marca
        self.palavras = palavras
        self.passo = duracao_por_palavra
        self.total = len(palavras) * duracao_por_palavra

    def combina(self, audio):
        if not len(audio):
            return False
        return abs(float(self.np.max(self.np.abs(audio))) - self.marca) < 0.01

    def responder(self, audio):
        restante = len(audio) / 16000.0
        consumido = max(0.0, self.total - restante)
        saida = []
        for numero, palavra in enumerate(self.palavras):
            inicio = numero * self.passo
            if inicio < consumido - 0.01:
                continue
            saida.append({"texto": " " + palavra,
                          "inicio": inicio - consumido,
                          "fim": inicio + self.passo - consumido})
        return saida


def rodar(p, comum):
    voz = comum.carregar("claude_em_voz")
    np = voz.np

    tela = Tela()

    # A fala ao vivo e a revisao usam reconhecedores diferentes. Aqui os dois
    # sao apenas marcas: quem responde e o roteiro, escolhido pelo audio.
    modelo_vivo = object()
    modelo_final = object()

    fala1 = Roteiro(np, 0.50, ["criar", "a", "pasta", "nova"])
    fala2 = Roteiro(np, 0.25, ["tudo", "certo"])

    # A revisao devolve a frase caprichada: mesma coisa, com ponto no fim.
    revisao = {0.50: "criar a pasta nova.", 0.25: "tudo certo."}

    def palavras_de_mentira(modelo, audio, feixe=1):
        for roteiro in (fala1, fala2):
            if not roteiro.combina(audio):
                continue
            if modelo is modelo_final:
                frase = revisao[roteiro.marca]
                return [{"texto": " " + palavra, "inicio": 0.0, "fim": 0.1}
                        for palavra in frase.split(" ")]
            return roteiro.responder(audio)
        return []

    # ---- trocar o mundo de fora pelo de mentira ----
    original = {
        "palavras_de": voz.palavras_de,
        "escrever": voz.escrever,
        "apagar": voz.apagar,
        "focar": voz.focar,
        "guardar_no_historico": voz.guardar_no_historico,
        "CADENCIA": voz.CADENCIA,
        "MOSTRAR_NO_TERMINAL": voz.MOSTRAR_NO_TERMINAL,
        "DEVOLVER_O_FOCO": voz.DEVOLVER_O_FOCO,
    }

    voz.palavras_de = palavras_de_mentira
    voz.escrever = tela.escrever
    voz.apagar = tela.apagar
    voz.focar = lambda janela: None
    voz.guardar_no_historico = lambda texto: None
    voz.CADENCIA = 0.05           # o teste nao pode levar segundos por passada
    voz.MOSTRAR_NO_TERMINAL = False
    voz.DEVOLVER_O_FOCO = False

    try:
        # O programa conta o que faz por prints, e alguns saem de dentro das
        # threads. Engolidos aqui, a lista de resultados fica legivel.
        with comum.Silencio():
            _rodar_os_casos(p, voz, np, tela, modelo_vivo, modelo_final)
    finally:
        for nome, valor in original.items():
            setattr(voz, nome, valor)


def _rodar_os_casos(p, voz, np, tela, modelo_vivo, modelo_final):

    def montar():
        ditado = voz.DitadoAoVivo(modelo_vivo, modelo_final)
        falas = queue.Queue()
        parar = voz.threading.Event()
        thread = voz.threading.Thread(
            target=voz.trabalhador, args=(ditado, falas, parar), daemon=True)
        thread.start()
        return ditado, falas, parar, thread

    def nova_fala(marca, segundos):
        # Uma LISTA de pedacos, e nao um bloco unico: e assim que o microfone
        # entrega o audio, um pedaco por vez.
        return voz.Fala([fabricar_audio(np, segundos, marca)], janela=None)

    def esperar_a_fila(falas, limite=8.0):
        fim = time.time() + limite
        while time.time() < fim:
            if falas.unfinished_tasks == 0:
                return True
            time.sleep(0.02)
        return False

    # =====================================================================
    # 1) uma fala sozinha, do comeco ao fim
    # =====================================================================
    tela.texto = ""
    ditado, falas, parar, thread = montar()

    fala = nova_fala(0.50, 2.0)
    falas.put(fala)
    time.sleep(0.35)               # deixa as passadas ao vivo acontecerem
    fala.encerrar()
    p.certo("a fala termina de ser processada", esperar_a_fila(falas))

    p.igual("a fala sozinha comeca sem espaco na frente",
            tela.texto, "criar a pasta nova.")
    p.certo("o texto ao vivo apareceu antes da revisao",
            fala.digitado.strip().startswith("criar"),
            "digitado: %r" % fala.digitado)

    # =====================================================================
    # 2) a segunda fala continua de onde a primeira parou
    # =====================================================================
    segunda = nova_fala(0.25, 1.0)
    falas.put(segunda)
    time.sleep(0.25)
    segunda.encerrar()
    p.certo("a segunda fala termina de ser processada", esperar_a_fila(falas))

    p.igual("a segunda fala continua com um espaco no meio",
            tela.texto, "criar a pasta nova. tudo certo.")
    p.certo("a segunda fala comeca com espaco",
            segunda.digitado.startswith(" "),
            "digitado: %r" % segunda.digitado)
    p.certo("a revisao da segunda nao apagou a primeira",
            tela.texto.startswith("criar a pasta nova."))

    # =====================================================================
    # 3) o Enter zera a continuacao
    # =====================================================================
    ditado.ja_escreveu = True
    ditado.ja_escreveu = False     # e o que ao_pressionar faz no Enter
    tela.texto = ""
    terceira = nova_fala(0.25, 1.0)
    falas.put(terceira)
    time.sleep(0.25)
    terceira.encerrar()
    esperar_a_fila(falas)
    p.igual("depois do Enter a fala recomeca sem espaco",
            tela.texto, "tudo certo.")

    parar.set()
    falas.put(None)
    thread.join(timeout=2)

    # =====================================================================
    # 4) o caso do defeito: falar de novo com a revisao anterior em curso
    # =====================================================================
    tela.texto = ""
    ditado, falas, parar, thread = montar()

    primeira = nova_fala(0.50, 2.0)
    falas.put(primeira)
    time.sleep(0.35)

    # A segunda entra na fila ANTES de a primeira ser finalizada: e assim que
    # a revisao da primeira encontrava a tela ja mudada pela segunda.
    seguinte = nova_fala(0.25, 1.0)
    falas.put(seguinte)
    primeira.encerrar()
    time.sleep(0.35)
    seguinte.encerrar()
    p.certo("as duas falas terminam", esperar_a_fila(falas))

    p.igual("nada foi apagado: a tela e a soma exata das duas falas",
            tela.texto, primeira.digitado + seguinte.digitado)
    p.contem("a primeira fala continua inteira na tela",
             tela.texto, "criar a pasta")
    p.contem("a segunda fala tambem esta la", tela.texto, "tudo certo")
    p.certo("a segunda fala comeca com espaco",
            seguinte.digitado.startswith(" "),
            "digitado: %r" % seguinte.digitado)

    parar.set()
    falas.put(None)
    thread.join(timeout=2)

    # =====================================================================
    # 5) a revisao nao mexe em nada se voce comecou a digitar
    # =====================================================================
    tela.texto = ""
    ditado, falas, parar, thread = montar()

    minha = nova_fala(0.50, 2.0)
    falas.put(minha)
    time.sleep(0.35)
    minha.usuario_digitou = True   # e o que registrar_tecla_do_usuario faz
    minha.encerrar()
    esperar_a_fila(falas)

    p.certo("com o usuario digitando, a revisao nao apaga nada",
            "." not in tela.texto,
            "tela: %r" % tela.texto)
    p.contem("o que a fala escreveu continua la", tela.texto, "criar a pasta")

    parar.set()
    falas.put(None)
    thread.join(timeout=2)

    # =====================================================================
    # 6) o acordo local: so escreve o que ja esta firme
    # =====================================================================
    ditado = voz.DitadoAoVivo(modelo_vivo, modelo_final)
    ditado.ja_escreveu = False
    fala = nova_fala(0.50, 2.0)

    with comum_silencio(voz):
        ditado.passada(fala)
    p.igual("a primeira passada nao escreve nada", fala.digitado, "")
    p.certo("mas ja guardou a hipotese", len(fala.hipotese) == 4)

    with comum_silencio(voz):
        ditado.passada(fala)
    p.igual("na segunda passada saem as palavras que se repetiram",
            fala.digitado, "criar a pasta")
    p.certo("a ultima palavra fica esperando: pode estar cortada no meio",
            "nova" not in fala.digitado)
    p.certo("o audio ja escrito e jogado fora",
            len(fala.trecho_aberto()) < 16000,
            "sobraram %d amostras" % len(fala.trecho_aberto()))


def comum_silencio(voz):
    """Atalho para engolir os prints do programa dentro de um bloco."""
    import comum
    return comum.Silencio()
