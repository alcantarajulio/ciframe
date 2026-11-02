# coding: utf-8
"""Catálogo de sequências de acordes em SQLite (biblioteca padrão).

Caminho via SEQUENCIAS_DB; default relativo dados/sequencias.db — no
container o WORKDIR é /app, então o arquivo cai em /app/dados/sequencias.db;
localmente cai no checkout, coerente com o CSV, que já exige rodar da raiz.
Conexão por chamada (sqlite3 não deve ser compartilhado entre threads).
Versão do esquema em PRAGMA user_version, conferida no init.
"""
import json
import os
import sqlite3
from datetime import datetime, timezone

SCHEMA_VERSION = 1

SCHEMA = '''
CREATE TABLE IF NOT EXISTS sequencias (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chave TEXT NOT NULL UNIQUE,
    acordes TEXT NOT NULL,
    origem TEXT NOT NULL,
    criado_em TEXT NOT NULL
)
'''

# as 6 originais, na ordem que o matching usa hoje
SEMENTES = [
    ['Bm', 'G', 'D', 'A'],
    ['C', 'G', 'Am', 'F'],
    ['Em', 'G'],
    ['C', 'A7', 'Dm', 'G7'],
    ['Gm', 'F'],
    ['C', 'C7', 'F', 'Fm'],
]

COLUNAS = 'id, chave, acordes, origem, criado_em'


def caminho_db():
    return os.environ.get('SEQUENCIAS_DB',
            os.path.join('dados', 'sequencias.db'))


def chave_de(tokens):
    # caixa exata: A7M (sétima maior) e A7m (menor com sétima) são acordes
    # diferentes, então a identidade não baixa mais para minúsculas
    return ';'.join(tokens)


def conectar():
    con = sqlite3.connect(caminho_db())
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA journal_mode=WAL')
    con.execute('PRAGMA busy_timeout=5000')
    con.execute('PRAGMA foreign_keys=ON')
    return con


def init():
    diretorio = os.path.dirname(caminho_db())
    if diretorio:
        os.makedirs(diretorio, exist_ok=True)
    con = conectar()
    try:
        con.execute(SCHEMA)
        versao = con.execute('PRAGMA user_version').fetchone()[0]
        if versao == 0:
            con.execute('PRAGMA user_version = %d' % SCHEMA_VERSION)
        elif versao != SCHEMA_VERSION:
            raise RuntimeError('user_version %d inesperado em %s (esperado %d)'
                    % (versao, caminho_db(), SCHEMA_VERSION))
        con.commit()
    finally:
        con.close()


def seed():
    con = conectar()
    try:
        for tokens in SEMENTES:
            con.execute(
                'INSERT OR IGNORE INTO sequencias'
                ' (chave, acordes, origem, criado_em) VALUES (?, ?, ?, ?)',
                (chave_de(tokens), json.dumps(tokens), 'seed', _agora()))
        con.commit()
    finally:
        con.close()


def listar():
    con = conectar()
    try:
        linhas = con.execute(
            'SELECT %s FROM sequencias ORDER BY id' % COLUNAS).fetchall()
        return [_para_dict(linha) for linha in linhas]
    finally:
        con.close()


def inserir_ou_obter(tokens, origem='usuario'):
    chave = chave_de(tokens)
    con = conectar()
    try:
        cursor = con.execute(
            'INSERT OR IGNORE INTO sequencias'
            ' (chave, acordes, origem, criado_em) VALUES (?, ?, ?, ?)',
            (chave, json.dumps(list(tokens)), origem, _agora()))
        con.commit()
        linha = con.execute(
            'SELECT %s FROM sequencias WHERE chave = ?' % COLUNAS,
            (chave,)).fetchone()
        return _para_dict(linha), cursor.rowcount > 0
    finally:
        con.close()


def buscar_por_chave(chave):
    con = conectar()
    try:
        linha = con.execute(
            'SELECT %s FROM sequencias WHERE chave = ?' % COLUNAS,
            (chave,)).fetchone()
        return _para_dict(linha) if linha else None
    finally:
        con.close()


def _agora():
    return datetime.now(timezone.utc).isoformat()


def _para_dict(linha):
    return {
        'id': linha['id'],
        'chave': linha['chave'],
        'acordes': json.loads(linha['acordes']),
        'origem': linha['origem'],
        'criado_em': linha['criado_em'],
    }
