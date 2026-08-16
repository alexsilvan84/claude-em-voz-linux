# -*- coding: utf-8 -*-
"""
O diagnostico, e principalmente a conferencia dos ganchos.

A armadilha que ele existe para pegar: mover a pasta do programa de lugar
deixa os quatro ganchos apontando para o vazio, e tudo para de funcionar sem
nenhum aviso na tela. Aqui se confere que ele acusa isso - e, mais dificil,
que NAO acusa quando esta tudo certo.

Aqui a comparacao de caminhos e mais simples que na versao para Windows -
nao ha barra invertida nem barra dobrada -, mas ganhou uma exigencia: no
Linux maiuscula e minuscula sao pastas DIFERENTES. Uniformizar isso, como se
faz no Windows, faria o diagnostico dizer que esta tudo certo enquanto os
ganchos apontam para outro lugar.
"""

import os
import sys
import json
import shutil
import tempfile

TITULO = "Diagnostico"

# Os arquivos que os ganchos citam. Eles precisam EXISTIR na pasta fingida,
# senao o proprio diagnostico acusa - com razao - que um gancho aponta para
# arquivo que sumiu, e o caso deixaria de testar o que se queria.
ARQUIVOS_CITADOS = ("claude_em_voz.py", "parar.sh", "comando_de_voz.py")


def montar_pasta_do_programa():
    """
    Uma pasta de mentira com os arquivos que os ganchos citam.

    O caminho sai com barra normal mesmo nesta maquina Windows, que e como
    ele seria no Linux - assim os casos abaixo conferem a mesma coisa nos
    dois lugares.
    """
    pasta = tempfile.mkdtemp(prefix="teste_programa_")
    for nome in ARQUIVOS_CITADOS:
        with open(os.path.join(pasta, nome), "w", encoding="utf-8") as arquivo:
            arquivo.write("# so para existir\n")
    return pasta.replace("\\", "/")


def ganchos_completos(pasta):
    """Um settings.json como o configurar_ganchos.py escreve de verdade."""
    python = sys.executable.replace("\\", "/")
    return {
        "hooks": {
            "PreToolUse": [{
                "matcher": "AskUserQuestion",
                "hooks": [{"type": "command", "shell": "bash",
                           "command": "{ cat; echo; } >> '%s/perguntas_pendentes.jsonl'"
                                      % pasta}],
            }],
            "SessionStart": [{
                "hooks": [{"type": "command", "shell": "bash",
                           "command": "setsid nohup '%s' -X utf8 -u "
                                      "'%s/claude_em_voz.py' &" % (python, pasta)}],
            }],
            "SessionEnd": [{
                "matcher": "logout|other",
                "hooks": [{"type": "command", "shell": "bash",
                           "command": "'%s/parar.sh'" % pasta}],
            }],
            "UserPromptSubmit": [{
                "hooks": [{"type": "command", "shell": "bash",
                           "command": "'%s' -X utf8 "
                                      "'%s/comando_de_voz.py'" % (python, pasta)}],
            }],
        }
    }


