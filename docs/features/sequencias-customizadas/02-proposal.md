# Proposta — Sequências de Acordes Customizadas

## Abordagem escolhida

### Algoritmo de matching

Uma música é compatível com a sequência `S = (t1 … tn)` se, e somente se, as duas
condições valerem, comparando tokens sem diferenciar maiúsculas de minúsculas:

1. **Bloco contíguo.** `(t1 … tn)` aparece como sequência contígua de tokens na
   cifra da música, sobre os tokens que `limpa_cifra` já produziu
   (`main.py:11-23`, aplicado em `main.py:49-61`). Ordem e adjacência contam;
   repetição de acorde na música não invalida nada.
2. **Vocabulário exato.** Todo acorde da música pertence ao conjunto de `S`.

É exatamente a regra que gerou a coluna `SEQ_FAMOSA`
(`scripts/generate_data_set.py:7-24`), reproduzida em 514 de 514 músicas, zero
divergência nos dois sentidos (`01-research.md` §2.1). Ela vale para **todas** as
sequências, antigas e novas: essa é a condição para que as 6 originais devolvam o
mesmo conjunto de hoje sem nenhum caso especial no código.

O que a regra **não** faz, e precisa estar dito na proposta porque é uma
limitação de produto, não um bug: ela não pergunta "a progressão aparece na
música?", e sim "a música inteira usa somente esses acordes, e eles aparecem
nessa ordem". Como a média é 7,8 acordes distintos por música, só 19.923 das
67.585 (29,5%) têm ≤ 4 acordes distintos e podem, em princípio, casar uma
sequência de 4 acordes. As 10 progressões populares medidas devolveram de 10 a
278 músicas (§2.5), então sequência nova não devolve zero em geral — mas uma
sequência de vocabulário incomum devolve. É o preço de manter a semântica do app.

**Implementação.** A condição (2) permite transformar o matching em um lookup,
o que resolve a única objeção real de custo que existia contra esta proposta:

- no load do CSV, cada música ganha duas estruturas derivadas: a cifra
  normalizada com bordas, `cifra_borda = ';' + ';'.join(tokens em minúsculas) +
  ';'`, e entra no índice `vocabulario -> [músicas]`, chaveado por
  `frozenset(tokens em minúsculas de musica.acordes)`;
- para uma sequência `S`, `seq_vocab = frozenset(S em minúsculas)` e
  `seq_borda = ';' + ';'.join(S em minúsculas) + ';'`. Os candidatos são
  `indice.get(seq_vocab)`, e o match é `seq_borda in musica.cifra_borda`.
  Como o bloco contíguo implica `vocabulário de S ⊆ vocabulário da música`, e o
  índice já garante a inclusão contrária, o lookup é a regra A inteira.

Medido nesta máquina (Python 3.9.6, mesmo CSV): 39.385 vocabulários distintos,
índice construído em 1,3 s no boot, ~48 MB de memória adicional, **0,15 ms de
mediana e 0,42 ms no pior caso por sequência**, com 514/514 preservado para as 6.
Para comparação, a implementação literal do gerador custa 87 ms por sequência
(522 ms para as 6), e a varredura com poda por vocabulário custa 2,8 ms. Os
405 ms do §1.4 são uma passada com as 6 sequências, não o custo de uma; medido
por sequência, o número que importa é o de cima. O boot cresce junto: o parse do
CSV leva ~4,3 s nesta máquina e a construção do índice ~1,3 s, então ~5,6 s até
a primeira resposta. Se a memória incomodar, a varredura com poda por vocabulário
(2,8 ms, +45 MB) ou por tamanho do vocabulário (64 ms, sem memória extra) são
substitutas diretas — todas produzem o mesmo conjunto.

**Bordas, e não `in` puro.** A comparação do gerador é
`';'.join(seq).lower() in ';'.join(cifra).lower()`, sem delimitador nas pontas.
Sob vocabulário exato isso coincide com o token a token nas 6 (§2.1), mas não em
geral: com a sequência `A7 D A`, a cifra `A7;D;A7` casa por prefixo
(`'a7;d;a' in 'a7;d;a7'`) e produz **17** matches em vez de **1** — 16 falsos
positivos medidos. As bordas `;` eliminam o artefato, e as 6 continuam 514/514.

