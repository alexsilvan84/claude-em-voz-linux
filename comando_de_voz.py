# -*- coding: utf-8 -*-
"""
=============================================================================
 O MENU DA VOZ  -  ligar e desligar sem sair de onde voce esta
=============================================================================

Voce digita  /voz  na janela do Claude Code e aparece um menu:

    /voz       mostra como esta e o que da para fazer
    /voz 1     desliga a LEITURA  (ele para de falar as respostas)
    /voz 2     desliga o DITADO   (a tecla para de valer)
    /voz 3     desliga os dois
    /voz 4     liga os dois de volta
    /voz 5     le de novo a ultima resposta

O "voz 5" existe por um caso real: a pessoa sai da sala esperando a resposta,
o programa le para ninguem, e quando ela volta nao ha mais como ouvir. Sem
ele, so restaria pedir ao Claude que repetisse - gastando outra resposta para
dizer o mesmo. Tambem atende por "voz repetir" e "voz de novo".

Este arquivo e chamado pelo gancho UserPromptSubmit, que dispara ANTES de a
linha ser enviada. Quando a linha e um destes comandos, ele responde na tela
e ENGOLE a linha: ela nao chega ao Claude, nao vira pergunta, nao gasta nada.
Qualquer outra coisa que voce digite passa direto, sem ser tocada.

A barra tem uma segunda via, alem do gancho: o arquivo voz.md, na pasta de
comandos do Claude Code, criado por configurar_ganchos.py. Ele e o que faz o
/voz aparecer na lista ao digitar a barra - e, se algum dia o gancho nao
pegar a linha, e ele que chama este arquivo, agora passando o numero como
argumento comum em vez de pelo stdin.

O comando funciona com ou sem a barra ( /voz 1 ou voz 1 ), com ou sem acento,
com maiuscula ou sem. Isso e de proposito: quem esta ditando por voz nao tem
como garantir a pontuacao.

A escolha e anotada em interruptor.json, ao lado deste arquivo. O programa
principal vigia esse arquivo e obedece em menos de meio segundo. Vale para o
momento: quando o Claude Code for aberto de novo, tudo volta ligado.
=============================================================================
"""

import io
import os
import re
import sys
import json
import unicodedata

# O gancho manda a linha por aqui e le a resposta de volta. Sem forcar o
# utf-8, um "leitura ligada" com acento pode estourar na saida e o
# usuario ficaria sem resposta nenhuma.
for canal in ("stdin", "stdout", "stderr"):
    try:
        getattr(sys, canal).reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError, ValueError):
        pass


PASTA = os.path.dirname(os.path.abspath(__file__))
ARQUIVO_DO_INTERRUPTOR = os.path.join(PASTA, "interruptor.json")

# Codigo de saida que o Claude Code entende como "engula esta linha e mostre
# isto ao usuario". Sair com zero deixaria a linha seguir para o Claude.
ENGOLIR_A_LINHA = 2
DEIXAR_PASSAR = 0

PALAVRAS_DE_CHAMADA = ("voz", "audio", "fala")

# Este arquivo tem dois patroes. O gancho manda a linha pelo stdin e espera o
# codigo 2 para engoli-la. O comando de barra ( /voz 1 ) chama o mesmo arquivo
# como programa comum, passando o numero como argumento - e ai nao ha linha
# nenhuma para engolir: a resposta sai pelo stdout e o codigo e sempre zero.
CHAMADO_NA_MAO = len(sys.argv) > 1


def sem_enfeite(texto):
    """Minusculas, sem acento, sem barra na frente, sem espaco sobrando."""
    texto = (texto or "").strip()
    texto = texto.lstrip("/\\!.")
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(letra for letra in texto if not unicodedata.combining(letra))
    texto = texto.lower().strip()
    texto = re.sub(r"[\s,;:.!?]+", " ", texto).strip()
    return texto


