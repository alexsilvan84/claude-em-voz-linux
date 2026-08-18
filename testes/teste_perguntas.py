# -*- coding: utf-8 -*-
"""
As perguntas de multipla escolha.

E a armadilha do projeto: elas nao chegam pelo arquivo da conversa a tempo -
so sao gravadas la depois que a pessoa ja escolheu. A via que chega na hora e
o gancho, que despeja o pedido cru numa caixa de entrada. Como o envelope
desse pedido pode mudar de uma versao para outra do Claude Code, os tres
formatos conhecidos sao aceitos, e e isso que se confere aqui.
"""

TITULO = "Perguntas de multipla escolha"


PERGUNTA = {
    "questions": [
        {
            "question": "Qual caminho seguir?",
            "header": "Caminho",
            "options": [
                {"label": "O curto", "description": "Menos seguro"},
                {"label": "O longo", "description": "Mais seguro"},
            ],
        }
    ]
}


def rodar(p, comum):
    voz = comum.carregar("claude_em_voz")
    import json

    # ---------- a frase falada ----------

    falado = voz.texto_da_pergunta(PERGUNTA)
    p.contem("o enunciado e falado", falado, "Pergunta: Qual caminho seguir?")
    p.contem("a primeira opcao e numerada", falado, "Opção 1: O curto")
    p.contem("a segunda opcao e numerada", falado, "Opção 2: O longo")
    p.contem("lembra que da para escrever a propria resposta",
             falado, "escrever uma resposta")

    p.igual("entrada que nao e pergunta nao vira frase",
            voz.texto_da_pergunta({"outra_coisa": 1}), "")
    p.igual("entrada que nem e dicionario nao quebra",
            voz.texto_da_pergunta("texto solto"), "")

    # ---------- os tres envelopes do gancho ----------

    da_linha = voz.VigiaDePerguntas.pergunta_da_linha

    p.contem(
        "envelope com tool_input e entendido",
        da_linha(json.dumps({"tool_name": "AskUserQuestion",
                             "tool_input": PERGUNTA})),
        "Qual caminho seguir?")

    p.contem(
        "envelope com input e entendido",
        da_linha(json.dumps({"input": PERGUNTA})),
        "Qual caminho seguir?")

    p.contem(
        "pergunta crua, sem envelope, e entendida",
        da_linha(json.dumps(PERGUNTA)),
        "Qual caminho seguir?")

    # ---------- o que nao deve virar fala ----------

    p.igual("linha pela metade nao vira lixo falado",
            da_linha('{"tool_input": {"questi'), "")
    p.igual("linha vazia nao vira nada", da_linha("   "), "")
    p.igual("chamada de outra ferramenta e ignorada",
            da_linha(json.dumps({"tool_name": "Read",
                                 "tool_input": {"file_path": "x.txt"}})), "")

    # ---------- nao falar a mesma pergunta duas vezes ----------

    # As duas vias funcionando juntas trazem a MESMA pergunta: o gancho na
    # hora certa, o arquivo da conversa minutos depois. A segunda tem que ser
    # engolida, senao a pessoa ouve tudo duas vezes.
    voz.marcar_pergunta_falada(falado)
    p.certo("pergunta ja falada e reconhecida", voz.pergunta_ja_falada(falado))
    p.certo("pergunta diferente nao e confundida",
            not voz.pergunta_ja_falada("Pergunta: outra coisa"))

    linha_da_conversa = json.dumps({
        "type": "assistant",
        "message": {
            "id": "msg_pergunta",
            "content": [{"type": "tool_use", "name": "AskUserQuestion",
                         "input": PERGUNTA}],
        },
    })
    identificador, texto = voz.extrair_resposta(linha_da_conversa)
    p.certo("a via lenta nao repete o que o gancho ja falou",
            texto is None, "veio: %r" % (texto,))

    # ---------- a explicacao que vem antes da pergunta ----------

    # O Claude Code so grava a mensagem inteira no arquivo da conversa DEPOIS
    # que a pessoa escolhe. Medido nesta maquina: a pergunta chegou ao gancho
    # aos 7 segundos e a mensagem foi gravada aos 86, junto com a escolha.
    # Logo, a explicacao escrita antes da pergunta seria falada depois dela -
    # e depois de a escolha ja ter sido feita. Ela e descartada.
    def linha_com_texto_e_pergunta(pergunta):
        return json.dumps({
            "type": "assistant",
            "message": {
                "id": "msg_texto_e_pergunta",
                "content": [
                    {"type": "text", "text": "Vou te mostrar uma escolha."},
                    {"type": "tool_use", "name": "AskUserQuestion",
                     "input": pergunta},
                ],
            },
        })

    _, texto = voz.extrair_resposta(linha_com_texto_e_pergunta(PERGUNTA))
    p.certo("explicacao antes de pergunta ja falada e descartada",
            texto is None, "veio: %r" % (texto,))

    # Sem o gancho instalado, a via lenta e a unica que existe: ai a mensagem
    # inteira e falada, e na ordem em que foi escrita.
    OUTRA = {"questions": [{"question": "Prefere qual cor?",
                            "header": "Cor",
                            "options": [{"label": "Azul", "description": "Fria"},
                                        {"label": "Vermelha",
                                         "description": "Quente"}]}]}
    _, texto = voz.extrair_resposta(linha_com_texto_e_pergunta(OUTRA))
    p.certo("sem o gancho, a explicacao continua sendo falada",
            texto is not None and "escolha" in texto, "veio: %r" % (texto,))
    p.contem("sem o gancho, a pergunta vem junto", texto or "",
             "Prefere qual cor?")
    p.certo("sem o gancho, a explicacao vem antes da pergunta",
            (texto or "").index("escolha") < (texto or "x").index("Prefere"))

    # Mensagem comum, sem pergunta nenhuma, nao pode ser afetada pelo corte.
    so_texto = json.dumps({
        "type": "assistant",
        "message": {"id": "msg_so_texto",
                    "content": [{"type": "text", "text": "Terminei a tarefa."}]},
    })
    _, texto = voz.extrair_resposta(so_texto)
    p.igual("mensagem sem pergunta segue sendo falada por inteiro",
            texto, "Terminei a tarefa.")
