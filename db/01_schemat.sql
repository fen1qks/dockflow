DROP SCHEMA IF EXISTS dockflow CASCADE;
CREATE SCHEMA dockflow;
SET search_path = dockflow;

CREATE TABLE kraje (
    kod                 char(2) PRIMARY KEY,
    nazwa               varchar(60) NOT NULL,
    domyslny_czas_dok   smallint NOT NULL CHECK (domyslny_czas_dok BETWEEN 0 AND 120)
);

CREATE TABLE towary (
    id                  serial PRIMARY KEY,
    nazwa               varchar(60) NOT NULL UNIQUE,
    chlodniczy          boolean NOT NULL DEFAULT false,
    domyslny_min_paleta numeric(4,2) NOT NULL CHECK (domyslny_min_paleta > 0)
);

CREATE TABLE typy_palet (
    kod                 varchar(4) PRIMARY KEY,
    nazwa               varchar(40) NOT NULL
);

CREATE TABLE przyczyny_przestojow (
    kod                 varchar(20) PRIMARY KEY,
    nazwa               varchar(80) NOT NULL
);

CREATE TABLE organizacje (
    id                  serial PRIMARY KEY,
    nazwa               varchar(120) NOT NULL,
    nip                 varchar(20) NOT NULL UNIQUE,
    kraj_kod            char(2) NOT NULL REFERENCES kraje,
    typ                 varchar(12) NOT NULL CHECK (typ IN ('operator', 'przewoznik'))
);

CREATE TABLE centra (
    id                  serial PRIMARY KEY,
    organizacja_id      int NOT NULL REFERENCES organizacje,
    nazwa               varchar(120) NOT NULL,
    adres               varchar(200) NOT NULL,
    godz_otwarcia       time NOT NULL,
    godz_zamkniecia     time NOT NULL,
    zapas_procent       smallint NOT NULL DEFAULT 30 CHECK (zapas_procent BETWEEN 0 AND 100),
    CHECK (godz_zamkniecia > godz_otwarcia)
);

CREATE TABLE rampy (
    id                  serial PRIMARY KEY,
    centrum_id          int NOT NULL REFERENCES centra,
    numer               varchar(10) NOT NULL,
    chlodnia            boolean NOT NULL DEFAULT false,
    aktywna             boolean NOT NULL DEFAULT true,
    UNIQUE (centrum_id, numer)
);

CREATE TABLE limity_godzinowe (
    centrum_id          int NOT NULL REFERENCES centra,
    dzien_tygodnia      smallint NOT NULL CHECK (dzien_tygodnia BETWEEN 1 AND 7),
    godzina             smallint NOT NULL CHECK (godzina BETWEEN 0 AND 23),
    max_pojazdow        smallint NOT NULL CHECK (max_pojazdow > 0),
    PRIMARY KEY (centrum_id, dzien_tygodnia, godzina)
);

CREATE TABLE kamery (
    id                  serial PRIMARY KEY,
    centrum_id          int NOT NULL REFERENCES centra,
    rampa_id            int REFERENCES rampy,
    typ                 varchar(6) NOT NULL CHECK (typ IN ('brama', 'rampa')),
    klucz_api_hash      varchar(128) NOT NULL,
    aktywna             boolean NOT NULL DEFAULT true,
    CHECK ((typ = 'brama' AND rampa_id IS NULL) OR (typ = 'rampa' AND rampa_id IS NOT NULL))
);

CREATE TABLE uzytkownicy (
    id                  serial PRIMARY KEY,
    organizacja_id      int NOT NULL REFERENCES organizacje,
    keycloak_id         uuid NOT NULL UNIQUE,
    email               varchar(120) NOT NULL UNIQUE,
    rola                varchar(12) NOT NULL CHECK (rola IN
                        ('admin','kierownik','dyspozytor','ochrona','brygadzista','spedytor','kierowca')),
    aktywny             boolean NOT NULL DEFAULT true
);

CREATE TABLE brygady (
    id                  serial PRIMARY KEY,
    centrum_id          int NOT NULL REFERENCES centra,
    nazwa               varchar(20) NOT NULL,
    UNIQUE (centrum_id, nazwa)
);

CREATE TABLE pracownicy (
    id                  serial PRIMARY KEY,
    centrum_id          int NOT NULL REFERENCES centra,
    imie                varchar(40) NOT NULL,
    nazwisko            varchar(60) NOT NULL
);

