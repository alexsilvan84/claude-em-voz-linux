# CLAUDE.md

> **Nota deste repositório.** Este arquivo é a referência técnica das DUAS
> versões do projeto, e vive na pasta que contém as duas. Aqui está a versão
> **Linux**: onde o texto diz `ClaudeEmVozLinux/`, leia "a raiz deste
> repositório"; onde diz `ClaudeEmVoz/`, é a versão irmã, em
> https://github.com/alexsilvan84/claude-em-voz-windows


This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Regra de comunicação (obrigatória neste projeto)

As respostas desta pasta são lidas em voz alta por um leitor de texto (o próprio
programa deste projeto). Portanto:

- Responder **em português do Brasil**.
- Antes de qualquer ação técnica — PowerShell, bash, Python, apagar/renomear
  arquivo, gerar documento — explicar em até três frases, em linguagem cotidiana:
  **o que** vai ser feito, **por que** agora, e **o que muda** (incluindo se algo
  será apagado, sobrescrito ou movido). Só depois mostrar o comando.
- Nunca abrir uma resposta com bloco de comando.
- Evitar jargão e caminho completo de pasta: citar só o nome do arquivo.
- Pedidos de confirmação também em linguagem simples
  ("posso apagar o arquivo antigo e manter só o atualizado?").
- Manter blocos de código curtos e no fim da resposta — o leitor os descarta,
  mas texto técnico solto no meio quebra o entendimento.

O brief original está em `Projeto_Voz_do_Claude_Code.txt`.

## Duas cópias: `ClaudeEmVoz/` (Windows) e `ClaudeEmVozLinux/`

O projeto existe **duas vezes**, uma por sistema. Tudo o que este arquivo
descreve vale para as duas, salvo onde estiver dito o contrário — a lógica é a
mesma linha por linha, e a maior parte dos arquivos é cópia idêntica.

**Mudança de comportamento entra nas duas.** Alterar só uma faz o projeto
divergir em silêncio, e a segunda quebra na próxima vez que alguém a usar.
Depois de mexer, rode a bateria nas duas (`testar.bat` e `testar.sh`).

O que difere é a camada de baixo, reunida de propósito para ficar fácil de
achar:

| | Windows | Linux |
|---|---|---|
| falar | SAPI via `comtypes` | `espeak-ng`, `piper` ou `spd-say`, um processo por frase |
| calar no meio | fala assíncrona + sondagem de `RunningState` | encerra o processo (sai de graça) |
| digitar | `pynput.type()` | `pynput`, `xdotool`, `wtype` ou `ydotool`, escolhido em `escolher_como_escrever()` |
| janelas | `win32gui` | `xdotool` |
| processos | `CreateToolhelp32Snapshot` | leitura de `/proc` |
| evento nosso | bit `LLKHF_INJECTED` do evento | só o sinal `_estamos_escrevendo` |
| bipe | `winsound.Beep` | tom gerado com numpy, tocado pelo `sounddevice` |
| instância única | mutex nomeado | `flock` num arquivo |
| scripts | `.bat` | `.sh` |

Duas armadilhas do lado Linux que não existem no Windows:

**Wayland.** Ele impede, por segurança, que um programa saiba qual janela está
na frente e digite nela — as duas coisas de que o ditado depende. A leitura não
é afetada. `_conferir_area_de_trabalho()` detecta e explica as saídas (wtype no
KDE/Sway, sessão X11, ou ydotool com permissão de uinput).

**Reconhecer o Claude entre os processos.** No Linux ele costuma rodar como
`node` com o caminho do claude na linha de comando, então `_e_o_claude()` olha
**também** a `cmdline` — e compara **pedaço inteiro de caminho**, não texto
solto. Sem isso uma pasta chamada `claudeteca` faria qualquer programa passar
por Claude Code (o teste `teste_sistema` cobre exatamente esse caso, e foi ele
que pegou o erro).

`caminho_comparavel()` também difere: no Windows uniformiza a caixa; no Linux
**não pode**, porque `Voz` e `voz` são pastas diferentes.

## Comandos

```
ClaudeEmVoz/testar.bat                     # a bateria de testes — rode após qualquer mudança
ClaudeEmVozLinux/testar.sh                 # a mesma, do lado Linux
ClaudeEmVoz/diagnostico.bat                # confere tudo e FALA o resultado
python claude_em_voz.py --diagnostico      # o mesmo, pelo terminal
python claude_em_voz.py --teste-voz        # fala três frases (uma só não pega a falha)
python claude_em_voz.py --teste-pronuncia  # ouve a tabela PRONUNCIAS
python claude_em_voz.py --vozes            # lista as vozes SAPI5 instaladas
ClaudeEmVoz/ligar.bat                      # liga sem janela
ClaudeEmVoz/desligar.bat                   # encerra pelo PID anotado
ClaudeEmVoz/parar.bat                      # o mesmo, silencioso — usado pelo hook SessionEnd
```

## O programa é um só: `ClaudeEmVoz/claude_em_voz.py`

**Leia isto antes de mexer em qualquer coisa.** O projeto nasceu como
`leitor_voz_claude.py` (só falar) e ganhou depois um `escritor_voz_claude.py`
(só escrever). Os dois foram **unificados** em `ClaudeEmVoz/claude_em_voz.py`,
a pedido do usuário: são duas metades da mesma conversa e precisam se
coordenar — a leitura espera a fala terminar (`_gravando`), a voz é uma fila
só (respostas, perguntas e lembretes não se atropelam), e há um único lugar
para ligar, desligar e configurar.

Os arquivos antigos seguem no repositório por ora, mas **não são mais
executados**: o hook aponta para o programa único. Tudo abaixo sobre o leitor
descreve código que hoje vive dentro de `claude_em_voz.py` — as decisões e os
porquês continuam valendo; os nomes de arquivo, não.

`ClaudeEmVoz/PERGUNTAS_E_RESPOSTAS.txt` é a documentação do usuário, em
pergunta e resposta, com o porquê de cada decisão. Ao mudar comportamento,
atualize-a junto com `COMO_USAR.txt`.

