# -*- coding: utf-8 -*-
"""
A tecla: acionar de proposito, nunca por acidente.

O Ctrl da esquerda tinha que continuar servindo de tecla de atalho. A saida
foi exigir que ela fique presa TRES SEGUNDOS SOZINHA - gesto que ninguem faz
sem querer. Cada caso abaixo e um jeito de encostar nessa tecla, e o que se
confere e se a gravacao comecou ou nao.

Nada de microfone nem de reconhecedor: o controle e montado a mao e as duas
pontas que interessam - comecar e parar - viram anotadores.
"""

import time

TITULO = "A tecla de falar"

ESPERA = 0.06          # o lugar dos 3 segundos, para o teste nao demorar
FOLGA = 0.10           # tempo de sobra para o gatilho disparar


class Anotador(object):
    """Um ControleDeFala com comecar e parar trocados por anotacoes."""

    def __init__(self, voz):
        self.voz = voz
        self.comecos = 0
        self.paradas = 0

        controle = voz.ControleDeFala.__new__(voz.ControleDeFala)
        controle.microfone = None
        controle.ditado = self
        controle.falas = None
        controle.alvo = voz.descobrir_tecla("ctrl_l")
        controle.ativo = False
        controle.vigia_do_limite = None
        controle.nossa_janela = None
        controle.apertada_em = 0.0
        controle.teve_companhia = False
        controle.gatilho = None
        controle.comecar = self._comecar
        controle.parar = self._parar
        self.controle = controle

        # A metade do ditado que o controle chama: aqui so precisa existir.
        self.ja_escreveu = False
        self.teclas_do_usuario = 0

    # ---- o que o ControleDeFala espera de um DitadoAoVivo ----
    def registrar_tecla_do_usuario(self):
        self.teclas_do_usuario += 1

    # ---- as duas pontas que este teste observa ----
    def _comecar(self):
        if not self.voz._ditado_ligado.is_set():
            return                      # a mesma trava do programa de verdade
        self.comecos += 1
        self.controle.ativo = True

    def _parar(self):
        if not self.controle.ativo:
            return
        self.controle.ativo = False
        self.paradas += 1

    # ---- atalhos para escrever os casos ----
    def apertar(self, tecla):
        self.controle.ao_pressionar(tecla)

    def soltar(self, tecla):
        self.controle.ao_soltar(tecla)


def rodar(p, comum):
    voz = comum.carregar("claude_em_voz")
    teclado = voz.keyboard

    CTRL = teclado.Key.ctrl_l
    LETRA_C = teclado.KeyCode.from_char("c")
    ALT_GR = teclado.Key.alt_gr
    ENTER = teclado.Key.enter

    original_espera = voz.SEGUNDOS_PARA_ACIONAR
    original_modo = voz.MODO_DE_ESCUTA
    voz.SEGUNDOS_PARA_ACIONAR = ESPERA
    voz.MODO_DE_ESCUTA = "segurar"
    voz._ditado_ligado.set()

    try:
        with comum.Silencio():
            _casos(p, voz, CTRL, LETRA_C, ALT_GR, ENTER)
    finally:
        voz.SEGUNDOS_PARA_ACIONAR = original_espera
        voz.MODO_DE_ESCUTA = original_modo
        voz._ditado_ligado.set()
        voz._tecla_presa.clear()
        voz._estamos_escrevendo.clear()


