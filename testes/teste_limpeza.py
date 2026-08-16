# -*- coding: utf-8 -*-
"""
A limpeza do texto: o que sobra para ser falado.

Aqui se protege a regra mais visivel do projeto - nunca ler codigo em voz
alta - e a ordem das etapas de limpeza, que importa: se o bloco de codigo nao
sair antes das outras, o conteudo dele vaza para as etapas seguintes e acaba
falado em pedacos.
"""

TITULO = "Limpeza do texto falado"


def rodar(p, comum):
    voz = comum.carregar("claude_em_voz")
    limpar = voz.limpar_texto

    # ---------- o basico ----------

    p.igual("frase simples ganha ponto final",
            limpar("Olá, tudo bem"), "Olá, tudo bem.")

    p.igual("frase que ja termina em ponto fica como esta",
            limpar("Pronto."), "Pronto.")

    p.igual("texto vazio nao vira nada", limpar(""), "")

    # ---------- codigo ----------

    p.igual(
        "bloco de codigo sai inteiro",
        limpar("Vou criar o arquivo.\n\n```python\nprint('oi')\n```\n\nPronto."),
        "Vou criar o arquivo. Pronto.")

    p.nao_contem(
        "nada do bloco de codigo escapa",
        limpar("Antes.\n\n```\nsenha = 'segredo'\n```\n\nDepois."),
        "segredo")

    p.igual(
        "linha de comando de terminal e descartada",
        limpar("Rode isto:\npip install algo\nDepois teste."),
        "Rode isto: Depois teste.")

    p.igual(
        "linha indentada e tratada como codigo",
        limpar("Assim:\n    funcao_qualquer()\nFim."),
        "Assim: Fim.")

    p.igual(
        "codigo entre crases vira so a palavra",
        limpar("Abra o `registro.txt` agora"),
        "Abra o registro.txt agora.")

    # Bloco aberto e nunca fechado: acontece quando a resposta ainda esta
    # sendo escrita e o vigia pega o arquivo no meio.
    p.nao_contem(
        "bloco de codigo sem fechamento tambem sai",
        limpar("Segue o codigo:\n\n```python\nsenha = 'segredo'\n"),
        "segredo")

    # ---------- markdown ----------

    p.igual("titulo perde o sinal de cerquilha",
            limpar("## O resultado"), "O resultado.")

    p.igual("lista vira frases soltas",
            limpar("- **Primeiro** item\n- Segundo item"),
            "Primeiro item. Segundo item.")

    p.igual("link vira so o texto dele",
            limpar("Veja a [documentação](https://exemplo.com) agora"),
            "Veja a documentação agora.")

    p.igual("tabela inteira e descartada",
            limpar("| a | b |\n| - | - |\nTexto normal."),
            "Texto normal.")

    p.igual("citacao perde o sinal de maior",
            limpar("> Isto foi citado"), "Isto foi citado.")

    p.certo("emoji nao e falado",
            "✅" not in limpar("Pronto ✅ tudo certo."))

    # ---------- caminhos ----------

    p.igual(
        "caminho de pasta vira so o nome do arquivo",
        limpar("O arquivo C:\\Users\\ana\\projeto\\notas.txt foi salvo"),
        "O arquivo notas.txt foi salvo.")

    p.nao_contem(
        "o comeco da frase nao se perde junto com o caminho",
        limpar("Salvei em C:\\Users\\ana\\notas.txt"), "Users")

    p.contem(
        "o comeco da frase continua la",
        limpar("Salvei em C:\\Users\\ana\\notas.txt"), "Salvei em")

    # ---------- tags de sistema ----------

    p.igual(
        "aviso de sistema nao e falado",
        limpar("<system-reminder>lembrete interno</system-reminder>Olá."),
        "Olá.")

    p.nao_contem(
        "nada da tag de sistema escapa",
        limpar("<system-reminder>lembrete interno</system-reminder>Olá."),
        "lembrete")

    # ---------- a rede de seguranca ----------

    p.certo("linha so de simbolos e descartada",
            limpar("=== >>> ||| ===") == "")

    p.certo("linha curta demais e descartada",
            limpar("ok") == "")