CREATE TABLE brygady_sklad (
    brygada_id          int NOT NULL REFERENCES brygady,
    pracownik_id        int NOT NULL REFERENCES pracownicy,
    od                  date NOT NULL,
    "do"                date,
    PRIMARY KEY (brygada_id, pracownik_id, od),
    CHECK ("do" IS NULL OR "do" >= od)
);

CREATE TABLE przydzial_brygad (
    rampa_id            int NOT NULL REFERENCES rampy,
    data                date NOT NULL,
    zmiana              smallint NOT NULL CHECK (zmiana IN (1, 2)),
    brygada_id          int NOT NULL REFERENCES brygady,
    PRIMARY KEY (rampa_id, data, zmiana)
);

CREATE TABLE pojazdy (
    id                  serial PRIMARY KEY,
    przewoznik_id       int NOT NULL REFERENCES organizacje,
    nr_rejestracyjny    varchar(15) NOT NULL UNIQUE,
    chlodnia            boolean NOT NULL DEFAULT false
);

CREATE TABLE kierowcy (
    id                  serial PRIMARY KEY,
    przewoznik_id       int NOT NULL REFERENCES organizacje,
    imie_nazwisko       varchar(100) NOT NULL,
    telefon             varchar(20) NOT NULL
);

CREATE TABLE awizacje (
    id                  serial PRIMARY KEY,
    numer               varchar(20) NOT NULL UNIQUE,
    centrum_id          int NOT NULL REFERENCES centra,
    przewoznik_id       int NOT NULL REFERENCES organizacje,
    pojazd_id           int NOT NULL REFERENCES pojazdy,
    kierowca_id         int NOT NULL REFERENCES kierowcy,
    rampa_id            int NOT NULL REFERENCES rampy,
    kierunek            varchar(10) NOT NULL CHECK (kierunek IN ('zaladunek', 'rozladunek')),
    okno_od             timestamptz NOT NULL,
    okno_do             timestamptz NOT NULL,
    czas_planowany_min  smallint NOT NULL CHECK (czas_planowany_min > 0),
    status              varchar(20) NOT NULL DEFAULT 'zaplanowana' CHECK (status IN
                        ('zaplanowana','na_bramie','na_placu','lista_oczekujacych','przy_rampie',
                         'w_trakcie','zakonczona','wyjazd','no_show','odrzucona','anulowana')),
    utworzono           timestamptz NOT NULL DEFAULT now(),
    CHECK (okno_do > okno_od),

    CONSTRAINT ex_rampa_bez_kolizji EXCLUDE USING gist (
        int4range(rampa_id, rampa_id, '[]') WITH =,
        tstzrange(okno_od, okno_do) WITH &&
    ) WHERE (status NOT IN ('no_show', 'odrzucona', 'anulowana'))
);
CREATE INDEX ix_awizacje_dzien ON awizacje (centrum_id, okno_od);
CREATE INDEX ix_awizacje_pojazd ON awizacje (pojazd_id, okno_od);

CREATE TABLE pozycje_ladunku (
    id                  serial PRIMARY KEY,
    awizacja_id         int NOT NULL REFERENCES awizacje ON DELETE CASCADE,
    towar_id            int NOT NULL REFERENCES towary,
    typ_palety          varchar(4) NOT NULL REFERENCES typy_palet,
    liczba_palet        smallint NOT NULL CHECK (liczba_palet BETWEEN 1 AND 66)
);
CREATE INDEX ix_pozycje_awizacja ON pozycje_ladunku (awizacja_id);

CREATE TABLE historia_statusow (
    id                  bigserial PRIMARY KEY,
    awizacja_id         int NOT NULL REFERENCES awizacje ON DELETE CASCADE,
    status_z            varchar(20),
    status_na           varchar(20) NOT NULL,
    kiedy               timestamptz NOT NULL,
    uzytkownik          varchar(120),
    powod               varchar(200)
);
CREATE INDEX ix_historia_awizacja ON historia_statusow (awizacja_id);

CREATE TABLE zgloszenia_opoznien (
    id                  serial PRIMARY KEY,
    awizacja_id         int NOT NULL REFERENCES awizacje ON DELETE CASCADE,
    zgloszono           timestamptz NOT NULL,
    nowa_godzina        timestamptz NOT NULL,
    CHECK (nowa_godzina > zgloszono)
);

