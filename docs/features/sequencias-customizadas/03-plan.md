# Plano — Sequências de Acordes Customizadas

Baseado em `02-proposal.md` e `docs/adr/0002-persist-custom-sequences.md`.
Restrições fixas: testes com `unittest` da stdlib (zero dependência nova em
`requirements.txt`); `main.py` continua servindo `json.dumps` com
`Content-Type: text/html`; a regressão das 6 sequências é o contrato do produto.

Três restrições que atravessam o plano:

- **Ordem não é contrato entre processos.** A ordem dos resultados de
  `/similares?sequencia=` varia com `PYTHONHASHSEED` (§2.4 da pesquisa) —
  comportamento pré-existente, fora do escopo corrigir. Por isso o gabarito
  grava ids **ordenados alfabeticamente** e toda comparação entre processos é
  de conjunto; paridade de ordem só se verifica **dentro do mesmo processo**.
- **Banco em caminho relativo.** Default de `SEQUENCIAS_DB` é
  `dados/sequencias.db` (não `/app/dados/...`, que não existe no mac). No
  container o `WORKDIR` é `/app`, então o arquivo cai em
  `/app/dados/sequencias.db` — mesmo lugar de antes, mesmo volume. Localmente
  cai no checkout, coerente com o CSV, que já exige rodar da raiz.
- **Porta local 5000 ocupada no macOS.** O AirPlay Receiver escuta na 5000
  nesta máquina, então `python main.py` não bindaria. As verificações locais
  com servidor de pé usam
  `python -c "import main; main.app.run(port=5001)"` e `localhost:5001`; o
  Docker continua na 8080. Nenhuma mudança em `main.py`: o default segue 5000.

## Passos

1. [x] **Gabarito da regressão com o código atual (antes de tocar em
   `main.py`).** Criar `scripts/gerar_gabarito_sequencias.py`: importa `main`
   (com `SEQUENCIAS_DB` temporário, para não criar `dados/`) e lê a coluna
   `SEQ_FAMOSA` direto de `musica.seqs_famosas` para `id_seq` 0–5 — sem chamar
   função de busca de `main.py`, para o oráculo ficar independente do código
   testado. Grava `tests/fixtures/gabarito_sequencias.json` com
   `{chave: [id_unico_musica, ...]}` — **ids em `sorted()`**, porque a ordem
   de iteração varia entre processos (§2.4). Chaves: `bm;g;d;a`, `c;g;am;f`,
   `em;g`, `c;a7;dm;g7`, `gm;f`, `c;c7;f;fm`. O fixture é commitado.
   **Verificação:** `python scripts/gerar_gabarito_sequencias.py` imprime os
   totais, que têm de bater com a §2.1 da pesquisa: `bm;g;d;a` = 199,
   `c;g;am;f` = 296, `em;g` = 4, `c;a7;dm;g7` = 5, `gm;f` = 7,
   `c;c7;f;fm` = 3 (soma 514). O JSON tem 6 chaves com listas não vazias, e
   `git diff --exit-code tests/fixtures/gabarito_sequencias.json` sai vazio
   depois de rodar o script sobre o fixture commitado.

