# Claude em Voz — Linux

Conversa por voz com o Claude Code, **100% local e offline**. Sem serviço pago,
sem chave de acesso, sem mandar áudio para lugar nenhum.

Um programa só, com as duas metades da conversa:

- **Ouvir** — ele **fala** as respostas novas do Claude em voz alta, inclusive as
  perguntas de múltipla escolha com as opções, **na hora em que aparecem** — e
  não depois que você já escolheu.
- **Falar** — ele **escreve** o que você fala, ao vivo, palavra por palavra,
  enquanto você ainda está falando, como a digitação por voz do celular.

Ele nunca aperta Enter sozinho: a frase fica na linha esperando você ler e
enviar.

> A versão para Windows está em **[claude-em-voz-windows](https://github.com/alexsilvan84/claude-em-voz-windows)**.
> As duas fazem a mesma coisa; o que muda é a camada que encosta no sistema.

## Antes de instalar: X11 ou Wayland

São os dois jeitos de o Linux desenhar as janelas, e a diferença muda o que
funciona aqui:

- A metade que **fala** funciona igual nos dois. Não depende de janela nenhuma.
- A metade que **escreve** precisa saber qual janela está na frente e digitar
  dentro dela. No **X11** funciona sem ajuste. No **Wayland** o sistema impede
  isso de propósito, por segurança.

No Wayland há dois caminhos: instalar o `wtype` (funciona no KDE e no Sway; o
GNOME recusa), ou escolher a sessão X11 na tela de login. O `./diagnostico.sh`
diz qual serve para você.

Para saber onde está: `echo "$XDG_SESSION_TYPE"`

## Instalar

Num terminal, dentro da pasta:

```
bash INSTALAR_TUDO.sh
```

O `bash` na frente porque os arquivos podem chegar sem permissão de execução; o
próprio script conserta isso no fim.

Ele instala o espeak (a voz), o portaudio (o microfone), o xdotool (as
janelas), as bibliotecas do Python, os reconhecedores de fala e os quatro
ganchos do Claude Code — e no fim confere tudo e **diz em voz alta** o que ficou
faltando. Pede a sua senha uma vez, para os programas do sistema.

O **Claude Code não é instalado** por aqui, de propósito: quem chega neste
programa já o usa, e passar um instalador por cima trocaria a versão de uma
instalação que funciona.

A receita completa, passo a passo, está em `INSTALAR_DO_ZERO.txt`.

## No dia a dia

Ele liga e desliga sozinho junto com o Claude Code.

Para ditar: clique na janela do Claude, **segure o Ctrl da esquerda**, espere o
bipe, fale, e solte a tecla.

Digite `/voz` na janela do Claude para o menu que liga e desliga cada metade
sem fechar nada, e `/voz 5` para reler a última resposta.

## Uma voz melhor

Por padrão ele usa o espeak, que existe em qualquer Linux e fala português do
Brasil sem ajuste — mas é claramente robótico e cansa numa resposta longa.

Para uma voz quase natural, instale o `piper` e aponte um modelo em português na
constante `MODELO_DO_PIPER`. O `PERGUNTAS_E_RESPOSTAS.txt`, seção 1d, explica o
passo a passo.

## Se alguma coisa parar

```
./diagnostico.sh
```

Confere a fala, o microfone, a sua sessão gráfica e o jeito de digitar, os
reconhecedores, os quatro ganchos e o Claude Code — e **diz em voz alta** o que
encontrou. Ele pega sozinho a falha mais provável: mover a pasta de lugar deixa
os ganchos apontando para o vazio, e tudo para sem nenhum aviso.

## Os arquivos

| | |
|---|---|
| `COMO_USAR.txt` | o dia a dia |
| `PERGUNTAS_E_RESPOSTAS.txt` | o porquê de cada decisão |
| `INSTALAR_DO_ZERO.txt` | a receita completa de instalação |
| `CLAUDE.md` | a referência técnica, para quem for mexer no código |
| `testar.sh` | a bateria de testes — mais de 230 verificações em 5 s |

## Um aviso honesto

Esta versão foi escrita e testada a partir de uma máquina Windows. A lógica toda
passa na bateria de testes — 235 verificações —, os scripts têm sintaxe
conferida e os arquivos estão com terminação de linha do Linux. Mas **duas
verificações da bateria só podem ser fechadas rodando no Linux de verdade**, e
elas aparecem marcadas no resumo do `./testar.sh`.

O que depende do sistema — a voz sair, o microfone gravar, o texto ser digitado
na janela certa — só o primeiro `./diagnostico.sh` numa máquina Linux confirma.
