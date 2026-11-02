# Notas de processo

Registro de como as fases foram conduzidas, o que deu errado no caminho e o
que eu mudaria nos comandos do RePPIT. As sessões exportadas do opencode estão
em [`sessoes/`](sessoes/).

## Modelo por fase

O enunciado pede BigPickle. Usei BigPickle onde deu; nas outras fases o limite
gratuito do opencode tinha acabado e segui com modelos do OpenCode Go para não
parar o trabalho. Fica registrado aqui para quem for avaliar.

| Fase | Modelo | Sessão |
|---|---|---|
| Pesquisa | BigPickle | `01-pesquisa.json` |
| Proposta + ADR | BigPickle; ajuste de escopo com GLM-5.3 | `02-proposta.json` |
| Plano | Kimi K3 | `03-plano-kimi.json` |
| Implementação, passos 1 a 3 | Kimi K3 | `04-implementacao.json` |
| Implementação, passos 4 a 10, review e relatório de testes | BigPickle | `04-implementacao.json` |

Os limites que bateram, em 01/11/2026:

- por volta das 16h20, o limite diário gratuito do opencode acabou. Ele é
  compartilhado por todos os modelos gratuitos, então trocar de modelo grátis
  não resolveu. Voltou às 21h56;
- assinei o OpenCode Go, que não inclui o BigPickle. O GLM-5.3 deu timeout de
  transporte e troquei para o Kimi K3;
- às 18h28 o limite de 5 horas do Go também acabou, no meio da implementação.
  Esperei o gratuito voltar e terminei com BigPickle.

## Onde o agente errou

Os erros abaixo foram pegos por mim, pela revisão do próprio agente ou por
teste. Deixo registrado porque a nota avalia o raciocínio, e boa parte do
raciocínio útil veio de desconfiar do que o agente entregou.

**Pesquisa**

- Pulou duas vezes os itens de validação (acorde inexistente e tamanho de
  sequência), provavelmente depois de compactação de contexto. Só voltou a
  eles quando cobrei.
- Afirmou sem medir que a regra A daria zero resultados para sequências novas.
  Quando pedi a medição, as sequências populares deram de 10 a 278.
- Errou uma contagem (290 contra 296 para `C G Am F`) e corrigiu sozinho.

**Proposta**

- A ADR citava "~400 ms" por sequência. A medição real da regra literal é de
  61 a 93 ms, e com o índice por vocabulário cai para 0,15 ms.

**Plano**

- A primeira versão comparava a ordem dos resultados entre processos, mas a
  ordem varia com `PYTHONHASHSEED`. Passou a comparar conjuntos.
- Esqueceu o filtro de gênero na busca por sequência, que a tela usa, e a
  guarda contra sequência vazia (sem ela, `;;` casaria as 8.141 músicas de
  cifra vazia).

**Implementação**

- Disse "desta vez parei para perguntar antes de decidir" numa sessão em que
  não tinha perguntado nada, e se atribuiu mudanças no plano que eram da
  sessão anterior, feita com outro modelo.
- Alterou um teste de idempotência para caber na implementação, com o
  argumento de que grafias com caixa diferente sempre virariam 400. O dataset
  tem 151 pares de acordes que só diferem na caixa (`Am7`/`AM7`), então o
  argumento estava errado.
- O erro maior foi de decisão, e passou por pesquisa, proposta, plano e
  implementação: o matching baixava tudo para minúsculas, copiando o script
  que gerou a tag. Musicalmente `F7M` (sétima maior) e `F7m` são acordes
  diferentes. Percebi isso no meio da implementação. Medimos a regra com caixa
  exata, as 6 originais continuaram 514/514, e revisei proposta, ADR, plano,
  código e testes antes de seguir.
- Depois da mudança de caixa, a sugestão de grafia passou a indicar o acorde
  errado (`am7` sugeria `AM7`, usado em 40 músicas, em vez de `Am7`, usado em
  5.729). Virou uma lista ordenada por uso.
- O `#` dos acordes não era codificado na URL da busca: `C#m,A,E` chegava ao
  backend como `sequencia=C`. O checklist manual não pegou porque nenhuma
  sequência testada tinha `#`. Quem pegou foi o `/review-code`.
- O teste de borda passava mesmo sem as bordas. Descobri com teste de mutação
  (tirei as bordas e os 30 testes continuaram verdes) e troquei o caso por
  `B Em E`, que dá 0 com borda e 2 sem.

O agente também acertou coisas que vale citar: perguntou antes de mudar o
plano nas vezes em que havia ambiguidade, avisou sozinho que o script do
gabarito tinha quebrado depois que a função antiga foi removida, e o
`/review-code` achou o bug do `#`.

## Sugestões para os comandos do RePPIT

1. **`research-codebase` fixa a saída em `research/`.** A atividade já tinha
   o template em `docs/features/.../01-research.md`, e precisei mandar o
   agente ignorar o caminho do comando. O destino deveria vir como argumento.
2. **`research-codebase` proíbe avaliar ("no suggestions or evaluations").**
   A pesquisa da atividade pedia comparar regras de matching candidatas, o
   que é avaliação. Seria melhor separar "descrever o que existe" de "medir
   alternativas" em vez de proibir a segunda.
3. **O checklist da pesquisa é "interno".** O agente pulou itens duas vezes e
   ninguém viu. Se o checklist fosse escrito no documento e conferido no fim,
   o item pulado apareceria.
4. **`make-plan` aponta para `@templates/design_doc_template.md` e
   `desired_location`,** que não vêm com o repositório de comandos. O agente
   precisa adivinhar o formato.
5. **`implement` é uma linha só,** com o caminho literal `/path/to/plan_md` e
   sem `$ARGUMENTS`. Precisei escrever o caminho do plano no prompt. Também
   não diz nada sobre escrever o teste antes do código, nem sobre atualizar o
   plano quando a decisão muda, que o enunciado exige.
6. **`review-code` só olha mudanças não commitadas.** Como commitei por fatia,
   ele não teria nada para revisar. Precisei pedir `git diff <plano>..HEAD`.
   O comando deveria aceitar um intervalo e conferir o código contra o plano e
   a proposta, não só contra o diff.
7. **Não existe comando para o T do RePPIT.** Falta um passo de testes que
   peça teste antes da implementação, um oráculo independente do código
   testado e algum teste de mutação. Foi a mutação que mostrou que o teste de
   borda não protegia nada.
8. **Nenhum comando fala de tamanho de sessão.** A pesquisa passou de 300
   mensagens numa sessão só, o contexto foi compactado e itens se perderam. Os
   comandos poderiam recomendar uma sessão por fase e o documento da fase
   anterior como entrada, o que também ajuda quando o limite de uso acaba no
   meio.
