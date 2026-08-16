# -*- coding: utf-8 -*-
"""
O comando de voz: o que vira menu e o que segue para o Claude.

Este e o unico pedaco do projeto que pode COMER uma linha que voce escreveu.
Se ele exagerar, uma pergunta de verdade some sem explicacao; se faltar, a
palavra "voz" vira conversa e gasta uma resposta. Cada caso aqui e um lado
dessa fronteira.

Roda contra um interruptor temporario: o do programa de verdade nao e tocado.
"""

import os
import json
import shutil
import tempfile

TITULO = "O comando de voz (interruptor)"


def rodar(p, comum):
    menu = comum.carregar("comando_de_voz")

    pasta = tempfile.mkdtemp(prefix="teste_interruptor_")
    original_arquivo = menu.ARQUIVO_DO_INTERRUPTOR
    original_na_mao = menu.CHAMADO_NA_MAO
    original_pedido = menu.ler_o_pedido
    original_ligado = menu.esta_ligado

    menu.ARQUIVO_DO_INTERRUPTOR = os.path.join(pasta, "interruptor.json")
    menu.CHAMADO_NA_MAO = False           # o modo do gancho, que e o de sempre
    menu.esta_ligado = lambda: True       # senao toda resposta ganha um aviso

    def digitar(linha):
        """Faz de conta que voce digitou esta linha e devolve (codigo, tela)."""
        menu.ler_o_pedido = lambda: linha
        with comum.Silencio() as silencio:
            codigo = menu.main()
        return codigo, silencio.texto

    def estado():
        with open(menu.ARQUIVO_DO_INTERRUPTOR, encoding="utf-8") as arquivo:
            return json.load(arquivo)

    try:
        ENGOLIR, PASSAR = menu.ENGOLIR_A_LINHA, menu.DEIXAR_PASSAR

        # ---------- o menu ----------
        codigo, tela = digitar("voz")
        p.igual("a palavra sozinha mostra o menu e some da linha",
                codigo, ENGOLIR)
        p.contem("o menu diz como esta a leitura", tela, "leitura das respostas")
        p.contem("o menu diz como esta o ditado", tela, "ditado pela tecla")

        # ---------- desligar e ligar ----------
        codigo, tela = digitar("voz 1")
        p.igual("desligar a leitura engole a linha", codigo, ENGOLIR)
        p.igual("a leitura fica desligada no arquivo",
                estado()["leitura"], False)
        p.igual("o ditado continua ligado", estado()["ditado"], True)

        codigo, tela = digitar("voz 2")
        p.igual("desligar o ditado nao religa a leitura",
                estado()["leitura"], False)
        p.igual("o ditado fica desligado", estado()["ditado"], False)

        codigo, tela = digitar("voz 4")
        p.igual("ligar tudo devolve a leitura", estado()["leitura"], True)
        p.igual("ligar tudo devolve o ditado", estado()["ditado"], True)

        digitar("voz 3")
        p.certo("desligar os dois de uma vez",
                estado()["leitura"] is False and estado()["ditado"] is False)
        digitar("voz 4")

        # ---------- os apelidos, para quem esta ditando por voz ----------
        digitar("voz desligar")
        p.igual("a palavra desligar tambem vale", estado()["leitura"], False)
        digitar("voz ligar")
        p.igual("a palavra ligar tambem vale", estado()["leitura"], True)

        # ---------- barra, maiuscula e acento ----------
        codigo, tela = digitar("/voz 1")
        p.igual("com barra na frente funciona igual", codigo, ENGOLIR)
        p.igual("e realmente desliga", estado()["leitura"], False)
        digitar("voz 4")

        codigo, tela = digitar("VOZ 1")
        p.igual("maiuscula nao atrapalha", codigo, ENGOLIR)
        digitar("voz 4")

        codigo, tela = digitar("vóz 1")
        p.igual("acento errado nao atrapalha", codigo, ENGOLIR)
        digitar("voz 4")

        # ---------- ler de novo ----------
        antes = estado().get("repetir", 0)
        codigo, tela = digitar("voz 5")
        p.igual("pedir para reler engole a linha", codigo, ENGOLIR)
        p.igual("o pedido de reler e contado", estado()["repetir"], antes + 1)

        codigo, tela = digitar("voz de novo")
        p.igual("pedir 'de novo' tambem vale", codigo, ENGOLIR)
        p.igual("dois pedidos seguidos contam duas vezes",
                estado()["repetir"], antes + 2)

        digitar("voz 1")                       # leitura desligada
        antes = estado().get("repetir", 0)
        codigo, tela = digitar("voz 5")
        p.contem("com a leitura desligada ele recusa e explica",
                 tela, "repetir nao adiantaria")
        p.igual("e nao conta o pedido", estado().get("repetir", 0), antes)
        digitar("voz 4")

        # ---------- o que NAO pode ser engolido ----------
        codigo, tela = digitar("voz do Claude muito rapida")
        p.igual("frase de verdade comecando com voz segue para o Claude",
                codigo, PASSAR)

        codigo, tela = digitar("como faco para mudar a voz do programa")
        p.igual("pergunta comum segue intocada", codigo, PASSAR)

        codigo, tela = digitar("crie uma pasta nova")
        p.igual("linha sem a palavra de chamada segue intocada",
                codigo, PASSAR)

        codigo, tela = digitar("")
        p.igual("linha vazia segue intocada", codigo, PASSAR)

        # ---------- engano de digitacao ----------
        codigo, tela = digitar("voz xis")
        p.igual("uma palavra desconhecida so mostra o menu", codigo, ENGOLIR)
        p.contem("e avisa que nao entendeu", tela, "entendi")

        # ---------- numero solto nunca e comando ----------
        codigo, tela = digitar("1")
        p.igual("um numero sozinho nao e comando nenhum", codigo, PASSAR)

        # ---------- o interruptor comeca inteiro ----------
        p.certo("o arquivo do interruptor e um JSON valido",
                isinstance(estado(), dict))

    finally:
        menu.ARQUIVO_DO_INTERRUPTOR = original_arquivo
        menu.CHAMADO_NA_MAO = original_na_mao
        menu.ler_o_pedido = original_pedido
        menu.esta_ligado = original_ligado
        shutil.rmtree(pasta, ignore_errors=True)
