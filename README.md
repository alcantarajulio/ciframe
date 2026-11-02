# deciframe

Descubra as músicas que você já sabe tocar (e ainda não faz ideia). Busque por
título/artista, gênero, pelos acordes que você já manja, ou por sequências de
acordes famosas — o deciframe cruza isso com uma base de cifras e sugere
músicas parecidas.

Stack: backend Flask (Python) servindo uma API JSON + um frontend AngularJS
estático. As músicas vêm de um CSV carregado em memória; o catálogo de
sequências de acordes customizadas fica num SQLite em `dados/sequencias.db`.

## Rodando localmente

### Com Docker

```
docker build -t ciframe .
docker run -v deciframe-dados:/app/dados -p 8080:8080 ciframe
```

Acesse [http://localhost:8080](http://localhost:8080).

O volume `deciframe-dados` guarda o catálogo de sequências: sequências
cadastradas continuam lá depois de `docker rm -f` e de subir de novo com o
mesmo volume. Sem `-v`, o banco vive apenas dentro do container — cadastros
somem quando ele é removido. Para descartar o catálogo de vez, remova o volume
com `docker volume rm deciframe-dados`.

### Com virtualenv

```
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

Acesse [http://localhost:5000](http://localhost:5000).

---

Para convenções de contribuição, veja [CONTRIB.md](CONTRIB.md). Licença: [LICENSE](LICENSE).
