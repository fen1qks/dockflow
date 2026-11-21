SET search_path = dockflow;

CREATE SEQUENCE seq_numer_awizacji;

CREATE FUNCTION fn_status_zajmuje(p_status text) RETURNS boolean
LANGUAGE sql IMMUTABLE AS $$ SELECT p_status NOT IN ('no_show', 'odrzucona', 'anulowana') $$;

CREATE FUNCTION fn_teraz() RETURNS timestamptz
LANGUAGE sql STABLE AS $$
    SELECT coalesce(nullif(current_setting('dockflow.czas', true), '')::timestamptz, now())
$$;

CREATE FUNCTION fn_org() RETURNS int
LANGUAGE sql STABLE AS $$ SELECT nullif(current_setting('dockflow.org_id', true), '')::int $$;

CREATE FUNCTION fn_sprawdz_przewoznika(p_przewoznik int) RETURNS void
LANGUAGE plpgsql STABLE AS $$
BEGIN
    IF EXISTS (SELECT 1 FROM organizacje o WHERE o.id = fn_org() AND o.typ = 'przewoznik')
       AND p_przewoznik IS DISTINCT FROM fn_org() THEN
        RAISE EXCEPTION 'Brak uprawnień do danych innego przewoźnika';
    END IF;
END $$;

CREATE FUNCTION fn_min_na_palete(p_towar int, p_kierunek text, p_typ text) RETURNS numeric
LANGUAGE sql STABLE AS $$
    SELECT coalesce(
        (SELECT m.min_na_palete FROM model_czasu m
          WHERE m.towar_id = p_towar AND m.kierunek = p_kierunek
            AND m.typ_palety = p_typ AND m.liczba_pomiarow >= 30),
        (SELECT t.domyslny_min_paleta FROM towary t WHERE t.id = p_towar))
$$;

CREATE FUNCTION fn_czas_dokumentow(p_kraj char) RETURNS numeric
LANGUAGE sql STABLE AS $$
    SELECT coalesce(
        (SELECT d.min_przygotowania FROM model_dokumenty d
          WHERE d.kraj_kod = p_kraj AND d.liczba_pomiarow >= 30),
        (SELECT k.domyslny_czas_dok FROM kraje k WHERE k.kod = p_kraj))
$$;

CREATE FUNCTION fn_wspolczynnik_brygady(p_brygada int, p_czas timestamptz) RETURNS numeric
LANGUAGE sql STABLE AS $$
    SELECT coalesce(
        (SELECT w.wspolczynnik FROM wspolczynniki_brygad w
          WHERE w.brygada_id = p_brygada
            AND w.miesiac < date_trunc('month', p_czas AT TIME ZONE 'Europe/Warsaw')
          ORDER BY w.miesiac DESC LIMIT 1),
        1.00)
$$;

CREATE FUNCTION fn_brygada_na_rampie(p_rampa int, p_czas timestamptz) RETURNS int
LANGUAGE sql STABLE AS $$
    SELECT p.brygada_id FROM przydzial_brygad p
     WHERE p.rampa_id = p_rampa
       AND p.data = (p_czas AT TIME ZONE 'Europe/Warsaw')::date
       AND p.zmiana = CASE WHEN extract(hour FROM p_czas AT TIME ZONE 'Europe/Warsaw') < 14 THEN 1 ELSE 2 END
$$;

CREATE FUNCTION fn_czas_z_pozycji(p_kraj char, p_kierunek text, p_pozycje jsonb, p_wsp numeric DEFAULT 1)
RETURNS numeric LANGUAGE sql STABLE AS $$
    SELECT (fn_czas_dokumentow(p_kraj)
            + coalesce(sum((x->>'liczba_palet')::int
                 * fn_min_na_palete((x->>'towar_id')::int, p_kierunek, x->>'typ_palety')), 0)) * p_wsp
      FROM jsonb_array_elements(p_pozycje) x
