import os, pathlib, psycopg2, pgserver

KATALOG = pathlib.Path(__file__).resolve().parent.parent
DANE = pathlib.Path(os.environ.get('DOCKFLOW_PGDATA', KATALOG / '.pgdata'))


def polacz(nowa_baza=False):
    DANE.mkdir(exist_ok=True)
    srv = pgserver.get_server(str(DANE), cleanup_mode='stop')
    con = psycopg2.connect(srv.get_uri())
    con.autocommit = True
    if nowa_baza:
        cur = con.cursor()
        cur.execute("DROP ROLE IF EXISTS df_aplikacja")
        for plik in sorted((KATALOG / 'db').glob('0*.sql')):
            cur.execute(plik.read_text(encoding='utf-8'))
            print('wczytano', plik.name)
    con.cursor().execute('SET search_path = dockflow')
    return con


if __name__ == '__main__':
    polacz(nowa_baza=True)
