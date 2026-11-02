# Relatório de testes — Sequências de Acordes Customizadas

## Cobertura

`python -m unittest discover -s tests -v` roda **30 testes** a partir da raiz
(saída: `Ran 30 tests in 2.176s`, `OK`). Nenhuma dependência nova: só
`unittest` da stdlib sobre o Flask e o gunicorn já existentes.

**`tests/test_matching.py` — 5 testes, o núcleo do matching.**

- Regressão das 6 contra o gabarito: para cada uma, `sorted(ids)` devolvido por
  `busca_por_sequencia` é igual à lista do fixture (514 ids no total).
- Borda: `B,Em,E` devolve 0; sem as bordas `;` devolveria 2 (`E` casaria
  como prefixo de `Em`). O caso `A7,D,A` citado na proposta não serve de
  teste: com vocabulário exato ele devolve 1 com ou sem borda — os 17 foram
  medidos com a regra literal do gerador, que não é a regra usada aqui.
  Confirmado por mutação: removendo as bordas de `busca_por_sequencia`, este
  teste falha.
- Sequência vazia devolve `[]` (não casa as músicas de cifra vazia).
- Filtro de gênero: só Rock, no mesmo subconjunto e na mesma ordem relativa do
  resultado sem filtro.
- Caixa em caso real do dataset: `C#M,A,E` devolve só `rpm_ninfa`; `C#m,A,E`
  devolve as 4 músicas com `C#m`.

**`tests/test_api.py` — 19 testes, contrato dos endpoints.**

- `GET /sequencias`: 6 sementes, `origem='seed'`, campos `id`/`acordes`/
  `total_musicas`, `Content-Type: text/html`; o total de `Bm,G,D,A` bate com o
  gabarito.
- `POST /sequencias`: 201 na sequência nova; 200 idempotente com o mesmo `id`;
  caixa distingue entradas (`Am7,D` ≠ `AM7,D`, `A7M,D` ≠ `A7m,D`); trim nas
  pontas; os três 400 (`corpo_invalido`, `sequencia_vazia`,
  `acorde_desconhecido` com `sugestoes` completas, ordenadas por uso, e `[]`
  quando não há grafia parecida); POST seguido da busca da mesma sequência com
  `#` (`C#m,A,E`), conferindo ids e `total_musicas`.
- `GET /similares`: página 1 idêntica a
  `get_pagina(busca_por_sequencia(...))`; regressão das 6 paginando até o fim e
  comparando conjunto com o fixture; espaços nos tokens; filtro de gênero;
  sequência inexistente e versão em minúscula devolvem `[]` com 200;
  `pagina=abc` devolve 400.
- Endpoints antigos: `/similares?acordes=Bm,G` devolve a página de 100 e
  `/search?key=legiao` continua devolvendo resultados.

**`tests/test_sequencias_db.py` — 6 testes, camada SQLite.**

- Schema criado e `PRAGMA user_version = 1`.
- Seed insere as 6 na ordem certa e com as chaves na grafia exibida
  (`Bm;G;D;A`, ...).
- Seed repetido não duplica.
- `inserir_ou_obter` devolve `(linha, criada=False)` na segunda chamada.
- Caixa diferente cria outra linha.
- `buscar_por_chave` só encontra a grafia exata (`'Em;G'` sim, `'em;g'` não).

**`tests/fixtures/gabarito_sequencias.json`** — oráculo com 6 chaves e 514 ids
(199, 296, 4, 5, 7, 3), ids em ordem alfabética.

## Teste de regressão obrigatório

As 6 sequências originais (hoje as sementes em `sequencias_db.py:28-35`)
precisam devolver exatamente o mesmo conjunto de músicas de antes da migração
para o banco.

O gabarito foi gerado no passo 1 (commit `2f6aa95`), **antes** de o matching
novo existir, chamando a função antiga `get_similares_por_sequencia`. Depois,
no commit `f4746d4`, o gerador passou a ler direto a coluna `SEQ_FAMOSA`
(`musica.seqs_famosas`, ids 0–5), sem chamar nenhuma função de busca de
`main.py`: o oráculo deixou de depender do código testado.
`scripts/gerar_gabarito_sequencias.py` reproduz o fixture commitado sem
diferença (`git diff --exit-code` vazio), com os totais 199, 296, 4, 5, 7, 3
(soma 514).