$$;

CREATE FUNCTION fn_czas_obslugi(p_awizacja int, p_wsp numeric DEFAULT 1) RETURNS numeric
LANGUAGE sql STABLE AS $$
    SELECT fn_czas_z_pozycji(o.kraj_kod, a.kierunek,
             (SELECT jsonb_agg(jsonb_build_object('towar_id', p.towar_id, 'typ_palety', p.typ_palety,
                                                  'liczba_palet', p.liczba_palet))
                FROM pozycje_ladunku p WHERE p.awizacja_id = a.id),
             p_wsp)
      FROM awizacje a JOIN organizacje o ON o.id = a.przewoznik_id
     WHERE a.id = p_awizacja
$$;

CREATE FUNCTION fn_zarezerwuj_okno(p_centrum int, p_przewoznik int, p_pojazd int, p_kierowca int,
                                   p_kierunek text, p_od timestamptz, p_pozycje jsonb)
RETURNS int LANGUAGE plpgsql AS $$
DECLARE
    v_kraj      char(2);
    v_minuty    int;
    v_do        timestamptz;
    v_chlodnia  boolean;
    v_limit     int;
    v_zajete    int;
    v_rampa     int;
    v_id        int;
    v_lokalnie  timestamp := p_od AT TIME ZONE 'Europe/Warsaw';
BEGIN
    PERFORM fn_sprawdz_przewoznika(p_przewoznik);
    SELECT kraj_kod INTO v_kraj FROM organizacje WHERE id = p_przewoznik AND typ = 'przewoznik';
    IF v_kraj IS NULL THEN RAISE EXCEPTION 'Nieznany przewoźnik %', p_przewoznik; END IF;

    v_minuty := ceil(fn_czas_z_pozycji(v_kraj, p_kierunek, p_pozycje) / 15.0) * 15;
    v_do := p_od + make_interval(mins => v_minuty);

    IF NOT EXISTS (SELECT 1 FROM centra c WHERE c.id = p_centrum
                     AND v_lokalnie::time >= c.godz_otwarcia
                     AND (v_do AT TIME ZONE 'Europe/Warsaw')::time <= c.godz_zamkniecia) THEN
        RAISE EXCEPTION 'Okno % – % poza godzinami pracy centrum', p_od, v_do;
    END IF;

    SELECT l.max_pojazdow INTO v_limit FROM limity_godzinowe l
     WHERE l.centrum_id = p_centrum
       AND l.dzien_tygodnia = extract(isodow FROM v_lokalnie)
       AND l.godzina = extract(hour FROM v_lokalnie);
    SELECT count(*) INTO v_zajete FROM awizacje a
     WHERE a.centrum_id = p_centrum AND fn_status_zajmuje(a.status)
       AND date_trunc('hour', a.okno_od) = date_trunc('hour', p_od);
    IF v_limit IS NOT NULL AND v_zajete >= v_limit THEN
        RAISE EXCEPTION 'Limit pojazdów (%) w tej godzinie został osiągnięty', v_limit;
    END IF;

    SELECT bool_or(t.chlodniczy) INTO v_chlodnia
      FROM jsonb_array_elements(p_pozycje) x JOIN towary t ON t.id = (x->>'towar_id')::int;

    SELECT r.id INTO v_rampa FROM rampy r
     WHERE r.centrum_id = p_centrum AND r.aktywna AND (NOT v_chlodnia OR r.chlodnia)
       AND NOT EXISTS (SELECT 1 FROM awizacje a
                        WHERE a.rampa_id = r.id AND fn_status_zajmuje(a.status)
                          AND tstzrange(a.okno_od, a.okno_do) && tstzrange(p_od, v_do))
     ORDER BY r.chlodnia, r.numer
     LIMIT 1;
    IF v_rampa IS NULL THEN RAISE EXCEPTION 'Brak wolnej rampy w oknie % – %', p_od, v_do; END IF;

    INSERT INTO awizacje (numer, centrum_id, przewoznik_id, pojazd_id, kierowca_id, rampa_id,
                          kierunek, okno_od, okno_do, czas_planowany_min)
    VALUES ('WRO/' || extract(year FROM v_lokalnie) || '/' || lpad(nextval('seq_numer_awizacji')::text, 5, '0'),
            p_centrum, p_przewoznik, p_pojazd, p_kierowca, v_rampa, p_kierunek, p_od, v_do, v_minuty)
    RETURNING id INTO v_id;

    INSERT INTO pozycje_ladunku (awizacja_id, towar_id, typ_palety, liczba_palet)
    SELECT v_id, (x->>'towar_id')::int, x->>'typ_palety', (x->>'liczba_palet')::int
      FROM jsonb_array_elements(p_pozycje) x;
    RETURN v_id;