CREATE TABLE zdarzenia_kamer (
    id                  bigserial PRIMARY KEY,
    kamera_id           int NOT NULL REFERENCES kamery,
    typ                 varchar(12) NOT NULL CHECK (typ IN ('wjazd','wyjazd','podstawienie','odjazd')),
    nr_odczytany        varchar(15) NOT NULL,
    pewnosc             numeric(3,2) NOT NULL CHECK (pewnosc BETWEEN 0 AND 1),
    czas                timestamptz NOT NULL,
    awizacja_id         int REFERENCES awizacje,
    zdjecie_url         varchar(300),
    UNIQUE (kamera_id, typ, nr_odczytany, czas)
);
CREATE INDEX ix_zdarzenia_awizacja ON zdarzenia_kamer (awizacja_id, typ);

CREATE TABLE operacje_rampowe (
    id                  serial PRIMARY KEY,
    awizacja_id         int NOT NULL UNIQUE REFERENCES awizacje,
    brygada_id          int NOT NULL REFERENCES brygady,
    start               timestamptz NOT NULL,
    koniec              timestamptz,
    palety_obsluzone    smallint CHECK (palety_obsluzone BETWEEN 0 AND 66),
    uszkodzenia         smallint NOT NULL DEFAULT 0 CHECK (uszkodzenia >= 0),
    awaria              boolean NOT NULL DEFAULT false,
    CHECK (koniec IS NULL OR koniec > start)
);
CREATE INDEX ix_operacje_brygada ON operacje_rampowe (brygada_id, start);

CREATE TABLE przestoje (
    id                  serial PRIMARY KEY,
    operacja_id         int NOT NULL REFERENCES operacje_rampowe ON DELETE CASCADE,
    przyczyna_kod       varchar(20) NOT NULL REFERENCES przyczyny_przestojow,
    od                  timestamptz NOT NULL,
    "do"                timestamptz NOT NULL,
    CHECK ("do" > od)
);

CREATE TABLE kary (
    id                  serial PRIMARY KEY,
    awizacja_id         int NOT NULL REFERENCES awizacje,
    typ                 varchar(12) NOT NULL CHECK (typ IN ('no_show', 'spoznienie')),
    naliczono           timestamptz NOT NULL,
    status              varchar(10) NOT NULL DEFAULT 'naliczona'
                        CHECK (status IN ('naliczona', 'anulowana', 'oplacona')),
    UNIQUE (awizacja_id, typ)
);

CREATE TABLE model_czasu (
    towar_id            int NOT NULL REFERENCES towary,
    kierunek            varchar(10) NOT NULL CHECK (kierunek IN ('zaladunek', 'rozladunek')),
    typ_palety          varchar(4) NOT NULL REFERENCES typy_palet,
    min_na_palete       numeric(5,2) NOT NULL CHECK (min_na_palete > 0),
    liczba_pomiarow     int NOT NULL CHECK (liczba_pomiarow >= 0),
    przeliczono         timestamptz NOT NULL,
    PRIMARY KEY (towar_id, kierunek, typ_palety)
);

CREATE TABLE model_dokumenty (
    kraj_kod            char(2) PRIMARY KEY REFERENCES kraje,
    min_przygotowania   numeric(5,1) NOT NULL CHECK (min_przygotowania >= 0),
    liczba_pomiarow     int NOT NULL,
    przeliczono         timestamptz NOT NULL
);

CREATE TABLE wspolczynniki_brygad (
    brygada_id          int NOT NULL REFERENCES brygady,
    miesiac             date NOT NULL CHECK (extract(day FROM miesiac) = 1),
    wspolczynnik        numeric(4,2) NOT NULL CHECK (wspolczynnik > 0),
    liczba_operacji     int NOT NULL,
    PRIMARY KEY (brygada_id, miesiac)
);

CREATE TABLE dziennik_audytu (
    id                  bigserial PRIMARY KEY,
    tabela              varchar(40) NOT NULL,
    operacja            varchar(6) NOT NULL,
    uzytkownik          varchar(120),
    kiedy               timestamptz NOT NULL DEFAULT now(),
    stare_dane          jsonb,
    nowe_dane           jsonb
);
