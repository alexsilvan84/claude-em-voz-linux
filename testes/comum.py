# -*- coding: utf-8 -*-
"""
Apoio comum dos testes: carregar o programa e anotar o que passou.

Sem biblioteca de teste de fora, de proposito. Este projeto tem uma pasta de
instaladores com versoes fixadas e precisa funcionar offline; acrescentar uma
dependencia so para rodar teste obrigaria a baixar mais uma roda e a explica-la
no INSTALAR_DO_ZERO. O que se ganharia nao paga isso: as verificacoes aqui sao
comparacoes simples.
"""

import io
import os
import sys
import importlib.util


PASTA_DOS_TESTES = os.path.dirname(os.path.abspath(__file__))
PASTA_DO_PROGRAMA = os.path.dirname(PASTA_DOS_TESTES)

_carregados = {}


def carregar(nome):
    """
    Carrega um dos arquivos do programa como modulo, pelo caminho.

    Por caminho, e nao por "import" comum, porque os testes vivem numa subpasta
    e o programa nao e um pacote instalado. O modulo fica guardado: carregar
    duas vezes criaria dois estados diferentes do mesmo programa, e um teste
    passaria a nao enxergar o que o outro ajustou.
    """
    if nome in _carregados:
        return _carregados[nome]

    caminho = os.path.join(PASTA_DO_PROGRAMA, nome + ".py")
    if not os.path.isfile(caminho):
        raise IOError("nao achei %s" % caminho)

    especificacao = importlib.util.spec_from_file_location(
        "programa_" + nome, caminho)
    modulo = importlib.util.module_from_spec(especificacao)
    sys.modules[especificacao.name] = modulo
    especificacao.loader.exec_module(modulo)
    _carregados[nome] = modulo
    return modulo


class Silencio(object):
    """
    Engole o que o programa imprime durante um teste.

    O programa conta o que faz por meio de prints - util em uso, mas aqui a
    lista de resultados ficaria ilegivel no meio deles. O texto engolido fica
    guardado, porque as vezes e justamente ele que se quer conferir.
    """

    def __init__(self):
        self.texto = ""
        self._stdout = None
        self._stderr = None
        self._buffer = None

    def __enter__(self):
        self._stdout, self._stderr = sys.stdout, sys.stderr
        self._buffer = io.StringIO()
        sys.stdout = sys.stderr = self._buffer
        return self

    def __exit__(self, *_):
        self.texto = self._buffer.getvalue()
        sys.stdout, sys.stderr = self._stdout, self._stderr
        return False


def no_linux():
    """
    Estamos rodando no Linux de verdade?

    Alguns casos so podem ser conferidos la - os que dependem de caminho de
    arquivo do sistema. Eles nao sao ignorados em silencio: ficam anotados
    como pulados e aparecem no resumo, para ninguem confundir "nao conferido"
    com "conferido e passou".
    """
    return os.name == "posix"


class Provas(object):
    """Guarda o que passou, o que falhou e o que nao deu para conferir."""

    def __init__(self, titulo):
        self.titulo = titulo
        self.passaram = 0
        self.falhas = []
        self.pulados = []

    def pular(self, nome, motivo):
        self.pulados.append((nome, motivo))

    def _anotar(self, nome, deu_certo, detalhe=""):
        if deu_certo:
            self.passaram += 1
        else:
            self.falhas.append((nome, detalhe))
        return deu_certo

    def igual(self, nome, obtido, esperado):
        return self._anotar(
            nome, obtido == esperado,
            "esperava %r\n           obteve   %r" % (esperado, obtido))

    def certo(self, nome, condicao, detalhe=""):
        return self._anotar(nome, bool(condicao), detalhe)

    def contem(self, nome, texto, trecho):
        return self._anotar(
            nome, trecho in (texto or ""),
            "nao encontrei %r em %r" % (trecho, texto))

    def nao_contem(self, nome, texto, trecho):
        return self._anotar(
            nome, trecho not in (texto or ""),
            "encontrei %r, que nao devia estar em %r" % (trecho, texto))