END $$;

CREATE FUNCTION fn_przydziel_rampe(p_awizacja int, p_teraz timestamptz) RETURNS int
LANGUAGE plpgsql AS $$
DECLARE
    a           awizacje%ROWTYPE;
    v_bazowy    numeric;
    v_zapas     numeric;
    v_chlodnia  boolean;
    w           record;
BEGIN
    SELECT * INTO a FROM awizacje WHERE id = p_awizacja FOR UPDATE;
    v_bazowy := fn_czas_obslugi(p_awizacja);
    SELECT 1 + c.zapas_procent / 100.0 INTO v_zapas FROM centra c WHERE c.id = a.centrum_id;
    SELECT coalesce(bool_or(t.chlodniczy), false) INTO v_chlodnia
      FROM pozycje_ladunku p JOIN towary t ON t.id = p.towar_id WHERE p.awizacja_id = p_awizacja;

    SELECT r.id AS rampa_id, k.potrzeba, l.luka INTO w
      FROM rampy r
      JOIN centra c ON c.id = r.centrum_id
      CROSS JOIN LATERAL (
          SELECT make_interval(secs => v_bazowy * 60 * v_zapas
                   * fn_wspolczynnik_brygady(fn_brygada_na_rampie(r.id, p_teraz), p_teraz)) AS potrzeba) k
      CROSS JOIN LATERAL (
          SELECT coalesce(min(x.okno_od),
                   ((p_teraz AT TIME ZONE 'Europe/Warsaw')::date + c.godz_zamkniecia) AT TIME ZONE 'Europe/Warsaw')
                 - p_teraz AS luka
            FROM awizacje x
           WHERE x.rampa_id = r.id AND x.id <> p_awizacja AND fn_status_zajmuje(x.status)
             AND x.okno_od >= p_teraz) l
     WHERE r.centrum_id = a.centrum_id AND r.aktywna AND (NOT v_chlodnia OR r.chlodnia)
       AND l.luka >= k.potrzeba

       AND NOT EXISTS (SELECT 1 FROM awizacje x
                        WHERE x.rampa_id = r.id AND x.id <> p_awizacja AND fn_status_zajmuje(x.status)
                          AND tstzrange(x.okno_od, x.okno_do) && tstzrange(p_teraz, p_teraz + k.potrzeba))

       AND NOT EXISTS (SELECT 1 FROM awizacje x JOIN operacje_rampowe o ON o.awizacja_id = x.id
                        WHERE x.rampa_id = r.id AND o.koniec IS NULL)
     ORDER BY l.luka, r.numer
     LIMIT 1;

    IF w.rampa_id IS NULL THEN RETURN NULL; END IF;

    UPDATE awizacje
       SET rampa_id = w.rampa_id, okno_od = p_teraz, okno_do = p_teraz + w.potrzeba
     WHERE id = p_awizacja;
    RETURN w.rampa_id;
END $$;

CREATE FUNCTION fn_obsluz_oczekujacych(p_centrum int, p_teraz timestamptz) RETURNS int
LANGUAGE plpgsql AS $$
DECLARE
    v_id  int;
    v_ile int := 0;