`ClaudeEmVoz/INSTALAR_DO_ZERO.txt` é a **receita de reinstalação**, para o
usuário refazer tudo sozinho numa máquina formatada, sem o Claude: links dos
programas, versões, os quatro hooks completos, a voz pt-BR, o microfone e os
testes de conferência. Foi pedido explicitamente porque a documentação existente
só explicava decisões, não dizia como montar. Nunca deixe essa receita
desatualizada: **qualquer nova dependência, novo hook, novo arquivo ou nova
configuração externa entra ali** — junto com `requirements.txt` (versões
fixadas) e `instalar.bat` (pip + `--baixar` em dois cliques).

Cuidado documentado ali: `comtypes` é obrigatório (é por ele que a voz alcança
o SAPI) e não é dependência de nenhum dos outros pacotes — só existia nesta
máquina porque um dia se instalou `pyttsx3`. A linha de instalação antiga
omitia-o, e seguir a documentação numa máquina limpa deixaria o programa
funcionando e mudo.

`ClaudeEmVoz/INSTALAR_TUDO.bat` é o **pacote de instalação**: dois cliques e ele
instala Python (`/quiet PrependPath=1`), Git (`/VERYSILENT`), as bibliotecas, os
modelos e os hooks, pulando o que já existe.

**O Claude Code não é instalado por nenhuma das duas vias** — nem pelo `.bat`,
nem pela receita manual —, decisão do usuário: quem chega neste programa já usa
o Claude, e rodar `claude.exe install` por cima trocaria a versão de uma
instalação que funciona, por causa de um acessório. O `.bat` faz só uma
conferência (`claude --version`, marca `FALTOU` e segue), e o PASSO 4 do
`INSTALAR_DO_ZERO.txt` virou "conferir, não instalar", com o diagnóstico do
caso comum (janela aberta antes, ou `.local\bin` fora do PATH) em vez de
reinstalação. Os binários `claude-2.1.233-win32-x64.exe` e o `install.ps1`
seguem em `Instaladores/programas/`, mas agora **só como cópia guardada**, e a
documentação diz explicitamente para não executá-los.

Detalhe que não é opcional: logo após instalar o Python ele passa a
chamá-lo pelo caminho absoluto (`%PY%`), porque a janela do `cmd` já estava
aberta e não enxerga o PATH novo — e `instalar.bat` foi partido para aceitar
`PY` e `SEM_PAUSA` de quem o chama, em vez de duplicar a lógica. A detecção do
Python é `python -c "import sys; sys.exit(...)"`, não `where python`: o Windows
tem um `python.exe` falso que só abre a loja.

## O interruptor: desligar cada metade sem fechar o programa

Digitar `/voz` na janela do Claude Code mostra um menu; `/voz 1` desliga a
leitura, `/voz 2` o ditado, `/voz 3` os dois, `/voz 4` religa, `/voz 5` relê a
última resposta. A via é um hook
`UserPromptSubmit` que chama `comando_de_voz.py`: ele reconhece o comando,
escreve em `interruptor.json` e **sai com código 2**, o que faz o Claude Code
engolir a linha (não vira prompt, não custa tokens) e mostrar o stderr na tela.
Qualquer outra linha sai com 0 e passa intocada — inclusive frases de mais de
duas palavras começando com "voz", que são conversa de verdade. Um `except`
geral no fim devolve 0: um hook quebrado não pode comer a linha do usuário.

Arquivo, e não recado direto, porque são dois processos: o hook nasce e morre a
cada linha; o programa já está rodando. `VigiaDoInterruptor` confere o mtime a
cada 0,3 s (JSON pela metade → `None` → tenta de novo na volta seguinte).

O estado é **reescrito como tudo ligado em toda partida** (escolha do usuário):
desligar vale para o momento. Consequência para quem for testar: mudar
`interruptor.json` antes de o programa subir não tem efeito.

`VozDoWindows.falar` ganhou `desistir_se`: fala assíncrona (`Speak(texto, 1)`)
com sondagem de `Status.RunningState` e `Speak("", 3)` para descartar o resto.
Sem isso, desligar a leitura no meio de uma resposta comprida deixaria a frase
sair inteira — medido: 17,6 s viram 1,5 s. Todas as chamadas COM continuam na
thread do locutor, que é o requisito do SAPI. A fila é esvaziada ao desligar:
religar é para ouvir o que vem a seguir, não para receber o que se escolheu não
ouvir.

**O aviso do interruptor é falado mesmo ao desligar a leitura**, e é o único
item da fila marcado como `(texto, True)` — atravessa o gate e não é
interrompível. Isso foi correção do usuário: um "leitura desligada" seguido de
silêncio é a confirmação de que o pedido foi atendido; sem ele o silêncio é
ambíguo entre obediência e defeito. Ordem obrigatória em `aplicar()`: esvaziar a
fila **antes** de enfileirar o aviso, senão ele mesmo é descartado. Duas metades
mudando de uma vez viram uma frase só (`AVISOS[(leitura, ditado)]`, `None` na
metade que não mudou) — duas frases seguidas seriam o despejo que o programa
existe para evitar. Única exceção ao aviso: leitura já desligada e continuando
desligada (mexer só no ditado) — aí o usuário já pediu silêncio antes.

O gate do ditado fica em `ao_pressionar` (depois do `mesma_tecla`, antes da
autorrepetição) e de novo em `comecar()`, porque o `threading.Timer` dos 3 s
pode ter sido armado antes do desligamento.

**`voz 5` (reler)** existe porque o usuário sai da sala e a resposta é lida
para ninguém — a alternativa era pedir ao Claude que repetisse, gastando outra
resposta. `interruptor.json` ganhou `repetir`, um **contador** e não um
booleano: pedir duas vezes seguidas precisa valer duas vezes. `_ultima_resposta`
é gravada por `enfileirar_resposta()`, usada só pelos dois vigias — avisos do
programa (abertura, lembrete, interruptor) ficam de fora de propósito. O repeat
entra na fila como resposta comum (interrompível). Com a leitura desligada o
hook recusa na tela em vez de falar: repetir contradiria o silêncio pedido, e
evita ter de tornar um item forçado interrompível. Guarda só a última, e só da
partida atual.