2. [x] **Matching pela regra A com índice por vocabulário, sem mexer nas
   rotas.** Em `main.py`, no load do CSV: montar `cifra_borda` por música
   (`';' + ';'.join(tokens na caixa exata) + ';'` — dict à parte em `main.py`,
   não atributo de `Musica`, para não vazar no `__dict__` devolvido por
   `/musicas` e `/musica/<id>`; `musica.py` não muda) e o índice
   `frozenset(acordes na caixa exata) -> [músicas]`, com as listas construídas
   na ordem de
   `apply_filtro(musicas.values(), generos)` — gênero a gênero, cada gênero
   por popularidade. (`apply_filtro`, `main.py:266-272`, **ignora** o primeiro
   argumento e concatena `genero_musicas[genero]`; essa é a iteração real de
   `get_similares_por_sequencia`, verificado empiricamente: a ordem de
   `musicas.values()` puro **não** bate em 5 das 6 sequências.) Nova função
   `busca_por_sequencia(tokens, generos_key=None)` faz lookup no índice +
   teste de substring com bordas, devolvendo os mesmos campos de
   `get_similares_por_sequencia`; com `generos_key`, os candidatos são
   filtrados por `musica.genero` — a função velha filtrava via `apply_filtro`
   e a tela manda `&generos=`, então sem esse parâmetro o passo 8 quebraria o
   filtro de gênero sem teste pegar. **A caixa é exata**: `A7M` e `A7m` são
   vocabulários diferentes e a busca não baixa mais nada para minúsculas
   (revisão de 2026-11-01 na proposta e no ADR 0002). Guarda no início:
   `tokens` vazio devolve
   `[]` (sem ela, a sequência vazia casaria as 8.141 músicas de cifra vazia
   por `';;' in ';;'`, o perigo da §2.8).
   **Verificação:** `python -m unittest tests.test_matching`, com cinco
   testes commitados: (a) para cada uma das 6, na grafia do seed,
   `sorted(ids novos) == gabarito[chave]` — as chaves do fixture seguem em
   minúsculas, o casamento é `';'.join(token.lower())`; (b) borda:
   `["B","Em","E"]` devolve 0 na caixa exata e devolveria 2 sem as bordas
   (`E` casaria como prefixo de `Em`; o `A7,D,A` da proposta devolve 1 com ou
   sem borda sob vocabulário exato); (c) `busca_por_sequencia([])` devolve `[]` — a
   sequência vazia não chega à busca; (d) filtro de gênero:
   `busca_por_sequencia(["Bm","G","D","A"], ['Rock'])` devolve só músicas de
   Rock, na mesma ordem relativa do resultado sem filtro; (e) caixa muda o
   resultado em caso real do dataset: `["C#M","A","E"]` devolve só
   `rpm_ninfa`, enquanto `["C#m","A","E"]` devolve as 4 músicas com `C#m`.
   Mais uma **conferência
   manual única**, não commitada (a função velha morre no passo 8): no mesmo
   processo, comparar a ordem de `busca_por_sequencia` com a de
   `get_similares_por_sequencia` para as 6, sem filtro e com
   `generos_key=['Rock']` — `python -c "import main; ..."` —, que é o único
   lugar onde a ordem é determinística.

3. [x] **Camada SQLite em módulo novo `sequencias_db.py`.** Conexão por
   chamada; `PRAGMA journal_mode=WAL`, `busy_timeout=5000`,
   `foreign_keys=ON`; esquema da tabela `sequencias` (proposta §Esquema) com
   `UNIQUE(chave)`; `PRAGMA user_version = 1` conferido no init; seed das 6
   com `INSERT OR IGNORE` e `origem='seed'`; funções `listar()`,
   `inserir_ou_obter(tokens)` (devolve `(linha, criada)`),
   `buscar_por_chave(chave)`. A chave é `';'.join(tokens)` na grafia digitada
   (caixa exata; revisão de 2026-11-01), não em minúsculas. Caminho via
   `SEQUENCIAS_DB`, default
   `dados/sequencias.db` (relativo), com `makedirs` do diretório no init.
   **Verificação:** `python -m unittest tests.test_sequencias_db` — usa
   arquivo temporário: schema criado, `user_version=1`, seed insere as 6 na
   ordem certa com as chaves na grafia do seed (`Bm;G;D;A`, ...), seed
   repetido não duplica, `inserir_ou_obter` com os mesmos tokens devolve a
   linha existente com `criada=False`, tokens com caixa diferente criam outra
   linha, e `buscar_por_chave('Em;G')` encontra enquanto `'em;g'` não.