**Ordem, rotação e caixa.** Rotação é sequência diferente: `Bm G D A` marca 199
músicas e `D A Bm G` marca 216 (§2.7), então tratá-las como a mesma entrada
faria a busca devolver um conjunto que o usuário não digitou. A chave de
identidade é a tupla na ordem digitada, em minúsculas, unida por `;`
(`bm;g;d;a` ≠ `d;a;bm;g`). Minúsculas são intencionais: o matching já é
insensível a caixa (o gerador baixa tudo, `generate_data_set.py:12`), então
`A7M` e `A7m` produziriam resultados idênticos e não há razão para duas linhas —
as 151 grafias que colidem (§1.4) colidem também no resultado. `acordes` é
guardado como foi digitado, para exibição.

**Validação de entrada.** Rejeita-se **apenas** o que é vazio: lista vazia,
tokens em branco ou só separadores → 400. Um acorde é válido (`C` devolve 17
músicas e `Am` devolve 2, §2.8, reconferido). Acorde fora do vocabulário do
dataset → 400 com o token recusado, validando contra o set `acordes`
(`main.py:39`, 6.653 tokens, exposto em `main.py:162-164`), comparação exata;
se existir um token igual ignorando a caixa, a resposta traz `sugestao`. Não se
usa lista curada de acordes: ela recusaria grafias que o CSV usa (`7M`, `maj7`,
`º`, `(9)`, inversões) e 3.045 tokens aparecem em uma única música (§2.8). O
critério é "existe no dataset", não "é um acorde bonito" — e o próprio set tem
44 tokens que não são acordes, custo aceito e documentado.

### Banco de dados

`sqlite3` da biblioteca padrão, arquivo único, sem dependência nova em
`requirements.txt` e sem serviço extra — compatível com o container único de
`docs/adr/0001-local-only-docker-deploy.md:9-16`. Só o **catálogo de sequências**
vai para o banco; músicas, gêneros e acordes continuam vindo do CSV em memória,
como hoje (`main.py:37-98`).

- Caminho: `SEQUENCIAS_DB`, default `/app/dados/sequencias.db`; `makedirs` do
  diretório no boot.
- Volume nomeado documentado no README/AGENTS:
  `docker run -v deciframe-dados:/app/dados -p 8080:8080 ciframe`. O
  `Dockerfile` ganha `RUN mkdir -p /app/dados` e `VOLUME ["/app/dados"]`;
  `dados/` entra no `.dockerignore` para que `COPY . .` não asse um banco de
  desenvolvimento dentro da imagem. Sem o volume, o arquivo sobrevive a
  `restart` mas não a `docker rm` nem a rebuild (§3.2).
- `PRAGMA journal_mode=WAL`, `PRAGMA busy_timeout=5000`, `foreign_keys=ON`.
  Conexão por request (`sqlite3` não deve ser compartilhado entre threads).
  Escrita serializada é irrelevante aqui: o gunicorn atual roda 1 worker e 1
  thread (§3.1) e o catálogo é aberto mas minúsculo.
- Seed das 6 no boot, depois do load do CSV, com `INSERT` idempotente apoiado no
  `UNIQUE(chave)` — não em `SELECT` antes de `INSERT`, que perde a corrida se o
  número de workers mudar. As 6 entram com a ordem atual, porque é a ordem que o
  matching usa: `Bm G D A`, `C G Am F`, `Em G`, `C A7 Dm G7`, `Gm F`,
  `C C7 F Fm`.
- Versão do esquema em `PRAGMA user_version` (1), conferida no boot: não há
  framework de migração e não vale a pena introduzir um para uma tabela.

### Esquema de dados (alto nível)

```
sequencias
  id         INTEGER PRIMARY KEY AUTOINCREMENT
  chave      TEXT NOT NULL UNIQUE      -- acordes na ordem, em minúsculas, ';'-unidos
  acordes    TEXT NOT NULL             -- JSON array na ordem digitada (exibição)
  origem     TEXT NOT NULL             -- 'seed' | 'usuario'
  criado_em  TEXT NOT NULL             -- ISO 8601 UTC
```

