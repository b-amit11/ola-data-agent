"""Defence in depth: SQL AST checks AND database-enforced read-only execution."""
import sqlite3
import time
from decimal import Decimal
from datetime import date,datetime

import sqlglot
from sqlglot import exp

from .seed import ROOT, TABLES

FUNCTIONS={'COUNT','SUM','AVG','MIN','MAX','ROUND','COALESCE','NULLIF','ABS','LOWER','UPPER','CAST','DATE','STRFTIME','DATE_TRUNC','EXTRACT'}


def validate_sql(sql, dialect='sqlite'):
    if len(sql)>8000: raise ValueError('SQL exceeds length limit')
    try: statements=sqlglot.parse(sql,read=dialect)
    except sqlglot.errors.ParseError as exc: raise ValueError('SQL could not be parsed') from exc
    if len(statements)!=1 or not isinstance(statements[0],exp.Query):
        raise ValueError('Exactly one SELECT query is permitted')
    tree=statements[0]
    forbidden={'Insert','Update','Delete','Drop','Create','Alter','Command','Copy','Into','Lock','Merge','Transaction','Grant','Revoke'}
    if any(type(n).__name__ in forbidden for n in tree.walk()):
        raise ValueError('Write, lock, and administrative operations are blocked')
    if any(w.args.get('recursive') for w in tree.find_all(exp.With)):
        raise ValueError('Recursive queries are not supported')
    ctes={c.alias_or_name for c in tree.find_all(exp.CTE)}
    for table in tree.find_all(exp.Table):
        if table.db or table.catalog or table.name not in set(TABLES)|ctes:
            raise ValueError('Only the five demo tables and local CTEs are allowed')
    for func in tree.find_all(exp.Func):
        if isinstance(func,(exp.Case,exp.If,exp.And,exp.Or)): continue
        name=func.name.upper() if isinstance(func,exp.Anonymous) else func.sql_name().upper()
        if name not in FUNCTIONS:
            raise ValueError(f'Function {name} is not in the analytics allowlist')
    return sql.strip().rstrip(';')


class Database:
    def __init__(self,path=None,url=None):
        self.path=path or ROOT/'data/ola.db'
        self.url=url
        self.dialect='postgres' if url else 'sqlite'
        if url and not url.startswith('postgresql+psycopg://'):
            raise ValueError('Only PostgreSQL psycopg URLs are supported')

    def schema(self):
        if self.url:
            from sqlalchemy import create_engine,inspect
            engine=create_engine(self.url,connect_args={'connect_timeout':3})
            try:
                inspector=inspect(engine)
                return {t:[c['name'] for c in inspector.get_columns(t)] for t in TABLES}
            finally: engine.dispose()
        with sqlite3.connect(f'file:{self.path.resolve()}?mode=ro',uri=True) as conn:
            return {t:[r[1] for r in conn.execute(f'PRAGMA table_info({t})')] for t in TABLES}

    def query(self,sql,limit=100):
        sql=validate_sql(sql,self.dialect)
        limit=max(1,min(int(limit),1000))
        if self.url:
            from sqlalchemy import create_engine,text
            engine=create_engine(self.url,connect_args={'connect_timeout':3})
            try:
                with engine.connect() as conn, conn.begin():
                    conn.execute(text('SET TRANSACTION READ ONLY'))
                    conn.execute(text("SET LOCAL statement_timeout = '3000ms'"))
                    conn.execute(text("SET LOCAL search_path = public"))
                    result=conn.execute(text(sql));columns=list(result.keys());rows=result.fetchmany(limit+1)
            finally: engine.dispose()
        else:
            conn=sqlite3.connect(f'file:{self.path.resolve()}?mode=ro',uri=True)
            try:
                conn.execute('PRAGMA query_only=ON')
                deadline=time.monotonic()+3
                conn.set_progress_handler(lambda: int(time.monotonic()>deadline),1000)
                allowed={sqlite3.SQLITE_SELECT,sqlite3.SQLITE_READ,sqlite3.SQLITE_FUNCTION}
                def authorize(action,a,b,db,trigger):
                    if action==sqlite3.SQLITE_READ and a not in TABLES: return sqlite3.SQLITE_DENY
                    if action==sqlite3.SQLITE_FUNCTION and (b or '').upper() not in FUNCTIONS: return sqlite3.SQLITE_DENY
                    return sqlite3.SQLITE_OK if action in allowed else sqlite3.SQLITE_DENY
                conn.set_authorizer(authorize)
                result=conn.execute(sql);columns=[r[0] for r in result.description];rows=result.fetchmany(limit+1)
            finally: conn.close()
        def scalar(value):
            if isinstance(value,Decimal): return float(value)
            if isinstance(value,(date,datetime)): return value.isoformat()
            return value
        return {'columns':columns,'rows':[[scalar(v) for v in r] for r in rows[:limit]],'truncated':len(rows)>limit}