4. [x] **Boot: init do banco + seed, sem mudar rota nenhuma.** Em `main.py`,
   depois do load do CSV: chamar o init de `sequencias_db.py` (cria diretório,
   schema, confere `user_version`) e rodar o seed das 6. Nenhum endpoint novo
   ainda; o dict `sequencias` continua em uso.
   **Verificação:** com a 5001 local (ver restrição de porta),
   `SEQUENCIAS_DB=/tmp/seq-boot.db python -c "import main; main.app.run(port=5001)"`
   sobe sem erro; em outro terminal,
   `sqlite3 /tmp/seq-boot.db 'select count(*), origem from sequencias group by origem'`
   devolve 6 linhas `seed`; `curl localhost:5001/generos` continua devolvendo
   o JSON de gêneros.

5. [x] **`GET /sequencias`.** Devolve
   `[{id, acordes, origem, total_musicas}]`, com `total_musicas` calculado na
   hora via `busca_por_sequencia`. Resposta em `json.dumps`, como sempre.
   **Verificação:** `python -m unittest tests.test_api` (test_client com
   `SEQUENCIAS_DB` temporário setado antes de importar `main`): lista tem as
   6 sementes, e `total_musicas` de `bm;g;d;a` é igual a
   `len(gabarito["bm;g;d;a"])`. Mais `curl localhost:5001/sequencias` com o
   servidor de pé.

6. [x] **`POST /sequencias`: criação e idempotência.** Corpo
   `{"acordes": [...]}` válido → 201 `{"id", "acordes", "existente": false,
   "total_musicas"}`; mesma chave de novo → 200 com `existente: true` e mesmo
   `id`. Chave = tokens como digitados (só `strip`), unidos por `;`, na ordem
   digitada — **caixa exata**: `A7M;D` ≠ `A7m;D`; `acordes` guardado como
   digitado.
   **Verificação:** unittest — POST cria, GET passa a listar 7, POST repetido
   com os mesmos tokens devolve 200 com o mesmo `id` e a lista continua com 7;
   POST com a caixa trocada (`Am7,D` depois de `AM7,D`, e `A7m,D` depois de
   `A7M,D`) devolve 201 com outro `id`. Mais um `curl -X POST` manual.

7. [x] **`POST /sequencias`: os três 400.** Corpo que não é JSON com
   `acordes` → `corpo_invalido`; lista vazia ou tokens em branco/separadores
   → `sequencia_vazia`; token fora do set `acordes` → `acorde_desconhecido`
   com `sugestoes`: lista de **todas** as grafias que batem ignorando caixa,
   ordenada pelo número de músicas que usam cada uma (decrescente; empate
   alfabético), e `[]` quando não há nenhuma (validação exata contra o set,
   como na proposta). A validação é exata inclusive na
   caixa — `AM7` e `Am7` são tokens válidos e **distintos** —, e as
   `sugestoes` continuam sendo o caminho para corrigir grafia de caixa errada
   (`bm` → `Bm`). A contagem é de músicas, não de ocorrências: cada música
   conta uma vez por grafia (via `musica.acordes`), então um refrão repetido
   não distorce a ordem.
   Cada token sofre `strip` de espaços nas pontas **antes** da validação e é
   guardado já sem eles (`[" Bm "]` vira `["Bm"]` e cai na chave `Bm`); sem
   isso `"Bm "` seria recusado como desconhecido mesmo sendo grafia do
   dataset. A checagem de vazio roda depois do trim e só separadores
   (`,`/`;`) também contam como vazio. O trim não funde acordes diferentes:
   `A7M` (sétima maior) continua em `A7M`, distinto de `Am7` em `Am7`.
   **Verificação:** unittest cobrindo cada 400 — status, campo `erro` e, no
   caso do acorde, `sugestoes` com todas as grafias (`bm` → `['Bm']`), ordem
   por uso (`am7` começa com `Am7`, não `AM7`; 5.729 x 40 músicas; `f#m`
   começa com `F#m`) e `[]` para token inexistente (`Cb`); mais `[" Bm "]`
   aceito e guardado
   sem os espaços.