**A barra tem duas vias, e a segunda é obrigatória.** O hook já aceitava
`/voz` (`sem_enfeite` faz `lstrip("/\\!.")`), mas o Claude Code recusa um
comando de barra inexistente *antes* de o hook ver a linha. Por isso
`configurar_ganchos.py` também escreve `~/.claude/commands/voz.md` — é ele que
faz `/voz` aparecer na lista ao digitar a barra. O arquivo chama
`comando_de_voz.py` passando o número como argumento (`$ARGUMENTS`), o que
exigiu o modo `CHAMADO_NA_MAO`: com argv, o script repõe a palavra "voz",
responde pelo **stdout** e sai com **0** — não há linha para engolir, e o
stderr apareceria como erro. No modo argv, resto desconhecido mostra o menu em
vez de deixar passar: pela barra não existe o risco de comer conversa de
verdade. Na prática o hook responde primeiro e o `voz.md` fica de reserva. O
comando vai na pasta do **usuário**, não do projeto: o programa é um só para a
máquina. `remover_comando_de_barra()` confere o conteúdo antes de apagar —
`voz.md` é nome comum demais para apagar às cegas.

O parser do hook: `voz` + resto; resto vazio → menu; resto conhecido → aplica;
resto de **uma** palavra desconhecida → menu com "não entendi" (engole, é
engano de digitação); resto de duas ou mais → deixa passar, porque "a voz do
Claude está muito rápida" é conversa de verdade.

`ClaudeEmVoz/configurar_ganchos.py` escreve os quatro hooks derivando os caminhos
de `__file__` e de `sys.executable` — é o que torna a instalação portátil para
qualquer usuário/pasta. Preserva o resto do `settings.json`, faz cópia de
segurança, é idempotente (remove os próprios hooks antes de reescrever,
reconhecidos por `claude_em_voz`/`perguntas_pendentes`/`parar.bat`) e tem
`--remover`/`--mostrar`. Lê com `utf-8-sig`: o Bloco de Notas carimba BOM, e
sem isso um arquivo que o usuário abriu para olhar seria recusado como
corrompido. JSON inválido aborta sem escrever — perder tema e permissões por
uma vírgula seria pior. Validado nos casos: hook alheio sobrevive, duas rodadas
não duplicam, arquivo quebrado fica intacto, máquina sem arquivo cria do zero,
e os hooks gerados são byte a byte iguais aos que já funcionavam.

`ClaudeEmVoz/Instaladores/` (1,1 GB, versionado à mão) guarda os binários da
instalação, a pedido do usuário — link sai do ar e versão nova quebra o que
funcionava: `programas/` (Python 3.13.1, Git 2.55.0.4, `claude.exe` 2.1.233 com
checksum conferido pelo manifest, e o `install.ps1` oficial), `bibliotecas/`
(32 rodas baixadas com `pip download --only-binary=:all:`) e `modelos_de_voz/`
(a cópia de `~/.cache/huggingface/hub` — sem symlinks nesta máquina, então
copiar de volta basta). `instalar.bat` prefere essa pasta (`pip install
--no-index --find-links`, `xcopy` dos modelos) e só cai para a internet se ela
não existir; validado com `--dry-run --ignore-installed`, resolve os 32 pacotes
sem rede. Ao trocar de versão de Python ou acrescentar dependência, rebaixe as
rodas — as atuais são `cp313`/`win_amd64` e não servem para outra versão.

## Início automático

Um hook `SessionStart` em `~/.claude/settings.json` lança
`ClaudeEmVoz/claude_em_voz.py` a cada sessão do Claude Code, via
`nohup pythonw.exe … &` com `shell: bash` e `async: true`. `pythonw.exe` (não `python.exe`) é o que evita a janela de
console; `nohup … &` é o que desprende o processo, para o leitor sobreviver ao
fim do hook e não morrer junto com a sessão.

Como toda sessão dispara o hook, o script precisa ser idempotente: `main()`
chama `ja_existe_um_leitor()` antes de qualquer coisa, que cria um mutex
nomeado do Windows (`Local\LeitorDeVozDoClaudeCode`) via `ctypes` e sai se o
erro for `ERROR_ALREADY_EXISTS` (183). Mutex e não arquivo de lock porque o
Windows o solta mesmo se o processo for morto à força — um lockfile ficaria
preso e travaria o leitor para sempre. O handle fica na global `_cadeado` só
para não ser coletado enquanto o programa vive.

`ARQUIVO_PID` (no diretório temporário) existe apenas para o `desligar_leitor.bat`
saber qual PID encerrar, sem matar outros processos Python da máquina.

O programa também morre junto com o Claude Code: um hook `SessionEnd` chama
`ClaudeEmVoz/parar.bat` (versão sem `echo` nem `pause` — hook não pode abrir
janela nem esperar tecla). O matcher é `logout|prompt_input_exit|bypass_permissions_disabled|other`,
de propósito **sem** `clear` e `resume`: nesses dois a sessão termina e recomeça
em seguida, e desligar ali arriscaria o `SessionStart` seguinte esbarrar no mutex
do processo ainda morrendo e ficar sem leitor nenhum. Se a janela do terminal for
fechada à força, o `SessionEnd` não roda e o leitor fica no ar — sem prejuízo, o
mutex impede duplicatas e o próximo `SessionEnd` o encerra.

A saída do script vai para `leitor_registro.txt` (na pasta do projeto, reescrito
a cada partida) em vez de `/dev/null`. Foi um silêncio sem explicação que motivou
isso: com a saída descartada não havia como saber se o leitor tinha visto a
resposta, falado, ou travado. O hook usa `-X utf8 -u` para o registro sair com
acento correto e sem atraso de buffer.

Ao mexer no hook, lembre que o watcher de settings pode não recarregar na
sessão corrente: o efeito real só aparece ao reabrir o Claude Code ou depois
de abrir `/hooks` uma vez.

## Testes

**Rode `ClaudeEmVoz/testar.bat` (ou `python -X utf8 testes/testar.py`) depois de
qualquer mudança.** Mais de 200 verificações em ~5 s. `testar.py <palavra>` roda
só o arquivo que casar. Sai com 0 se tudo passou, 1 se algo falhou — o código de
saída é verificado, um runner que sempre diz "passou" não protegeria nada.