Uma tabela, sem tabela de junção e sem resultado materializado: o matching custa
0,15 ms e não precisa de cache. Nada é migrado do CSV. As 6 sementes têm
`origem='seed'` e chaves `bm;g;d;a`, `c;g;am;f`, `em;g`, `c;a7;dm;g7`, `gm;f`,
`c;c7;f;fm`.

### API

Tudo continua saindo como `json.dumps(...)` e `Content-Type: text/html`
(`main.py:142`, `197`, `201`), inclusive as respostas de erro — nada de
`jsonify`.

- `GET /sequencias` → `[{id, acordes, origem, total_musicas}]`. `total_musicas` é
  calculado na hora (0,15 ms por linha); com centenas de sequências isso precisa
  de cache, e é aí que a decisão volta — ver escopo fora.
- `POST /sequencias` com `{"acordes": ["Bm","G","D","A"]}`:
  - 201 `{"id": 7, "acordes": [...], "existente": false, "total_musicas": 199}`
    quando cria;
  - 200 `{"id": 0, "existente": true, "total_musicas": 199}` quando a chave já
    existe (idempotente, sem 409: o catálogo é anônimo e "já existe, use esta" é
    mais útil que um conflito para explicar);
  - 400 `{"erro": "sequencia_vazia"}`;
  - 400 `{"erro": "acorde_desconhecido", "acordes": [{"acorde": "cb",
    "sugestao": null}]}`;
  - 400 `{"erro": "corpo_invalido"}` para corpo que não é JSON com `acordes`.
- `GET /similares?sequencia=Bm,G,D,A` mantém a forma atual: separa por vírgula,
  faz `strip` e descarta token vazio, baixa a caixa e resolve pela `chave`. Se
  não existir, devolve `[]` com 200, como hoje (§2.8) — a busca não é o
  cadastro e o contrato antigo fica preservado. A resposta continua com os
  mesmos campos de `main.py:210-220`, a mesma ordem de hoje (a iteração de
  `get_similares_por_sequencia` sobre `apply_filtro`, `main.py:203-223` e
  `main.py:266-272`) e o mesmo corte de `get_pagina` (`main.py:226-228`). A
  única mudança de parâmetro é a validação de `pagina` (inteiro ≥ 1; hoje
  `pagina=abc` derruba com 500, `main.py:227`).

Efeitos colaterais aceitos e mensuráveis: `Bm, G, D, A` (com espaço) passa a
funcionar (hoje devolve 0) e `Bm,G,D,A,` continua funcionando. Nada mais muda no
comportamento observável do endpoint — nem a ordem, nem o conteúdo da página 1;
o fato de a ordem variar entre processos (`PYTHONHASHSEED`, §2.4) continua
existindo, porque corrigi-lo é decisão de produto, não pré-requisito desta
feature.

### Frontend

`static/assets/js/controllers/sequencia.js` perde os quatro objetos hardcoded
(`sequencia.js:2-37`) e carrega `GET /sequencias` no início do controller,
montando `{acorde, cor}` a partir de `acordes` para o `df-hex` que o template já
usa (`sequencia.html:6-8`). Isso corrige a divergência 4-vs-6 do §4 e faz a tela
refletir o catálogo.

Cadastro na mesma página, acima da lista: um campo de texto que aceita `Bm G D A`
(espaço ou vírgula), um `datalist` alimentado por `GET /acordes` para evitar
digitação livre, e um botão que faz `POST /sequencias`. Em 201/200 a lista é
recarregada e a sequência nova é selecionada; em 400 a mensagem do servidor é
exibida (sequência vazia, acorde desconhecido e a sugestão de grafia). Mostrar o
`total_musicas` no bloco de cada sequência é o que torna o efeito da regra A
compreensível para quem cadastra.

