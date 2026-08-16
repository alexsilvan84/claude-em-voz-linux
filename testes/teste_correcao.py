# -*- coding: utf-8 -*-
"""
Onde a revisao comeca a reescrever.

E a conta mais perigosa do programa: e ela que decide quantas letras apagar da
tela. Duas regras vieram de erro medido em uso, e as duas estao aqui:

  - a comparacao e por PALAVRA. Letra por letra, um "Quero" contra "quero" no
    comeco obrigava a apagar a frase inteira - 166 letras por uma maiuscula.
  - o corte fica DEPOIS da ultima palavra que combinou. Cortando no comeco da
    palavra nova, o espaco sumia junto e saia "crie a pastanova".
"""

TITULO = "Correcao do fim da fala"


def rodar(p, comum):
    voz = comum.carregar("claude_em_voz")
    onde_muda = voz.DitadoAoVivo.onde_muda

    # ---------- quando NAO vale mexer ----------

    p.igual("texto identico nao e reescrito",
            onde_muda("crie a pasta nova", "crie a pasta nova"), None)

    p.igual("diferenca so de maiuscula no comeco nao e reescrita",
            onde_muda("quero café", "Quero café"), None)

    p.igual("maiuscula no meio da frase nao e reescrita",
            onde_muda("eu Vi o carro", "eu vi o carro"), None)

    p.igual("virgula no meio nao vale uma reescrita",
            onde_muda("bom dia pessoal agora", "bom dia, pessoal agora"), None)

    # ---------- quando vale ----------

    corte = onde_muda("crie a pasta velha", "crie a pasta nova")
    p.certo("palavra trocada e reescrita", corte is not None)
    if corte:
        atual, certo = "crie a pasta velha", "crie a pasta nova"
        p.igual("o corte fica depois da ultima palavra que combinou",
                atual[:corte[0]], "crie a pasta")
        p.igual("o texto novo traz o espaco junto",
                certo[corte[1]:], " nova")
        p.igual("juntando os dois, o espaco nao some",
                atual[:corte[0]] + certo[corte[1]:], "crie a pasta nova")

    corte = onde_muda("crie a pasta", "crie a pasta nova")
    p.certo("palavra acrescentada no fim e escrita", corte is not None)
    if corte:
        p.igual("acrescentar nao apaga nada do que ja estava",
                "crie a pasta"[:corte[0]], "crie a pasta")
        p.igual("so o que falta e digitado",
                "crie a pasta nova"[corte[1]:], " nova")

    corte = onde_muda("crie a pasta nova", "crie a pasta")
    p.certo("palavra a mais e apagada", corte is not None)
    if corte:
        sobra = len("crie a pasta nova") - corte[0]
        p.igual("apaga so a palavra que sobrou", sobra, len(" nova"))

    # Pontuacao no fim: todas as palavras batem, mas a ultima esta diferente
    # literalmente. E o unico caso em que vale mexer com tudo combinando.
    corte = onde_muda("bom dia", "bom dia.")
    p.certo("ponto final e acrescentado", corte is not None)
    if corte:
        p.igual("so a ultima palavra e refeita",
                "bom dia"[:corte[0]], "bom ")
        p.igual("a ultima palavra volta com o ponto",
                "bom dia."[corte[1]:], "dia.")

    # ---------- os extremos ----------

    corte = onde_muda("", "alguma coisa")
    p.igual("tela vazia recebe o texto inteiro", corte, (0, 0))

    corte = onde_muda("alguma coisa", "")
    p.certo("revisao vazia apaga tudo o que a fala escreveu", corte is not None)
    if corte:
        p.igual("apaga da primeira letra em diante", corte[0], 0)

    p.igual("dois vazios nao dao trabalho nenhum", onde_muda("", ""), None)

    # ---------- a frase que deu origem a regra ----------

    # Medido em uso: por letra, esta linha mandava reescrever 166 letras por
    # causa da maiuscula inicial. Por palavra, nao se mexe em nada.
    longa = ("quero que voce crie uma pasta nova dentro do projeto e coloque "
             "ali os arquivos de teste que a gente combinou ontem de manha")
    p.igual("a frase longa nao e reescrita por uma maiuscula",
            onde_muda(longa, longa[0].upper() + longa[1:]), None)