BEGIN
    FOR v_id IN
        SELECT a.id FROM awizacje a
         WHERE a.centrum_id = p_centrum AND a.status = 'lista_oczekujacych'
         ORDER BY EXISTS (SELECT 1 FROM zgloszenia_opoznien z WHERE z.awizacja_id = a.id) DESC,
                  (SELECT min(e.czas) FROM zdarzenia_kamer e WHERE e.awizacja_id = a.id AND e.typ = 'wjazd')
    LOOP
        IF fn_przydziel_rampe(v_id, p_teraz) IS NOT NULL THEN
            UPDATE awizacje SET status = 'na_bramie' WHERE id = v_id;
            v_ile := v_ile + 1;
        END IF;
    END LOOP;
    RETURN v_ile;
END $$;

CREATE FUNCTION fn_zglos_opoznienie(p_awizacja int, p_nowa_godzina timestamptz, p_teraz timestamptz)
RETURNS timestamptz LANGUAGE plpgsql AS $$
DECLARE
    a          awizacje%ROWTYPE;
    v_dlugosc  interval;
    v_start    timestamptz;
    v_rampa    int;
    v_chlodnia boolean;
BEGIN
    SELECT * INTO a FROM awizacje WHERE id = p_awizacja FOR UPDATE;
    PERFORM fn_sprawdz_przewoznika(a.przewoznik_id);
    IF a.status <> 'zaplanowana' THEN RAISE EXCEPTION 'Opóźnienie można zgłosić tylko przed przyjazdem'; END IF;
    INSERT INTO zgloszenia_opoznien (awizacja_id, zgloszono, nowa_godzina) VALUES (p_awizacja, p_teraz, p_nowa_godzina);

    v_dlugosc := make_interval(mins => a.czas_planowany_min);
    SELECT coalesce(bool_or(t.chlodniczy), false) INTO v_chlodnia
      FROM pozycje_ladunku p JOIN towary t ON t.id = p.towar_id WHERE p.awizacja_id = p_awizacja;

    FOR v_start IN
        SELECT g FROM generate_series(date_bin('15 minutes', p_nowa_godzina + interval '14 minutes 59 seconds',
                                               timestamptz '2000-01-01'),
                                      p_nowa_godzina + interval '2 days', interval '15 minutes') g
    LOOP
        SELECT r.id INTO v_rampa FROM rampy r JOIN centra c ON c.id = r.centrum_id
         WHERE r.centrum_id = a.centrum_id AND r.aktywna AND (NOT v_chlodnia OR r.chlodnia)
           AND (v_start AT TIME ZONE 'Europe/Warsaw')::time >= c.godz_otwarcia
           AND ((v_start + v_dlugosc) AT TIME ZONE 'Europe/Warsaw')::time <= c.godz_zamkniecia
           AND (v_start + v_dlugosc) AT TIME ZONE 'Europe/Warsaw' > v_start AT TIME ZONE 'Europe/Warsaw'
           AND NOT EXISTS (SELECT 1 FROM awizacje x
                            WHERE x.rampa_id = r.id AND x.id <> p_awizacja AND fn_status_zajmuje(x.status)
                              AND tstzrange(x.okno_od, x.okno_do) && tstzrange(v_start, v_start + v_dlugosc))
         ORDER BY r.chlodnia, r.numer LIMIT 1;
        IF v_rampa IS NOT NULL THEN
            UPDATE awizacje SET rampa_id = v_rampa, okno_od = v_start, okno_do = v_start + v_dlugosc
             WHERE id = p_awizacja;
            RETURN v_start;
        END IF;
    END LOOP;
    RAISE EXCEPTION 'Brak wolnego okna w ciągu 2 dni';
END $$;

