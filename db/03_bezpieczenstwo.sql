SET search_path = dockflow;

DO $$
DECLARE r text;
BEGIN
    FOREACH r IN ARRAY ARRAY['df_admin','df_kierownik','df_dyspozytor','df_ochrona',
                             'df_brygadzista','df_spedytor','df_kierowca','df_kamera'] LOOP
        IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = r) THEN
            EXECUTE format('CREATE ROLE %I NOLOGIN', r);
        END IF;
    END LOOP;

    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'df_aplikacja') THEN
        CREATE ROLE df_aplikacja LOGIN NOINHERIT PASSWORD 'zmien-mnie';
    END IF;
END $$;
GRANT df_admin, df_kierownik, df_dyspozytor, df_ochrona, df_brygadzista,
      df_spedytor, df_kierowca, df_kamera TO df_aplikacja;

REVOKE ALL ON ALL TABLES IN SCHEMA dockflow FROM PUBLIC;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA dockflow FROM PUBLIC;
GRANT USAGE ON SCHEMA dockflow TO df_admin, df_kierownik, df_dyspozytor, df_ochrona,
      df_brygadzista, df_spedytor, df_kierowca, df_kamera;

GRANT SELECT ON kraje, towary, typy_palet, przyczyny_przestojow, centra, rampy, organizacje
      TO df_kierownik, df_dyspozytor, df_ochrona, df_brygadzista, df_spedytor, df_kierowca;

GRANT ALL ON ALL TABLES IN SCHEMA dockflow TO df_admin;
GRANT ALL ON ALL SEQUENCES IN SCHEMA dockflow TO df_admin;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA dockflow TO df_admin;

GRANT SELECT ON ALL TABLES IN SCHEMA dockflow TO df_kierownik;
GRANT EXECUTE ON FUNCTION fn_przelicz_model(timestamptz, int) TO df_kierownik;

GRANT SELECT ON awizacje, pozycje_ladunku, pojazdy, kierowcy, zdarzenia_kamer, operacje_rampowe,
      przestoje, historia_statusow, zgloszenia_opoznien, kary, brygady, przydzial_brygad,
      v_wizyty, v_kpi_dzienne TO df_dyspozytor;
GRANT UPDATE (status, rampa_id, okno_od, okno_do) ON awizacje TO df_dyspozytor;
GRANT INSERT ON zdarzenia_kamer TO df_dyspozytor;
GRANT USAGE ON SEQUENCE zdarzenia_kamer_id_seq TO df_dyspozytor;
GRANT EXECUTE ON FUNCTION fn_przydziel_rampe(int, timestamptz), fn_obsluz_oczekujacych(int, timestamptz)
      TO df_dyspozytor;

GRANT SELECT ON awizacje, pojazdy TO df_ochrona;
GRANT INSERT ON zdarzenia_kamer TO df_ochrona;
GRANT USAGE ON SEQUENCE zdarzenia_kamer_id_seq TO df_ochrona;

GRANT SELECT ON awizacje, pozycje_ladunku, operacje_rampowe, przestoje TO df_brygadzista;
GRANT INSERT, UPDATE (koniec, palety_obsluzone, uszkodzenia, awaria) ON operacje_rampowe TO df_brygadzista;
GRANT INSERT ON przestoje TO df_brygadzista;
GRANT USAGE ON SEQUENCE operacje_rampowe_id_seq, przestoje_id_seq TO df_brygadzista;

GRANT SELECT, INSERT, UPDATE ON pojazdy, kierowcy TO df_spedytor;
GRANT USAGE ON SEQUENCE pojazdy_id_seq, kierowcy_id_seq TO df_spedytor;
GRANT SELECT ON awizacje, pozycje_ladunku, kary, zgloszenia_opoznien TO df_spedytor;
GRANT EXECUTE ON FUNCTION fn_zarezerwuj_okno(int, int, int, int, text, timestamptz, jsonb),
      fn_zglos_opoznienie(int, timestamptz, timestamptz) TO df_spedytor;

GRANT SELECT ON awizacje TO df_kierowca;
GRANT EXECUTE ON FUNCTION fn_zglos_opoznienie(int, timestamptz, timestamptz) TO df_kierowca;

