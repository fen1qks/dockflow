import json, pathlib
from pg_lokalny import polacz

con = polacz(); cur = con.cursor()


def q(sql):
    cur.execute(sql)
    kol = [d[0] for d in cur.description]
    return [dict(zip(kol, [float(v) if hasattr(v, 'as_integer_ratio') and not isinstance(v, int) else v for v in r]))
            for r in cur.fetchall()]


w = {
    'liczby': q("""SELECT (SELECT count(*) FROM awizacje) awizacje, (SELECT count(*) FROM operacje_rampowe) operacje,
                          (SELECT count(*) FROM zdarzenia_kamer) zdarzenia, (SELECT count(*) FROM przestoje) przestoje,
                          (SELECT count(*) FROM kary) kary, (SELECT count(*) FROM pojazdy) pojazdy,
                          (SELECT count(*) FROM organizacje WHERE typ='przewoznik') przewoznicy""")[0],
    'model': q("""SELECT t.nazwa, m.kierunek, m.min_na_palete, m.liczba_pomiarow FROM model_czasu m
                  JOIN towary t ON t.id = m.towar_id ORDER BY m.min_na_palete"""),
    'dokumenty': q("SELECT kraj_kod, min_przygotowania, liczba_pomiarow FROM model_dokumenty ORDER BY min_przygotowania"),
    'brygady': q("""SELECT brygada, operacje, wspolczynnik, sr_przygotowanie_min, min_na_palete, proc_opoznien_zmiana_2,
                           glowna_przyczyna FROM v_raport_brygad WHERE miesiac = '2026-09-01' ORDER BY brygada"""),
    'odcinki': q("""SELECT round(avg(min_oczekiwanie)::numeric,0) oczekiwanie, round(avg(min_przygotowanie)::numeric,0) przygotowanie,
                           round(avg(min_operacja)::numeric,0) operacja, round(avg(min_zakonczenie)::numeric,0) zakonczenie,
                           round(avg(min_pobyt)::numeric,0) pobyt FROM v_wizyty""")[0],
}
pathlib.Path(__file__).with_name('wyniki_analizy.json').write_text(json.dumps(w, ensure_ascii=False, indent=1, default=str))
print(json.dumps(w, ensure_ascii=False, indent=1, default=str))