CREATE FUNCTION fn_oznacz_no_show(p_teraz timestamptz) RETURNS int
LANGUAGE plpgsql AS $$
DECLARE v_ile int;
BEGIN
    PERFORM set_config('dockflow.czas', p_teraz::text, true);
    WITH n AS (
        UPDATE awizacje SET status = 'no_show'
         WHERE status = 'zaplanowana' AND okno_do + interval '30 minutes' < p_teraz
        RETURNING id
    )
    INSERT INTO kary (awizacja_id, typ, naliczono)
    SELECT id, 'no_show', p_teraz FROM n
    ON CONFLICT DO NOTHING;
    GET DIAGNOSTICS v_ile = ROW_COUNT;
    RETURN v_ile;
END $$;

CREATE FUNCTION trg_historia_statusow() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'INSERT' OR NEW.status IS DISTINCT FROM OLD.status THEN
        INSERT INTO historia_statusow (awizacja_id, status_z, status_na, kiedy, uzytkownik, powod)
        VALUES (NEW.id, CASE WHEN TG_OP = 'UPDATE' THEN OLD.status END, NEW.status, fn_teraz(),
                coalesce(current_setting('dockflow.uzytkownik', true), current_user),
                nullif(current_setting('dockflow.powod', true), ''));
    END IF;
    RETURN NULL;
END $$;
CREATE TRIGGER awizacje_historia AFTER INSERT OR UPDATE OF status ON awizacje
    FOR EACH ROW EXECUTE FUNCTION trg_historia_statusow();

CREATE FUNCTION trg_zdarzenie_przypisz() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.awizacja_id IS NULL THEN
        SELECT a.id INTO NEW.awizacja_id
          FROM awizacje a
          JOIN pojazdy p ON p.id = a.pojazd_id
          JOIN kamery k ON k.id = NEW.kamera_id AND k.centrum_id = a.centrum_id
         WHERE p.nr_rejestracyjny = NEW.nr_odczytany
           AND a.status NOT IN ('wyjazd', 'no_show', 'odrzucona', 'anulowana')
           AND (a.okno_od AT TIME ZONE 'Europe/Warsaw')::date = (NEW.czas AT TIME ZONE 'Europe/Warsaw')::date
         ORDER BY abs(extract(epoch FROM a.okno_od - NEW.czas))
         LIMIT 1;
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER zdarzenia_przypisz BEFORE INSERT ON zdarzenia_kamer
    FOR EACH ROW EXECUTE FUNCTION trg_zdarzenie_przypisz();

CREATE FUNCTION trg_zdarzenie_obsluz() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    a          awizacje%ROWTYPE;
    v_zgloszone boolean;
BEGIN
    IF NEW.awizacja_id IS NULL THEN
        RAISE NOTICE 'Pojazd % bez awizacji – ostrzeżenie dla ochrony', NEW.nr_odczytany;
        RETURN NULL;
    END IF;
    PERFORM set_config('dockflow.czas', NEW.czas::text, true);
    PERFORM set_config('dockflow.uzytkownik', 'kamera ' || NEW.kamera_id, true);
    SELECT * INTO a FROM awizacje WHERE id = NEW.awizacja_id;

    IF NEW.typ = 'wjazd' THEN
        UPDATE awizacje SET status = 'na_bramie' WHERE id = a.id;
        v_zgloszone := EXISTS (SELECT 1 FROM zgloszenia_opoznien z WHERE z.awizacja_id = a.id);
        IF NEW.czas > a.okno_od + interval '30 minutes' AND NOT v_zgloszone THEN
            INSERT INTO kary (awizacja_id, typ, naliczono) VALUES (a.id, 'spoznienie', NEW.czas)
            ON CONFLICT DO NOTHING;
        END IF;

        IF NEW.czas < a.okno_od - interval '5 minutes' OR NEW.czas > a.okno_od THEN
            IF fn_przydziel_rampe(a.id, NEW.czas) IS NULL THEN
                UPDATE awizacje
                   SET status = CASE WHEN NEW.czas < a.okno_od THEN 'na_placu' ELSE 'lista_oczekujacych' END
                 WHERE id = a.id;
            END IF;
        END IF;
    ELSIF NEW.typ = 'podstawienie' THEN
        UPDATE awizacje SET status = 'przy_rampie' WHERE id = a.id;
    ELSIF NEW.typ = 'wyjazd' THEN
        UPDATE awizacje SET status = 'wyjazd' WHERE id = a.id;
    END IF;
    RETURN NULL;
