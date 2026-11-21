import datetime as dt
import random
import sys
import uuid
import zoneinfo
import pathlib

from psycopg2.extras import execute_values

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / 'testy'))
from pg_lokalny import polacz

random.seed(2026)
TZ = zoneinfo.ZoneInfo('Europe/Warsaw')
OD, DO = dt.date(2026, 7, 1), dt.date(2026, 9, 30)
PRZYDZIAL_DO = dt.date(2026, 10, 31)

KRAJE = {
    'PL': ('Polska', 55, 20, 6), 'DE': ('Niemcy', 12, 35, 8), 'UA': ('Ukraina', 10, 150, 22),
    'CZ': ('Czechy', 8, 30, 8), 'LT': ('Litwa', 6, 70, 9), 'RO': ('Rumunia', 5, 90, 10),
    'NL': ('Holandia', 4, 45, 8),
}
TOWARY = {
    'Napoje': (False, 'rozladunek', 'EUR', 2.7, 35, (10, 33)),
    'Chemia gospodarcza': (False, 'rozladunek', 'EUR', 2.9, 25, (10, 33)),
    'Mrożonki': (True, 'rozladunek', 'EUR', 3.6, 18, (12, 33)),
    'Zwroty': (False, 'rozladunek', 'MIX', 5.5, 12, (3, 15)),
    'Drobnica (zamówienia mieszane)': (False, 'zaladunek', 'MIX', 4.8, 50, (8, 24)),
}
BRYGADY = {
    'A': (0.92, 0.92, 0, 0), 'B': (1.08, 1.30, 5, 48), 'C': (0.97, 0.97, 0, 0),
    'D': (1.03, 1.03, 0, 0), 'E': (1.00, 1.00, 0, 0), 'F': (0.98, 0.98, 0, 0),
}
NO_SHOW = 0.03
AWARIA = 0.02
GODZINY_ZAPOTRZEBOWANIA = [6] * 18 + [7] * 16 + [8] * 12 + [9] * 9 + [10] * 9 + [11] * 8 + [12] * 7 \
    + [13] * 6 + [14] * 6 + [15] * 5 + [16] * 4 + [17] * 3 + [18] * 3 + [19] * 2 + [20] * 2


def tablica(kraj):
    L, C = 'ABCDEFGHJKLMNPRSTUVWXYZ', '0123456789'
    r = lambda s, n: ''.join(random.choice(s) for _ in range(n))
    return {'PL': f'D{random.choice("WLKBJ")} {r(C, 1)}{r(L, 2)}{r(C, 2)}', 'DE': f'{r(L, 1)}-{r(L, 2)} {r(C, 4)}',
            'UA': f'{r(L, 2)}{r(C, 4)}{r(L, 2)}', 'CZ': f'{r(C, 1)}{r(L, 1)}{r(C, 1)} {r(C, 4)}',
            'LT': f'{r(L, 3)} {r(C, 3)}', 'RO': f'B {r(C, 2)} {r(L, 3)}', 'NL': f'{r(L, 2)}-{r(C, 3)}-{r(L, 1)}'}[kraj]


def lok(d, minuty):
    return dt.datetime.combine(d, dt.time()).replace(tzinfo=TZ) + dt.timedelta(minutes=minuty)