def _casos(p, voz, CTRL, LETRA_C, ALT_GR, ENTER):

    def novo():
        # Cada caso ganha um controle proprio: aproveitar o mesmo faria um
        # caso herdar a contagem do anterior e o resultado deixaria de valer.
        voz._tecla_presa.clear()
        return Anotador(voz)

    # ---------- segurar sozinha: e o gesto de propósito ----------
    a = novo()
    a.apertar(CTRL)
    time.sleep(ESPERA + FOLGA)
    p.igual("segurar a tecla sozinha comeca a gravar", a.comecos, 1)
    a.soltar(CTRL)
    p.igual("soltar encerra a fala", a.paradas, 1)

    # ---------- toque rapido: nao e gesto de proposito ----------
    a = novo()
    a.apertar(CTRL)
    a.soltar(CTRL)
    time.sleep(ESPERA + FOLGA)
    p.igual("um toque rapido nao aciona nada", a.comecos, 0)

    # ---------- Ctrl+C rapido ----------
    a = novo()
    a.apertar(CTRL)
    a.apertar(LETRA_C)
    a.soltar(LETRA_C)
    a.soltar(CTRL)
    time.sleep(ESPERA + FOLGA)
    p.igual("Ctrl+C continua sendo Ctrl+C", a.comecos, 0)

    # ---------- Ctrl+C com a outra tecla chegando quase no fim ----------
    # E o caso apertado: a contagem ja esta terminando quando o C chega.
    a = novo()
    a.apertar(CTRL)
    time.sleep(ESPERA * 0.8)
    a.apertar(LETRA_C)
    time.sleep(ESPERA + FOLGA)
    p.igual("outra tecla no fim da contagem ainda cancela", a.comecos, 0)
    a.soltar(LETRA_C)
    a.soltar(CTRL)

    # ---------- AltGr, que no teclado brasileiro manda um Ctrl junto ----------
    a = novo()
    a.apertar(CTRL)
    a.apertar(ALT_GR)
    time.sleep(ESPERA + FOLGA)
    p.igual("AltGr nao liga o ditado", a.comecos, 0)
    a.soltar(ALT_GR)
    a.soltar(CTRL)

    # ---------- autorrepeticao do Windows ----------
    # Com a tecla presa, o Windows manda o mesmo aperto varias vezes; se cada
    # um reiniciasse a contagem, ela nunca fecharia.
    a = novo()
    for _ in range(12):
        a.apertar(CTRL)
        time.sleep(ESPERA / 8.0)
    time.sleep(ESPERA + FOLGA)
    p.igual("a tecla repetindo aciona uma vez so", a.comecos, 1)
    a.soltar(CTRL)

    # ---------- atalho com o ditado JA gravando ----------
    a = novo()
    a.apertar(CTRL)
    time.sleep(ESPERA + FOLGA)
    p.igual("gravando", a.comecos, 1)
    a.apertar(LETRA_C)             # um Ctrl+C no meio da fala
    a.soltar(LETRA_C)
    p.igual("um atalho no meio da fala nao encerra a gravacao", a.paradas, 0)
    a.soltar(CTRL)
    p.igual("quem encerra a fala e soltar a tecla", a.paradas, 1)

    # ---------- o ditado desligado pelo /voz 2 ----------
    a = novo()
    voz._ditado_ligado.clear()
    a.apertar(CTRL)
    time.sleep(ESPERA + FOLGA)
    p.igual("com o ditado desligado a tecla nao faz nada", a.comecos, 0)
    a.soltar(CTRL)
    voz._ditado_ligado.set()

    # A contagem pode ter comecado ANTES de o ditado ser desligado, e o
    # gatilho dispara sozinho depois. Por isso a trava esta nos dois lugares.
    a = novo()
    a.apertar(CTRL)
    voz._ditado_ligado.clear()
    time.sleep(ESPERA + FOLGA)
    p.igual("desligar no meio da contagem tambem impede a gravacao",
            a.comecos, 0)
    a.soltar(CTRL)
    voz._ditado_ligado.set()

    # ---------- o Enter zera a continuacao entre falas ----------
    a = novo()
    a.ja_escreveu = True
    a.apertar(ENTER)
    p.certo("o Enter avisa que a linha foi enviada", not a.ja_escreveu)

    a.ja_escreveu = True
    a.apertar(LETRA_C)
    p.certo("uma letra qualquer nao zera a continuacao", a.ja_escreveu)
    p.certo("mas conta como voce digitando", a.teclas_do_usuario > 0)

    # ---------- o modo alternar, para quem preferir ----------
    voz.MODO_DE_ESCUTA = "alternar"
    a = novo()
    a.apertar(CTRL)
    time.sleep(ESPERA + FOLGA)
    p.igual("no modo alternar, segurar liga", a.comecos, 1)
    a.soltar(CTRL)
    p.igual("no modo alternar, soltar nao desliga", a.paradas, 0)
    a.apertar(CTRL)
    time.sleep(ESPERA + FOLGA)
    p.igual("segurar de novo e o que desliga", a.paradas, 1)
    a.soltar(CTRL)
    voz.MODO_DE_ESCUTA = "segurar"

    # ---------- eventos que nos mesmos criamos ----------
    # Ao escrever, o programa avisa o sistema que o Ctrl esta solto - senao
    # cada letra viraria atalho. So que ele tambem ESCUTA o teclado. Se
    # ouvisse o proprio aviso, encerraria a fala na primeira leva de palavras,
    # e falas longas parariam no meio.
    #
    # No Linux nao ha como perguntar ao evento quem o criou, entao o que
    # distingue e o sinal ligado enquanto escrevemos. E ele que se confere
    # aqui.
    a = novo()
    a.apertar(CTRL)
    time.sleep(ESPERA + FOLGA)
    p.igual("gravando antes de escrever", a.comecos, 1)

    voz._estamos_escrevendo.set()      # e o que escrever() faz
    a.soltar(CTRL)
    p.igual("o programa nao se encerra ao soltar o proprio Ctrl", a.paradas, 0)

    voz._estamos_escrevendo.clear()
    a.soltar(CTRL)
    p.igual("mas obedece quando quem solta e voce", a.paradas, 1)

    # E a volta: uma tecla sua que chegue enquanto escrevemos tambem e
    # ignorada. E o preco de nao ter a marca do sistema - documentado, e
    # pequeno: sao os 50 ms de folga no fim de cada escrita.
    a = novo()
    voz._estamos_escrevendo.set()
    a.apertar(CTRL)
    time.sleep(ESPERA + FOLGA)
    p.igual("tecla apertada enquanto escrevemos nao aciona nada", a.comecos, 0)
    voz._estamos_escrevendo.clear()
    a.soltar(CTRL)