A comparação é de **conjunto, não de ordem**: a ordem de iteração varia com
`PYTHONHASHSEED`, então o fixture grava os ids em `sorted()` e os testes
comparam listas ordenadas. Paridade de ordem só é verificada dentro do mesmo
processo, em `test_pagina_1_igual_a_busca_por_sequencia`.

Resultado: **514/514** nas três frentes.

- Em processo: `test_matching.py::test_regressao_das_seis_sequencias`.
- Pelo endpoint: `test_api.py::test_regressao_das_seis_pelo_endpoint`,
  paginando `/similares?sequencia=` de 100 em 100 até o fim.
- No container, na 8080: verificação do passo 9 (commit `a49d8e4`), com
  `docker run -v deciframe-dados:/app/dados -p 8080:8080 ciframe` e comparação
  id a id contra o fixture.

## Como rodar

Da raiz do repositório:

```
python -m unittest discover -s tests -v
```

Nesta máquina, com o virtualenv do projeto:
`.venv/bin/python -m unittest discover -s tests -v`.

## O que ficou de fora

**Frontend sem teste automatizado.** Nada do AngularJS é coberto por teste:
lista, formulário, sugestões clicáveis, mensagem de vazio e filtro de gênero
foram conferidos num checklist manual no navegador (passo 10, verificado por
você). Na revisão final você também conferiu no navegador o encode e a
mensagem: `C#m A E` trouxe as 4 músicas, e com o filtro Sertanejo apareceu
"Nenhuma música desse gênero tem essa sequência".

**Limitações conhecidas (itens 8–11 do review), não corrigidas nem testadas.**

- Ordem de `/similares` com mais de um gênero: os conjuntos são os mesmos da
  função antiga, mas a ordem pode mudar quando a ordem dos gêneros no request
  difere da ordem interna de `main.generos`. Ficou como limitação herdada.
- `GET /sequencias` recalcula a lista completa de matches por linha; `POST
  /sequencias` é anônimo e não tem limite de tamanho de corpo nem de número de
  tokens.
- `/acordes` devolve `list(acordes)` sem ordenação; nenhum teste fixa essa
  ordem.
- O isolamento do banco nos testes depende de `SEQUENCIAS_DB` ser definido
  antes do import de `main` em cada arquivo de teste. Se outro teste importar
  `main` primeiro, o catálogo pode vazar para `dados/` no checkout.

**Falhas que os testes não pegaram.**

- Caixa do acorde (`A7M` × `A7m`): só apareceu porque você percebeu. Pior, a
  suíte garantia o erro:
  `test_post_idempotente_entre_grafias_que_so_diferem_na_caixa` (commit
  `234932d`) afirmava que `Am7,D` e `AM7,D` eram a mesma entrada, com o mesmo
  `id`. Foi substituído por `test_post_caixa_distingue_acordes` em `40fb2e1`,
  junto com a mudança para caixa exata. A regressão não podia pegar: o código
  antigo também baixava tudo para minúsculas e a fixture usa chaves minúsculas.
- `#` na URL: passou no checklist manual do passo 10 porque as sequências
  testadas não tinham `#`. Só o review pegou, com `C#m,A,E` virando
  `sequencia=C` (o `#` corta a URL) e devolvendo outro conjunto. O teste novo
  cobre o caminho POST → `/similares?sequencia=`; o `encodeURIComponent` do
  controller segue sem teste automatizado.
- Borda do bloco: o teste antigo (`A7,D,A` = 1) passava com e sem as bordas
  `;`, então a mutação que removeu as bordas não derrubou nenhum dos 30
  testes. O caso foi trocado por `B,Em,E` (0 com bordas, 2 sem), que agora
  falha quando as bordas somem.
