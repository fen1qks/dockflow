import json
import pathlib
import time

import psycopg2

from pg_lokalny import polacz

WYNIKI = []
DZIEN = '2026-10-06'


def test(nazwa, oczekiwane):
    def dek(f):
        def run(con):
            cur = con.cursor()
            cur.execute("SET search_path = dockflow")
            t0 = time.perf_counter()
            try:
                wynik = f(cur)
                ok = True
            except AssertionError as e:
                wynik, ok = f'BŁĄD: {e}', False
            ms = (time.perf_counter() - t0) * 1000
            con.rollback()
            WYNIKI.append({'test': nazwa, 'oczekiwane': oczekiwane, 'wynik': wynik, 'ok': ok, 'ms': round(ms)})
            print(('✓' if ok else '✗'), nazwa, '–', wynik)
        TESTY.append(run)
        return run
    return dek


TESTY = []


def blad(cur, sql, args=()):
    cur.execute('SAVEPOINT t')
    try:
        cur.execute(sql, args)
    except psycopg2.Error as e:
        cur.execute('ROLLBACK TO SAVEPOINT t')
        return e.diag.constraint_name or e.diag.message_primary
    raise AssertionError('polecenie nie zostało odrzucone')


def rampa(cur, numer):
    cur.execute("SELECT id FROM rampy WHERE numer = %s", (numer,))
    return cur.fetchone()[0]


def pojazd_pl(cur, n=0):
    cur.execute("""SELECT p.id, p.nr_rejestracyjny, p.przewoznik_id, (SELECT min(k.id) FROM kierowcy k WHERE k.przewoznik_id = p.przewoznik_id)
                     FROM pojazdy p JOIN organizacje o ON o.id = p.przewoznik_id
                    WHERE o.kraj_kod = 'PL' AND NOT p.chlodnia ORDER BY p.id OFFSET %s LIMIT 1""", (n,))
    return cur.fetchone()


NAPOJE = {}


def napoje(palety=22):
    return json.dumps([{'towar_id': NAPOJE['id'], 'typ_palety': 'EUR', 'liczba_palet': palety}])


def rezerwuj(cur, poj, godzina, palety=22):
    cur.execute("SELECT fn_zarezerwuj_okno(1, %s, %s, %s, 'rozladunek', %s, %s)",
                (poj[2], poj[0], poj[3], f'{DZIEN} {godzina}+02', napoje(palety)))
    return cur.fetchone()[0]


def blokada(cur, numer_rampy, od, do, n):
    poj = pojazd_pl(cur, n % 39 + 1)
    cur.execute("""INSERT INTO awizacje (numer, centrum_id, przewoznik_id, pojazd_id, kierowca_id, rampa_id, kierunek,
                                         okno_od, okno_do, czas_planowany_min)
                   VALUES (%s, 1, %s, %s, %s, %s, 'rozladunek', %s, %s, 60)""",
                (f'TEST/{n}', poj[2], poj[0], poj[3], rampa(cur, numer_rampy), f'{DZIEN} {od}+02', f'{DZIEN} {do}+02'))


@test('CHECK: koniec okna przed początkiem', 'odrzucenie')
def t_check_okno(cur):
    poj = pojazd_pl(cur)
    return blad(cur, """INSERT INTO awizacje (numer, centrum_id, przewoznik_id, pojazd_id, kierowca_id, rampa_id, kierunek,
                        okno_od, okno_do, czas_planowany_min) VALUES ('X1',1,%s,%s,%s,1,'rozladunek',
                        '2026-10-06 10:00+02','2026-10-06 09:00+02',60)""", (poj[2], poj[0], poj[3]))


@test('CHECK: 0 palet w pozycji ładunku', 'odrzucenie')
def t_check_palety(cur):
    return blad(cur, "INSERT INTO pozycje_ladunku (awizacja_id, towar_id, typ_palety, liczba_palet) VALUES (1, 4, 'EUR', 0)")


@test('EXCLUDE: dwie rezerwacje tej samej rampy w nakładającym się czasie', 'odrzucenie (ex_rampa_bez_kolizji)')
def t_exclude(cur):
    blokada(cur, 'R1', '10:00', '11:00', 1)
    poj = pojazd_pl(cur, 1)
    return blad(cur, """INSERT INTO awizacje (numer, centrum_id, przewoznik_id, pojazd_id, kierowca_id, rampa_id, kierunek,
                        okno_od, okno_do, czas_planowany_min) VALUES ('X2',1,%s,%s,%s,%s,'rozladunek',
                        '2026-10-06 10:30+02','2026-10-06 11:30+02',60)""", (poj[2], poj[0], poj[3], rampa(cur, 'R1')))