Nada de pytest, de propósito: o projeto tem `Instaladores/` com rodas fixadas e
precisa instalar offline; mais uma dependência teria de entrar no
`requirements.txt`, nas rodas baixadas e no `INSTALAR_DO_ZERO`. As verificações
são comparações simples e não pagam esse custo. `testes/comum.py` traz o
carregador (`importlib` por caminho — os testes vivem numa subpasta e o programa
não é pacote instalado), o `Provas` e o `Silencio`, que engole os prints do
programa para a lista de resultados ficar legível.

Nenhum teste toca em nada de verdade: `settings.json` é redirecionado por
`CLAUDE_CONFIG_DIR`, `ARQUIVO_DO_INTERRUPTOR` é apontado para pasta temporária, e
não há microfone, modelo, janela nem rede envolvidos. Podem rodar com o programa
ligado.

| arquivo | o que protege |
|---|---|
| `teste_limpeza` | nunca ler código em voz alta; a ordem das etapas de limpeza |
| `teste_vocabulario` | `PRONUNCIAS`/`VOCABULARIO`: trocar palavra dentro de outra |
| `teste_perguntas` | os três envelopes do hook; não falar a pergunta duas vezes |
| `teste_vigia` | os oito casos do vigia, sobre pasta temporária |
| `teste_correcao` | `onde_muda`: por palavra, corte depois da última que combinou |
| `teste_ditado` | o `trabalhador` de verdade numa thread; duas falas seguidas |
| `teste_tecla` | acionar de propósito, nunca por Ctrl+C, AltGr ou autorrepetição |
| `teste_interruptor` | o que vira menu e o que segue para o Claude |
| `teste_ganchos` | preservar o alheio, não duplicar, abortar em JSON quebrado |
| `teste_diagnostico` | a conferência dos ganchos, inclusive o falso alarme |
| `teste_som_ocupado` | som ocupado não é defeito; e a fala não pode falhar calada |

Dois detalhes que custaram tempo ao escrever os testes, e que voltarão a morder:
`Fala()` recebe uma **lista** de pedaços de áudio (é assim que o microfone a
alimenta), não um array; e o reconhecedor de mentira em `teste_ditado` responde a
partir do **tamanho do áudio** que recebe, e não de um contador de chamadas —
com contador, o número de passadas passa a depender do relógio e o teste fica
intermitente.

## O diagnóstico falado

`--diagnostico` (ou `diagnostico.bat`) confere voz, microfone, os dois modelos,
os quatro hooks, o Claude Code e o estado atual, imprime tudo e **fala** o
resumo. Falado por coerência: o programa não tem janela, então descobrir um
defeito significava abrir o registro e ler — justamente o que ele existe para
evitar. A fala vem por último de propósito: se a voz for o que está quebrado,
tudo já está na tela quando se descobre isso.

O item que justifica o resto é `_conferir_ganchos`: compara o caminho gravado em
cada hook com a pasta atual e acusa **pasta movida** — a falha mais provável do
futuro, e a única que quebra tudo sem deixar pista. Também acusa hook faltando e
caminho apontando para arquivo que sumiu.

`caminho_comparavel()` existe por um falso alarme real: três hooks são lidos pelo
bash e usam barra normal; o de desligar é executado pelo `cmd` e usa barra
invertida **dobrada**. Sem uniformizar (barras → `/`, colapsar repetidas,
minúsculas), o diagnóstico acusava "a pasta mudou" com tudo no lugar. Está
coberto em `teste_diagnostico`.

`main()` trata `--diagnostico` **antes** do mutex, como as outras opções: conferir
tem de funcionar com o programa ligado, que é quando se precisa disso. E o
`__main__` virou `sys.exit(main() or 0)` para o `.bat` saber se achou problema.

`--teste-voz`, `--teste-pronuncia` e o resumo falado do diagnóstico passam por
`falar_esperando_a_vez()`, e não por `voz.falar()` direto. Motivo real (visto na
versão Windows): rodar o teste logo depois de uma resposta comprida encontra o
**próprio leitor** falando e segurando a saída de som, e o teste despejava um
erro técnico — quem lesse concluiria que a voz quebrou, com a voz perfeita.
Agora ele reconhece o caso, explica que **não é defeito**, e espera a vez.
Aqui a detecção é por texto (`SINAIS_DE_SOM_OCUPADO`), porque cada camada de
áudio — ALSA, PulseAudio, PipeWire — reclama com palavras diferentes.

E um defeito só desta versão, corrigido junto: `VozDoLinux.falar()` descartava
o `stderr` e **ignorava o código de saída**. Um espeak que não conseguisse abrir
o som falhava calado — o programa achava que falou, o registro dizia "falando",
e não saía som nenhum. Agora `_conferir_o_fim()` levanta erro com a reclamação
do programa de fala. O flag `calamos` existe para que encerrar a fala de
propósito (o `/voz 1` no meio da frase) não seja confundido com falha.

A trava que mantém isso honesto: só "som ocupado" vira espera; **qualquer outro
erro continua subindo**. Está em `teste_som_ocupado`.

## Vocabulário e pronúncia

Duas tabelas no topo de `claude_em_voz.py`, uma para cada metade.

`VOCABULARIO` vai ao Whisper em **`hotwords`**, não em `initial_prompt`: os dois
servem de pista, mas o `initial_prompt` entra como se fosse fala anterior — que é
exatamente o que `condition_on_previous_text=False` desliga, e pelo mesmo motivo
(em frases soltas o modelo entra em círculo). Lista vazia manda `None`; lista
comprida dilui a pista e o modelo passa a ouvir esses termos onde não estão.
Fecha, em parte, a vantagem que a doc reconhece no `/voice` nativo (seção 1b do
`PERGUNTAS_E_RESPOSTAS`).

