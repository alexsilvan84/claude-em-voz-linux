#!/usr/bin/env bash
# ============================================================
#  Roda a bateria de testes do Claude em Voz.
#
#  Rode isto depois de mexer em qualquer coisa do programa. Em
#  poucos segundos ele confere tudo o que ja deu errado alguma
#  vez: leitura de codigo em voz alta, historico relido, texto
#  apagado da tela por engano, a tecla brigando com Ctrl+C, e a
#  instalacao estragando o settings.json.
#
#  Nao precisa de microfone, nem de caixa de som, nem de
#  internet, e nao encosta no seu settings.json nem no
#  interruptor: tudo o que ele escreve vai para pasta
#  temporaria.
#
#  Pode rodar com o programa ligado.
#
#  Para rodar so uma parte:   ./testar.sh limpeza
# ============================================================
cd "$(dirname "$(readlink -f "$0")")" || exit 1

PY="${PYTHON:-python3}"
"$PY" -X utf8 -u testes/testar.py "$@"
RESULTADO=$?

if [ "$RESULTADO" -ne 0 ]; then
    echo
    echo " ----------------------------------------------------------"
    echo "  Alguma coisa falhou. Cada linha acima marcada com x diz o"
    echo "  que era esperado e o que aconteceu. Se voce acabou de"
    echo "  mexer no programa, o defeito costuma estar ai."
    echo " ----------------------------------------------------------"
fi

exit "$RESULTADO"
