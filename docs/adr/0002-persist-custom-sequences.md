# Introduzir SQLite, com arquivo em volume nomeado, para o catálogo de sequências

O catálogo de sequências "famosas" sempre viveu em dois lugares que não são um
banco: um `dict` de seis entradas no backend (`main.py:40-45`) e quatro objetos
literais no controller Angular (`sequencia.js:2-37`), com as seis tags
correspondentes pré-computadas na coluna `SEQ_FAMOSA` do CSV. A feature nova
exige o contrário disso: qualquer visitante, sem login, pode cadastrar uma
sequência, e o catálogo tem de sobreviver a reinícios do servidor e crescer sem
novo deploy. O projeto não tinha banco, ORM, migração nem escrita em disco em
nenhum ponto do backend — `main.py` só lê `data/top/dataset_final.csv` no import
e mantém músicas, gêneros e acordes em memória.

Decidimos usar `sqlite3` da biblioteca padrão, com um arquivo único em
`/app/dados/sequencias.db` montado a partir de um volume nomeado, e persistir
**apenas** o catálogo de sequências. Músicas, gêneros e acordes continuam vindo
do CSV em memória, como hoje. A escolha segue de perto o ADR 0001: nada de
serviço auxiliar, nada de rede, nada de dependência nova em `requirements.txt` —
o módulo `_sqlite3` já existe na imagem `python:3.9-slim` (verificado, SQLite
3.46.1) e o container continua sendo um só. SQLite dá o que o catálogo precisa e
um arquivo JSON não dá sem código: transações, um `UNIQUE` que resolve
"sequência duplicada" com garantia mesmo sob concorrência (em vez de um `SELECT`
antes do `INSERT` que perde a corrida quando o número de workers mudar) e
consultas por chave sem reescrever o arquivo inteiro a cada cadastro. Um
Postgres ou MySQL em outro container resolveria o mesmo problema criando um
segundo serviço, uma rede e um volume a mais, o que contradiz o container único
do ADR 0001 para um catálogo que deve ter dezenas de linhas.

O matching **não** é materializado no banco. A regra escolhida (bloco contíguo
com vocabulário exato, a mesma que gerou a tag) permite indexar as músicas pelo
conjunto de acordes no próprio load do CSV, e uma busca passa a custar 0,15 ms
de mediana por sequência, contra ~87 ms da implementação literal do gerador —
os ~400 ms medidos na pesquisa são uma passada com as 6 sequências juntas, não o
custo de uma consulta. Isso mantém o banco
com uma única tabela, sem estado derivado para invalidar quando o CSV muda — que
é justamente o tipo de inconsistência silenciosa que este projeto não tem
ferramenta para detectar.

As consequências são conhecidas e algumas são desagradáveis. O arquivo só
sobrevive a `docker rm` e a rebuild se o volume for montado; o comando documentado
no README e no AGENTS passa a ser `docker run -v deciframe-dados:/app/dados -p
8080:8080 ciframe`, e `dados/` entra no `.dockerignore` para que `COPY . .` não
asse um banco de desenvolvimento dentro da imagem. O esquema é versionado à mão
com `PRAGMA user_version`, porque não há framework de migração e não vale
introduzir um para uma tabela. A escrita é serializada e não há `USER` no
container, então o arquivo pertence ao root: backup é copiar o arquivo (com o
`-wal`), e rodar com mais de um worker do gunicorn exigiria revisitar o seed e o
`busy_timeout`. Por fim, o seed das seis sequências originais roda no boot com
`INSERT` idempotente apoiado na chave única, o que deixa o catálogo
autossuficiente: o CSV continua sendo a fonte das músicas e o oráculo do teste de
regressão, mas deixa de ser a fonte do catálogo.
