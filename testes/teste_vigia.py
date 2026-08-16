# -*- coding: utf-8 -*-
"""
O vigia das conversas: o que e novo, e so o que e novo.

Roda contra uma pasta temporaria que imita a de conversas do Claude Code, sem
tocar nas conversas de verdade. Os oito casos aqui sao os que ja quebraram
durante a construcao: historico relido do zero ao ligar, linha pega no meio da
escrita virando fala picada, resposta lida duas vezes, e conversa nova que
comecava a ser vigiada so na proxima vez que o programa subisse.
"""

import os
import json
import queue
import shutil
import tempfile

TITULO = "Vigia das conversas"


def resposta(identificador, texto, extra=None):
    linha = {
        "type": "assistant",
        "message": {"id": identificador,
                    "content": [{"type": "text", "text": texto}]},
    }
    if extra:
        linha.update(extra)
    return json.dumps(linha, ensure_ascii=False) + "\n"


def acrescentar(caminho, texto):
    with open(caminho, "a", encoding="utf-8") as arquivo:
        arquivo.write(texto)


def rodar(p, comum):
    voz = comum.carregar("claude_em_voz")

    pasta = tempfile.mkdtemp(prefix="teste_vigia_")
    try:
        projeto = os.path.join(pasta, "projeto-a")
        os.makedirs(projeto)
        conversa = os.path.join(projeto, "sessao1.jsonl")

        # Historico que ja existia antes de o programa ligar.
        acrescentar(conversa, resposta("velha1", "Resposta antiga um."))
        acrescentar(conversa, resposta("velha2", "Resposta antiga dois."))

        fila = queue.Queue()
        parar = voz.threading.Event()
        vigia = voz.VigiaDeSessoes(pasta, fila, parar)

        def varrer():
            """Uma volta do vigia, sem thread nem espera."""
            with comum.Silencio():
                for caminho in voz.listar_sessoes(pasta):
                    vigia.ler_novidades(caminho)

        def falado():
            """Tudo o que foi para a fila desde a ultima vez."""
            saida = []
            while True:
                try:
                    saida.append(fila.get_nowait())
                except queue.Empty:
                    return saida

        # ---------- 1) o historico antigo nao e lido ----------
        with comum.Silencio():
            vigia.preparar()
        varrer()
        p.igual("historico anterior a ligar nao e lido", falado(), [])

        # ---------- 2) resposta nova e lida ----------
        acrescentar(conversa, resposta("nova1", "Esta é nova."))
        varrer()
        p.igual("resposta nova e lida", falado(), ["Esta é nova."])

        # ---------- 3) linha pela metade nao vira lixo ----------
        metade = resposta("nova2", "Frase que ainda está sendo escrita.")
        corte = len(metade) // 2
        acrescentar(conversa, metade[:corte])
        varrer()
        p.igual("linha escrita pela metade nao e falada", falado(), [])

        # ---------- 4) a mesma linha, completada, e lida ----------
        acrescentar(conversa, metade[corte:])
        varrer()
        p.igual("a linha completada e lida inteira",
                falado(), ["Frase que ainda está sendo escrita."])

        # ---------- 5) resposta repetida nao e lida duas vezes ----------
        # Acontece de verdade: o arquivo as vezes e reescrito, e sem guardar
        # os identificadores ja falados a conversa inteira sairia de novo.
        acrescentar(conversa, resposta("nova1", "Esta é nova."))
        varrer()
        p.igual("resposta com id repetido nao e falada de novo", falado(), [])

        # ---------- 6) conversa nova na mesma pasta ----------
        outra = os.path.join(projeto, "sessao2.jsonl")
        acrescentar(outra, resposta("outra1", "Conversa nova aqui."))
        varrer()
        p.igual("conversa nova e detectada sem reiniciar",
                falado(), ["Conversa nova aqui."])

        # ---------- 7) projeto novo ----------
        projeto_b = os.path.join(pasta, "projeto-b")
        os.makedirs(projeto_b)
        acrescentar(os.path.join(projeto_b, "sessao1.jsonl"),
                    resposta("b1", "Projeto novo falando."))
        varrer()
        p.igual("projeto novo e detectado sem reiniciar",
                falado(), ["Projeto novo falando."])

        # ---------- 8) conversa de subagente e ignorada ----------
        acrescentar(conversa, resposta("sub1", "Isto e de um subagente.",
                                       {"isSidechain": True}))
        varrer()
        p.igual("conversa de subagente nao e falada", falado(), [])

        # ---------- extras que valem tanto quanto ----------

        # Raciocinio interno e chamada de ferramenta nunca sao falados.
        acrescentar(conversa, json.dumps({
            "type": "assistant",
            "message": {"id": "so_ferramenta", "content": [
                {"type": "thinking", "thinking": "pensando alto"},
                {"type": "tool_use", "name": "Read", "input": {"file_path": "x"}},
            ]},
        }) + "\n")
        varrer()
        p.igual("raciocinio e chamada de ferramenta nao sao falados",
                falado(), [])

        # Linha do usuario tambem nao.
        acrescentar(conversa, json.dumps(
            {"type": "user", "message": {"content": "eu escrevi isto"}}) + "\n")
        varrer()
        p.igual("o que o usuario escreveu nao e lido de volta", falado(), [])

        # Arquivo que encolheu foi recriado: volta ao inicio em vez de ficar
        # esperando para sempre por um tamanho que nunca mais chega.
        with open(conversa, "w", encoding="utf-8") as arquivo:
            arquivo.write(resposta("recriada", "Arquivo recriado do zero."))
        varrer()
        p.igual("arquivo recriado volta a ser lido do comeco",
                falado(), ["Arquivo recriado do zero."])

        # Linha quebrada no meio do JSON nao pode derrubar o vigia.
        acrescentar(conversa, '{"type": "assistant", isso nao e json}\n')
        acrescentar(conversa, resposta("depois", "Continuei funcionando."))
        varrer()
        p.igual("linha corrompida nao derruba o vigia",
                falado(), ["Continuei funcionando."])

    finally:
        shutil.rmtree(pasta, ignore_errors=True)
