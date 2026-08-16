# -*- coding: utf-8 -*-
"""
Vocabulario e pronuncia: as duas pontas do mesmo problema.

De um lado, o reconhecedor recebe uma lista das palavras que voce costuma
dizer, para preferi-las quando o som for parecido. Do outro, a voz recebe uma
tabela de como pronunciar os termos em ingles, que ela leria com sotaque de
portugues.

O que se confere aqui e o mecanismo, e nao o som - som so o ouvido julga, e
para isso existe o --teste-pronuncia. O risco de mecanismo e sempre o mesmo:
trocar uma palavra DENTRO de outra. "Git" nao pode virar "guit" no meio de
"GitHub", e nenhuma troca pode encostar num nome de arquivo.
"""

TITULO = "Vocabulario e pronuncia"


def rodar(p, comum):
    voz = comum.carregar("claude_em_voz")
    ajustar = voz.ajustar_pronuncia

    # ---------- a troca basica ----------

    p.igual("um termo conhecido e trocado",
            ajustar("abra o Python"), "abra o páiton")

    p.igual("o termo mais longo ganha do mais curto",
            ajustar("o Claude Code respondeu"), "o Clôd Côud respondeu")

    p.igual("o termo curto sozinho continua valendo",
            ajustar("o Claude respondeu"), "o Clôd respondeu")

    p.igual("maiuscula ou minuscula da no mesmo",
            ajustar("python e PYTHON"), "páiton e páiton")

    # ---------- nao encostar em palavra vizinha ----------

    p.igual("Git nao e trocado dentro de GitHub",
            ajustar("GitHub"), "guit rábi")

    p.certo("nenhuma troca acontece dentro de outra palavra",
            ajustar("digital, agitado, capitulo") == "digital, agitado, capitulo")

    p.igual("nome de arquivo com sublinhado fica intacto",
            ajustar("claude_em_voz.py"), "claude_em_voz.py")

    p.igual("nome de pasta grudado tambem",
            ajustar("ClaudeEmVoz"), "ClaudeEmVoz")

    # ---------- texto sem nada a trocar ----------

    p.igual("frase comum passa intocada",
            ajustar("bom dia, tudo bem por aqui"),
            "bom dia, tudo bem por aqui")
    p.igual("texto vazio nao quebra", ajustar(""), "")
    p.igual("None nao quebra", ajustar(None), None)

    # ---------- tabela vazia desliga a troca ----------

    antes = voz.RE_PRONUNCIAS
    voz.RE_PRONUNCIAS = None
    try:
        p.igual("com a tabela vazia, nada e trocado",
                ajustar("abra o Python"), "abra o Python")
    finally:
        voz.RE_PRONUNCIAS = antes

    # ---------- a troca acontece no texto que vai ser falado ----------

    p.contem("a limpeza do texto ja entrega a pronuncia corrigida",
             voz.limpar_texto("Rodei o Python aqui"), "páiton")

    p.nao_contem("e o termo original nao sobra",
                 voz.limpar_texto("Rodei o Python aqui"), "Python")

    # ---------- a dica entregue ao reconhecedor ----------

    p.certo("existe uma lista de vocabulario", len(voz.VOCABULARIO) > 0)
    p.certo("a lista nao e longa demais para servir de dica",
            len(voz.VOCABULARIO) <= 40,
            "sao %d termos; acima de ~30 a dica se dilui"
            % len(voz.VOCABULARIO))
    p.contem("a dica vai como um texto so", voz.DICA_DE_VOCABULARIO, "Claude")

    # O reconhecedor de verdade recebe a dica em "hotwords". Aqui um modelo de
    # mentira so anota com que argumentos foi chamado.
    anotado = {}

    class ModeloQueAnota(object):
        def transcribe(self, audio, **argumentos):
            anotado.update(argumentos)
            return [], None

    voz.palavras_de(ModeloQueAnota(), voz.np.zeros(1600, dtype=voz.np.float32))

    p.igual("a dica de vocabulario chega ao reconhecedor",
            anotado.get("hotwords"), voz.DICA_DE_VOCABULARIO)
    p.igual("a fala anterior continua desligada como contexto",
            anotado.get("condition_on_previous_text"), False)
    p.igual("o idioma continua sendo o portugues",
            anotado.get("language"), "pt")

    # Sem vocabulario nenhum, nada e enviado - lista vazia nao pode virar uma
    # dica vazia, que confundiria o reconhecedor.
    antes_dica = voz.DICA_DE_VOCABULARIO
    voz.DICA_DE_VOCABULARIO = ""
    try:
        anotado.clear()
        voz.palavras_de(ModeloQueAnota(),
                        voz.np.zeros(1600, dtype=voz.np.float32))
        p.igual("lista vazia nao manda dica nenhuma",
                anotado.get("hotwords"), None)
    finally:
        voz.DICA_DE_VOCABULARIO = antes_dica
