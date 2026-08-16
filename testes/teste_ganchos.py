# -*- coding: utf-8 -*-
"""
Os ganchos: instalar sem estragar o que ja estava la.

O settings.json do Claude Code nao e nosso - guarda tema, permissoes e o que
mais a pessoa tiver configurado. Escrever nele e a parte da instalacao que
pode causar prejuizo de verdade, e por isso os casos aqui sao quase todos
sobre NAO estragar: preservar o alheio, nao duplicar ao rodar de novo, e
desistir sem escrever quando o arquivo esta com defeito.

Tudo acontece numa pasta temporaria, apontada pela variavel de ambiente que o
proprio programa respeita. O settings.json de verdade nao e tocado.
"""

import os
import io
import sys
import json
import shutil
import tempfile

TITULO = "Instalacao dos ganchos"


def rodar(p, comum):
    ganchos = comum.carregar("configurar_ganchos")

    pasta = tempfile.mkdtemp(prefix="teste_ganchos_")
    antes = os.environ.get("CLAUDE_CONFIG_DIR")
    argv_antes = list(sys.argv)
    os.environ["CLAUDE_CONFIG_DIR"] = pasta

    settings = os.path.join(pasta, "settings.json")

    def instalar(*opcoes):
        sys.argv = ["configurar_ganchos.py"] + list(opcoes)
        with comum.Silencio() as silencio:
            codigo = ganchos.main()
        return codigo, silencio.texto

    def ler():
        with io.open(settings, encoding="utf-8") as arquivo:
            return json.load(arquivo)

    def escrever_cru(texto):
        with io.open(settings, "w", encoding="utf-8") as arquivo:
            arquivo.write(texto)

    try:
        # ---------- maquina limpa: nem arquivo existe ----------
        codigo, tela = instalar()
        p.igual("instala do zero sem reclamar", codigo, 0)
        p.certo("o settings.json foi criado", os.path.isfile(settings))

        configuracao = ler()
        for evento in ("SessionStart", "SessionEnd", "PreToolUse",
                       "UserPromptSubmit"):
            p.certo("o gancho %s foi escrito" % evento,
                    evento in configuracao.get("hooks", {}))

        p.certo("o comando de barra foi criado",
                os.path.isfile(os.path.join(pasta, "commands", "voz.md")))

        # Os caminhos tem que apontar para esta pasta, e nao para a do
        # computador onde o programa foi escrito.
        tudo = json.dumps(configuracao)
        p.contem("o gancho aponta para o programa", tudo, "claude_em_voz.py")
        p.contem("o gancho de fim aponta para o parar.sh", tudo, "parar.sh")
        p.contem("o gancho do menu aponta para o comando de voz",
                 json.dumps(configuracao["hooks"]["UserPromptSubmit"]),
                 "comando_de_voz.py")

        # setsid e o que solta o programa do terminal que o criou. Sem ele o
        # programa morreria junto com a sessao e a leitura pararia no meio.
        p.contem("o gancho de inicio solta o programa do terminal",
                 json.dumps(configuracao["hooks"]["SessionStart"]), "setsid")

        # O caminho inteiro do Python, e nao "python3" solto: quem instalou
        # pode ter um ambiente virtual, e o gancho precisa da MESMA instalacao
        # em que as bibliotecas foram parar.
        p.contem("o gancho usa o Python inteiro, com caminho",
                 tudo, ganchos.achar_python().replace("\\", "\\\\"))

        # ---------- rodar de novo nao duplica ----------
        quantos_antes = len(configuracao["hooks"]["SessionStart"])
        instalar()
        p.igual("rodar duas vezes nao empilha dois ganchos iguais",
                len(ler()["hooks"]["SessionStart"]), quantos_antes)

        # ---------- o que ja estava la sobrevive ----------
        configuracao = ler()
        configuracao["theme"] = "dark"
        configuracao["permissions"] = {"allow": ["Bash(ls:*)"]}
        configuracao["hooks"]["SessionStart"].append({
            "hooks": [{"type": "command", "command": "echo gancho alheio"}]
        })
        with io.open(settings, "w", encoding="utf-8") as arquivo:
            json.dump(configuracao, arquivo)

        instalar()
        depois = ler()
        p.igual("o tema do usuario sobrevive", depois.get("theme"), "dark")
        p.igual("as permissoes do usuario sobrevivem",
                depois.get("permissions"), {"allow": ["Bash(ls:*)"]})
        p.contem("o gancho de outra pessoa sobrevive",
                 json.dumps(depois["hooks"]["SessionStart"]), "gancho alheio")
        p.igual("e o nosso continua um so",
                len([g for g in depois["hooks"]["SessionStart"]
                     if "claude_em_voz" in json.dumps(g)]), 1)

        # ---------- arquivo com defeito: nao mexer em nada ----------
        quebrado = '{"theme": "dark",}'      # a virgula a mais
        escrever_cru(quebrado)
        codigo, tela = instalar()
        p.igual("arquivo com defeito faz a instalacao parar", codigo, 1)
        with io.open(settings, encoding="utf-8") as arquivo:
            p.igual("e o arquivo com defeito fica intocado",
                    arquivo.read(), quebrado)
        p.contem("explicando o que houve", tela, "defeito de escrita")

        # ---------- a marca invisivel do Bloco de Notas ----------
        # Abrir o arquivo para olhar e salvar carimba um BOM no comeco. Sem
        # ler com utf-8-sig, isso seria confundido com arquivo corrompido.
        with io.open(settings, "w", encoding="utf-8-sig") as arquivo:
            json.dump({"theme": "claro"}, arquivo)
        codigo, tela = instalar()
        p.igual("arquivo salvo pelo Bloco de Notas ainda e aceito", codigo, 0)
        p.igual("e o que estava nele sobrevive", ler().get("theme"), "claro")

        # ---------- copia de seguranca ----------
        p.certo("uma copia do arquivo antigo e guardada",
                os.path.isfile(settings + ".copia-de-seguranca"))

        # ---------- desfazer ----------
        codigo, tela = instalar("--remover")
        p.igual("dá para desfazer", codigo, 0)
        sobrou = ler()
        p.certo("nenhum gancho nosso sobra",
                "claude_em_voz" not in json.dumps(sobrou))
        p.igual("mas o que era do usuario continua",
                sobrou.get("theme"), "claro")
        p.certo("o comando de barra e retirado junto",
                not os.path.isfile(os.path.join(pasta, "commands", "voz.md")))

        # ---------- mostrar nao escreve nada ----------
        instalar()
        assinatura = ler()
        codigo, tela = instalar("--mostrar")
        p.igual("mostrar nao mexe no arquivo", ler(), assinatura)
        p.contem("mostrar imprime os ganchos", tela, "SessionStart")

    finally:
        sys.argv = argv_antes
        if antes is None:
            os.environ.pop("CLAUDE_CONFIG_DIR", None)
        else:
            os.environ["CLAUDE_CONFIG_DIR"] = antes
        shutil.rmtree(pasta, ignore_errors=True)