`PRONUNCIAS` é aplicada no **fim** de `limpar_texto()` — antes, as regras
seguintes procurariam palavras que já não existem. Um regex só, montado do termo
mais longo para o mais curto (senão "Claude" casaria antes de "Claude Code") e
com `\b` nas bordas (senão "Git" seria trocado dentro de "GitHub" e nomes de
arquivo sairiam com pedaço em inglês no meio). Só afeta a fala; tela e registro
seguem corretos. `--teste-pronuncia [termos]` fala cada par escrito/corrigido,
porque ouvido é o único juiz de uma grafia fonética.

## Arquitetura

Programa único: `leitor_voz_claude.py`. Duas threads e uma fila entre elas.

```
pasta de sessões  ──►  VigiaDeSessoes (thread)  ──► queue.Queue ──►  locutor (thread) ──► pyttsx3/SAPI5
   *.jsonl              lê só bytes novos              texto limpo        fala um de cada vez
```

**Fonte de dados.** `%USERPROFILE%\.claude\projects\<projeto-com-traços>\<uuid>.jsonl`.
Uma linha = um JSON completo. Só interessam as linhas com `type == "assistant"`;
dentro delas `message.content` é uma lista de blocos de três tipos:

| bloco | conteúdo | uso |
|---|---|---|
| `text` | texto explicativo | **é o que se fala** |
| `thinking` | raciocínio interno | ignorado |
| `tool_use` | chamada de ferramenta | ignorado |

**As perguntas de múltipla escolha não chegam pelo `.jsonl` a tempo** — e essa
é a armadilha do projeto. O `tool_use` do `AskUserQuestion` só é persistido na
sessão *depois* que o usuário responde; ler o arquivo da conversa faz a
pergunta ser falada quando ela já não serve. Foi medido em uso real: o usuário
ouviu a pergunta só depois de escolher.

A via que chega a tempo é um hook **`PreToolUse` com matcher
`AskUserQuestion`** em `~/.claude/settings.json`, que faz
`{ cat; echo; } >> ClaudeEmVoz/perguntas_pendentes.jsonl`. `VigiaDePerguntas`
faz tail desse arquivo a cada 0,25 s (o arquivo é apagado na partida — pergunta
velha não interessa) e enfileira na voz. `pergunta_da_linha` aceita
`tool_input`, `input` ou o objeto cru, porque o envelope do hook pode variar.

O caminho pelo `.jsonl` fica como **reserva** para quando o hook não estiver
instalado, e `_perguntas_faladas` impede que a mesma pergunta seja falada duas
vezes pelas duas vias. `texto_da_pergunta()` monta "Pergunta: … Opção 1: … " e
passa pela mesma `limpar_texto()`; `LER_DESCRICAO_DAS_OPCOES` corta as
explicações se ficar longo.

Linhas com `isSidechain: true` são de subagentes e também são ignoradas.
Outros `type` observados (`user`, `attachment`, `system`, `file-history-snapshot`,
etc.) não são respostas e caem fora naturalmente.

**Leitura incremental.** `VigiaDeSessoes` guarda, por arquivo, o deslocamento em
bytes já lido (`self.posicoes`) e o resto de linha incompleta (`self.restos`).
`preparar()` marca todos os arquivos existentes como lidos até o fim — é isso que
impede a releitura do histórico. Arquivos que aparecem **depois** disso começam do
byte zero, porque tudo neles é novo. Arquivo que encolheu é tratado como recriado
e volta ao zero. A varredura é por polling (`INTERVALO`), não por evento de
sistema de arquivos, para ser imune a arquivo trocado ou recriado.

**Deduplicação.** `self.ja_falados` guarda `message.id` (com `uuid`/`requestId`
como reserva). Sem isso, um arquivo reescrito repetiria falas.

**Limpeza.** `limpar_texto()` aplica regexes numa ordem que importa: tags de
sistema e blocos de código saem antes de qualquer outra coisa, senão o conteúdo
deles vaza para as etapas seguintes. Caminhos de pasta viram só o nome final
(`encurtar_caminho`) em vez de sumirem, para a frase não perder o começo.
`parece_codigo()` é a rede de segurança final, descartando linhas que sobraram
mas ainda têm densidade alta de símbolos ou começam como comando de terminal.

**Voz.** A fala vai direto ao SAPI do Windows (`SAPI.SpVoice` via `comtypes`,
que já vem com o pyttsx3), **não** pelo pyttsx3. Motivo: com pyttsx3 só a
primeira frase sai — da segunda em diante `runAndWait()` retorna na hora, sem
erro, e nada é falado (medido: 4,1 s na primeira, 0,1 s nas seguintes). O
sintoma é traiçoeiro porque o `print("[falando] …")` acontece antes da fala:
o registro afirmava que tudo estava sendo lido enquanto o leitor estava mudo.
Recriar o motor com `pyttsx3.init()` não resolve — o `init` guarda e devolve o
mesmo motor já emudecido; só `pyttsx3.Engine()` cria um de verdade, e é o que a
classe reserva `VozPorPyttsx3` faz, um motor por frase, caso o SAPI falhe.
O motor **precisa ser criado e usado na mesma thread** — por isso
`montar_motor()` é chamado dentro de `locutor()`, nunca no `main()`, e o
`comtypes.CoInitialize()` roda no construtor, já na thread da fala. Uma thread
só de fala garante que respostas não se atropelem; se `falar()` levantar
qualquer erro, a voz é recriada e o loop continua. `--teste` fala três frases
seguidas de propósito: uma só não detectaria esse defeito.
`FRASE_DE_ABERTURA` entra na fila em `main()`, antes das threads, então é sempre
a primeira coisa dita — e só é dita por quem realmente ligou, já que uma segunda
instância sai no mutex antes de chegar lá.

**Impressão não pode matar a fala.** `preparar_saida()` roda logo após os imports:
troca `sys.stdout`/`sys.stderr` nulos (caso de `pythonw` sem redirecionamento) por
`os.devnull` e força `utf-8` com `errors="replace"`. Sem isso um `print` estoura
por caractere fora do cp1252 ou por saída inexistente; como o `print` do locutor
ficava fora do `try`, o erro mataria a thread de fala e o leitor seguiria ligado
porém mudo — falha difícil de diagnosticar justamente porque não fala. O `print`
do locutor agora também está dentro de um `try` próprio.

