# Pesquisa — Sequências de Acordes Customizadas

## Resumo

Hoje a busca por "sequência famosa" é um lookup em um dicionário de 6 chaves
(`main.py:40-45`): `GET /similares?sequencia=BmGDA` remove as vírgulas da string
recebida e, se a chave existir, devolve as músicas cujo campo `SEQ_FAMOSA`
(coluna 8 do CSV) contém o índice da sequência (`main.py:190-197`,
`main.py:203-223`). A tag `SEQ_FAMOSA` não significa "a progressão aparece na
música": ela foi gerada por `scripts/generate_data_set.py:7-24` e exige **duas**
condições simultâneas — a sequência aparece como bloco **contíguo e ordenado**
na cifra **e** o vocabulário de acordes da música é **exatamente** o conjunto de
acordes da sequência.

Um script novo (`scripts/research_seq_famosas_match.py`) rodou contra
`data/top/dataset_final.csv` replicando o parsing de `main.py:49-98`: a regra do
gerador reproduz a tag **exatamente**, 514 de 514 músicas, zero divergência nos
dois sentidos. As regras mais frouxas ("só o bloco contíguo", "só o conjunto de
acordes", "subsequência com buracos") marcam entre 1,8 e 61 vezes mais músicas do
que a tag. Hoje a tag marca 514 das 67.585 músicas (0,76%), e o frontend
`#/porsequencia` conhece apenas 4 das 6 sequências (`sequencia.js:2-37`). Medida
em 10 progressões populares fora do CSV, a regra A devolve de 10 a 278 músicas
por sequência (0,01% a 0,41% do catálogo) — mais que zero, mas ainda um filtro
estreito.

Sobre campo harmônico, medido na §2.9: comparar por classe de altura (união dos
12 tons) multiplica o alcance por 1,3 a 11,1 nas 6 do catálogo e por 4,1 a 5,9
nas progressões populares, mas é superconjunto da regra A e, aplicada às 6, não
reproduz a tag 514/514. Comparar por graus via `NCIFRA` leva `C G Am F` de 296
para 1.877, mas 797 dessas músicas têm qualidade, modo ou inversão diferente,
7,48% dos tokens de grau saem vazios e 6 das 296 literais ficam de fora (`TOM`
divergente ou base ausente). Os argumentos dos dois lados estão nos trade-offs;
a decisão fica para depois.

## Perguntas que você precisa responder

1. **Algoritmo de matching**: hoje, as 6 sequências hardcoded em `main.py` (linhas
   40-45) são comparadas contra músicas via uma tag pré-computada
   (`SEQ_FAMOSA`/`seqs_famosas`, vinda do CSV). Sequências cadastradas pelo usuário
   não têm essa tag — o matching precisa ser calculado em tempo real a partir da
   lista de acordes de cada música (`musica.acordes`/`musica.cifra`). O que vai
   definir "a sequência X aparece na música Y"? A ordem dos acordes importa?
   Repetições de acorde dentro da música importam? É preciso normalizar (ex.:
   maiúsculas/minúsculas, variações de escrita do mesmo acorde)?
2. **Validação da hipótese**: rode o algoritmo que você está considerando contra os
   dados reais em `data/top/dataset_final.csv`, para as 6 sequências hoje
   hardcoded, e confirme (ou refute) que ele reproduz os mesmos matches que o
   código atual produz via `seqs_famosas`. Esse é o bar mínimo de correção que
   você vai usar na fase de testes.
3. **Banco de dados**: quais bancos embarcados (sem serviço externo adicional) são
   viáveis dentro do container Docker único e local-only já documentado em
   `docs/adr/0001-local-only-docker-deploy.md`? O que cada opção implica para o
   `Dockerfile` atual e para a persistência dos dados entre reinícios do
   container?
4. **Frontend existente**: o que a página `#/porsequencia`
   (`static/templates/sequencia.html` +
   `static/assets/js/controllers/sequencia.js`) já faz? Repare que ela tem hoje uma
   lista *hardcoded no JavaScript* de 4 sequências (`sequencia1`..`sequencia4`),
   diferente das 6 que existem no backend — um detalhe real e pré-existente do
   código, não um erro seu, que vale entender antes de decidir o que precisa
   mudar.

## Registro das descobertas

As medições sobre o CSV e sobre o comportamento do app vêm de
`scripts/research_seq_famosas_match.py`, rodado nesta máquina (Python 3.9.6,
macOS), contra o CSV real. As verificações que não saem do script estão
marcadas no texto: a configuração do gunicorn (§3.1) e os testes com Docker
(§3.2). Comando na seção [Como reproduzir](#como-reproduzir). Nenhuma linha do
CSV é escrita.

### 1. Algoritmo de matching

#### 1.1 O que o runtime faz hoje

- As 6 sequências são um `dict` de chave concatenada para índice:
  `'BmGDA': 0, 'CGAmF': 1, 'EmG': 2, 'CA7DmG7': 3, 'GmF': 4, 'CC7FFm': 5`
  (`main.py:40-45`). Os nomes legíveis estão em
  `data/mapeamento_sequencias_famosas.txt:1-6`.
- O branch de sequência em `/similares` (`main.py:170-201`) só é alcançado se
  `acordes` e `id_unico_musica` não vieram na query (`main.py:184-191`). A string
  recebida é **concatenada sem separador** — `acordes = sequencia_tag.replace(',','')`
  (`main.py:191`), resultado: `"Bm,G,D,A"` vira `"BmGDA"` — e comparada por
  igualdade exata contra as chaves do `dict` (`main.py:194`). Chave desconhecida
  retorna `[]` com HTTP 200, sem erro (`main.py:192-197`).
- `get_similares_por_sequencia` (`main.py:203-223`) filtra por gênero
  (`apply_filtro`, `main.py:266-272`), percorre as músicas e mantém as que passam
  em `str(id_seq) in musica.seqs_famosas` (`main.py:209`). Não há cálculo sobre
  `musica.cifra` nem sobre `musica.acordes` nesse caminho.
- `musica.seqs_famosas` é a coluna 8 do CSV splitada em `';'` (`main.py:63`,
  `musica.py:18`); `musica.acordes` é `list(set(cifra))` (`musica.py:17`).
- Paginação: `TAM_PAGINA = 100` (`main.py:35`) e `get_pagina`
  (`main.py:226-228`). O frontend **nunca envia `pagina`**
  (`sequencia.js:73-76`), então a UI recebe sempre a página 1.
- Verificação com o app real (Flask test client, módulo `main` importado):

  | requisição | itens devolvidos |
  |---|---|
  | `/musicas` | 67.585 (o docstring fala em paginação, o código não pagina — `main.py:154-156`) |
  | `/generos` | 52 |
  | `/acordes` | 6.653 |
  | `/similares?sequencia=BmGDA` | 100 |
  | `/similares?sequencia=BmGDA&pagina=2` | 99 (total 199) |
  | `/similares?sequencia=Bm,G,D,A` | 100 (idêntico à chave concatenada) |
  | `/similares?sequencia=EmG` | 4 |
  | `/similares?sequencia=CG` | 0 |
  | `/similares?sequencia=xyz` | 0 |
  | `/similares?sequencia=AmF` | 0 |
  | `/similares?acordes=Bm,G` | 100 |

  Todas as respostas saem com `Content-Type: text/html; charset=utf-8`, porque
  são `json.dumps(...)` como string (`main.py:142`, `156`, `160`, `168`, `197`,
  `201`).

#### 1.2 O que a tag `SEQ_FAMOSA` significa de fato

O gerador é `scripts/generate_data_set.py:7-24`. Em duas etapas:

```python
# scripts/generate_data_set.py:7-24
def get_famosas(acorde):
    seqs = ['bm;g;d;a','c;g;am;f', 'em;g' , 'c;a7;dm;g7', 'gm;f', 'c;c7;f;fm' ]
    out = []
    for i in range(len(seqs)):
        s = seqs[i]
        acorde = acorde.lower()
        if s in acorde:                      # (1) bloco contíguo, na ordem
            achou = True
            tem_seqs = []
            for l in acorde.split(';'):      # (2) todo acorde DA MÚSICA ...
                tokens = s.split(';')
                if l not in tokens:          # ... tem que estar NA SEQUÊNCIA
                    achou = False
                    break
            if achou:
                tem_seqs.append(str(i))
                out.append("-".join(tem_seqs))
    return out
```

O loop interno itera sobre `acorde.split(';')`, isto é, sobre os acordes **da
música**, e quebra se algum não estiver entre os acordes **da sequência**. Como
(1) já garante que todos os acordes da sequência aparecem na música, (1)+(2)
equivalem a:

> a sequência aparece como bloco contíguo na cifra **e** o conjunto de acordes
> da música é exatamente o conjunto de acordes da sequência.

Medições que confirmam essa leitura:

- 514 músicas têm tag; distribuição dos valores (já splitados em `';'` como em
  `main.py:63`): `'1'`: 296, `'0'`: 199, `'4'`: 7, `'3'`: 5, `'2'`: 4, `'5'`: 3,
  vazio: 67.071. Nenhuma música tem mais de uma tag.
- Nenhuma música com tag tem acorde fora do conjunto da sequência (0 de 514).
- O código do gerador tem um detalhe latente: `out` é unido com `''`
  (`generate_data_set.py:88`) e o runtime separa por `';'` (`main.py:63`). Se
  duas sequências casassem, a tag sairia `"01"` e `str(id_seq) in seqs_famosas`
  (`main.py:209`) não acharia nem `0` nem `1`. Isso não ocorre no CSV porque os
  seis conjuntos de acordes são distintos entre si, então a condição (2) só pode
  ser satisfeita por uma sequência por música.
- As cifras de `data/top/dataset_final.csv` e de `data/dataset_seq_notas.csv`
  (66.523 ids em comum) são idênticas na coluna `CIFRA` crua em 66.523 de
  66.523 casos. Depois de `limpa_cifra`, caem para 66.480 de 66.523: as 43
  diferenças são de espaço em branco — 28 tokens com espaço interno, que
  `limpa_cifra` parte em dois (p.ex. `A#7+  Am7/9-`), e 15 tokens com espaço
  sobrando (p.ex. `F# `) —, não de acorde diferente. Ou seja: a tag não é
  resultado de uma versão antiga com outra cifra.

#### 1.3 O que a tag **não** significa

Não é "a música contém a progressão". Medições:

| leitura | músicas (6 sequências somadas) |
|---|---|
| tag (`SEQ_FAMOSA`) | **514** |
| bloco contíguo por substring, sem exigir vocabulário exato | 7.684 |
| bloco contíguo token a token | 6.459 |
| vocabulário exato, ordem ignorada | 947 |
| todos os acordes da sequência presentes, ordem ignorada | 31.616 |
| sequência como subsequência (ordem, com buracos) | 28.641 |
| sequência abre a cifra (prefixo) | 922 |

Ou seja: 7.170 músicas têm o bloco contíguo e **não** têm a tag; 31.102 músicas
têm todos os acordes da sequência e **não** têm a tag.

#### 1.4 Ordem, repetição e normalização — o que o código faz

- **Ordem**: importa para a tag, por dois motivos. A condição (1) é um `in` de
  string (`';'.join(seq) in ';'.join(cifra)`), logo exige adjacência e ordem. A
  condição (2) ignora ordem (é pertinência a conjunto). Há 433 músicas em que o
  vocabulário é exatamente o da sequência mas o bloco contíguo não existe: 196
  para `Bm G D A`, 236 para `C G Am F`, 1 para `C A7 Dm G7`, 0 para as demais.
  Todas ficam fora da tag. Exemplo: `data/top/dataset_final.csv:139`
  (30 Seconds To Mars - Do Or Die), cifra começando em `D G Bm A D G Bm A ...` —
  vocabulário exato `{Bm,G,D,A}`, sem o bloco `Bm G D A`, tag ausente.
- **Repetições dentro da música**: não invalidam nada. A condição (1) casa o
  bloco uma vez; a condição (2) compara conjuntos e é insensível a repetição. As
  músicas marcadas têm de 3 a 208 tokens de cifra (mediana de 47–48 tokens para
  as duas sequências de 4 acordes, `Bm G D A` e `C G Am F`). Exemplo:
  `dataset_final.csv:136` (30 Seconds To Mars - City Of Angels) tem 57 tokens e
  é marcada; `dataset_final.csv:39568` (Marcelo D2 - Mão Na Cabeça) tem 4 tokens
  (`Em G Em G`) e também é marcada.
- **Maiúsculas/minúsculas**: o gerador baixa tudo para minúsculas
  (`generate_data_set.py:12`), então a tag é case-insensitive. O runtime não é:
  as chaves do `dict` (`main.py:40-45`) são case-sensitive e a comparação é
  `==`/`in` exato (`main.py:194`, `main.py:209`). Normalizar caixa nos dados
  colide 151 grafias distintas, incluindo pares que são acordes diferentes:
  `A7M`/`A7m`, `AbM7`/`Abm7`, `A7(b13)`/`A7(B13)`, `A#dim`/`A#Dim`, e o trio
  `AbMaj7`/`AbmAJ7`/`Abmaj7`.
- **Enarmonia**: não há normalização nenhuma no runtime. O CSV usa as duas
  grafias: `A#` em 1.501 músicas e `Bb` em 7.812; `D#` em 1.962 e `Eb` em 3.290;
  `C#` em 3.449 e `Db` em 642; `G#` em 3.248 e `Ab` em 1.799; `F#` em 6.656 e
  `Gb` em 314. As 6 sequências usam só grafias canônicas (`Bm G D A`, `C G Am F`,
  `Em G`, `C A7 Dm G7`, `Gm F`, `C C7 F Fm`).
- **Acordes com baixo invertido** (`E/B`, `G/B`, `Bb5-/D` etc.) são tokens
  distintos; não há simplificação para a tríade. Existem scripts offline de
  normalização (`scripts/normalize_chords.R`, `scripts/simplify_chords.R`, que
  geram uma coluna `NCIFRA` em algarismos romanos a partir de
  `data/transposition_matrix2.csv`), mas **nenhum é chamado pelo runtime** —
  `main.py` abre apenas `data/top/dataset_final.csv` (`main.py:49`).
- **Tablaturas**: `limpa_cifra` (`main.py:11-23`) trata tokens com `|` cortando
  antes da barra (`main.py:16-18`). Nos tokens que o runtime usa, **0** contêm
  `|` e **0** são vazios ou têm espaço.
- **`replace('NA','')`** em `main.py:53` roda na linha inteira, não só na
  coluna. Efeitos medidos: 8.141 músicas ficam com cifra vazia — todas as 8.141
  têm `CIFRA == "NA"` cru e **nenhuma** já era vazia antes do replace — e 7
  músicas têm nome de artista/música alterado, p.ex.
  `Gusttavo Lima / DNA` → `Gusttavo Lima / D`,
  `Lourenço e Lourival / CABANA` → `... / CABA`,
  `Chico Rey e Paraná / ROTINA DE POBRE` → `... / ROTI DE POBRE`.
- **Rotação**: nada no runtime trata a sequência como ciclo. As rotações de
  `Bm G D A` são `G D A Bm`, `D A Bm G` e `A Bm G D`; o gerador compara a
  string fixa (`generate_data_set.py:12`) e o endpoint faz lookup exato da
  chave (`main.py:190-197`), então cada rotação é uma sequência diferente. Na
  regra A, `Bm G D A` marca 199 músicas e a rotação `D A Bm G` marca 216
  (união: 240): uma música que toca `D A Bm G` uma vez, sem repetir o bloco, não
  contém `Bm G D A`. Números e trade-offs na §2.7.
- **Tom e função harmônica**: a coluna `TOM` (coluna 7 do CSV) existe e não é
  usada por nenhum código do runtime. Tem 13 valores distintos — as 12 notas e
  vazio — e 805 músicas vazias (98,8% preenchidas); não há marca de modo menor
  nem de modulação. Das 66.780 músicas com `TOM`, o valor aparece como acorde
  exato na cifra em 46.052 (69%), só na grafia enarmônica em 1.997 (3%) e não
  aparece como acorde em 18.731 (28%); `TOM` é o primeiro acorde em 24.812
  (37%). Os scripts R offline (`normalize_chords.R`, `simplify_chords.R`) usam
  `TOM` + `data/transposition_matrix2.csv` para gerar `NCIFRA` em graus; a
  conversão reduz cada acorde à sua letra: qualidade e extensão desaparecem
  (`C`, `C7` e `Cmaj7` caem no mesmo grau; `A7`, `A7M` e `A7m` também), o baixo
  da inversão é descartado (`G/B` → grau de `G`), bemóis caem na letra natural
  (em dó, `Bb` e `B` dão o mesmo grau) e 7,48% dos tokens saem sem grau (vazio),
  mais 0,07% que saem `NA`, quando a raiz do acorde não tem célula preenchida na
  linha do tom (ex.: `F#` em dó).
  `data/dataset_seq_notas.csv` já tem a coluna `NCIFRA` pronta. Números da
  coluna `TOM` na seção 13 do script.
- **Custo**: uma passada completa (67.585 músicas × 6 sequências, um processo)
  nesta máquina: regra do gerador 405 ms, bloco por substring 366 ms,
  vocabulário exato 380 ms, todos os acordes 377 ms, prefixo 296 ms;
  as regras que percorrem token a token com `lower()` a cada chamada custaram
  2.040 ms (tokens contíguos) e 1.698 ms (subsequência). Números indicativos,
  reproduzíveis pela seção 10 do script.

### 2. Validação da hipótese

Script: `scripts/research_seq_famosas_match.py`. Ele replica `main.py:49-98`
(inclusive `replace('NA','')`, `[:-1]`, `split(',')`, `limpa_cifra` e
`split(';')` da coluna 8) e compara a tag com 7 regras calculadas em tempo real
a partir da cifra.

#### 2.1 A regra do gerador reproduz a tag

| idx | chave | música (mapeamento) | tag | regra A | ambos | so_algo | so_tag |
|---|---|---|---|---|---|---|---|
| 0 | `BmGDA` | Sequência de Bm | 199 | 199 | 199 | 0 | 0 |
| 1 | `CGAmF` | Sequência de C | 296 | 296 | 296 | 0 | 0 |
| 2 | `EmG` | Sequência Em | 4 | 4 | 4 | 0 | 0 |
| 3 | `CA7DmG7` | Sequência de C (Samba) | 5 | 5 | 5 | 0 | 0 |
| 4 | `GmF` | Sequência de Gm | 7 | 7 | 7 | 0 | 0 |
| 5 | `CC7FFm` | Sequência de C (Samba cont.) | 3 | 3 | 3 | 0 | 0 |
| — | **total** | | **514** | **514** | **514** | **0** | **0** |

Regra A = bloco contíguo (`';'.join(seq).lower() in ';'.join(cifra).lower()`)
**e** todo acorde da música pertence ao conjunto da sequência. Zero divergência
nos dois sentidos: a tag é 100% reproduzível a partir da cifra.

O cross-check com o módulo `main` carregado confirma que o script lê o CSV
igual ao app: `main.musicas` = 67.585, `main.generos` = 52, `main.acordes` =
6.653, e `get_similares_por_sequencia(idx, main.generos)` devolve exatamente o
mesmo conjunto de `id_unico_musica` que o conjunto marcado pela tag, para as 6
sequências (`iguais=True` em todas).

#### 2.2 Divergência nos dois sentidos para as regras candidatas

`so_algo` = a regra diz sim e a tag diz não. `so_tag` = a tag diz sim e a regra
diz não.

| regra | total de matches | so_algo | so_tag |
|---|---|---|---|
| A. bloco contíguo + vocabulário exato (regra do gerador) | 514 | 0 | 0 |
| B. bloco contíguo por substring, sem vocabulário exato | 7.684 | 7.170 | 0 |
| C. bloco contíguo token a token, sem vocabulário exato | 6.459 | 5.945 | 0 |
| D. vocabulário exato, ordem ignorada | 947 | 433 | 0 |
| E. todos os acordes da sequência presentes, ordem ignorada | 31.616 | 31.102 | 0 |
| F. subsequência (ordem, com buracos) | 28.641 | 28.127 | 0 |
| G. sequência abre a cifra (prefixo) | 922 | 719 | 311 |

Por sequência, `so_algo`:

| idx | chave | B | C | D | E | F | G (so_algo / so_tag) |
|---|---|---|---|---|---|---|---|
| 0 | `BmGDA` | 773 | 667 | 196 | 5.569 | 4.564 | 110 / 111 |
| 1 | `CGAmF` | 950 | 920 | 236 | 6.598 | 5.591 | 196 / 197 |
| 2 | `EmG` | 3.700 | 3.106 | 0 | 14.156 | 13.639 | 257 / 1 |
| 3 | `CA7DmG7` | 91 | 91 | 1 | 577 | 422 | 13 / 2 |
| 4 | `GmF` | 1.515 | 1.032 | 0 | 3.840 | 3.634 | 127 / 0 |
| 5 | `CC7FFm` | 141 | 129 | 0 | 362 | 277 | 16 / 0 |

Observação estrutural: **toda** regra mais frouxa que a tag tem `so_tag = 0`,
porque o conjunto marcado pela tag é subconjunto do conjunto de todas elas (a
tag é a mais estrita). A direção `so_tag > 0` só aparece com uma regra **mais
estrita** que a tag — a regra G (prefixo) é o exemplo medido.

#### 2.3 Exemplos verificados

Todos os exemplos abaixo foram reconferidos linha a linha; "bloco" = bloco
contíguo token a token.

`Bm G D A` (idx 0, tag = 199):

- marcada: `dataset_final.csv:136` — 30 Seconds To Mars, City Of Angels
  (57 tokens; vocabulário `{Bm,G,D,A}`; bloco presente; **não** começa com a
  sequência: `... D A Bm G D A Bm G D ...`).
- marcada: `dataset_final.csv:221` — 5 Seconds Of Summer, Heartache On The Big
  Screen (`... A G D Bm G D A G D Bm ...`).
- bloco presente sem tag: `dataset_final.csv:78` — 3 Doors Down, Every Time You
  Go (92 tokens; tem `G6`, `D9`, `B9`, `C` além do bloco `Bm G D A`).
- vocabulário exato sem bloco: `dataset_final.csv:139` — 30 Seconds To Mars, Do
  Or Die (`D G Bm A D G Bm A ...`).

`C G Am F` (idx 1, tag = 296):

- marcada: `dataset_final.csv:207` — 5 Seconds Of Summer, Broken Pieces
  (começa exatamente com `C G Am F C G Am ...`).
- marcada: `dataset_final.csv:205` — 5 Seconds Of Summer, Bad Dreams
  (`... F G F C G Am F C G Am ...`; não começa com a sequência).
- bloco presente sem tag: `dataset_final.csv:203` — 5 Seconds Of Summer,
  Airplanes (80 tokens, progressão no meio de `Am C F C Em F G ...`).
- vocabulário exato sem bloco: `dataset_final.csv:118` — 3 Doors Down,
  What's Left (`C G C G C G F G F G ...`, 61 tokens).

`Em G` (idx 2, tag = 4):

- marcada: `dataset_final.csv:39568` — Marcelo D2, Mão Na Cabeça (4 tokens:
  `Em G Em G`).
- marcada: `dataset_final.csv:20380` — Eric Clapton, Fall Like Rain (44 tokens;
  começa com `G Em`, o bloco `Em G` aparece depois).
- bloco por substring sem tag, por artefato de prefixo:
  `dataset_final.csv:13` — 14 Bis, Clareiras (`... D D5 Em Gm7 D D7+ ...`):
  `"em;g"` casa com `Em;Gm7`, mas token a token **não** casa.
- bloco token a token sem tag: `dataset_final.csv:20` — 14 Bis, Linda Juventude
  (`... Am7 Bm7 Em G A B ...`, 140 tokens).

`C A7 Dm G7` (idx 3, tag = 5):

- marcada: `dataset_final.csv:6565` — Benito Di Paula, Bendito Seja (começa com
  a sequência).
- marcada: `dataset_final.csv:4039` — Arlindo Cruz, Vai Pro Lado de Cá
  (`... G7 C A7 Dm G7 C G7 C ...`).
- bloco presente sem tag: `dataset_final.csv:801` — Adoniran Barbosa, Fica Mais
  Um Pouco Amor (`... G7 F G7 C A7 Dm G7 C F F#º ...`).
- vocabulário exato sem bloco: `dataset_final.csv:46927` — Os Originais do
  Samba, Samba da Vizinha (`C Dm A7 Dm G7 C G7 C C Dm ...`, 40 tokens).

`Gm F` (idx 4, tag = 7):

- marcada: `dataset_final.csv:4394` — Asa de Águia, Marajá (4 tokens:
  `Gm F Gm F`).
- bloco presente sem tag: `dataset_final.csv:56` — 14 Bis, Vou correndo até
  você (`... Cm F Cm Gm F Cm Gm Eb ...`; tem `Cm` e `Eb`).
- bloco presente sem tag: `dataset_final.csv:235` — 5 Seconds Of Summer, Out Of
  My Limit (`... A# F D# Gm F D# Gm F ...`; grafias `A#`/`D#`).

`C C7 F Fm` (idx 5, tag = 3):

- marcada: `dataset_final.csv:13764` — Claudia Leitte, Bem Vindo Amor (48
  tokens; começa com `C C7 F Fm C C7 F ...`).
- marcada: `dataset_final.csv:20761` — Exaltasamba, Jogo de Sedução
  (`... C C7 F Fm C C7 F ...`).
- bloco por substring sem tag, por artefato de prefixo:
  `dataset_final.csv:383` — A Turma do Balão Mágico, É Tão Lindo
  (`... C Gm7/C C7 F Fmaj7 Fm6 ...`): `"c;c7;f;fm"` casa com `C7;F;Fmaj7`,
  mas token a token **não** casa. O mesmo acontece em
  `dataset_final.csv:874` (Adoradores, Escuta Meu Clamor) com `F;Fm7`.
- bloco token a token sem tag: `dataset_final.csv:2467` — Almir Sater, Meu
  Veneno (`... Dm G7 C C7 F Fm C A7 ...`).

#### 2.4 Números por sequência para a UI

Com a tag (situação de hoje), o total por sequência é 199, 296, 4, 5, 7 e 3. O
endpoint pagina de 100 em 100 (`main.py:35`, `main.py:226-228`) e o frontend
nunca pede a página 2 (`sequencia.js:73-76`) → para `BmGDA` e `CGAmF` a UI mostra
100 de 199 e 100 de 296; para as outras quatro, todos os resultados.

Com uma regra mais frouxa, o número de páginas cresce: bloco contíguo por
substring gera 972, 1.246, 3.704, 96, 1.522 e 144 matches (10, 13, 38, 1, 16 e 2
páginas). "Todos os acordes presentes" gera 5.768, 6.894, 14.160, 582, 3.847 e
365.

Ordem dos resultados: `get_similares_por_sequencia` itera
`apply_filtro(musicas.values(), generos_key)`, e `apply_filtro`
(`main.py:266-272`) concatena as listas de cada gênero na ordem de
`list(generos)` (`main.py:92`), que vem de um `set`. Cada lista de gênero está
ordenada por popularidade (`main.py:95-96`), mas a lista final é agrupada por
gênero. Como o `Dockerfile` não fixa `PYTHONHASHSEED`, a ordem do `set`
muda entre processos: rodando o script com `PYTHONHASHSEED=0` e `=1`,
`list(generos)[:6]` sai
`['Soul', 'Romântico', 'Guarânia', 'Soft Rock', 'New Wave', 'Disco']` e
`['Forró', 'Romântico', 'Alternativo', 'Punk Rock', 'New Wave', 'MPB']`
(seção 8). Como a página 1 é a única que a UI pede, o conteúdo dela muda junto.
O `orderBy:'-popularidade'` do template
(`sequencia.html:42`) reordena apenas o subconjunto de 100 que chegou.

#### 2.5 Sequências populares: quanto cada regra encontra

As 6 do backend marcam 514 músicas; só `C G Am F` responde por 296 delas. Para
testar o que aconteceria com sequências novas, o script mede 10 progressões
populares fora do CSV sob as 7 regras (seção 11). A = regra do gerador; B–G
como na §2.2.

| sequência | A | B | C | D | E | F | G |
|---|---|---|---|---|---|---|---|
| `G D Em C` | 252 | 1.210 | 1.141 | 502 | 7.263 | 6.103 | 241 |
| `D A Bm G` | 216 | 959 | 944 | 395 | 5.768 | 4.765 | 204 |
| `Am F C G` | 278 | 1.219 | 1.125 | 532 | 6.894 | 5.843 | 225 |
| `Em C G D` | 220 | 1.231 | 1.051 | 502 | 7.263 | 6.101 | 180 |
| `C Am F G` | 75 | 558 | 503 | 532 | 6.894 | 5.964 | 144 |
| `G Em C D` | 103 | 669 | 583 | 502 | 7.263 | 6.252 | 129 |
| `Am G F E` | 22 | 305 | 160 | 32 | 1.884 | 1.428 | 50 |
| `C G F G` | 55 | 740 | 711 | 205 | 10.331 | 8.574 | 108 |
| `Em Am D G` | 10 | 454 | 443 | 22 | 4.712 | 3.775 | 16 |
| `G C D` | 162 | 2.900 | 1.913 | 318 | 11.946 | 10.978 | 303 |

Leituras:

- Na regra A, nenhuma das 10 devolveu 0: o intervalo foi de 10 (`Em Am D G`) a
  278 (`Am F C G`). A afirmação de que "a maioria das sequências novas devolveria
  0" **não** se sustenta para progressões comuns; ela pode valer para sequências
  com vocabulário incomum (acordes que quase não aparecem no CSV), que não foram
  medidas.
- O que continua valendo é o custo de relaxar a regra: E encontra de 25 a 471
  vezes mais músicas que A (`Em Am D G`: 10 vs 4.712); B, de 4 a 45 vezes mais.
- Comprimento não garante volume: `Em G` (2 acordes) marca 4 músicas, enquanto
  `G C D` (3 acordes) marca 162. Quem manda é o vocabulário exato, não a
  quantidade de acordes.
- Mesmo o maior número (278) é 0,41% das 67.585 músicas; a regra A continua
  sendo um filtro estreito em termos absolutos.

#### 2.6 Duplicatas e identidade de música hoje (seção 12)

- `id_unico_musica` (`id_artista` + `id_musica`) é único: 67.585 linhas, 67.585
  ids distintos, zero repetição.
- Por `(artista, nome)` normalizados há 680 grupos com mais de um id, envolvendo
  1.429 músicas (2,1%). Exemplos: `30 Seconds To Mars / Up In The Air`,
  `AC/DC / You Shook Me All Night Long`.
- Não existe catálogo de sequências armazenado hoje — as 6 vivem no `dict` de
  `main.py:40-45` —, então "sequência duplicada" é um problema que só a feature
  nova cria.

O que isso significa para usar um `set`: como `/similares?sequencia=` consulta
uma sequência por vez e percorre cada música uma vez (`main.py:203-223`), a
resposta atual não tem item repetido por construção, e um `set` não mudaria
nada hoje. Ele passa a importar se (a) um endpoint futuro consultar várias
sequências de uma vez, ou (b) o CSV tiver linhas repetidas (0 hoje). `set` de
ids resolve os dois casos, mas descarta a ordem; `dict.fromkeys` (ou lista com
checagem) deduplica preservando a ordem de iteração.

#### 2.7 Rotação: `G D Em C` é a mesma sequência que `D Em C G`? (seção 14)

São duas perguntas diferentes, e a resposta medida é diferente para cada uma.

**Como catálogo/validação.** `G D Em C` e `D Em C G` são a mesma progressão
cíclica vista de outro ponto de partida. A forma canônica mais óbvia é a menor
rotação (`min(rotacoes(seq))`, comparando as tuplas de strings): determinística,
barata, preserva ordem e repetição e não exige normalizar acorde. Entre as 10
progressões populares e as 6 do `main.py` (16 sequências), três formas
canônicas são compartilhadas:

- `C G D Em` ← `G D Em C` | `Em C G D`
- `A Bm G D` ← `D A Bm G` | `Bm G D A`
- `Am F C G` ← `Am F C G` | `C G Am F`

Ou seja, `D A Bm G` é rotação de uma sequência que já existe na tag
(`BmGDA`), e `Am F C G` é rotação de `CGAmF`. Se "rotação conta como
duplicata" virar regra, essas entradas não podem ser cadastradas como
sequências separadas.

**Como matching.** Aqui a rotação **não** dá o mesmo resultado. Rodando a regra
A sobre cada rotação, nenhum par de rotações devolveu o mesmo conjunto, exceto
os casos minúsculos (`Em G`/`G Em`, `Gm F`/`F Gm`, `C A7 Dm G7`/`G7 C A7 Dm` e
`C C7 F Fm`, todos com 3 a 7 músicas). A similaridade (Jaccard) entre a
sequência e suas rotações ficou entre 0,43 e 1,00; a interseção é grande, mas
cada rotação encontra músicas que a original não encontra, e vice-versa:

| sequência | A | rotações | Jaccard min–máx | união das rotações |
|---|---|---|---|---|
| `G D Em C` | 252 | 3 | 0,76–0,83 | 287 |
| `D A Bm G` | 216 | 3 | 0,84–0,89 | 240 |
| `Am F C G` | 278 | 3 | 0,83–0,90 | 329 |
| `C Am F G` | 75 | 3 | 0,52–0,74 | 146 |
| `G C D` | 162 | 2 | 0,58–0,68 | 248 |
| `Bm G D A` | 199 | 3 | 0,84–0,90 | 240 |
| `C G Am F` | 296 | 3 | 0,83–0,86 | 329 |

O motivo é o mesmo da §2.2: a regra A exige o bloco contíguo **naquela ordem** e
o vocabulário exato. Um loop repetido à exaustão contém todas as rotações — daí
a interseção grande —, mas uma música que toca o bloco uma vez, ou com
interrupções, contém só a rotação que aparece. Em `C Am F G`, a rotação
`Am F G C` acrescenta 57 músicas que a original não marca; em `Bm G D A`, a
rotação `D A Bm G` acrescenta 27. Em `G D Em C`, a união das 4 rotações chega a
287 contra 252.

Isso também mostra que "casar qualquer rotação" não é o mesmo que "ignorar a
ordem": a união das rotações de `G D Em C` cobre 287 das 502 músicas com
exatamente o vocabulário `{C, D, Em, G}` (regra D) — as outras 215 têm os quatro
acordes, mas nenhuma rotação de `G D Em C` como bloco contíguo. Rotação é um
meio-termo entre bloco exato e conjunto: mantém adjacência e ordem relativa, mas
trata o ponto de partida como arbitrário.

Consequências práticas, sem decisão tomada: hoje não existe rotação em lugar
nenhum — o endpoint remove as vírgulas e faz lookup exato da string
(`main.py:190-197`), então `GDEmC` e `DEmCG` seriam chaves diferentes. Uma
dedupe por rotação é `min(rotacoes(seq))` (barata) e não exige mexer no
matching; casar rotações no matching custa até `n` vezes a regra A escolhida
(4× para progressões de 4 acordes) e muda os números das 6 originais se
aplicado a elas. As duas escolhas são independentes: dá para aceitar rotações
como sequências distintas e continuar casando só o bloco exato, ou o contrário.

#### 2.8 Acorde inexistente e sequência vazia/inexistente (seção 15)

**O vocabulário de acordes.** O runtime monta `acordes` como o conjunto de todos
os tokens de cifra (`main.py:39`, `main.py:78`, 6.653 tokens) e `GET /acordes`
devolve `list(acordes)` — um `set` sem ordenação; a ordem muda entre processos
(duas execuções seguidas começaram com `F7M(11+)/A)`, `G#m7/9/11`... e com
`E13`, `Cm6(9)`...). A distribuição é muito desigual:
3.045 tokens aparecem em uma única música, 4.827 em até 5, 5.355 em até 10 e
6.291 em até 100. Os dez mais frequentes são `G` (31.310 músicas), `D` (27.632),
`C` (25.852), `A` (23.901), `E` (19.498), `F` (17.721), `Am` (16.792), `Em`
(16.695), `Bm` (13.240) e `Dm` (10.405). A cauda contém lixo de parsing: 44
tokens nem começam por nota maiúscula, como `#13`, `#º`, `(B9)`, `2x` e `/C#`.

**O que o endpoint faz hoje com entrada inválida.** `main.py:190-197` só remove
vírgulas e faz lookup exato no `dict`; não há `strip`, validação nem distinção
entre "não existe" e "vazio". Medido com o Flask test client:

| requisição | status | itens |
|---|---|---|
| `?sequencia=` | 200 | 0 |
| `?sequencia=,` / `?sequencia=,,,` | 200 | 0 |
| `?sequencia=%20` / `?sequencia=%20,%20` | 200 | 0 |
| `?sequencia=xyz` (inexistente) | 200 | 0 |
| `?sequencia=G` (não é chave) | 200 | 0 |
| `?sequencia=bm,g,d,a` (minúsculas) | 200 | 0 |
| `?sequencia=Bm,G,D,A,` (vírgula final) | 200 | 100 |
| `?sequencia=Bm,%20G` (espaço) | 200 | 0 |
| `?sequencia=Bm,G,D,A,C,C,C` (acorde a mais) | 200 | 0 |
| `?sequencia=BmGDA&pagina=abc` | **500** | — |
| `?sequencia=BmGDA&pagina=0` | 200 | 0 |
| `?sequencia=BmGDA&pagina=-1` | 200 | 99 |

Ou seja: sequência vazia e sequência inexistente hoje são indistinguíveis — as
duas devolvem `[]` com 200. `pagina` não numérica derruba a requisição com
`ValueError` (`main.py:227`), e página 0/negativa não é validada (0 devolve
nada, −1 devolve 99 por fatiamento negativo).

**O que aconteceria no matching em tempo real.** Sem guarda, a sequência vazia é
perigosa: na regra A ela casa as 8.141 músicas de cifra vazia (`'' in ''` e
vocabulário vazio), e na regra B casa **todas** as 67.585. Um acorde inexistente
zera a regra A (vocabulário exato nunca terá `Cb`), mas as regras por substring
amplificam o erro: `Cb` casa 9 músicas por causa de tokens como `Abm/Cb` e
`Db/Cb`, e `H` casa 2 por causa de `C7+/9(hibr)` e `heF#`. Comprimento mínimo
também não é garantido: `C` (um acorde) casa 17 na regra A e `Am` casa 2; `G G`
casa 6 e a sequência de 8 acordes repetidos (`G D Em C G D Em C`) casa 163.

Então há três casos distintos, que as opções abaixo tratam separadamente:
acorde que não existe no vocabulário; sequência vazia ou só com separadores; e
sequência inexistente no catálogo (chave/`id` que não existe). Hoje, o único
comportamento é o "passa e devolve vazio", com 200. Nada disso é alcançável pela
UI atual — `sequencia.js:2-37` só monta as 4 sequências fixas —, mas é alcançável
por qualquer requisição direta e por qualquer formulário novo.

#### 2.9 Seleção por campo harmônico: o que mudaria (seção 16)

"Selecionar por campo harmônico" pode significar duas coisas diferentes, com
custos diferentes. A primeira é comparar a consulta **transposta por classe de
altura**: a mesma forma em qualquer um dos 12 tons, sem usar `TOM`; a grafia
(`A#`/`Bb`) deixa de importar, mas qualidade e inversão continuam importando
(`Am` ≠ `A`, `G/B` ≠ `G`). A segunda é comparar **graus** (I, V, vi, IV) usando
`TOM` + `NCIFRA`, o que é independente do tom e da grafia, mas perde qualidade,
modo e inversão. Nenhuma das duas é "o campo harmônico" no sentido completo: o
`NCIFRA` é uma sequência de graus, sem modo, sem função e sem modulação.

**(a) Transposição por classe de altura (sem `TOM`).** A consulta é normalizada
para classe de altura + sufixo e comparada com as 12 transposições; o conjunto
resultante é a união dos 12 tons.

| consulta | literal (A) | união 12 tons | ganho |
|---|---|---|---|
| `C G Am F` | 296 | 1.260 | 4,3× |
| `G D Em C` | 252 | 1.260 | 5,0× |
| `G C D` | 162 | 660 | 4,1× |
| `Bm G D A` | 199 | 1.173 | 5,9× |
| `BmGDA` (catálogo) | 199 | 1.173 | 5,9× |
| `CGAmF` (catálogo) | 296 | 1.260 | 4,3× |
| `EmG` (catálogo) | 4 | 11 | 2,8× |
| `CA7DmG7` (catálogo) | 5 | 32 | 6,4× |
| `GmF` (catálogo) | 7 | 78 | 11,1× |
| `CC7FFm` (catálogo) | 3 | 4 | 1,3× |

Nas progressões populares o ganho fica entre 4,1× e 5,9×; nas 6 do catálogo,
entre 1,3× e 11,1×. Como a união é um superconjunto da regra A, aplicá-la às 6
já não devolve o conjunto da tag (514/514 deixa de valer). 53 músicas ficam fora
desse matching porque têm algum token sem nota (`2x`, `/C#`, `13)`), e o
vocabulário exato continua exigindo que a música use exatamente os mesmos
acordes, só que transpostos.

**(b) Graus via `NCIFRA`.** A base offline tem 66.525 linhas para 67.585 músicas
no runtime (66.880 pares artista+música distintos; 2 linhas da base não existem
no runtime). Dessas, 7.730 têm `CIFRA` vazia; 58.772 alinham `CIFRA` e `NCIFRA`
token a token (58.770 dentro do runtime, 87,0% das músicas). Nas alinhadas, 3
têm `TOM` vazio, 21.696 têm pelo menos um grau vazio e 455 têm `NA`. Os únicos
graus que existem são os sete (I–VII), vazio e `NA`: 7,48% dos tokens saem
vazios e 0,07% saem `NA`. Para consultar por graus é preciso dizer qual é o tom
da sequência — `C G Am F` só vira I V VI IV se C for a tônica —, informação que
a sequência de acordes não carrega.

| progressão | tom | graus | só bloco | bloco + vocabulário |
|---|---|---|---|---|
| `C G Am F` | C | I V VI IV | 6.527 | 1.877 |
| `G D Em C` | G | I V VI IV | 6.527 | 1.877 |
| `G C D` | G | I IV V | 12.017 | 1.712 |
| `Bm G D A` | D | VI IV I V | 5.845 | 1.720 |

`C G Am F` em C e `G D Em C` em G caem no **mesmo** padrão I V VI IV porque o
`NCIFRA` descarta o modo (`vi` vira `VI`). `Bm G D A` em D vira VI IV I V, o
mesmo conjunto em outra ordem, e casa 1.720 — não os mesmos 1.877, porque o
bloco tem que aparecer contíguo. Existem 1.730 blocos de 4 graus distintos que
casam ao menos uma música; os mais frequentes são I V VI IV (1.877), IV I V I
(1.830), I IV I V (1.813), IV I V VI (1.762), VI IV I V (1.720) e V VI IV I
(1.711) — rotações e variantes de I–V–vi–IV e I–IV–I–V.

Para `C G Am F`, as três leituras se sobrepõem assim: 296 na regra A, 1.260 na
união dos 12 tons e 1.877 por graus; 1.080 estão nas duas leituras (tons e
graus), 797 só nos graus e 180 só nos tons. As 797 que só os graus encontram são
músicas cuja progressão tem a mesma sequência de graus mas qualidade, modo ou
inversão diferente — por exemplo `G D Em C7+` e `C9 G Am F5`. As 180 que só os
tons encontram têm `TOM` divergente do tom da progressão ou grau vazio/ausente.
A leitura por graus também não contém toda a regra A: dos 296 matches literais
de `C G Am F`, 290 aparecem nela; os 6 restantes são 5 músicas sem linha na base
e 1 com `TOM` (G) que não é o tom da progressão.

Os números de graus usam comparação token a token: os algarismos romanos têm de
1 a 3 letras, e uma busca por substring casaria `I;V` dentro de `VI;V` (o bloco
de I V VI IV subiria de 6.527 para 7.605). Isso também é um detalhe de
implementação, não só de medição.

### 3. Banco de dados

#### 3.1 O que existe hoje

- Não há banco, ORM, migração nem escrita em disco em nenhum lugar do backend.
  `main.py` só lê `data/top/dataset_final.csv` uma vez no import (`main.py:49-98`)
  e mantém tudo em memória (`musicas_dict`, `musicas`, `genero_musicas`,
  `acordes`, `generos` — `main.py:37-39`, `47`, `88-96`). Busca por
  `sqlite|shelve|pickle|tinydb|sqlalchemy|database` no código não retorna nada
  no backend.
- `requirements.txt:5-6` tem só `Flask==3.1.3` e `gunicorn==23.0.0`.
- `Dockerfile:1-12`: `FROM python:3.9-slim`, `WORKDIR /app`,
  `pip install -r requirements.txt`, `COPY . .`, `EXPOSE 8080`,
  `CMD ["gunicorn", "--bind", "0.0.0.0:8080", "main:app"]`. Não há `VOLUME`,
  não há `USER` (o processo roda como root), não há serviço auxiliar.
- O comando documentado de execução não monta volume:
  `docker run -p 8080:8080 ciframe` (`README.md:16-18`, também em
  `AGENTS.md`).
- Gunicorn com esses argumentos usa os defaults: 1 worker, 1 thread, classe
  `sync` (verificado com `gunicorn.config.Config` na versão 23.0.0) → um único
  processo, requisições serializadas.
- `.dockerignore` contém `.git`, `.venv`, `__pycache__`, `*.pyc` — qualquer
  arquivo de banco no diretório do projeto entra na imagem via `COPY . .`.

#### 3.2 O que "persistir entre reinícios" significa no Docker atual

Fatos documentados pela própria Docker (docs.docker.com, "Volumes" / "A volume's
lifecycle"): *"When a container is destroyed, the writable layer is destroyed
with it. Using a volume ensures that the data is persisted even if the container
using it is removed."* Aplicado a este projeto:

| operação | arquivo gravado em `/app/...` dentro do container |
|---|---|
| `docker restart` / `stop` + `start` no mesmo container | sobrevive (camada gravável do container) |
| `docker rm` do container, depois `docker run` de novo | **perde** (camada gravável é descartada) |
| `docker build` + `docker run` de imagem nova | **perde** o que estava na camada gravável; o que estiver no contexto de build é copiado para a imagem |
| `docker run -v <volume-ou-pasta>:/app/...` | sobrevive a `rm` e a rebuild (estado fora do container) |

Nada disso está configurado hoje: nem `VOLUME` no `Dockerfile`, nem `-v` no
comando do README. Verificado nesta máquina com o daemon disponível
(Docker 29.1.3, Docker Desktop), sobre a imagem construída do `Dockerfile`
atual:

- `docker image inspect ciframe` → `Config.Volumes: null`, `Config.User: ""`,
  e `PYTHONHASHSEED` ausente de `Config.Env` (a ordem dos gêneros realmente
  varia por processo).
- `python:3.9-slim` (e a imagem `ciframe`) têm o módulo `_sqlite3`: `import
  sqlite3` funciona, Python 3.9.25, SQLite 3.46.1.
- um arquivo criado em `/app/persist_test.txt` dentro do container sobrevive a
  `docker restart` e some depois de `docker rm` + `docker run` da mesma imagem.
- o mesmo tipo de arquivo, gravado em `/app/dados` com
  `-v cif_teste:/app/dados`, sobrevive ao `docker run --rm` seguinte.
- o container sobe e responde `GET /generos` com HTTP 200 e
  `Content-Type: text/html; charset=utf-8`, igual ao app local.

#### 3.3 Opções embarcadas (sem serviço externo)

| opção | como entra no projeto | o que implica |
|---|---|---|
| `sqlite3` (biblioteca padrão) | nenhuma linha em `requirements.txt` | arquivo único; SQL; transações; trava de escrita por banco; leitura concorrente com WAL; precisa de caminho gravável |
| arquivo JSON + escrita atômica | nenhuma dependência | leitura/escrita do arquivo inteiro; sem transação; concorrência depende de lock de arquivo manual |
| `shelve`/`dbm` (padrão) | nenhuma dependência | chave-valor em arquivo; sem consulta/ordenação; sem transação |
| TinyDB | nova linha em `requirements.txt` e rebuild | documento JSON puro Python; sem transação/SQL; arquivo único |
| SQLAlchemy + SQLite | nova linha em `requirements.txt` | camada de ORM/migração sobre o mesmo arquivo SQLite; mais código e dependência |
| Postgres/MySQL em outro container | segundo serviço, rede e volume | conflita com o container único de `docs/adr/0001-local-only-docker-deploy.md:9-16` |

### 4. Frontend existente (`#/porsequencia`)

- Rota: `routes.js:17-21` (`/porsequencia` → `templates/sequencia.html` +
  `SequenciaController`, `controllerAs: "Sequencia"`). O link de entrada está em
  `home.html:79-85`.
- Catálogo hardcoded: 4 objetos `sequencia1..sequencia4`
  (`sequencia.js:2-31`), empilhados em `vm.sequenciasFamosas`
  (`sequencia.js:34-37`). Correspondência com o backend:

  | objeto JS | acordes | chave no backend | idx |
  |---|---|---|---|
  | `sequencia1` | `Bm, G, D, A` | `BmGDA` | 0 |
  | `sequencia2` | `C, G, Am, F` | `CGAmF` | 1 |
  | `sequencia3` | `Gm, F` | `GmF` | 4 |
  | `sequencia4` | `C, C7, F, Fm` | `CC7FFm` | 5 |

  Ficam de fora `EmG` (idx 2) e `CA7DmG7` (idx 3). Cada acorde é
  `{acorde, cor}` com a cor fixa `#2E1C74` e o campo `index: 1` em todos os
  quatro objetos.
- Busca: clicar em um bloco dispara `pesquisarPorSequencia(sequencia)`
  (`sequencia.html:6` → `sequencia.js:63-90`). `createChordsString`
  (`sequencia.js:55-61`) monta `"Bm,G,D,A"`; a URL é
  `"similares?sequencia=" + string` e, se um gênero estiver escolhido,
  `&generos=<genero>` (`sequencia.js:72-76`); não há `pagina`. O `$http.get` usa
  `apiUrl = ""` (relativo) — a constante `RESTAPI` de `app.js:3-5`
  (`http://localhost:5003`) não é usada nesse controller.
- Gêneros do `<select>` (`sequencia.html:24-30`) vêm da constante `GENEROS` de
  `app.js:6-58`: 51 gêneros, contra 52 no backend. O que existe só no backend é
  `'R&B;'` (o valor da coluna 4 no CSV inclui o ponto e vírgula).
- Resultados: `vm.musics` recebe o array cru (`sequencia.js:83`) e o template
  repete cards com `orderBy:'-popularidade'` (`sequencia.html:42`), mostrando
  `nome_musica`, `nome_artista`, `genero`, e abrindo `music.url` em nova aba
  (`sequencia.js:97-99`). O template referencia `music.diferenca`
  (`sequencia.html:43`), campo que não aparece na resposta de sequência: a
  resposta em `main.py:210-220` traz `id_unico_musica`, `id_artista`,
  `id_musica`, `nome_artista`, `nome_musica`, `popularidade`, `acordes`,
  `genero`, `url` — sem `diferenca` (esse campo só existe no caminho de
  `acordes`, `main.py:246-258`).
- Não existe formulário de cadastro, nem campo de acordes livres, nem chamada
  para listar sequências: o único estado de "sequências" é o array literal do
  controller. `limparPesquisa` (`sequencia.js:92-95`) só zera
  `vm.minhaSequencia` e `vm.musics` quando se clica num acorde do resultado.
- O mesmo endpoint é usado pela busca por acordes
  (`acordes.js:84-115`), que manda `similares?acordes=...` e recebe o formato
  com `diferenca`/`intersecao` de `main.py:246-258`.

## Conexões entre componentes e fluxo de dados

CSV → memória → API → Angular:

1. `main.py:49` abre `data/top/dataset_final.csv`; cada linha é limpa
   (`main.py:53`), splitada (`main.py:55`) e vira um `Musica`
   (`main.py:69-72`, classe em `musica.py:1-25`). Três índices são construídos:
   `musicas_dict` → `musicas` ordenado por popularidade (`main.py:74`,
   `88-89`), `genero_musicas` por gênero (`main.py:82-85`, `95-96`) e o set
   `acordes` (`main.py:77-78`).
2. `/generos` (`main.py:158-160`) e `/acordes` (`main.py:162-164`) expõem os sets.
3. `#/porsequencia` (Angular) → clique no bloco → `sequencia.js:73` monta
   `similares?sequencia=Bm,G,D,A` → `main.py:191` remove as vírgulas →
   `main.py:194` resolve o índice → `main.py:196` chama
   `get_similares_por_sequencia` → `main.py:209` filtra pela tag →
   `main.py:226-228` corta 100 → `json.dumps` (string, `text/html`) →
   `sequencia.js:83` guarda → `sequencia.html:42` reordena por popularidade e
   renderiza.
4. Filtro de gênero: `sequencia.js:74-76` acrescenta `&generos=`;
   `main.py:179-182` usa a lista recebida em `apply_filtro` (`main.py:266-272`).
   Gênero inexistente é ignorado silenciosamente (`main.py:270`).
5. `#/poracordes` usa o mesmo endpoint com `acordes=` (`acordes.js:92`), cai no
   caminho de `main.py:199`/`230-263`, que calcula interseção e diferença de
   acordes — caminho independente do de sequência.
6. Nenhum componente escreve no CSV ou em qualquer arquivo: o único I/O de
   escrita do projeto são os scripts offline (`scripts/*.R`, `scripts/*.py`).

## Trade-offs identificados

Opções e o que cada uma implica. Nada aqui está decidido.

### Algoritmo de matching

| opção | prós | contras |
|---|---|---|
| A. Reproduzir a tag: bloco contíguo **e** vocabulário exato | zero regressão por construção (514/514 medido); mesma semântica de hoje; barato (~405 ms/6 seqs) | marca só 514 músicas no total; para sequência nova, exige que a música só tenha aqueles acordes e naquela ordem — as 10 progressões populares medidas devolveram 10 a 278 músicas, mas sequências com vocabulário fora do CSV podem devolver 0; ignora músicas longas que tocam a progressão |
| B. Bloco contíguo por substring | casa "a progressão aparece em algum ponto" com ordem e adjacência; barato (~366 ms) | 7.170 falsos positivos contra a tag; substring casa prefixos (`Em;Gm7`, `F;Fmaj7`, `F;Fm7`); quebra a regressão de hoje se aplicado às 6 originais |
| C. Bloco contíguo token a token | mesma ideia de B sem os artefatos de prefixo; previsível | 5.945 falsos positivos contra a tag; mais lento (~2.040 ms); ainda exige adjacência exata |
| D. Vocabulário exato, ordem ignorada | 947 matches; para sequências curtas (2 acordes) coincide com a tag (4/4 e 7/7) | 433 falsos positivos; ignora a progressão como sequência (só o conjunto); para `EmG`/`GmF` não distingue ordem nenhuma |
| E. Todos os acordes da sequência presentes | 31.616 matches; simples de explicar e implementar; barato (~377 ms) | 31.102 falsos positivos; qualquer música com os acordes casa, inclusive baladas sem a progressão; muito ruidoso para consultas amplas |
| F. Subsequência com buracos | 28.641 matches; tolera acordes intermediários | 28.127 falsos positivos; ordem rígida pode perder progressões invertidas; ~1.698 ms |
| G. Prefixo (sequência abre a cifra) | casa "a música começa com a progressão" | 719 falsos positivos e 311 falsos negativos contra a tag; perde progressões no meio (ex.: `dataset_final.csv:136`) |
| Casar qualquer rotação da sequência (tratar a progressão como loop) | pega a mesma progressão começada em outro ponto, mantendo ordem e adjacência | custa até n× a regra escolhida (4× para 4 acordes); muda as contagens contra a tag se aplicado às 6 (a união das rotações de `BmGDA` dá 240 contra 199); assume que a progressão é um ciclo, o que não vale para progressão linear |
| Aplicar a tag para as 6 originais e outra regra para as novas | mantém a regressão exata e dá utilidade às sequências novas | duas semânticas no mesmo endpoint; resultados não comparáveis entre sequências antigas e novas |

### Normalização de acordes

| opção | prós | contras |
|---|---|---|
| Comparação exata como está no CSV | determinístico; é o que a tag e o `dict` fazem hoje | `A#`/`Bb`, `D#`/`Eb`, `C#`/`Db`, `G#`/`Ab`, `F#`/`Gb` contam como acordes distintos (1.501 vs 7.812 para `A#`/`Bb`); inversões (`E/B`) também |
| Caixa normalizada (`C#m7` = `c#m7`) | tolera digitação do usuário | 151 grupos colidem, incluindo `A7M`/`A7m` e `AbM7`/`Abm7`, que são acordes diferentes |
| Reduzir à tríade / ignorar extensões | aumentaria os matches | muda o que é "o mesmo acorde"; nenhuma função disso existe no runtime (só os scripts R offline) |
| Enarmonia (`Bb` = `A#`) | unifica grafias | exige tabela de equivalência; nenhuma existe no código Python hoje |
| Normalizar por tom com `NCIFRA` (algarismos romanos) | compara progressões em tons diferentes | hoje só existe em R offline (`scripts/normalize_chords.R`), não no runtime; muda a unidade de comparação; perde qualidade/extensão e acidente (`C`=`C7`=`Cmaj7`, `Bb`=`B`) e deixa 7,48% dos tokens sem grau (mais 0,07% `NA`) |

### Campo harmônico e transposição (argumentos; decisão adiada)

Selecionar por campo harmônico é comparar a progressão em graus (I, V, vi, IV)
em vez de acordes literais. Há duas implementações medidas na §2.9 e na seção 16
do script: transpor a consulta por classe de altura (12 tons, sem `TOM`) ou
converter tudo para graus com `TOM` + `NCIFRA`. A decisão não é desta fase; os
argumentos dos dois lados, com os números, são estes.

**A favor**

- **Alcance.** Para `C G Am F`, a regra A devolve 296 músicas, a união dos 12
  tons devolve 1.260 (4,3×) e a leitura por graus devolve 1.877 (6,3×). Nas
  progressões populares medidas, o ganho da transposição fica entre 4,1× e 5,9×.
- **Grafia e tom deixam de ser obstáculo.** A classe de altura unifica
  `A#`/`Bb` (1.501 vs 7.812 músicas hoje), `D#`/`Eb`, `C#`/`Db`, `G#`/`Ab` e
  `F#`/`Gb` sem tabela de enarmonia, e a mesma progressão em outro tom casa.
- **Vocabulário funcional.** I–V–vi–IV é como músicos descrevem a progressão; a
  busca por graus permitiria procurar pela forma em vez do acorde concreto, e a
  mesma forma em qualquer tom cai no mesmo padrão (`C G Am F` em C e `G D Em C`
  em G).
- **Artefato já existe.** `data/dataset_seq_notas.csv` tem `NCIFRA` para 58.770
  músicas do runtime (87,0%), e `data/transposition_matrix2.csv` +
  `scripts/normalize_chords.R` já produzem a coluna; não seria preciso inventar
  um modelo harmônico do zero.
- **Custo de consulta da variante por graus.** Comparar uma coluna pré-computada
  token a token é da mesma ordem da varredura atual; a variante por transposição
  repete a varredura 12 vezes (uma por tom), e o custo por consulta cresce na
  mesma proporção (seção 10).

**Contra**

- **`TOM` é o elo fraco da variante por graus.** 805 músicas sem tom (98,8%
  preenchidas), um único valor por música, sem modo nem modulação; em 28% das
  músicas com tom o valor não aparece como acorde na cifra e só 37% começam com
  ele. Um `TOM` errado produz graus errados em silêncio.
- **`NCIFRA` perde informação.** 7,48% dos tokens saem sem grau e 0,07% saem
  `NA`; só existem 9 valores (I–VII, vazio, `NA`). `C`, `C7` e `Cmaj7` viram o
  mesmo grau; `Am` vira VI (o modo menor some); `G/B` perde o baixo; `Bb` cai na
  letra `B`; acorde com sustenido em tom natural fica sem grau.
- **Precisão cai, e não é pouco.** 1.877 matches por graus contra 296 literais;
  dos 1.877, 797 não estão na união dos 12 tons, ou seja, têm qualidade, modo ou
  inversão diferente (`G D Em C7+`, `C9 G Am F5`). É outro produto: "mesma
  função" em vez de "mesma progressão".
- **A consulta não tem tom.** `C G Am F` só vira I V VI IV se C for a tônica.
  Hoje o matching não precisa dessa decisão; por graus, ou o usuário digita
  graus, ou informa o tom, ou o sistema infere (mais uma regra, com ambiguidade
  própria).
- **Quebra a regressão das 6.** A união dos 12 tons é superconjunto da regra A;
  nas 6, `CC7FFm` vai de 3 para 4, `EmG` de 4 para 11, `GmF` de 7 para 78 e
  `BmGDA` de 199 para 1.173. A tag 514/514 é o único ground truth que existe
  hoje.
- **Maquinário extra.** Segunda base (66.525 linhas, contra 67.585 músicas no
  runtime), regenerada offline quando o CSV muda; 7.730 linhas têm `CIFRA`
  vazia, 58.772 alinham, 12 têm `;` sobrando e 23 não têm `NCIFRA`; a geração
  depende de R (`normalize_chords.R`) ou de uma reimplementação em Python.
- **Colisões de padrão.** 1.730 blocos de 4 graus casam ao menos uma música; os
  seis mais frequentes vão de 1.711 a 1.877 músicas cada. Progressões distintas
  como `C G Am F`, `G D Em C` e `D A Bm G` caem no mesmo padrão I V VI IV;
  `Bm G D A` vira uma rotação (VI IV I V) e casa 1.720 em vez de 1.877 — o que
  funde entradas de catálogo que hoje são diferentes.
- **Teoria na UI.** Para consultar por graus o usuário precisa saber algarismos
  romanos; para exibir o campo harmônico sem casar por ele, é teoria a mais numa
  página que hoje só lista 4 sequências fixas.

| opção | prós | contras |
|---|---|---|
| Comparação literal de acordes (hoje) | reproduz a tag exatamente; determinístico; barato | a mesma progressão em outro tom não casa; grafias enarmônicas contam como acordes distintos |
| Comparar por classe de altura (12 transposições) | acha a mesma forma em qualquer tom; unifica enarmonia sem tabela; não usa `TOM` | 12× o custo; 53 músicas têm token sem nota e ficam fora; é superconjunto da regra A (não reproduz a tag); em progressões curtas pode casar muita coisa |
| Transpor a consulta para o `TOM` de cada música (1 transposição) | mais barato que as 12; usa informação que já existe | depende da qualidade do `TOM`; 805 sem tom; sem modo nem modulação; mesmo problema de superconjunto |
| Comparar por graus via `NCIFRA` | independente de tom e de grafia; permite buscar por função; artefato offline pronto | perde qualidade, modo e inversão; 7,48% dos tokens sem grau; `TOM` é o elo fraco; 1.877 vs 296; não reproduz a tag |
| Exibir o campo harmônico da sequência sem mudar o matching | barato; informativo para o músico | não faz parte do contrato de busca; exige teoria na UI; não resolve nenhum requisito da feature |

A escolha não é desta fase; as medições acima delimitam o que cada lado ganha e
perde.

### Validação e duplicatas

| opção | prós | contras |
|---|---|---|
| Nenhuma validação: aceita sequências repetidas | simples; zero código | catálogo com entradas equivalentes; buscas idênticas em duplicata; não há uma entrada canônica |
| Dedupe por rotação (forma canônica = menor rotação) | reconhece a mesma progressão começada em outro ponto; barato (`min(rotacoes(seq))`) e determinístico | funde sequências que hoje dariam resultados diferentes (`BmGDA` 199 vs `D A Bm G` 216, união 240); impede cadastrar a rotação de propósito |
| Tratar rotação como sequência distinta | preserva o recall de cada ponto de partida; o catálogo reflete o que o usuário digitou | entradas quase equivalentes; o usuário não entende por que `D Em C G` devolve outro conjunto |
| Dedupe por tupla exata (ordenada, com `strip`) | não colide acordes diferentes (`A7M` ≠ `A7m`); preserva ordem e repetição; barato | `Bm,G,D,A` e `bm,g,d,a` contam como sequências diferentes |
| Dedupe por tupla em minúsculas | tolera digitação | colide 151 grafias distintas, incluindo `A7M`/`A7m` e `AbM7`/`Abm7`, que são acordes diferentes — duas sequências distintas virariam uma |
| Dedupe com enarmonia (`Bb` = `A#`) | unifica a mesma sequência escrita de dois jeitos | exige normalização de acorde; nenhuma existe no runtime; pode juntar grafias que o usuário quer manter separadas |
| `UNIQUE` no banco sobre a chave canônica | garante unicidade mesmo com concorrência; erro tratável | exige escolher e versionar a chave; duplicatas antigas precisam ser limpas |
| Checagem na aplicação (`SELECT` antes do `INSERT`) | mensagem amigável; sem constraint | corrida entre requisições; o gunicorn padrão tem 1 worker, mas a garantia some com mais workers |
| Devolver a sequência existente em vez de erro | UX: "já existe, use esta" | exige busca por chave; impede duplicata intencional |
| Responder 409/erro de conflito | deixa o conflito explícito | visitante anônimo precisa entender e corrigir; mais atrito |
| Dedupe de resultados por `id_unico_musica` com `set` | resposta sem cartão repetido se o matching mudar | descarta a ordem; hoje não há repetição (ids únicos, uma sequência por request) |
| Dedupe de resultados com `dict.fromkeys` | deduplica preservando a ordem de iteração | código extra para um caso que hoje não ocorre |
| Dedupe de resultados por `(artista, nome)` | esconde versões repetidas (680 grupos, 1.429 músicas) | apaga músicas legítimas de mesmo nome; o id é o identificador confiável |

### Validação de acordes (inexistente ou incomum)

Três posturas possíveis para um acorde que não está no vocabulário do CSV —
rejeitar, aceitar com aviso ou deixar passar —, e variações de como decidir o que
é "inexistente".

| opção | prós | contras |
|---|---|---|
| Deixar passar (hoje) | zero código; mantém 200 e `[]` | o usuário não distingue "acorde não existe", "sequência não existe" e "sem resultados"; nas regras por substring o erro casa lixo (`Cb` → 9 músicas, `H` → 2) |
| Rejeitar com 400 | erro explícito e imediato; evita consulta inútil | quebra o contrato atual (sempre 200 + array); exige mensagem; visitante anônimo precisa entender e corrigir |
| Aceitar com aviso | mantém o 200 e informa o que foi ignorado | não há onde colocar o aviso hoje: a resposta é `json.dumps(lista)` cru com `text/html`, sem envelope; header novo exige mudança no cliente; se for só log, ninguém vê |
| Validar contra `GET /acordes` (6.653 tokens) | usa o conjunto que já existe; nenhum artefato novo | o próprio conjunto tem 44 tokens que não começam por nota e 3.045 de ocorrência única; aceitaria `2x`/`heF#` e rejeitaria um acorde incomum mas legítimo |
| Validar contra lista curada (raiz A–G, acidentes, sufixos conhecidos) | barra lixo e erro de digitação; mensagem clara | nova lista para manter; pode rejeitar grafias que o CSV usa (`7M`, `maj7`, `º`, `+`, `(9)`, inversões); decidir a whitelist é trabalho à parte |
| Validar pelo resultado (rejeitar consulta que não casa nada) | garante que a busca devolve algo | confunde acorde raro com acorde errado; depende da regra de matching; roda a busca antes de validar |
| Normalizar o desconhecido até uma tríade conhecida | aumenta recall; uma grafia a menos para o usuário | muda o acorde consultado; nenhuma normalização existe no runtime; pode casar progressão errada |
| Rejeitar só o vazio e deixar acordes passarem | mínimo e barato | não resolve acorde inexistente; erro continua silencioso |

### Sequência vazia, curta ou inexistente

O caso vazio é diferente do acorde inexistente: sem guarda, a regra A casa 8.141
músicas de cifra vazia e a regra B casa as 67.585. Os demais casos são de
produto (mínimo de acordes, tamanho máximo) e de contrato (200 com `[]` versus
404).

| opção | prós | contras |
|---|---|---|
| Deixar passar (hoje) | simples; compatível com todos os clientes | vazio e inexistente viram o mesmo `[]` com 200 |
| Rejeitar vazio/só separadores com 400 | impede resultado absurdo e consulta degenerada | status novo; o frontend atual nunca envia vazio, então só clientes novos veriam |
| Guarda no matching (vazio → lista vazia, sem rodar regra) | barato; mantém o contrato de 200 | não avisa o usuário; não valida acorde; precisa existir em todo caminho de matching |
| Exigir mínimo de 2 acordes | evita consulta de 1 acorde (2 a 18 matches na regra A) | progressão de 1 acorde é rara, mas é uma consulta legítima; decisão de produto |
| Limitar comprimento máximo | evita consultas degeneradas | progressões longas existem; exige escolher um número; hoje não há limite |
| `id`/chave inexistente → 404 | separa "não existe" de "não achou" | hoje tudo é 200; cliente teria que tratar erro; a busca por query string (`?sequencia=`) não tem id, então 404 só se aplica a um catálogo com URL própria |
| `id`/chave inexistente → 200 com `[]` (hoje) | compatível; simples | não distingue erro de zero resultado |
| `strip` e descarte de tokens vazios antes do lookup | tolera espaço e vírgula sobrando | muda quais strings são aceitas hoje (`Bm, G` devolve 0) |
| Lookup case-insensitive | tolera digitação | colide `A7M`/`A7m` e outros 151 grupos; muda as chaves atuais |
| Validar `pagina` (inteiro, ≥ 1) | evita o 500 de `pagina=abc` e o resultado de 0/−1 | mexe no contrato atual (500 → 400); é a mesma família de validação, ainda que fora do escopo de sequência |

### Banco de dados

| opção | prós | contras |
|---|---|---|
| SQLite via `sqlite3` (stdlib) | zero dependência nova; arquivo único; SQL, índices, transações; `requirements.txt` e `Dockerfile` inalterados | escrita serializada (1 writer); precisa de caminho gravável e de tratamento de `database is locked`; sem migração embutida |
| JSON + escrita atômica | sem dependência; inspecionável; trivial de ler | reescreve o arquivo inteiro a cada cadastro; sem transação; concorrência exige lock manual; cresce mal |
| `shelve`/`dbm` | sem dependência; chave-valor direto | sem consulta/ordenação; sem transação; formato dependente de plataforma |
| TinyDB | API Python simples; sem SQL | dependência nova em `requirements.txt` + rebuild; arquivo inteiro em memória; sem transação |
| SQLAlchemy + SQLite | ORM, migrações versionadas | dependência nova; mais código; o resto do backend continua sem ORM |
| Postgres/MySQL em outro container | concorrência e recursos de servidor | contraria o container único de `docs/adr/0001:9-16`; exige rede/volume/serviço extra |

### Persistência no Docker

| opção | prós | contras |
|---|---|---|
| Nada (arquivo na camada gravável) | zero mudança no `Dockerfile` e no comando | sobrevive a `restart`, mas não a `docker rm` nem a rebuild; não atende "não volta a ser perdido" |
| Bind mount (`-v $(pwd)/dados:/app/dados`) | arquivo visível no host; sobrevive a `rm` e rebuild | muda o comando documentado no README/AGENTS; depende do caminho no host |
| Volume nomeado (`-v deciframe:/app/dados`) | gerenciado pelo Docker; sobrevive a `rm` | muda o comando; o arquivo não fica acessível direto no host |
| `VOLUME` no `Dockerfile` | a imagem declara o ponto de montagem | cria volume anônimo por container se o usuário não nomear; ainda é preciso nomeá-lo para reuso previsível |
| Embutir o banco na imagem (`COPY`) | funciona sem flag extra | toda escrita vai para a camada gravável; rebuild sobrescreve com a versão da imagem |

### Frontend

| opção | prós | contras |
|---|---|---|
| Manter a lista hardcoded e só acrescentar um formulário | menor mudança em `sequencia.js`/`sequencia.html` | a UI continua sem refletir o catálogo real; as 6 do backend seguem divergindo das 4 da tela |
| Buscar o catálogo do backend (`GET` novo) e renderizar dinamicamente | a tela passa a refletir o backend; corrige o 4-vs-6 | exige endpoint novo e um estado de carregamento/erro que hoje não existe |
| Formulário de cadastro na mesma página | um lugar só para listar, cadastrar e buscar | a página já tem dois painéis e o layout é de colunas fixas |
| Cadastro em página/rota separada | isola o formulário | nova rota, novo template, novo link |
| Reaproveitar o `df-hex` para montar a sequência clicando acordes | consistente com a UI existente (é o que `acordes.html` faz) | exige lista de acordes disponíveis e validação de sequência vazia/duplicada |
| Campo de texto livre (`"Bm G D A"`) | simples de implementar | precisa de parsing/validação no cliente ou no servidor |

## Como reproduzir

```
# só a análise (só biblioteca padrão do Python 3.9)
python3 scripts/research_seq_famosas_match.py

# inclui o cross-check contra o módulo main.py (precisa de Flask instalado)
python3 scripts/research_seq_famosas_match.py --app

# quantos exemplos por bloco saem na seção 6 (default: 2)
python3 scripts/research_seq_famosas_match.py --exemplos 5
```

O script imprime, em ordem: (1) estatísticas do dataset e da coluna
`SEQ_FAMOSA`; (2) contagem da tag por sequência; (3) validação da regra do
gerador; (4) tabela de cada regra candidata contra a tag; (5) contagens de
ordem e repetição; (6) exemplos; (7) tokens e normalização; (8) paginação e
ordem dos gêneros; (9) frontend vs backend e a outra base de cifras; (10) custo
por regra; (11) sequências populares sob cada regra; (12) duplicatas e
identidade de música; (13) a coluna `TOM`; (14) rotações da sequência; (15)
vocabulário de acordes e entradas de borda; (16) campo harmônico: cobertura do
`NCIFRA`, união dos 12 tons e matching por graus; (17) cross-check com `main.py`
(este último só com `--app`). Nada é gravado em disco pelo script.

Ambiente usado nas medições: Python 3.9.6 (mesma minor version do
`Dockerfile:1`), `data/top/dataset_final.csv` com 67.585 linhas de dados.