8. [x] **`/similares?sequencia=` resolve pelo catálogo; remove o dict
   hardcoded.** Separar por vírgula, `strip`, descartar vazio, montar a chave
   **na caixa exata** (sem baixar para minúsculas; revisão de 2026-11-01) e
   buscar no catálogo; existe →
   `busca_por_sequencia(tokens_da_linha, generos_key)`, **repassando o filtro
   de gênero** como a função velha fazia via `apply_filtro` (a tela manda
   `&generos=`); não existe → `[]` com 200, como hoje.
   `pagina` validada como inteiro ≥ 1; fora disso, 400 com corpo
   `{"erro": "pagina_invalida"}` (em vez do 500 de hoje). Apagar o
   dict `sequencias` e a função `get_similares_por_sequencia`.
   **Verificação:** unittest — página 1 do endpoint idêntica a
   `get_pagina(busca_por_sequencia(tokens), '1')` calculada **no mesmo
   processo**; todos os ids da página 1 pertencem ao conjunto do gabarito;
   com `&generos=Rock`, só músicas de Rock, idêntica a
   `get_pagina(busca_por_sequencia(tokens, ['Rock']), '1')` no mesmo
   processo;
   regressão das 6 na **grafia do seed** (conjunto comparado ao gabarito,
   chaves do fixture em minúsculas); `Bm, G, D, A` (com espaços) funciona;
   a versão em minúsculas `bm,g,d,a` é outra chave → `[]` 200; sequência
   inexistente → `[]` 200;
   `pagina=abc` → 400; `/similares?acordes=` e `/search` intactos. Depois,
   suíte inteira: `python -m unittest discover -s tests`.

9. [x] **Docker e documentação.** `Dockerfile` ganha `RUN mkdir -p /app/dados`
   e `VOLUME ["/app/dados"]`; `dados/` entra no `.dockerignore` **e no
   `.gitignore`** (o default relativo cria o banco no checkout em dev); README
   e AGENTS documentam
   `docker run -v deciframe-dados:/app/dados -p 8080:8080 ciframe` e o
   comportamento sem volume.
   **Verificação:** `docker build -t ciframe .`; subir com o volume, cadastrar
   uma sequência via `curl -X POST`, `docker rm -f` no container, subir de
   novo com o mesmo volume → `curl localhost:8080/sequencias` ainda mostra a
   sequência. Repetir sem volume e confirmar que o cadastro some após
   `docker rm` (comportamento documentado). Com o container de pé, regressão
   das 6 por `/similares` na 8080 bate id a id com o gabarito (514/514). E
   localmente: o servidor na 5001 (`python -c "import main;
   main.app.run(port=5001)"`, porque o AirPlay ocupa a 5000) cria
   `dados/sequencias.db` sem erro de permissão.

