# -*- coding: utf-8 -*-
"""
A camada que encosta no sistema - a unica parte que difere da versao Windows.

Nem tudo aqui da para conferir fora do Linux: ler a arvore de processos em
/proc, digitar pelo xdotool e falar pelo espeak so acontecem la. O que se
protege aqui e a DECISAO: como o programa reconhece o Claude Code entre os
processos, e por qual caminho ele escolhe digitar. Sao justamente as duas
escolhas que, erradas, deixam o ditado sem funcionar sem dizer por que.
"""

import os

TITULO = "A camada do sistema (Linux)"


def rodar(p, comum):
    voz = comum.carregar("claude_em_voz")

    # =====================================================================
    # Reconhecer o Claude Code entre os processos
    # =====================================================================
    # No Linux ele costuma rodar como "node", com o caminho do claude na
    # linha de comando: procurar so pelo nome do processo nao acharia nada.
    e_o_claude = voz._e_o_claude
    procurados = ["claude"]

    p.certo("o processo chamado claude e reconhecido",
            e_o_claude(("claude", "claude"), procurados))

    p.certo("o claude rodando por node tambem e reconhecido",
            e_o_claude(("node", "node /casa/ana/.local/bin/claude"), procurados))

    p.certo("com argumentos depois, idem",
            e_o_claude(("node", "node /usr/lib/claude/cli.js --resume"),
                       ["claude"]))

    # Instalado por npm, a pasta do pacote se chama claude-code.
    p.certo("a pasta claude-code do pacote npm tambem conta",
            e_o_claude(("node", "node /casa/ana/node_modules/@anthropic-ai/"
                                "claude-code/cli.js"), procurados))

    # A busca e pelo CAMINHO, e nao pela palavra solta: uma pasta que por
    # acaso se chame claude nao pode transformar qualquer programa no Claude.
    p.certo("uma pasta chamada claude nao engana",
            not e_o_claude(("firefox", "firefox /casa/ana/claudeteca/x.html"),
                           procurados))

    p.certo("um editor com a palavra no texto nao engana",
            not e_o_claude(("gedit", "gedit anotacoes-sobre-claude.txt"),
                           procurados))

    p.certo("processo comum nao e confundido",
            not e_o_claude(("bash", "bash"), procurados))

    p.certo("processo sem linha de comando nao quebra",
            not e_o_claude(("kworker", ""), procurados))

    # =====================================================================
    # X11 ou Wayland
    # =====================================================================
    guardado = {nome: os.environ.get(nome)
                for nome in ("WAYLAND_DISPLAY", "DISPLAY")}

    def ambiente(wayland, x11):
        for nome, valor in (("WAYLAND_DISPLAY", wayland), ("DISPLAY", x11)):
            if valor is None:
                os.environ.pop(nome, None)
            else:
                os.environ[nome] = valor

    try:
        ambiente("wayland-0", None)
        p.certo("sessao Wayland e reconhecida", voz.usando_wayland())

        ambiente(None, ":0")
        p.certo("sessao X11 nao e confundida com Wayland",
                not voz.usando_wayland())

        # Com as duas variaveis, o X11 esta disponivel por compatibilidade
        # (XWayland) e e por ele que tudo funciona: nao vale tratar como
        # Wayland puro, senao o programa desistiria de algo que funciona.
        ambiente("wayland-0", ":0")
        p.certo("Wayland com XWayland conta como X11",
                not voz.usando_wayland())

        ambiente(None, None)
        p.certo("sem area grafica nenhuma, nao e Wayland",
                not voz.usando_wayland())

        # =================================================================
        # Por qual caminho digitar
        # =================================================================
        antes_modo = voz.COMO_ESCREVER
        try:
            voz.COMO_ESCREVER = "xdotool"
            p.igual("um caminho escolhido a mao e respeitado",
                    voz.escolher_como_escrever(), "xdotool")

            voz.COMO_ESCREVER = "auto"
            ambiente(None, ":0")
            p.certo("no X11 ele escolhe um caminho que serve la",
                    voz.escolher_como_escrever() in ("pynput", "xdotool"))

            ambiente("wayland-0", None)
            escolhido = voz.escolher_como_escrever()
            p.certo("no Wayland ele nao escolhe o pynput sem motivo",
                    escolhido in ("wtype", "ydotool", "pynput"))
            if voz.tem_o_programa("wtype"):
                p.igual("havendo wtype, e ele que vale no Wayland",
                        escolhido, "wtype")
        finally:
            voz.COMO_ESCREVER = antes_modo
    finally:
        for nome, valor in guardado.items():
            if valor is None:
                os.environ.pop(nome, None)
            else:
                os.environ[nome] = valor
        voz._como_escrever = None      # a escolha e refeita na proxima vez

    # =====================================================================
    # Os ganchos que o diagnostico procura
    # =====================================================================
    eventos = dict((evento, marca)
                   for evento, marca, _para_que in voz.GANCHOS_ESPERADOS)
    p.igual("o gancho de desligar procura o parar.sh, e nao um .bat",
            eventos.get("SessionEnd"), "parar.sh")
    p.igual("o de ligar procura o programa",
            eventos.get("SessionStart"), "claude_em_voz.py")
    p.igual("sao quatro ganchos", len(voz.GANCHOS_ESPERADOS), 4)

    # =====================================================================
    # O que so da para conferir no Linux
    # =====================================================================
    if comum.no_linux():
        nomes, filhos = voz._arvore_de_processos()
        p.certo("a arvore de processos e lida", len(nomes) > 0)
        p.certo("este proprio programa aparece nela", os.getpid() in nomes)
        eu = nomes.get(os.getpid(), ("", ""))
        p.contem("com o nome certo", eu[0], "python")
        p.certo("e com a linha de comando junto", "testar" in eu[1])
    else:
        p.pular("a arvore de processos e lida",
                "so no Linux: depende da pasta /proc")

    p.certo("procurar um programa inexistente devolve nao",
            not voz.tem_o_programa("programa-que-nao-existe-mesmo"))