END $$;
CREATE TRIGGER zdarzenia_obsluz AFTER INSERT ON zdarzenia_kamer
    FOR EACH ROW EXECUTE FUNCTION trg_zdarzenie_obsluz();

CREATE FUNCTION trg_operacja() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE v_centrum int;
BEGIN
    IF TG_OP = 'INSERT' THEN
        PERFORM set_config('dockflow.czas', NEW.start::text, true);
        UPDATE awizacje SET status = 'w_trakcie' WHERE id = NEW.awizacja_id;
    ELSIF NEW.koniec IS NOT NULL AND OLD.koniec IS NULL THEN
        PERFORM set_config('dockflow.czas', NEW.koniec::text, true);

        UPDATE awizacje
           SET status = 'zakonczona', okno_do = greatest(NEW.koniec, okno_od + interval '1 minute')
         WHERE id = NEW.awizacja_id
        RETURNING centrum_id INTO v_centrum;
        PERFORM fn_obsluz_oczekujacych(v_centrum, NEW.koniec);
    END IF;
    RETURN NULL;
END $$;
CREATE TRIGGER operacje_status AFTER INSERT OR UPDATE OF koniec ON operacje_rampowe
    FOR EACH ROW EXECUTE FUNCTION trg_operacja();

CREATE FUNCTION trg_audyt() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    INSERT INTO dziennik_audytu (tabela, operacja, uzytkownik, stare_dane, nowe_dane)
    VALUES (TG_TABLE_NAME, TG_OP, coalesce(current_setting('dockflow.uzytkownik', true), current_user),
            CASE WHEN TG_OP <> 'INSERT' THEN to_jsonb(OLD) END,
            CASE WHEN TG_OP <> 'DELETE' THEN to_jsonb(NEW) END);
    RETURN NULL;
END $$;
CREATE TRIGGER audyt_awizacje AFTER INSERT OR UPDATE OR DELETE ON awizacje
    FOR EACH ROW EXECUTE FUNCTION trg_audyt();
CREATE TRIGGER audyt_kary AFTER INSERT OR UPDATE OR DELETE ON kary
    FOR EACH ROW EXECUTE FUNCTION trg_audyt();
CREATE TRIGGER audyt_operacje AFTER INSERT OR UPDATE OR DELETE ON operacje_rampowe
    FOR EACH ROW EXECUTE FUNCTION trg_audyt();
CREATE TRIGGER audyt_uzytkownicy AFTER INSERT OR UPDATE OR DELETE ON uzytkownicy
    FOR EACH ROW EXECUTE FUNCTION trg_audyt();