Resultados ficam intocados: o controller continua sem enviar `pagina`
(`sequencia.js:73-76`) e o template continua com `orderBy:'-popularidade'`
(`sequencia.html:42`). A limitação atual de a UI mostrar só 100 dos 199/296
resultados (§2.4) permanece — conhecida, herdada e declarada fora do escopo. Um
cuidado ao mexir no template: `ng-hide="music.diferenca.length"`
(`sequencia.html:43`) funciona por acidente, porque `diferenca` não existe na
resposta de sequência; não remover a expressão.

## Alternativas consideradas e descartadas

**Regra C (bloco contíguo, sem vocabulário exato) para as sequências novas, com a
tag congelada para as 6.** É a alternativa que discorda da decisão de matching e
merece registro porque o argumento é bom: a condição (2) transforma a busca em
um filtro sobre o vocabulário da música, não sobre a progressão, e é por isso que
7.170 músicas têm o bloco contíguo sem a tag (§1.3); com regra C, `Em Am D G` sai
de 10 para 443 e `G D Em C` de 252 para 1.141 (§2.5). Descartada porque exigiria
duas semânticas no mesmo endpoint — as 6 continuariam na tag e as novas em C —,
com um degrau visível entre sequências equivalentes (a mesma `Bm G D A` daria 199
como semente e 667 como sequência nova), e porque o enunciado trata a regressão
das 6 como o contrato do produto, não como um detalhe de compatibilidade. Se a
regra A se mostrar estreita demais em uso, é esta a alternativa a retomar, e o
lugar seria um campo por sequência dizendo qual regra vale — explicitamente fora
do escopo agora.

**Catálogo aberto com matching materializado no cadastro.** As sequências
guardariam os ids das músicas casadas numa tabela de junção, calculados no
`POST`; a busca viraria leitura de algumas centenas de ids e o
`POST` devolveria `total_musicas` sem recalcular. Fazia sentido quando o custo de
matching era estimado em ~0,4 s por consulta. A medição derrubou a premissa
(0,15 ms): a materialização adicionaria latência de escrita, uma tabela derivada
para invalidar quando o CSV muda e um estado que pode ficar velho em silêncio,
sem ganho de leitura perceptível. Descartada. Se o catálogo crescer para milhares
de sequências, o caminho é cachear `total_musicas`, não materializar os matches.

**Dedupe por rotação (chave = menor rotação) e catálogo aberto a acordes fora do
dataset.** A primeira funde `D A Bm G` com `Bm G D A`, que devolvem conjuntos
diferentes (216 vs 199, união 240, §2.7); a chave deixaria de refletir o que o
matching faz, e o usuário receberia o resultado de outro ponto de partida sem
entender. A segunda aceitaria um acorde que, sob a regra A, nunca pode casar
(vocabulário exato não contém token inexistente) e criaria linhas permanentemente
inertes; o 400 com sugestão resolve o erro de digitação no momento em que ele
acontece.

## Escopo explícito

**Dentro do escopo:**

- Tabela `sequencias` em SQLite, criada e semeada no boot, com volume nomeado
  documentado no README e no AGENTS.
- Regra A como regra única de matching, com índice por vocabulário construído no
  load e teste de regressão 514/514 contra a coluna `SEQ_FAMOSA`.
- `GET /sequencias`, `POST /sequencias` e `GET /similares?sequencia=` resolvido
  pelo catálogo, preservando `json.dumps` e `text/html`.
- Validação: vazio → 400, acorde fora do dataset → 400, 1 acorde válido,
  `pagina` validada.
- `#/porsequencia` com catálogo do backend, formulário de cadastro e contagem
  por sequência.
- ADR `docs/adr/0002-persist-custom-sequences.md`.

**Fora do escopo (e por quê):**

- Campo harmônico, transposição e matching por graus (`NCIFRA`): a decisão está
  adiada no §2.9 e muda a unidade de comparação, não só o armazenamento; aplicá-la
  às 6 quebraria a regressão.
- Normalização de acordes (enarmonia, tríade, inversão): nenhuma existe no
  runtime e qualquer uma muda o que é "o mesmo acorde" — mexer nisso junto com a
  persistência tornaria impossível saber qual mudança causou qual diferença.
- Editar, renomear, excluir ou moderar sequências: o catálogo é append-only e
  anônimo nesta fase; exclusão e rate limit são o próximo problema, não este.