GRANT INSERT ON zdarzenia_kamer TO df_kamera;
GRANT USAGE ON SEQUENCE zdarzenia_kamer_id_seq TO df_kamera;

GRANT EXECUTE ON FUNCTION fn_org(), fn_status_zajmuje(text), fn_teraz(), fn_czas_obslugi(int, numeric),
      fn_czas_z_pozycji(char, text, jsonb, numeric), fn_min_na_palete(int, text, text),
      fn_czas_dokumentow(char), fn_wspolczynnik_brygady(int, timestamptz), fn_brygada_na_rampie(int, timestamptz)
      TO df_kierownik, df_dyspozytor, df_ochrona, df_brygadzista, df_spedytor, df_kierowca, df_kamera;

ALTER FUNCTION fn_zarezerwuj_okno(int, int, int, int, text, timestamptz, jsonb) SECURITY DEFINER SET search_path = dockflow;
ALTER FUNCTION fn_zglos_opoznienie(int, timestamptz, timestamptz)               SECURITY DEFINER SET search_path = dockflow;
ALTER FUNCTION fn_przydziel_rampe(int, timestamptz)                             SECURITY DEFINER SET search_path = dockflow;
ALTER FUNCTION fn_obsluz_oczekujacych(int, timestamptz)                         SECURITY DEFINER SET search_path = dockflow;
ALTER FUNCTION trg_historia_statusow()   SECURITY DEFINER SET search_path = dockflow;
ALTER FUNCTION trg_zdarzenie_przypisz()  SECURITY DEFINER SET search_path = dockflow;
ALTER FUNCTION trg_zdarzenie_obsluz()    SECURITY DEFINER SET search_path = dockflow;
ALTER FUNCTION trg_operacja()            SECURITY DEFINER SET search_path = dockflow;
ALTER FUNCTION trg_audyt()               SECURITY DEFINER SET search_path = dockflow;

ALTER TABLE awizacje ENABLE ROW LEVEL SECURITY;
CREATE POLICY awizacje_operator ON awizacje
    TO df_admin, df_kierownik, df_dyspozytor, df_ochrona, df_brygadzista
    USING (centrum_id IN (SELECT c.id FROM centra c WHERE c.organizacja_id = fn_org()));
CREATE POLICY awizacje_przewoznik ON awizacje FOR SELECT
    TO df_spedytor, df_kierowca
    USING (przewoznik_id = fn_org());

ALTER TABLE pojazdy ENABLE ROW LEVEL SECURITY;
CREATE POLICY pojazdy_operator ON pojazdy FOR SELECT
    TO df_admin, df_kierownik, df_dyspozytor, df_ochrona USING (true);
CREATE POLICY pojazdy_przewoznik ON pojazdy
    TO df_spedytor USING (przewoznik_id = fn_org()) WITH CHECK (przewoznik_id = fn_org());

ALTER TABLE kierowcy ENABLE ROW LEVEL SECURITY;
CREATE POLICY kierowcy_operator ON kierowcy FOR SELECT
    TO df_admin, df_kierownik, df_dyspozytor USING (true);
CREATE POLICY kierowcy_przewoznik ON kierowcy
    TO df_spedytor USING (przewoznik_id = fn_org()) WITH CHECK (przewoznik_id = fn_org());

ALTER TABLE kary ENABLE ROW LEVEL SECURITY;
CREATE POLICY kary_wg_awizacji ON kary USING (awizacja_id IN (SELECT id FROM awizacje));
ALTER TABLE pozycje_ladunku ENABLE ROW LEVEL SECURITY;
CREATE POLICY pozycje_wg_awizacji ON pozycje_ladunku USING (awizacja_id IN (SELECT id FROM awizacje));
ALTER TABLE zgloszenia_opoznien ENABLE ROW LEVEL SECURITY;
CREATE POLICY zgloszenia_wg_awizacji ON zgloszenia_opoznien USING (awizacja_id IN (SELECT id FROM awizacje));

ALTER VIEW v_wizyty SET (security_invoker = true);
ALTER VIEW v_kpi_dzienne SET (security_invoker = true);
ALTER VIEW v_raport_brygad SET (security_invoker = true);