def main():
    con = polacz(nowa_baza=True)
    cur = con.cursor()
    cur.execute("SET session_replication_role = replica")

    execute_values(cur, "INSERT INTO kraje VALUES %s",
                   [(k, v[0], 10) for k, v in KRAJE.items()])
    execute_values(cur, "INSERT INTO typy_palet VALUES %s",
                   [('EUR', 'Paleta EUR 120×80'), ('IND', 'Paleta przemysłowa 120×100'), ('MIX', 'Paleta mieszana')])
    execute_values(cur, "INSERT INTO przyczyny_przestojow VALUES %s",
                   [('brak_wozka', 'Brak wolnego wózka widłowego'), ('dokumenty', 'Oczekiwanie na dokumenty'),
                    ('awaria_wozka', 'Awaria wózka'), ('brak_miejsca', 'Brak miejsca w strefie buforowej')])
    towar_id = {}
    for i, (n, t) in enumerate(TOWARY.items(), 1):
        cur.execute("INSERT INTO towary (nazwa, chlodniczy, domyslny_min_paleta) VALUES (%s,%s,3.0) RETURNING id",
                    (n, t[0]))
        towar_id[n] = cur.fetchone()[0]

    cur.execute("INSERT INTO organizacje (nazwa, nip, kraj_kod, typ) VALUES ('WroLog Sp. z o.o.','8992990001','PL','operator') RETURNING id")
    operator = cur.fetchone()[0]
    cur.execute("""INSERT INTO centra (organizacja_id, nazwa, adres, godz_otwarcia, godz_zamkniecia)
                   VALUES (%s,'CD Bielany Wrocławskie','ul. Logistyczna 1, 55-040 Bielany Wrocławskie','06:00','22:00')
                   RETURNING id""", (operator,))
    centrum = cur.fetchone()[0]
    rampy = {}
    for n in range(1, 13):
        cur.execute("INSERT INTO rampy (centrum_id, numer, chlodnia) VALUES (%s,%s,%s) RETURNING id",
                    (centrum, f'R{n}', n >= 10))
        rampy[f'R{n}'] = cur.fetchone()[0]
    execute_values(cur, "INSERT INTO limity_godzinowe VALUES %s",
                   [(centrum, d, h, 12 if h < 14 else 10) for d in range(1, 7) for h in range(6, 22)])
    cur.execute("INSERT INTO kamery (centrum_id, typ, klucz_api_hash) VALUES (%s,'brama',%s) RETURNING id",
                (centrum, uuid.uuid4().hex))
    kamera_brama = cur.fetchone()[0]
    kamera_rampy = {}
    for nr, rid in rampy.items():
        cur.execute("INSERT INTO kamery (centrum_id, rampa_id, typ, klucz_api_hash) VALUES (%s,%s,'rampa',%s) RETURNING id",
                    (centrum, rid, uuid.uuid4().hex))
        kamera_rampy[rid] = cur.fetchone()[0]
    brygady = {}
    imiona = ['Adam', 'Piotr', 'Marek', 'Tomasz', 'Paweł', 'Michał', 'Jan', 'Krzysztof', 'Andrzej']
    nazwiska = ['Nowak', 'Kowalski', 'Wiśniewski', 'Wójcik', 'Kamiński', 'Lewandowski', 'Zieliński', 'Szymański']
    for b in BRYGADY:
        cur.execute("INSERT INTO brygady (centrum_id, nazwa) VALUES (%s,%s) RETURNING id", (centrum, b))
        brygady[b] = cur.fetchone()[0]
        for _ in range(3):
            cur.execute("INSERT INTO pracownicy (centrum_id, imie, nazwisko) VALUES (%s,%s,%s) RETURNING id",
                        (centrum, random.choice(imiona), random.choice(nazwiska)))
            cur.execute("INSERT INTO brygady_sklad VALUES (%s,%s,'2026-01-01',NULL)", (brygady[b], cur.fetchone()[0]))
    execute_values(cur, "INSERT INTO uzytkownicy (organizacja_id, keycloak_id, email, rola) VALUES %s",
                   [(operator, str(uuid.uuid4()), f'{r}@wrolog.example', r)
                    for r in ['admin', 'kierownik', 'dyspozytor', 'ochrona', 'brygadzista']])

    grupy = [['R1', 'R2', 'R3', 'R4'], ['R5', 'R6', 'R7', 'R8'], ['R9', 'R10', 'R11', 'R12']]
    grafik, przydzial = {}, []
    d = OD
    while d <= PRZYDZIAL_DO:
        if d.isoweekday() <= 6:
            rano, popol = (['A', 'B', 'C'], ['D', 'E', 'F']) if d.isocalendar().week % 2 == 0 else (['D', 'E', 'F'], ['A', 'B', 'C'])
            for zmiana, zespol in ((1, rano), (2, popol)):
                for i, b in enumerate(zespol):
                    for nr in grupy[(i + d.toordinal()) % 3]:
                        grafik[(d, zmiana, nr)] = b
                        przydzial.append((rampy[nr], d, zmiana, brygady[b]))
        d += dt.timedelta(days=1)
    execute_values(cur, "INSERT INTO przydzial_brygad VALUES %s", przydzial)

    kraje_waga = [k for k, v in KRAJE.items() for _ in range(v[1])]
    przewoznicy, uzyte_tablice = [], set()
    for i in range(65):
        kraj = kraje_waga[i * len(kraje_waga) // 65]
        cur.execute("INSERT INTO organizacje (nazwa, nip, kraj_kod, typ) VALUES (%s,%s,%s,'przewoznik') RETURNING id",
                    (f'Przewoźnik {kraj}-{i + 1:02d}', f'{kraj}{1000000 + i}', kraj))
        pid = cur.fetchone()[0]
        auta = []
        for _ in range(random.randint(3, 10)):
            chl = random.random() < 0.25
            nr = tablica(kraj)
            while nr in uzyte_tablice:
                nr = tablica(kraj)
            uzyte_tablice.add(nr)
            cur.execute("INSERT INTO pojazdy (przewoznik_id, nr_rejestracyjny, chlodnia) VALUES (%s,%s,%s) RETURNING id",
                        (pid, nr, chl))
            auta.append((cur.fetchone()[0], nr, chl))
        kierowcy = []
        for _ in range(len(auta)):
            cur.execute("INSERT INTO kierowcy (przewoznik_id, imie_nazwisko, telefon) VALUES (%s,%s,%s) RETURNING id",
                        (pid, f'Kierowca {random.randint(100, 999)}', f'+{random.randint(10**10, 10**11 - 1)}'))
            kierowcy.append(cur.fetchone()[0])
        przewoznicy.append((pid, kraj, auta, kierowcy))
    waga_przew = [p for p in przewoznicy for _ in range(len(p[2]))]

    awizacje, pozycje, zdarzenia, operacje, przestoje, kary = [], [], [], [], [], []
    nr_aw, nr_op = 0, 0
    d = OD
    while d <= DO:
        if d.isoweekday() > 6:
            d += dt.timedelta(days=1)
            continue
        zajete = {nr: [] for nr in rampy}
        dzien, uzyte_auta = [], set()
        for towar, (chl, kier, typ, mpp, ile, (pmin, pmax)) in TOWARY.items():
            for _ in range(ile):
                while True:
                    przew = random.choice(waga_przew)
                    pasujace = [a for a in przew[2] if a[2] == chl and a[0] not in uzyte_auta]
                    if pasujace:
                        break
                auto = random.choice(pasujace)
                uzyte_auta.add(auto[0])
                start = random.choice(GODZINY_ZAPOTRZEBOWANIA) * 60 + random.choice([0, 15, 30, 45])
                dzien.append([towar, przew, auto, start, random.randint(pmin, pmax)])
        random.shuffle(dzien)
        for z in dzien:
            towar, start = z[0], z[3]
            chl = TOWARY[towar][0]
            kandydaci = [nr for nr in rampy if (int(nr[1:]) >= 10) == chl]
            while True:
                wolne = [nr for nr in kandydaci if all(not (start < b and a < start + 60) for a, b in zajete[nr])]
                if wolne or start > 21 * 60:
                    break
                start += 15
            if not wolne:
                continue
            nr = wolne[0]
            zajete[nr].append((start, start + 60))
            z[3] = start
            z.append(nr)
        dzien = [z for z in dzien if len(z) == 6]

        wolna_od = {nr: 6 * 60 for nr in rampy}
        przyjazdy = []
        for towar, przew, auto, start, palety, nr_okna in dzien:
            nr_aw += 1
            aw = (nr_aw, f'WRO/2026/{nr_aw:05d}', centrum, przew[0], auto[0], random.choice(przew[3]),
                  rampy[nr_okna], TOWARY[towar][1], lok(d, start), lok(d, start + 60), 60)
            pozycje.append((nr_aw, towar_id[towar], TOWARY[towar][2], palety))
            if random.random() < NO_SHOW:
                awizacje.append(aw + ('no_show',))
                kary.append((nr_aw, 'no_show', lok(d, start + 90)))
                continue
            sd = KRAJE[przew[1]][2]
            przyjazd = max(5 * 60 + random.uniform(0, 45), start + random.gauss(-10, sd))
            przyjazdy.append((przyjazd, aw, towar, przew, auto, palety))
        przyjazdy.sort(key=lambda x: x[0])
        for przyjazd, aw, towar, przew, auto, palety in przyjazdy:
            chl, kier, typ, mpp, _, _ = TOWARY[towar]
            kandydaci = [nr for nr in rampy if int(nr[1:]) >= 10 or not chl]
            nr = min(kandydaci, key=lambda r: (wolna_od[r], int(r[1:]) >= 10))
            podst = max(przyjazd + random.uniform(4, 8), wolna_od[nr] + random.uniform(2, 5))
            zmiana = 1 if podst < 14 * 60 else 2
            b = grafik[(d, zmiana, nr)]
            tempo, _, ext1, ext2 = BRYGADY[b]
            tempo = BRYGADY[b][zmiana - 1]
            extra = ext1 if zmiana == 1 else ext2
            dok = KRAJE[przew[1]][3] * random.uniform(0.7, 1.3)
            start_op = podst + dok + extra * random.uniform(0.7, 1.3)
            awaria = random.random() < AWARIA
            czas_op = palety * mpp * tempo * random.uniform(0.9, 1.1) * (3.5 if awaria else 1)
            koniec = start_op + czas_op
            odjazd = koniec + random.uniform(2, 5)
            wyjazd = odjazd + random.uniform(4, 10)
            wolna_od[nr] = odjazd
            nr_op += 1
            awizacje.append(aw + ('wyjazd',))
            operacje.append((nr_op, aw[0], brygady[b], lok(d, start_op), lok(d, koniec), palety,
                             1 if random.random() < (0.05 if extra > 20 else 0.02) else 0, awaria))
            if extra > 20:
                przestoje.append((nr_op, 'brak_wozka', lok(d, podst + dok), lok(d, start_op)))
            elif przew[1] == 'UA' and random.random() < 0.3:
                przestoje.append((nr_op, 'dokumenty', lok(d, podst), lok(d, podst + dok)))
            elif random.random() < 0.03:
                przestoje.append((nr_op, random.choice(['awaria_wozka', 'brak_miejsca']),
                                  lok(d, start_op), lok(d, start_op + 5)))
            tab = auto[1]
            zdarzenia += [(kamera_brama, 'wjazd', tab, round(random.uniform(0.85, 0.99), 2), lok(d, przyjazd), aw[0]),
                          (kamera_rampy[rampy[nr]], 'podstawienie', tab, 0.95, lok(d, podst), aw[0]),
                          (kamera_rampy[rampy[nr]], 'odjazd', tab, 0.95, lok(d, odjazd), aw[0]),
                          (kamera_brama, 'wyjazd', tab, round(random.uniform(0.85, 0.99), 2), lok(d, wyjazd), aw[0])]
        d += dt.timedelta(days=1)

    execute_values(cur, """INSERT INTO awizacje (id, numer, centrum_id, przewoznik_id, pojazd_id, kierowca_id, rampa_id,
                           kierunek, okno_od, okno_do, czas_planowany_min, status) VALUES %s""", awizacje, page_size=2000)
    cur.execute("SELECT setval('awizacje_id_seq', (SELECT max(id) FROM awizacje)), setval('seq_numer_awizacji', (SELECT max(id) FROM awizacje))")
    execute_values(cur, "INSERT INTO pozycje_ladunku (awizacja_id, towar_id, typ_palety, liczba_palet) VALUES %s", pozycje, page_size=2000)
    execute_values(cur, "INSERT INTO operacje_rampowe (id, awizacja_id, brygada_id, start, koniec, palety_obsluzone, uszkodzenia, awaria) VALUES %s",
                   operacje, page_size=2000)
    cur.execute("SELECT setval('operacje_rampowe_id_seq', (SELECT max(id) FROM operacje_rampowe))")
    execute_values(cur, "INSERT INTO przestoje (operacja_id, przyczyna_kod, od, \"do\") VALUES %s", przestoje, page_size=2000)
    execute_values(cur, "INSERT INTO zdarzenia_kamer (kamera_id, typ, nr_odczytany, pewnosc, czas, awizacja_id) VALUES %s",
                   zdarzenia, page_size=5000)
    execute_values(cur, "INSERT INTO kary (awizacja_id, typ, naliczono) VALUES %s", kary)
    cur.execute("SET session_replication_role = origin")
    cur.execute("SELECT fn_przelicz_model('2026-10-01 00:00+02', 92)")

    print(f'awizacje: {len(awizacje)}, operacje: {len(operacje)}, zdarzenia z kamer: {len(zdarzenia)}, '
          f'przestoje: {len(przestoje)}, no-show: {len(kary)}')


if __name__ == '__main__':
    main()