@test('UNIQUE: powtórzone zdarzenie z kamery', 'odrzucenie')
def t_duplikat(cur):
    cur.execute("SELECT kamera_id, typ, nr_odczytany, pewnosc, czas FROM zdarzenia_kamer LIMIT 1")
    return blad(cur, "INSERT INTO zdarzenia_kamer (kamera_id, typ, nr_odczytany, pewnosc, czas) VALUES (%s,%s,%s,%s,%s)",
                cur.fetchone())


@test('Rezerwacja: długość okna z modelu (22 palety napojów, PL)', '75 min, wolna rampa, numer WRO/2026/…')
def t_rezerwacja(cur):
    aid = rezerwuj(cur, pojazd_pl(cur), '10:00')
    cur.execute("""SELECT a.numer, r.numer, a.czas_planowany_min, round(fn_czas_obslugi(a.id), 1)
                     FROM awizacje a JOIN rampy r ON r.id = a.rampa_id WHERE a.id = %s""", (aid,))
    numer, nr_rampy, minuty, t = cur.fetchone()
    assert minuty == 75, minuty
    return f'{numer}, rampa {nr_rampy}, T = {t} min → okno {minuty} min'


@test('Rezerwacja: limit pojazdów na godzinę (12)', '13. rezerwacja odrzucona')
def t_limit(cur):
    for i in range(12):
        rezerwuj(cur, pojazd_pl(cur, i), f'07:{(i % 4) * 15:02d}', palety=8)
    poj = pojazd_pl(cur, 12)
    return blad(cur, "SELECT fn_zarezerwuj_okno(1, %s, %s, %s, 'rozladunek', %s, %s)",
                (poj[2], poj[0], poj[3], f'{DZIEN} 07:30+02', napoje(8)))


@test('Wcześniejszy przyjazd: przydział rampy z najmniejszą wystarczającą luką',
      'R4 (luka 72 min) odrzucona, R5 (luka 90 min) wybrana, okno 09:30 zwolnione')
def t_wczesniejszy(cur):
    cur.execute("UPDATE przydzial_brygad SET brygada_id = (SELECT id FROM brygady WHERE nazwa='A') WHERE rampa_id=%s AND data=%s AND zmiana=1",
                (rampa(cur, 'R4'), DZIEN))
    cur.execute("UPDATE przydzial_brygad SET brygada_id = (SELECT id FROM brygady WHERE nazwa='C') WHERE rampa_id=%s AND data=%s AND zmiana=1",
                (rampa(cur, 'R5'), DZIEN))
    poj = pojazd_pl(cur)
    aid = rezerwuj(cur, poj, '09:30')
    cur.execute("SELECT r.numer FROM awizacje a JOIN rampy r ON r.id = a.rampa_id WHERE a.id = %s", (aid,))
    stara = cur.fetchone()[0]
    for i, nr in enumerate(['R1', 'R2', 'R3', 'R6', 'R7', 'R8', 'R9', 'R10', 'R11', 'R12']):
        if nr != stara:
            blokada(cur, nr, '07:30', '12:00', 100 + i)
    blokada(cur, 'R4', '09:12', '10:12', 200)
    blokada(cur, 'R5', '09:30', '10:30', 201) if stara != 'R5' else None
    cur.execute("""SELECT round(fn_czas_obslugi(%s) * fn_wspolczynnik_brygady((SELECT id FROM brygady WHERE nazwa='A'), %s) * 1.3, 1),
                          round(fn_czas_obslugi(%s) * fn_wspolczynnik_brygady((SELECT id FROM brygady WHERE nazwa='C'), %s) * 1.3, 1)""",
                (aid, f'{DZIEN} 08:00+02', aid, f'{DZIEN} 08:00+02'))
    pot_r4, pot_r5 = cur.fetchone()
    cur.execute("INSERT INTO zdarzenia_kamer (kamera_id, typ, nr_odczytany, pewnosc, czas) VALUES (1,'wjazd',%s,0.97,%s)",
                (poj[1], f'{DZIEN} 08:00+02'))
    cur.execute("""SELECT r.numer, a.status, to_char(a.okno_od AT TIME ZONE 'Europe/Warsaw','HH24:MI'),
                          to_char(a.okno_do AT TIME ZONE 'Europe/Warsaw','HH24:MI')
                     FROM awizacje a JOIN rampy r ON r.id = a.rampa_id WHERE a.id = %s""", (aid,))
    nr, status, od, do = cur.fetchone()
    assert nr == 'R5' and status == 'na_bramie', (nr, status)
    return f'potrzeba R4 {pot_r4} min > 72 → odrzucona; R5 {pot_r5} min ≤ 90 → przydział {nr} {od}–{do}; stare okno na {stara} zwolnione'