def rodar(p, comum):
    voz = comum.carregar("claude_em_voz")

    # ---------- uniformizar caminhos ----------

    igual = voz.caminho_comparavel
    p.igual("barras repetidas viram uma so",
            igual("/casa/ana//Programas///Voz"), "/casa/ana/Programas/Voz")
    p.igual("caminho ja limpo nao muda",
            igual("/casa/ana/Voz"), "/casa/ana/Voz")

    # No Linux estas sao DUAS pastas diferentes. Uniformizar a caixa, como a
    # versao para Windows faz, esconderia uma mudanca de pasta de verdade.
    p.certo("maiuscula e minuscula continuam diferentes",
            igual("/casa/ana/Voz") != igual("/casa/ana/voz"))

    p.igual("texto vazio nao quebra", igual(""), "")
    p.igual("None nao quebra", igual(None), "")

    # ---------- a conferencia dos ganchos ----------

    pasta = tempfile.mkdtemp(prefix="teste_diagnostico_")
    PASTA_FINGIDA = montar_pasta_do_programa()
    antes = os.environ.get("CLAUDE_CONFIG_DIR")
    os.environ["CLAUDE_CONFIG_DIR"] = pasta
    settings = os.path.join(pasta, "settings.json")

    def gravar(configuracao, texto=None):
        with open(settings, "w", encoding="utf-8") as arquivo:
            if texto is not None:
                arquivo.write(texto)
            else:
                json.dump(configuracao, arquivo)

    def conferir(pasta_do_programa=PASTA_FINGIDA):
        c = voz.Conferencia()
        with comum.Silencio():
            voz._conferir_ganchos(c, pasta_do_programa)
        return c

    def problemas(c):
        return " ".join(titulo for _, titulo, _d in c.de("problema"))

    try:
        # ---------- tudo certo ----------
        gravar(ganchos_completos(PASTA_FINGIDA))
        c = conferir()
        p.igual("com tudo no lugar, nenhum problema e acusado",
                problemas(c), "")
        p.certo("e ele diz que os quatro estao la",
                any("quatro ganchos" in t for _, t, _d in c.de("ok")))

        # ---------- pasta com barra repetida nao e pasta mudada ----------
        # Um caminho escrito com barra dobrada por descuido - "/casa//ana" -
        # e o mesmo lugar. Sem colapsar as barras, isto viraria um falso
        # alarme de "a pasta mudou".
        com_barras = {"hooks": {
            "SessionEnd": [{"hooks": [{
                "type": "command", "shell": "bash",
                "command": "'%s//parar.sh'" % PASTA_FINGIDA}]}]}}
        gravar(com_barras)
        c = conferir()
        p.nao_contem("barra repetida nao vira falso alarme de pasta mudada",
                     problemas(c), "OUTRA pasta")

        # ---------- a pasta mudou de lugar ----------
        gravar(ganchos_completos("/casa/ana/Antigo/ClaudeEmVozLinux"))
        c = conferir()
        p.contem("pasta mudada e acusada", problemas(c), "OUTRA pasta")
        p.certo("e explica o que fazer",
                any("configurar_ganchos" in (d or "")
                    for _s, _t, d in c.de("problema")))

        # ---------- falta um gancho ----------
        parcial = ganchos_completos(PASTA_FINGIDA)
        del parcial["hooks"]["SessionStart"]
        gravar(parcial)
        c = conferir()
        p.contem("gancho faltando e acusado", problemas(c), "Faltam ganchos")
        p.certo("dizendo o que se perde com ele",
                any("ligar sozinho" in (d or "")
                    for _s, _t, d in c.de("problema")))

        # ---------- nenhum gancho instalado ----------
        gravar({"theme": "dark"})
        c = conferir()
        p.contem("nenhum gancho instalado e acusado",
                 problemas(c), "Faltam ganchos")

        # ---------- arquivo inexistente ----------
        os.remove(settings)
        c = conferir()
        p.contem("sem settings.json ele avisa que nada foi instalado",
                 problemas(c), "nao estao instalados")

        # ---------- arquivo com defeito ----------
        gravar(None, texto='{"hooks": {,}}')
        c = conferir()
        p.contem("settings.json quebrado e acusado, sem estourar",
                 problemas(c), "Nao consegui ler")

        # ---------- o gancho aponta para arquivo que sumiu ----------
        # Acontece ao apagar ou renomear um arquivo do programa sem refazer
        # os ganchos: o caminho continua certo, mas nao ha mais nada la.
        #
        # So da para conferir no Linux: a busca pelo caminho dentro do
        # comando procura por caminhos que comecam com barra, e nesta maquina
        # Windows os caminhos comecam com a letra do disco.
        if comum.no_linux():
            gravar(ganchos_completos(PASTA_FINGIDA))
            guardado = os.path.join(PASTA_FINGIDA, "parar.sh")
            os.remove(guardado)
            c = conferir()
            p.contem("arquivo que sumiu e acusado",
                     problemas(c), "aponta para arquivo que nao existe")
            p.certo("dizendo qual arquivo",
                    any("parar.sh" in (d or "")
                        for _s, _t, d in c.de("problema")))
            with open(guardado, "w", encoding="utf-8") as arquivo:
                arquivo.write("# de volta\n")
        else:
            p.pular("arquivo que sumiu e acusado",
                    "so no Linux: aqui os caminhos nao comecam com barra")

        # ---------- o comando de barra ----------
        gravar(ganchos_completos(PASTA_FINGIDA))
        c = conferir()
        p.certo("sem o voz.md ele avisa, mas sem alarde",
                any("nao aparece na lista" in t for _, t, _d in c.de("aviso")))
        p.nao_contem("e isso nao conta como problema",
                     problemas(c), "lista")

        os.makedirs(os.path.join(pasta, "commands"), exist_ok=True)
        with open(os.path.join(pasta, "commands", "voz.md"), "w",
                  encoding="utf-8") as arquivo:
            arquivo.write("teste")
        c = conferir()
        p.certo("com o voz.md no lugar, ele reconhece",
                any("/voz aparece" in t for _, t, _d in c.de("ok")))

        # ---------- o resumo falado ----------
        c = voz.Conferencia()
        c.ok("tudo bem")
        p.contem("sem problemas, o resumo e curto",
                 voz._resumo_falado(c), "tudo certo")

        c = voz.Conferencia()
        c.problema("A voz nao respondeu.")
        c.problema("Faltam ganchos: 2 de 4.")
        frase = voz._resumo_falado(c)
        p.contem("com problemas, ele diz quantos", frase, "2 problemas")
        p.contem("e diz quais sao", frase, "A voz nao respondeu.")
        p.contem("mandando olhar a tela para saber o que fazer",
                 frase, "na tela")

        c = voz.Conferencia()
        c.aviso("O programa nao parece estar rodando.")
        frase = voz._resumo_falado(c)
        p.contem("aviso nao e problema", frase, "Nada impedindo")

    finally:
        if antes is None:
            os.environ.pop("CLAUDE_CONFIG_DIR", None)
        else:
            os.environ["CLAUDE_CONFIG_DIR"] = antes
        shutil.rmtree(pasta, ignore_errors=True)
        shutil.rmtree(PASTA_FINGIDA, ignore_errors=True)