## A metade que escreve (o ditado)

Caminho inverso da leitura: transcreve a fala do usuário e digita o texto na
janela ativa. Vive no mesmo `claude_em_voz.py`, mesmas restrições (offline,
sem serviço pago).

**A ordem de escrita e de fala é coordenada.** O locutor espera `_gravando`
baixar antes de cada frase: duas vozes ao mesmo tempo não se entendem, e o
microfone ouviria a própria leitura.

A transcrição é **ao vivo, palavra por palavra** — a primeira versão colava a
frase inteira ao soltar a tecla e o usuário rejeitou: ele quer o
comportamento do ditado de celular.

`PERGUNTAS_E_RESPOSTAS.txt` é a documentação voltada ao usuário, em pergunta e
resposta, com o *porquê* de cada decisão. Foi pedido explicitamente; ao mudar
comportamento, atualize-o junto com `COMO_USAR.txt`.

```
tecla F9 (pynput) ──► Microfone ──► Fala (um pacote por aperto) ──► trabalhador (thread) ──► pynput.type() na janela
  segurar/soltar    stream sempre   áudio + texto + janela + flag     uma fala por vez        + historico_de_voz.txt
                       aberto       "aberto" encolhe / "completo"     passada a cada 0,7 s
                                            fica inteiro              ao soltar: revisão
```

**Uma `Fala` por aperto de tecla, e uma de cada vez no trabalhador.** Cada fala
carrega o próprio áudio, o próprio `digitado` e a própria janela de destino.
Isso existe por causa de um bug relatado pelo usuário: começar a falar de novo
enquanto o revisor da fala anterior ainda rodava fazia a revisão cair em cima
do texto da fala nova e apagá-lo. Gravar e transcrever são independentes — o
microfone continua enchendo a `Fala` seguinte enquanto o trabalhador termina a
anterior, então nada se perde na espera.

**Continuação entre falas.** `ditado.ja_escreveu` é consultado em `entregar()`,
no momento de escrever, e não no `press`: apertando de novo antes de a revisão
anterior acabar, no `press` a resposta ainda seria "não" e as frases sairiam
grudadas. O separador é um espaço à esquerda no primeiro pedaço da fala; a
revisão recebe o mesmo prefixo, senão `onde_muda` acha que o começo mudou e
reescreve a frase toda. `Enter`/`Esc` do usuário zeram o flag — a linha foi
enviada ou limpa, a próxima fala recomeça sem espaço.

**Dois modelos, e a medição que obriga a isso.** Nesta máquina (8 núcleos,
`int8`, `cpu_threads=4`): `small` leva 3,3–4,9 s por passada, `base` 1,0–1,7 s,
`tiny` 0,45 s. Mais núcleos *pioram* — com 8 fios o `small` sobe para 4,9 s.
Logo, nenhum modelo bom acompanha fala em tempo real: `base` escreve ao vivo e
`small` relê uma única vez no fim.

**Acordo local (LocalAgreement-2).** A cada passada, só vão para a tela as
palavras que apareceram iguais (por `comparavel()`, ignorando pontuação e
maiúscula) em duas passadas seguidas; a última palavra da hipótese nunca é
escrita na hora, porque enquanto a pessoa fala ela está cortada no meio. É isso
que garante que o texto nunca precise ser apagado *durante* a fala.

**Áudio em dois buffers.** `aberto` encolhe a cada palavra confirmada
(`descartar()` corta até o `fim` da última palavra escrita, e os tempos da
hipótese restante são deslocados por esse mesmo valor); `completo` guarda a
fala inteira para a revisão final. Sem o corte, uma fala de um minuto ficaria
progressivamente mais lenta, reprocessando tudo a cada passada.

**Cadência a partir do horário previsto.** `proxima = max(agora, proxima +
CADENCIA)`, não `agora + CADENCIA`: contando do fim do cálculo, o tempo de cada
passada se somava ao intervalo e o texto ia ficando cada vez mais atrás da voz.

**A correção do fim é a parte perigosa** — é ela que apaga texto da tela.
Regras, todas apoiadas em teste: o diff é por **palavra**, não por letra (letra
a letra, um "Quero" contra "quero" no começo da frase mandava reescrever 166
letras); o corte fica **depois da última palavra que combinou**, senão o espaço
some e sai "crie a pastanova"; se todas as palavras batem, só mexe quando a
última difere literalmente (pontuação final). E nada é corrigido se
`usuario_digitou` — qualquer tecla que não seja a de fala levanta o flag,
verificado duas vezes, antes e depois da releitura.

**Distinguir nossas teclas das do usuário.** O `Listener` do pynput enxerga os
eventos que o próprio `Controller` gera, então toda escrita acontece entre
`_estamos_escrevendo.set()` e `.clear()`, com 50 ms de folga no fim para os
eventos em trânsito. Sem isso o programa cancelaria a própria correção.

**Por que Whisper local e não o Windows.** A máquina não tem reconhecedor
SAPI clássico instalado — `System.Speech...InstalledRecognizers()` levanta
`NullReferenceException` e as chaves `Speech\Recognizers\Tokens` não existem.
Há só um reconhecedor OneCore (`MS-1046-110-WINMO-DNN`, pt-BR), alcançável
apenas pela API WinRT, sem binding estável para Python 3.13.

**Microfone sempre aberto.** O stream do `sounddevice` nunca fecha; o áudio só
é *acumulado* enquanto a tecla está pressionada. Abrir na hora do aperto
custaria uma fração de segundo e comeria a primeira sílaba. Um anel curto
(`PRE_ROLL`) guarda o instante anterior ao aperto, para quem fala junto com a
tecla. Autorrepetição do Windows no `on_press` é neutralizada pelo flag
`ativo`.

**Push-to-talk, não escuta contínua.** Com o microfone sempre escutando, ele
capturaria a própria voz do leitor falando as respostas e transcreveria o
Claude para dentro do Claude.