@test('Spóźnienie bez zgłoszenia, wszystkie rampy zajęte', 'lista oczekujących + kara; rampa po wcześniejszym zakończeniu innej operacji')
def t_lista(cur):
    poj = pojazd_pl(cur)
    aid = rezerwuj(cur, poj, '08:00')
    cur.execute("SELECT rampa_id FROM awizacje WHERE id=%s", (aid,))
    jego = cur.fetchone()[0]
    for i, nr in enumerate(['R1', 'R2', 'R3', 'R4', 'R5', 'R6', 'R7', 'R8', 'R9', 'R10', 'R11', 'R12']):
        if rampa(cur, nr) != jego:
            blokada(cur, nr, '09:00', '11:00', 300 + i)
    blokada(cur, 'R1', '11:00', '15:00', 400) if rampa(cur, 'R1') != jego else None
    blokada_poj = pojazd_pl(cur, 60)
    cur.execute("""INSERT INTO awizacje (numer, centrum_id, przewoznik_id, pojazd_id, kierowca_id, rampa_id, kierunek, okno_od, okno_do, czas_planowany_min)
                   VALUES ('TEST/500',1,%s,%s,%s,%s,'rozladunek',%s,%s,60)""",
                (blokada_poj[2], blokada_poj[0], blokada_poj[3], jego, f'{DZIEN} 09:15+02', f'{DZIEN} 11:00+02'))
    cur.execute("INSERT INTO zdarzenia_kamer (kamera_id, typ, nr_odczytany, pewnosc, czas) VALUES (1,'wjazd',%s,0.95,%s)",
                (poj[1], f'{DZIEN} 09:10+02'))
    cur.execute("SELECT status FROM awizacje WHERE id=%s", (aid,))
    s1 = cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM kary WHERE awizacja_id=%s AND typ='spoznienie'", (aid,))
    kara = cur.fetchone()[0]
    assert s1 == 'lista_oczekujacych' and kara == 1, (s1, kara)
    cur.execute("SELECT id FROM awizacje WHERE numer='TEST/301'")
    inna = cur.fetchone()[0]
    cur.execute("INSERT INTO operacje_rampowe (awizacja_id, brygada_id, start) VALUES (%s, 1, %s) RETURNING id",
                (inna, f'{DZIEN} 09:05+02'))
    op = cur.fetchone()[0]
    cur.execute("UPDATE operacje_rampowe SET koniec=%s, palety_obsluzone=10 WHERE id=%s", (f'{DZIEN} 09:40+02', op))
    cur.execute("SELECT a.status, r.numer FROM awizacje a JOIN rampy r ON r.id=a.rampa_id WHERE a.id=%s", (aid,))
    s2, nr = cur.fetchone()
    assert s2 == 'na_bramie' and nr == 'R2', (s2, nr)
    return f'wjazd 09:10 → {s1}, kara za spóźnienie; o 09:40 R2 zwolniona wcześniej → przydział {nr}'


@test('Zgłoszenie opóźnienia: przebukowanie', 'nowe okno od zgłoszonej godziny, bez kary przy wjeździe')
def t_opoznienie(cur):
    poj = pojazd_pl(cur)
    aid = rezerwuj(cur, poj, '10:00')
    cur.execute("SELECT fn_zglos_opoznienie(%s, %s, %s)", (aid, f'{DZIEN} 13:05+02', f'{DZIEN} 08:30+02'))
    nowe = cur.fetchone()[0]
    cur.execute("INSERT INTO zdarzenia_kamer (kamera_id, typ, nr_odczytany, pewnosc, czas) VALUES (1,'wjazd',%s,0.95,%s)",
                (poj[1], f'{DZIEN} 13:12+02'))
    cur.execute("SELECT count(*) FROM kary WHERE awizacja_id=%s", (aid,))
    kary = cur.fetchone()[0]
    assert kary == 0
    return f'okno 10:00 → {nowe.astimezone().strftime("%H:%M")}, wjazd 13:12 bez kary'


@test('No-show: brak wjazdu 30 min po oknie', 'status no_show + kara')
def t_no_show(cur):
    aid = rezerwuj(cur, pojazd_pl(cur), '10:00')
    cur.execute("SELECT fn_oznacz_no_show(%s)", (f'{DZIEN} 11:50+02',))
    cur.execute("SELECT a.status, k.typ FROM awizacje a JOIN kary k ON k.awizacja_id = a.id WHERE a.id=%s", (aid,))
    s, k = cur.fetchone()
    assert s == 'no_show' and k == 'no_show'
    return f'status {s}, kara {k}'