- Paginar a UI ("carregar mais") e reordenar os resultados por popularidade no
  servidor: não é exigência do enunciado e muda comportamento observável de um
  endpoint que hoje serve à tela. A limitação de a UI mostrar 100 de 199/296
  (§2.4) fica documentada; a validação de `pagina` entra só para o request não
  morrer com 500.
- Migrar músicas, gêneros ou a coluna `SEQ_FAMOSA` para o banco: fixado no
  enunciado e desnecessário — a coluna fica no CSV como oráculo dos testes.
- Trocar `json.dumps` por `jsonify` ou corrigir o `Content-Type`: mudança de
  contrato, não limpeza.
- Reescrever o AngularJS 1.4.9 ou o layout da página: o ADR 0003 libera tocar no
  frontend quando a tarefa exige, e esta exige o mínimo.

## Revisão — caixa exata no matching e na chave (2026-11-01)

Esta seção revisa a decisão de "Ordem, rotação e caixa" acima, que continua no
texto como registro. O que muda: **a caixa do acorde passa a fazer parte da
identidade**, tanto no matching quanto na chave do catálogo. `cifra_borda`, o
índice por vocabulário e `busca_por_sequencia` deixam de baixar os tokens para
minúsculas; a chave passa a ser `';'.join(tokens)` na grafia digitada (depois do
`strip`). `acordes` continua guardado como foi digitado.

Por quê: `A7M` é sétima maior e `A7m` é menor com sétima; `AM7` ≠ `Am7`,
`F#M` ≠ `F#m`, `F7M` ≠ `F7m`. Nesses pares a caixa não é ruído de digitação —
é o que distingue o acorde. O `lower()` vinha do gerador
(`generate_data_set.py:12`), não de uma decisão musical; aplicá-lo fazia buscar
`AM7` trazer música com `Am7`. As 151 grafias que colidiam (§1.4) colidiam no
resultado justamente por causa disso.

Medição (regra A com caixa exata, índice e bordas sem `lower()`): as 6
sequências continuam batendo **id a id** com o gabarito — `bm;g;d;a` 199,
`c;g;am;f` 296, `em;g` 4, `c;a7;dm;g7` 5, `gm;f` 7, `c;c7;f;fm` 3 (514 no
total). Caso real do dataset: `C#M A E` devolve só `rpm_ninfa`, enquanto
`C#m A E` devolve 4 músicas (Kings Of Leon, U2, Hillsong United, Wiz Khalifa)
— com o `lower()` as duas buscas devolviam as mesmas 5.

Limite aceito: a caixa só separa acordes no par `m`/`M`. Grafias que diferem em
mais que isso continuam separadas como já eram, e grafias que são o mesmo
acorde mas mudam a caixa de outra letra também viram sequências diferentes:
`G7sus` e `G7SUS` são o mesmo acorde e agora são duas entradas, como `C7M` e
`Cmaj7` já são hoje. Normalizar notação (enarmonia, `maj7`/`7M`, `sus`) segue
fora do escopo — a mudança aqui é parar de descartar caixa, não passar a
normalizar.

Correção decorrente na sugestão: com a validação exata, o campo `sugestao`
(uma grafia só) passou a errar o acorde, porque `sorted()[0]` prefere
maiúsculas — `am7` sugeria `AM7` (40 músicas) em vez de `Am7` (5.729), e
`f#m` sugeria `F#M` (59) em vez de `F#m` (10.348). O 400 passa a trazer
`sugestoes`: a lista de **todas** as grafias que batem ignorando caixa,
ordenada pelo número de músicas que usam cada uma (decrescente; empate
alfabético), e `[]` quando não há nenhuma. O erro mostra todas as opções
reais do dataset sem escolher uma grafia que, como `AM7`, é outro acorde.

Consequência de dados: a chave antiga (`bm;g;d;a`) não encontra mais as
sequências novas (`Bm;G;D;A`). Como a feature ainda não foi publicada, não há
migração: o banco local `dados/sequencias.db` é recriado pelo seed no próximo
boot.