**Escrita por `pynput.type()`, não por área de transferência.** Medido com uma
janela Tk de teste: acento, cedilha, travessão e `backspace` chegam corretos —
o suposto problema de acento não existe, e o clipboard foi descartado (sujaria
o que o usuário copiou, e não serve para escrita incremental). Enter nunca é
enviado: ditado erra, e uma frase errada enviada sozinha viraria execução.
Quebras de linha viram espaço, senão o prompt do Claude Code envia no meio.

**Janela de destino.** Gravada no `press` (`GetForegroundWindow`) e trazida de
volta com `SetForegroundWindow` antes de cada escrita — o usuário reclamou
justamente de o texto cair "em outra área". Se a própria janela do escritor
estiver na frente no `press`, ele recusa a gravação com um bipe grave
(`win32console.GetConsoleWindow()` identifica qual é).

**A tecla só vale no Claude** (`SO_NO_CLAUDE`), porque o usuário usa F9 como
atalho em outros programas. A identificação é pelo processo, não pelo título —
o título muda a cada conversa. Regra: a janela em foco tem que ser de um
terminal (`PROGRAMAS_DE_TERMINAL`) e ter um `claude.exe` na descendência,
descendo **só por terminais**. A restrição do caminho não é decorativa: descendo
a árvore inteira, o Brave dava "sim" — havia um `cmd.exe` filho dele com um
`claude.exe` dentro. A varredura usa `CreateToolhelp32Snapshot` via `ctypes`
(~6 ms, 258 processos) com cache de 4 s por PID. A checagem vale só para
*iniciar*: parar tem que funcionar de qualquer janela.

**Toque-e-toque, não segurar** (`MODO_DE_ESCUTA = "alternar"`): em notebook a
fileira de cima exige `Fn`, e segurar `Fn+F9` falando ocupa as duas mãos.

**A tecla padrão é `ctrl_l`, não F9.** Medido com `--descobrir-tecla` no
notebook do usuário: F9 **com Fn** chega como `f9`; F9 **sozinho** manda
`cmd`+`l` — Windows+L, bloquear a tela. Esse atalho o próprio Windows
intercepta num nível inacessível a programas comuns, então a tecla é
inaproveitável: ela sempre bloqueia a tela. O `ctrl_r` foi cogitado e
descartado — o teclado não tem. `TECLA_DE_FALA` aceita `"vk:NNN"` para teclados
que mandem códigos fora do comum.

**Nunca confundir as próprias teclas com as do usuário.** `filtro_de_eventos`
(passado como `win32_event_filter` ao `Listener`) lê o bit `LLKHF_INJECTED`
(0x10) do evento e marca `_evento_injetado`; `ao_pressionar`/`ao_soltar` saem
na hora quando `evento_e_nosso()`. Sem isso o programa se sabotava: para
escrever ele manda um "soltei o Ctrl", ouvia esse próprio evento e — como
soltar encerra a fala no modo segurar — **encerrava a gravação na primeira
leva de palavras**. Era o sintoma "fala longa para no meio". `_filtro_ativo`
guarda o fallback (`_estamos_escrevendo`) para caso o filtro não exista.

**Nunca escrever com a tecla de acionar presa** (`liberar_o_teclado()`, chamada
no topo de `escrever()` e `apagar()`; no modo `"segurar"` ela não espera — o
dedo está na tecla de propósito — mas ainda solta as modificadoras). Bug relatado: para *desligar*, o usuário
segura o Ctrl; no instante em que a contagem fecha, o programa começa a digitar
o fecho da fala — com o dedo ainda no Ctrl. Cada letra virava atalho e o Claude
executou funções (o usuário viu "OV" na tela, rastro de Ctrl+O/Ctrl+V). A
função espera `_tecla_presa` limpar (até `ESPERA_PELA_TECLA`, 3 s) e depois
manda keyup em ctrl/alt/win por garantia — Shift fica de fora, só muda a letra.

**Lembrete falado e na tela** (`avisar_que_existe()`), na partida e a cada
`claude.exe` novo que `rondar_o_claude()` detecta (polling de 3 s sobre o mesmo
snapshot de processos). A fala usa SAPI direto, uma `SpVoice` por aviso, com
`CoInitialize()` na própria thread — igual ao leitor. A faixa na tela é um Tk
`overrideredirect` no canto inferior direito, sem barra de tarefas e sem roubar
foco, que se destrói sozinho: janela que o usuário possa fechar já custou caro
neste projeto.

**`MODO_DE_ESCUTA = "segurar"` combinado com a espera**: segure → bipe aos 3 s
→ fale → solte. Escolha do usuário, e também a mais segura: como o fim da fala
é o *release*, a tecla já saiu do caminho quando o fecho é digitado. No modo
`"alternar"` o Ctrl está fisicamente pressionado nesse instante — foi de onde
veio o bug do "OV".

**Segurar por `SEGUNDOS_PARA_ACIONAR` (3 s), sozinha.** Um `threading.Timer`
armado no press dispara `acionar()`; qualquer outra tecla no meio marca
`teve_companhia` e cancela o timer, e soltar antes também. Foi a saída para usar
o Ctrl da esquerda sem brigar com atalho nenhum: um toque rápido seria confundível
com o início de um Ctrl+C, mas segurar 3 s sozinha é gesto que ninguém faz sem
querer. Autorrepetição do Windows é neutralizada por `apertada_em` já estar
setado. Com `SEGUNDOS_PARA_ACIONAR = 0` volta o comportamento imediato
(`MODO_DE_ESCUTA` só tem efeito nesse caso), e o `main` avisa se isso for
combinado com uma modificadora.

**A revisão é pulada se outra fala já está na fila.** O usuário relatou "demora
muito grande" ao emendar falas: a revisão (~4 s) segurava a fala seguinte na
fila do trabalhador. Acompanhar a fala nova vale mais que caprichar numa frase
já escrita.

**Sem janela nenhuma.** `ligar.bat` chama `pythonw.exe` via `start`, e
sai. Duas tentativas anteriores falharam: janela aberta rouba o foco de onde se
ia ditar; janela *minimizada* continua sendo o processo, e o usuário a fechou —
matando o ditado, sem saber por quê. Sem janela não há o que fechar. Restam,
para diagnóstico, `ligar_com_janela.bat` (que é só `python -X utf8 -u` no lugar
do `pythonw`) e `registro.txt` (a saída, reescrita a cada partida). Dois bipes
subindo no fim do `main()` avisam que carregou — sem eles não haveria como saber
que subiu, e a tecla não responde durante os segundos de carga dos modelos. Na
unificação, `MINIMIZAR_JANELA` e `--com-janela` deixaram de existir: a escolha
entre janela e silêncio passou a ser qual `.bat` se usa.

