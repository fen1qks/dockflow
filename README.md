# DockFlow

## Struktura

| Katalog | Zawartość |
|---|---|
| `db/01_schemat.sql` | tabele, klucze, ograniczenia (CHECK, UNIQUE, EXCLUDE) |
| `db/02_logika.sql` | funkcje, wyzwalacze, widoki, zadania pg_cron |
| `db/03_bezpieczenstwo.sql` | role, uprawnienia, Row-Level Security |
| `symulator/symulator.py` | generator danych z 3 miesięcy pracy centrum (etap 1) |
| `testy/test_baza.py` | testy bazy danych (16 scenariuszy) |
| `testy/raport_wynikow.py` | zestawienie wyników analizy (model czasu, brygady) |
| `rysunki/` | model konceptualny, ERD, diagram sekwencji, makiety interfejsu |

## Uruchomienie

Wymagania: Python 3.12, PostgreSQL 16+ (lokalnie używany pakiet `pgserver`).

```bash
pip install pgserver psycopg2-binary
python3 symulator/symulator.py
python3 testy/test_baza.py
python3 testy/raport_wynikow.py
```