@test('Wyzwalacze: historia statusów i dziennik audytu', 'wpis przy każdej zmianie statusu')
def t_historia(cur):
    poj = pojazd_pl(cur)
    aid = rezerwuj(cur, poj, '12:00')
    for typ, godz in [('wjazd', '11:58'), ('podstawienie', '12:04')]:
        cur.execute("INSERT INTO zdarzenia_kamer (kamera_id, typ, nr_odczytany, pewnosc, czas) VALUES (%s,%s,%s,0.95,%s)",
                    (1 if typ == 'wjazd' else 2, typ, poj[1], f'{DZIEN} {godz}+02'))
    cur.execute("SELECT string_agg(coalesce(status_z,'–') || '→' || status_na, ', ' ORDER BY id) FROM historia_statusow WHERE awizacja_id=%s", (aid,))
    hist = cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM dziennik_audytu WHERE tabela='awizacje' AND (nowe_dane->>'id')::int = %s", (aid,))
    audyt = cur.fetchone()[0]
    assert hist.count('→') >= 3 and audyt >= 3
    return f'{hist}; dziennik audytu: {audyt} wpisy'


@test('RLS: spedytor widzi tylko awizacje swojej firmy', '0 cudzych wierszy')
def t_rls(cur):
    cur.execute("SELECT przewoznik_id, count(*) FROM awizacje GROUP BY 1 ORDER BY 2 DESC LIMIT 1")
    firma, swoje = cur.fetchone()
    cur.execute("SELECT count(*) FROM awizacje")
    wszystkie = cur.fetchone()[0]
    cur.execute("SET LOCAL ROLE df_spedytor")
    cur.execute("SELECT set_config('dockflow.org_id', %s, true)", (str(firma),))
    cur.execute("SELECT count(*), count(*) FILTER (WHERE przewoznik_id <> %s) FROM awizacje", (firma,))
    widzi, cudze = cur.fetchone()
    assert widzi == swoje and cudze == 0
    return f'w bazie {wszystkie} awizacji, spedytor widzi {widzi} (swoje), cudzych: {cudze}'


@test('Uprawnienia: rezerwacja w imieniu innego przewoźnika', 'odrzucenie')
def t_cudza_rezerwacja(cur):
    poj = pojazd_pl(cur)
    cur.execute("SELECT id FROM organizacje WHERE typ='przewoznik' AND id <> %s LIMIT 1", (poj[2],))
    inna = cur.fetchone()[0]
    cur.execute("SET LOCAL ROLE df_spedytor")
    cur.execute("SELECT set_config('dockflow.org_id', %s, true)", (str(inna),))
    return blad(cur, "SELECT fn_zarezerwuj_okno(1, %s, %s, %s, 'rozladunek', %s, %s)",
                (poj[2], poj[0], poj[3], f'{DZIEN} 10:00+02', napoje()))


@test('Uprawnienia: kamera nie może czytać awizacji', 'odrzucenie')
def t_kamera(cur):
    cur.execute("SET LOCAL ROLE df_kamera")
    return blad(cur, "SELECT count(*) FROM awizacje")


@test('Uprawnienia: ochrona nie może zmieniać awizacji', 'odrzucenie')
def t_ochrona(cur):
    cur.execute("SET LOCAL ROLE df_ochrona")
    return blad(cur, "UPDATE awizacje SET status = 'anulowana' WHERE id = 1")


@test('Wydajność: rezerwacja okna przy ~11 tys. awizacji', 'poniżej 1 s')
def t_wydajnosc(cur):
    t0 = time.perf_counter()
    rezerwuj(cur, pojazd_pl(cur), '15:00')
    ms = (time.perf_counter() - t0) * 1000
    assert ms < 1000
    return f'{ms:.0f} ms'


if __name__ == '__main__':
    con = polacz()
    cur = con.cursor()
    cur.execute("SELECT id FROM dockflow.towary WHERE nazwa = 'Napoje'")
    NAPOJE['id'] = cur.fetchone()[0]
    con.autocommit = False
    for t in TESTY:
        t(con)
    ok = sum(w['ok'] for w in WYNIKI)
    print(f'\n{ok}/{len(WYNIKI)} testów zaliczonych')
    pathlib.Path(__file__).with_name('wyniki_testow.json').write_text(json.dumps(WYNIKI, ensure_ascii=False, indent=1))