def ler_o_pedido():
    """
    Pega a linha que o usuario digitou.

    O envelope do gancho pode variar de versao para versao, entao aceitamos
    o campo conhecido, alguns parentes proximos, e por fim o texto cru - e
    melhor entender demais do que ficar surdo depois de uma atualizacao.
    """
    if CHAMADO_NA_MAO:
        # Veio do comando de barra: os argumentos sao so o resto ( "1" ),
        # sem a palavra de chamada. Repomos a palavra, senao a linha nao
        # seria reconhecida como nossa.
        pedido = " ".join(sys.argv[1:]).strip()
        if sem_enfeite(pedido).split(" ")[0] not in PALAVRAS_DE_CHAMADA:
            pedido = "voz " + pedido
        return pedido

    try:
        cru = sys.stdin.read()
    except (OSError, ValueError):
        return ""
    if not cru:
        return ""
    try:
        dados = json.loads(cru)
    except ValueError:
        return cru
    if isinstance(dados, dict):
        for campo in ("prompt", "user_prompt", "userPrompt", "message", "text"):
            valor = dados.get(campo)
            if isinstance(valor, str):
                return valor
    return ""


def estado_atual():
    """Devolve (leitura, ditado, repeticoes)."""
    try:
        with io.open(ARQUIVO_DO_INTERRUPTOR, "r", encoding="utf-8") as arquivo:
            dados = json.load(arquivo)
    except (OSError, ValueError):
        return True, True, 0
    if not isinstance(dados, dict):
        return True, True, 0
    try:
        repeticoes = int(dados.get("repetir", 0))
    except (TypeError, ValueError):
        repeticoes = 0
    return (bool(dados.get("leitura", True)),
            bool(dados.get("ditado", True)),
            repeticoes)


def guardar(leitura, ditado, repeticoes):
    try:
        with io.open(ARQUIVO_DO_INTERRUPTOR, "w", encoding="utf-8") as arquivo:
            arquivo.write(json.dumps({"leitura": bool(leitura),
                                      "ditado": bool(ditado),
                                      "repetir": int(repeticoes)},
                                     ensure_ascii=False))
        return True
    except OSError:
        return False


def esta_ligado():
    """
    O programa esta no ar? Ele anota o proprio numero num arquivo ao ligar.

    Serve so para o aviso: se estiver desligado, mudar o interruptor agora
    nao adianta nada, porque a partida seguinte comeca com tudo ligado.
    """
    import tempfile
    return os.path.isfile(os.path.join(tempfile.gettempdir(),
                                       "claude_em_voz.pid"))


def como_esta(leitura, ditado):
    return ("   leitura das respostas ... %s\n"
            "   ditado pela tecla ....... %s"
            % ("LIGADA" if leitura else "desligada",
               "LIGADO" if ditado else "desligado"))


def menu(leitura, ditado):
    return (
        "\n CLAUDE EM VOZ\n"
        "\n"
        "%s\n"
        "\n"
        "   /voz 1    desligar a leitura (ele para de falar)\n"
        "   /voz 2    desligar o ditado (a tecla para de valer)\n"
        "   /voz 3    desligar os dois\n"
        "   /voz 4    ligar tudo de volta\n"
        "   /voz 5    ler de novo a ultima resposta\n"
        "\n"
        " Vale para agora. Ao abrir o Claude de novo, volta tudo ligado.\n"
        % como_esta(leitura, ditado)
    )


REPETIR = "repetir"

ESCOLHAS = {
    "1": (False, None, "Leitura desligada. Ele para de falar as respostas."),
    "2": (None, False, "Ditado desligado. A tecla volta a ser uma tecla comum."),
    "3": (False, False, "Os dois desligados."),
    "4": (True, True, "Tudo ligado de novo."),
    "desligar": (False, False, "Os dois desligados."),
    "ligar": (True, True, "Tudo ligado de novo."),
    "leitura": (False, None, "Leitura desligada. Ele para de falar as respostas."),
    "ditado": (None, False, "Ditado desligado. A tecla volta a ser uma tecla comum."),
}