10. [x] **Frontend mínimo.** `sequencia.js`: remover os 4 objetos hardcoded,
    carregar `GET /sequencias` no início do controller montando
    `{acorde, cor}` para o `df-hex`; formulário acima da lista com campo que
    aceita espaço ou vírgula, `datalist` alimentado por `GET /acordes`, e
    botão que faz `POST /sequencias`; em 201/200 recarregar a lista e
    selecionar a sequência; em 400 exibir a mensagem do servidor (incluindo as
    `sugestoes`). `sequencia.html`: mostrar `total_musicas` em cada bloco; não
    tocar no `ng-hide="music.diferenca.length"` nem no
    `orderBy:'-popularidade'`. Ajustes finais de tela: busca sem resultado
    mostra "Nenhuma música tem essa sequência" (sem o botão "Encontrei essas
    músicas"), e quando o total passa de 100 a área de resultados mostra
    `mostrando 100 de N` (o total do catálogo, sem filtro de gênero, já que a
    API pagina de 100 em 100 e não devolve total filtrado).
    **Verificação:** checklist manual no navegador — a página lista as 6 do
    backend com totais; cadastro pela UI funciona e a nova fica selecionada;
    erro de acorde desconhecido aparece com a sugestão; resultados da busca
    batem com o `curl /similares?sequencia=` correspondente. Verificado pelo
    usuário no navegador: lista, busca, cadastro, sugestão clicável, sequência
    duplicada, campo vazio e filtro de gênero, tudo batendo com a API; os dois
    ajustes de tela (mensagem de zero resultados e `mostrando 100 de N`) foram
    conferidos depois contra a API (`Am7,D` → 0; `D,A,Bm,G` → 100 na página 1,
    total 216).

## Arquivos afetados

| Arquivo | Mudança |
|---|---|
| `main.py` | Índice por vocabulário + `cifra_borda` no load; `busca_por_sequencia`; init + seed no boot; `GET/POST /sequencias`; `/similares` resolve por chave e valida `pagina`; remove dict `sequencias` e `get_similares_por_sequencia` |
| (novo) `sequencias_db.py` | Acesso ao SQLite: schema, pragmas, `user_version`, seed idempotente, CRUD do catálogo; default relativo `dados/sequencias.db` |
| (novo) `scripts/gerar_gabarito_sequencias.py` | Gera `tests/fixtures/gabarito_sequencias.json` (ids ordenados) com o código atual |
| (novo) `tests/test_matching.py`, `tests/test_sequencias_db.py`, `tests/test_api.py` | Regressão do gabarito, unidade do banco, contrato dos endpoints (unittest puro) |
| `musica.py` | Nenhuma |
| `static/assets/js/controllers/sequencia.js` | Catálogo via `GET /sequencias`; formulário de cadastro com `datalist`; trata 201/200/400 |
| `static/templates/sequencia.html` | Form de cadastro; `total_musicas` por sequência |
| `Dockerfile` | `RUN mkdir -p /app/dados` + `VOLUME ["/app/dados"]` |
| `.dockerignore`, `.gitignore` | Adiciona `dados/` nos dois |
| `README.md`, `AGENTS.md` | Comando `docker run` com volume nomeado; comportamento sem volume |

## Riscos e mitigação

- **Comparar ordem entre processos dá falso negativo.** A iteração varia com
  `PYTHONHASHSEED` (§2.4), então o gabarito gravado num processo nunca bate
  em ordem com outro. Mitigação: fixture com ids em `sorted()` e testes de
  conjunto; a paridade de ordem é conferida uma única vez, manualmente, no
  passo 2 — não vira teste commitado porque o passo 8 apaga a função velha
  que serviria de referência. A variância em si é pré-existente e fica —
  corrigi-la é decisão de produto, fora do escopo.
- **Testes lentos e frágeis por importar `main.py`** (o load do CSV acontece
  no import, ~4–6 s, e usa caminho relativo). Mitigação: aceitar um load por
  rodada de testes, rodar sempre da raiz do repo, e setar `SEQUENCIAS_DB` para
  arquivo temporário antes do import para isolar o banco de teste.
- **Banco de desenvolvimento versionado ou assado na imagem.** O default
  relativo cria `dados/sequencias.db` no checkout. Mitigação: `dados/` no
  `.gitignore` e no `.dockerignore`; o caminho relativo é coerente com o CSV,
  que já exige rodar da raiz.
- **Seed duplicado se o número de workers mudar.** Mitigação: `INSERT OR
  IGNORE` apoiado no `UNIQUE(chave)` (ADR 0002); hoje o gunicorn roda 1
  worker, e o teste do passo 3 cobre a idempotência.
- **Boot mais lento (+~1,3 s) e +~48 MB de memória.** Medido na pesquisa e
  aceito na proposta; se incomodar em uso, o substituto direto é a varredura
  com poda por vocabulário (2,8 ms), sem mudança de comportamento — decisão
  já registrada, não entra neste plano.
- **Frontend sem infra de teste automatizado.** Mitigação: checklist manual do
  passo 10 com `curl` como oráculo de cada chamada que a página faz.

## Definição de pronto

- [x] `python -m unittest discover -s tests -v` passa a partir da raiz, com
  `requirements.txt` inalterado (só stdlib + Flask + gunicorn).
  **Prova:** suíte completa verde (30 testes, incluindo o novo
  `test_post_e_busca_da_mesma_sequencia_com_sustenido`); `requirements.txt`
  tem só `Flask==3.1.3` e `gunicorn==23.0.0`.
- [x] Regressão das 6 automatizada: para cada sequência do gabarito, o
  conjunto de ids devolvido pelo código novo é idêntico ao fixture (comparação
  ordenada alfabeticamente, imune a `PYTHONHASHSEED`).
  **Prova:** `tests/test_matching.py::test_regressao_das_seis_sequencias` e
  `tests/test_api.py::test_regressao_das_seis_pelo_endpoint` comparam
  `sorted(ids)` com o fixture (514 ids: 199, 296, 4, 5, 7, 3);
  `scripts/gerar_gabarito_sequencias.py` reproduz o fixture byte a byte
  (`git diff --exit-code` vazio).
- [x] `curl localhost:8080/sequencias` logo após o boot lista as 6 sementes
  com `total_musicas > 0`.
  **Prova:** verificado no container (passo 9): 6 sementes com totais
  199, 296, 4, 5, 7, 3.
- [x] Cadastro idempotente via API: `POST /sequencias` com sequência nova →
  201; repetição → 200 com `existente: true` e mesmo `id`;
  `/similares?sequencia=` com ela devolve resultado não vazio.
  **Prova:** `test_post_repetido_e_idempotente` (201 → 200, mesmo id) e
  `test_post_e_busca_da_mesma_sequencia_com_sustenido` (POST `C#m,A,E` →
  busca devolve os mesmos ids de `busca_por_sequencia`, não vazio).
- [x] Persistência verificada em container: com
  `docker run -v deciframe-dados:/app/dados -p 8080:8080 ciframe`, cadastrar
  uma sequência, `docker rm -f` no container, subir de novo com o mesmo
  volume → `GET /sequencias` ainda contém a sequência cadastrada.
  **Prova:** verificação manual do passo 9, com o volume nomeado.
- [x] Sem o volume, o cadastro não sobrevive a `docker rm` — e README e
  AGENTS documentam os dois comportamentos.
  **Prova:** verificação manual do passo 9 (cadastro some após `docker rm`
  sem `-v`); `README.md:23-27` e `AGENTS.md:29-36`.
- [x] Local sem Docker: `python main.py` cria `dados/sequencias.db` na raiz do
  checkout (sem tocar em `/app`), e o cadastro sobrevive a restart do
  processo.
  **Prova:** `dados/sequencias.db` existe no checkout e o servidor local na
  5001 (mesmo entrypoint, porta trocada só porque o AirPlay ocupa a 5000)
  lista, após restart, os cadastros feitos em execuções anteriores.
- [x] UI `#/porsequencia`: lista as sequências do backend com o total de
  músicas, cadastra pela página (a nova fica selecionada) e exibe as
  mensagens dos 400, incluindo a sugestão de grafia.
  **Prova:** checklist manual do passo 10 verificado pelo usuário no
  navegador (lista, busca, cadastro, sugestão clicável, duplicada, campo
  vazio e filtro de gênero).
- [x] Endpoints antigos intactos: `curl localhost:8080/generos` devolve o
  JSON de gêneros e `/search` + `/similares?acordes=` continuam respondendo
  como hoje.
  **Prova:** `test_acordes_e_search_intactos`; `curl /generos` na 8080
  verificado no passo 9.