**Silêncio e alucinação.** O Whisper inventa frases de legenda ("Legendas pela
comunidade Amara.org") quando recebe silêncio. Três defesas: `VOLUME_MINIMO`
(0,02 — medido: sala em silêncio bate 0,011, fala passa de 0,1),
`vad_filter=True` com `no_speech_threshold`, e a lista `FRASES_INVENTADAS`.
`condition_on_previous_text=False` porque, em frases soltas, o contexto
anterior faz o modelo entrar em círculo.

Validação usada no desenvolvimento, toda ela sem depender de alguém falando nem
de escrever numa janela real (recriar em `scratchpad/` se necessário):

1. **Áudio sintético** — gerar as frases com o SAPI (`SpFileStream`; o formato
   22 sai em 22050 Hz, não 16 kHz: reamostrar) e conferir a transcrição.
2. **Ditado ao vivo** — microfone falso que revela o áudio de 1 em 1 segundo e
   "tela" falsa que aplica `escrever`/`apagar` sobre uma string. Confere o
   texto incremental, o encolhimento do buffer aberto e a correção final.
3. **`onde_muda`** — nove casos: idêntico, só maiúscula, palavra trocada,
   palavra acrescentada, palavra removida, pontuação final, tela vazia,
   revisão vazia, maiúscula no meio.
3c. **Acionamento x atalho** — `ControleDeFala` montado à mão (sem microfone
   nem modelos), `SEGUNDOS_PARA_ACIONAR` encurtado, e `comecar`/`parar`
   trocados por registradores: segurar sozinha, segurar de novo (desliga),
   Ctrl+C rápido, Ctrl+C com a outra tecla chegando no fim da contagem, aperto
   curto, autorrepetição, AltGr (que manda um Ctrl junto no teclado
   brasileiro), Ctrl+C com o ditado ligado, e os dois modos sem espera.
   Copiar a lista de eventos ao guardar o caso: casos que reaproveitam o mesmo
   controle a mutariam.
3b. **Duas falas seguidas** — o `trabalhador` de verdade numa thread, áudio
   entregue no ritmo do relógio, e a segunda fala enfileirada com a revisão da
   primeira ainda rodando. Verifica que a tela final é exatamente
   `fala1.digitado + fala2.digitado` e que a segunda começa com espaço.
4. **Digitação** — janela Tk com `focus_force()` reaplicado periodicamente.
   Sem isso a janela recebe o foco mas o campo não, e o teste "falha" enquanto
   o texto vai parar na janela do usuário.

## O `/voice` nativo do Claude Code, e por que este projeto continua existindo

Desde a 2.1.x o Claude Code traz `/voice`: **ditado, e só ditado** — segurar
espaço (ou `/voice tap`) transcreve a fala na linha do prompt. Não lê nada em
voz alta. Conferido em agosto de 2026 na 2.1.233; fonte:
`https://code.claude.com/docs/en/voice-dictation`.

Não é redundância, e a comparação está documentada para o usuário em
`PERGUNTAS_E_RESPOSTAS.txt` seção 1b e em `COMO_USAR.txt`. Os três pontos que
sustentam este projeto: (1) a metade que **fala** não tem equivalente nativo —
inclusive as perguntas de múltipla escolha lidas na hora; (2) o `/voice` manda o
áudio para os servidores da Anthropic ("Audio is not processed locally"), contra
a restrição de 100% local; (3) aqui o Enter é sempre do usuário, enquanto o modo
tap envia sozinho. Menores: funciona com qualquer tipo de conta (o `/voice` exige
Claude.ai e é bloqueado por política de organização com HIPAA) e já fala pt-BR
sem ajuste.

Onde o nativo ganha, e a documentação diz isso: transcrição mais precisa
(servidor, vocabulário de código, nome do projeto/branch como pista), nada a
instalar, escreve direto no prompt sem descobrir janela nem devolver foco.

Convivência: teclas diferentes (espaço x Ctrl segurado), então não brigam. O
arranjo recomendado, se o usuário quiser os dois, é `/voz 2` — desliga nosso
ditado e mantém a leitura.

## Restrições do projeto

- 100% local e offline. Nada de API paga, chave de acesso ou serviço externo.
- Nunca ler blocos de código em voz alta.
- Nunca reler o histórico: só conteúdo novo a partir do momento em que o
  programa é ligado.
- Resistente a troca ou criação de sessões e de projetos, sem reiniciar.

## Ajustes

As configurações ficam em constantes no topo de `ClaudeEmVoz/claude_em_voz.py`.
Da metade que fala: `VELOCIDADE`, `VOLUME`, `INTERVALO`, `PREFERENCIA_VOZ`,
`FRASE_DE_ABERTURA` (`""` = liga calado), `LER_PERGUNTAS`,
`LER_DESCRICAO_DAS_OPCOES`, `FILTRAR_PROJETO` (`None` = todos os projetos),
`LIMITE_CARACTERES` (`0` = sem corte), `MOSTRAR_NO_TERMINAL` e `PRONUNCIAS`. Da
metade que escreve: `VOCABULARIO`,
`TECLA_DE_FALA`, `SEGUNDOS_PARA_ACIONAR`, `MODO_DE_ESCUTA`,
`SO_NO_CLAUDE`, `MODELO_AO_VIVO`, `MODELO_FINAL`, `CADENCIA`, `VOLUME_MINIMO`,
`MICROFONE`, `ESCREVER_NA_TELA`, `DEVOLVER_O_FOCO`, `GUARDAR_HISTORICO`,
`AVISO_SONORO`, `AVISO_FALADO` e `AVISO_NA_TELA`. Ambiente verificado:
Windows 11 Pro, Python 3.13, voz `Microsoft Maria Desktop - Portuguese(Brazil)`.