CREATE VIEW v_wizyty AS
SELECT a.id AS awizacja_id, a.centrum_id, a.kierunek, a.okno_od, o.kraj_kod, op.brygada_id,
       CASE WHEN extract(hour FROM z.podstawienie AT TIME ZONE 'Europe/Warsaw') < 14 THEN 1 ELSE 2 END AS zmiana,
       z.wjazd, z.podstawienie, op.start, op.koniec, z.odjazd, z.wyjazd,
       extract(epoch FROM z.podstawienie - z.wjazd) / 60 AS min_oczekiwanie,
       extract(epoch FROM op.start - z.podstawienie) / 60 AS min_przygotowanie,
       extract(epoch FROM op.koniec - op.start) / 60 AS min_operacja,
       extract(epoch FROM z.wyjazd - op.koniec) / 60 AS min_zakonczenie,
       extract(epoch FROM z.wyjazd - z.wjazd) / 60 AS min_pobyt,
       op.palety_obsluzone, op.awaria
  FROM awizacje a
  JOIN organizacje o ON o.id = a.przewoznik_id
  JOIN operacje_rampowe op ON op.awizacja_id = a.id
  JOIN LATERAL (
      SELECT min(czas) FILTER (WHERE typ = 'wjazd')        AS wjazd,
             min(czas) FILTER (WHERE typ = 'podstawienie') AS podstawienie,
             max(czas) FILTER (WHERE typ = 'odjazd')       AS odjazd,
             max(czas) FILTER (WHERE typ = 'wyjazd')       AS wyjazd
        FROM zdarzenia_kamer e WHERE e.awizacja_id = a.id) z ON true;

CREATE VIEW v_kpi_dzienne AS
SELECT a.centrum_id, (a.okno_od AT TIME ZONE 'Europe/Warsaw')::date AS dzien,
       count(*) AS awizacje,
       count(*) FILTER (WHERE a.status = 'no_show') AS no_show,
       round(avg(w.min_pobyt)::numeric, 1) AS sredni_pobyt_min,
       round(100.0 * count(*) FILTER (WHERE extract(hour FROM w.wjazd AT TIME ZONE 'Europe/Warsaw') BETWEEN 6 AND 8)
             / nullif(count(w.wjazd), 0), 1) AS proc_przyjazdow_6_9
  FROM awizacje a LEFT JOIN v_wizyty w ON w.awizacja_id = a.id
 GROUP BY 1, 2;

CREATE VIEW v_raport_brygad AS
WITH oczek AS (
    SELECT w.*, date_trunc('month', w.start AT TIME ZONE 'Europe/Warsaw')::date AS miesiac,
           fn_czas_obslugi(w.awizacja_id) AS min_oczekiwany,
           w.min_przygotowanie + w.min_operacja AS min_rzeczywisty
      FROM v_wizyty w WHERE NOT w.awaria
), przestoj AS (
    SELECT g.*, row_number() OVER (PARTITION BY g.brygada_id, g.miesiac ORDER BY g.ile DESC) AS nr,
           sum(g.ile) OVER (PARTITION BY g.brygada_id, g.miesiac) AS razem
      FROM (SELECT op.brygada_id, date_trunc('month', op.start AT TIME ZONE 'Europe/Warsaw')::date AS miesiac,
                   p.przyczyna_kod, count(*) AS ile
              FROM przestoje p JOIN operacje_rampowe op ON op.id = p.operacja_id
             GROUP BY 1, 2, 3) g
)
SELECT b.nazwa AS brygada, o.miesiac, count(*) AS operacje,
       round(sum(o.min_rzeczywisty) / sum(o.min_oczekiwany), 2) AS wspolczynnik,
       round(avg(o.min_przygotowanie)::numeric, 1) AS sr_przygotowanie_min,
       round((sum(o.min_operacja) / sum(o.palety_obsluzone))::numeric, 2) AS min_na_palete,
       round(100.0 * count(*) FILTER (WHERE o.zmiana = 2 AND o.min_rzeczywisty > 1.2 * o.min_oczekiwany)
             / nullif(count(*) FILTER (WHERE o.min_rzeczywisty > 1.2 * o.min_oczekiwany), 0), 0) AS proc_opoznien_zmiana_2,
       (SELECT p.przyczyna_kod || ' (' || round(100.0 * p.ile / p.razem) || '%)'
          FROM przestoj p WHERE p.brygada_id = o.brygada_id AND p.miesiac = o.miesiac AND p.nr = 1) AS glowna_przyczyna
  FROM oczek o JOIN brygady b ON b.id = o.brygada_id
 GROUP BY b.nazwa, o.brygada_id, o.miesiac;

