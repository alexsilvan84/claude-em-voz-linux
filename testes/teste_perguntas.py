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