# Jeitos de pedir a mesma coisa. Quem esta ditando por voz nao escolhe as
# palavras com precisao, entao vale a pena aceitar as formas naturais.
PEDIDOS_DE_REPETIR = (
    "5", "repetir", "repete", "repita", "de novo", "denovo",
    "ler de novo", "le de novo", "leia de novo", "repetir a ultima",
    "ultima", "a ultima",
)


def responder(texto):
    """Aparece na tela do Claude Code, no lugar da linha que voce digitou."""
    if CHAMADO_NA_MAO:
        # Chamado pelo comando de barra: nada a engolir, e o stderr do
        # Claude Code apareceria como se fosse erro. Sai pelo stdout e
        # termina bem.
        sys.stdout.write(texto.rstrip() + "\n")
        return DEIXAR_PASSAR
    sys.stderr.write(texto.rstrip() + "\n")
    return ENGOLIR_A_LINHA


def nao_esta_ligado():
    return ("\n O Claude em Voz nao parece estar ligado agora, entao isto\n"
            " so vai valer quando ele subir - e ele sobe com tudo ligado.\n"
            " Para liga-lo: ./ligar.sh\n")


def main():
    pedido = sem_enfeite(ler_o_pedido())
    if not pedido:
        return DEIXAR_PASSAR

    partes = pedido.split(" ")
    if partes[0] not in PALAVRAS_DE_CHAMADA:
        return DEIXAR_PASSAR        # nao e para nos; segue para o Claude

    resto = " ".join(partes[1:])
    leitura, ditado, repeticoes = estado_atual()

    if not resto:
        return responder(menu(leitura, ditado))

    # ---------- ler de novo ----------
    if resto in PEDIDOS_DE_REPETIR:
        if not leitura:
            return responder(
                "\n A leitura esta desligada, entao repetir nao adiantaria.\n"
                " Ligue com  /voz 4  e peca de novo.\n")
        if not guardar(leitura, ditado, repeticoes + 1):
            return responder("\n Nao consegui escrever o arquivo do"
                             " interruptor.\n")
        # "Pedindo", e nao "lendo": quem sabe se existe alguma resposta
        # guardada e o programa principal, nao este. Se nao houver, e ele
        # que responde, falando.
        recado = "\n Pedindo para ler a ultima resposta de novo.\n"
        if not esta_ligado():
            recado += nao_esta_ligado()
        return responder(recado)

    # ---------- ligar e desligar ----------
    escolha = ESCOLHAS.get(resto)
    if escolha is None:
        # Uma palavra so e engano de digitacao: vale mostrar o menu. Mais de
        # uma quase sempre e assunto de verdade - "a voz do Claude esta muito
        # rapida" -, e ai a linha segue intocada para o Claude. Pelo comando
        # de barra nao existe esse risco: quem digitou /voz quis o menu.
        if len(partes) == 2 or CHAMADO_NA_MAO:
            return responder(
                "\n Nao entendi \"%s\".\n%s" % (resto, menu(leitura, ditado)))
        return DEIXAR_PASSAR

    nova_leitura = leitura if escolha[0] is None else escolha[0]
    novo_ditado = ditado if escolha[1] is None else escolha[1]

    if not guardar(nova_leitura, novo_ditado, repeticoes):
        return responder(
            "\n Nao consegui escrever o arquivo do interruptor.\n"
            " Confira se a pasta do programa esta acessivel.")

    recado = "\n %s\n\n%s\n" % (escolha[2], como_esta(nova_leitura, novo_ditado))

    if not esta_ligado():
        recado += nao_esta_ligado()

    return responder(recado)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as erro:
        # Um gancho que quebra nao pode levar junto a linha do usuario: na
        # duvida, deixe passar.
        try:
            sys.stderr.write("[comando de voz] %s\n" % erro)
        except Exception:
            pass
        sys.exit(DEIXAR_PASSAR)