CREATE FUNCTION fn_przelicz_model(p_teraz timestamptz, p_dni int DEFAULT 90) RETURNS void
LANGUAGE plpgsql AS $$
BEGIN

    WITH pomiary AS (
        SELECT p.towar_id, a.kierunek, p.typ_palety,
               extract(epoch FROM op.koniec - op.start) / 60 / op.palety_obsluzone AS mpp
          FROM operacje_rampowe op
          JOIN awizacje a ON a.id = op.awizacja_id
          JOIN pozycje_ladunku p ON p.awizacja_id = a.id
         WHERE op.koniec BETWEEN p_teraz - make_interval(days => p_dni) AND p_teraz
           AND NOT op.awaria AND op.palety_obsluzone > 0
           AND (SELECT count(*) FROM pozycje_ladunku q WHERE q.awizacja_id = a.id) = 1
    ), mediany AS (
        SELECT towar_id, kierunek, typ_palety, percentile_cont(0.5) WITHIN GROUP (ORDER BY mpp) AS med
          FROM pomiary GROUP BY 1, 2, 3
    )
    INSERT INTO model_czasu (towar_id, kierunek, typ_palety, min_na_palete, liczba_pomiarow, przeliczono)
    SELECT p.towar_id, p.kierunek, p.typ_palety, round(avg(p.mpp)::numeric, 2), count(*), p_teraz
      FROM pomiary p JOIN mediany m USING (towar_id, kierunek, typ_palety)
     WHERE p.mpp <= 3 * m.med
     GROUP BY 1, 2, 3
    ON CONFLICT (towar_id, kierunek, typ_palety) DO UPDATE
       SET min_na_palete = EXCLUDED.min_na_palete, liczba_pomiarow = EXCLUDED.liczba_pomiarow,
           przeliczono = EXCLUDED.przeliczono;

    INSERT INTO model_dokumenty (kraj_kod, min_przygotowania, liczba_pomiarow, przeliczono)
    SELECT w.kraj_kod, round(percentile_cont(0.5) WITHIN GROUP (ORDER BY w.min_przygotowanie)::numeric, 1),
           count(*), p_teraz
      FROM v_wizyty w
     WHERE w.start BETWEEN p_teraz - make_interval(days => p_dni) AND p_teraz AND w.min_przygotowanie >= 0
     GROUP BY w.kraj_kod
    ON CONFLICT (kraj_kod) DO UPDATE
       SET min_przygotowania = EXCLUDED.min_przygotowania, liczba_pomiarow = EXCLUDED.liczba_pomiarow,
           przeliczono = EXCLUDED.przeliczono;

    INSERT INTO wspolczynniki_brygad (brygada_id, miesiac, wspolczynnik, liczba_operacji)
    SELECT w.brygada_id, date_trunc('month', w.start AT TIME ZONE 'Europe/Warsaw')::date,
           round((sum(w.min_przygotowanie + w.min_operacja) / sum(fn_czas_obslugi(w.awizacja_id)))::numeric, 2),
           count(*)
      FROM v_wizyty w
     WHERE w.start BETWEEN p_teraz - make_interval(days => p_dni) AND p_teraz AND NOT w.awaria
     GROUP BY 1, 2
    ON CONFLICT (brygada_id, miesiac) DO UPDATE
       SET wspolczynnik = EXCLUDED.wspolczynnik, liczba_operacji = EXCLUDED.liczba_operacji;
END $$;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_cron') THEN
        PERFORM cron.schedule('dockflow-no-show', '*/5 * * * *', 'SELECT dockflow.fn_oznacz_no_show(now())');
        PERFORM cron.schedule('dockflow-model', '0 3 * * *', 'SELECT dockflow.fn_przelicz_model(now())');
    ELSE
        RAISE NOTICE 'pg_cron niedostępny – zadania uruchamiane ręcznie';
    END IF;
END $$;
