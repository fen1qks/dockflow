import pathlib
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle

OUT = pathlib.Path(__file__).resolve().parent
INK, MUTED, ACC, SOFT = '#1b2129', '#5a6571', '#f6d58a', '#eef0f2'
GRUPY = {'org': '#dce6f2', 'prz': '#e4efe0', 'proc': '#f6d58a', 'an': '#ece1f2'}


def strzalka(ax, pts, lab=None, lpos=None, fs=10):
    xs, ys = zip(*pts)
    ax.plot(xs, ys, color=INK, lw=1.4, zorder=1)
    if lab:
        ax.text(*lpos, lab, fontsize=fs, color=MUTED, ha='center', va='center', zorder=6,
                bbox=dict(fc='white', ec='none', pad=1))


def konceptualny():
    import math
    fig, ax = plt.subplots(figsize=(17.6, 10.4), dpi=150)
    ax.set_xlim(0, 1760); ax.set_ylim(1040, 0); ax.axis('off')
    X = {0: 160, 1: 520, 2: 880, 3: 1240, 4: 1600}
    E = {
        'Organizacja': (1, 90, 'org'), 'Pojazd': (2, 90, 'prz'), 'Kierowca': (3, 90, 'prz'),
        'Centrum': (1, 290, 'org'), 'Pozycja ładunku': (3, 290, 'proc'), 'Towar': (4, 290, 'org'),
        'Rampa': (1, 490, 'org'), 'Awizacja': (2, 490, 'proc'), 'Kara': (3, 490, 'proc'),
        'Model czasu': (4, 490, 'an'), 'Brygada': (0, 690, 'org'), 'Kamera': (1, 690, 'org'),
        'Operacja rampowa': (3, 690, 'proc'), 'Pracownik': (0, 890, 'org'),
        'Zdarzenie kamery': (2, 890, 'proc'), 'Przestój': (3, 890, 'proc'),
    }
    E = {k: (X[c], y, g) for k, (c, y, g) in E.items()}
    W, H = 240, 64

    def clip(x, y, dx, dy):
        t = min(W / 2 / abs(dx) if dx else 1e9, H / 2 / abs(dy) if dy else 1e9)
        return x + dx * t, y + dy * t

    def kard(x, y, ux, uy, k):
        px, py = -uy, ux
        ax.text(x + ux * 20 + px * 13, y + uy * 20 + py * 13, k, fontsize=10.5, fontweight='bold', color=INK,
                ha='center', va='center', zorder=6)

    rel = [('Organizacja', 'Centrum', 'prowadzi', '1', 'N'), ('Organizacja', 'Pojazd', 'posiada', '1', 'N'),
           ('Centrum', 'Rampa', 'ma', '1', 'N'), ('Centrum', 'Brygada', 'zatrudnia', '1', 'N'),
           ('Rampa', 'Kamera', 'monitoruje', '1', '0..1'), ('Rampa', 'Awizacja', 'przydzielona', '1', 'N'),
           ('Brygada', 'Pracownik', 'skład', 'N', 'M'), ('Brygada', 'Rampa', 'przydział', 'N', 'M'),
           ('Pojazd', 'Awizacja', 'wykonuje', '1', 'N'), ('Kierowca', 'Awizacja', 'prowadzi', '1', 'N'),
           ('Organizacja', 'Awizacja', 'rezerwuje', '1', 'N'), ('Awizacja', 'Pozycja ładunku', 'zawiera', '1', 'N'),
           ('Pozycja ładunku', 'Towar', 'dotyczy', 'N', '1'), ('Towar', 'Model czasu', 'ma', '1', 'N'),
           ('Awizacja', 'Kara', 'nalicza', '1', 'N'), ('Awizacja', 'Operacja rampowa', 'obsługa', '1', '0..1'),
           ('Operacja rampowa', 'Przestój', 'ma', '1', 'N'), ('Kamera', 'Zdarzenie kamery', 'rejestruje', '1', 'N'),
           ('Awizacja', 'Zdarzenie kamery', 'dotyczy', '1', 'N')]
    for a, b, lab, ka, kb in rel:
        (x1, y1, _), (x2, y2, _) = E[a], E[b]
        p1 = clip(x1, y1, x2 - x1, y2 - y1); p2 = clip(x2, y2, x1 - x2, y1 - y2)
        strzalka(ax, [p1, p2], lab, ((p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2))
        d = math.hypot(p2[0] - p1[0], p2[1] - p1[1]); ux, uy = (p2[0] - p1[0]) / d, (p2[1] - p1[1]) / d
        kard(*p1, ux, uy, ka); kard(*p2, -ux, -uy, kb)
    strzalka(ax, [(520, 58), (520, 28), (1240, 28), (1240, 58)], 'zatrudnia', (880, 28))
    ax.text(532, 46, '1', fontsize=10.5, fontweight='bold'); ax.text(1250, 46, 'N', fontsize=10.5, fontweight='bold')
    strzalka(ax, [(280, 700), (310, 700), (310, 965), (1390, 965), (1390, 700), (1360, 700)], 'wykonuje', (850, 965))
    ax.text(292, 688, '1', fontsize=10.5, fontweight='bold'); ax.text(1368, 688, 'N', fontsize=10.5, fontweight='bold')
    for n, (x, y, g) in E.items():
        ax.add_patch(FancyBboxPatch((x - W / 2, y - H / 2), W, H, boxstyle='round,pad=0,rounding_size=8',
                                    fc=GRUPY[g], ec=INK, lw=1.6, zorder=3))
        ax.text(x, y, n, ha='center', va='center', fontsize=12.5, fontweight='bold', color=INK, zorder=4)
    for i, (g, t) in enumerate([('org', 'organizacja i zasoby'), ('prz', 'przewoźnik'),
                                ('proc', 'proces obsługi'), ('an', 'wyniki analizy')]):
        ax.add_patch(Rectangle((40 + i * 280, 1005), 26, 18, fc=GRUPY[g], ec=INK))
        ax.text(74 + i * 280, 1014, t, va='center', fontsize=11, color=INK)
    fig.savefig(OUT / 'rys4_konceptualny.png', bbox_inches='tight', facecolor='white'); plt.close(fig)


def erd():
    T = {
        'centra': (40, 60, 'org', ['PK id', 'FK organizacja_id', 'nazwa', 'godz_otwarcia', 'godz_zamkniecia', 'zapas_procent']),
        'rampy': (40, 340, 'org', ['PK id', 'FK centrum_id', 'numer', 'chlodnia', 'aktywna']),
        'kamery': (40, 560, 'org', ['PK id', 'FK centrum_id', 'FK rampa_id', 'typ', 'klucz_api_hash']),
        'przydzial_brygad': (40, 780, 'org', ['PK FK rampa_id', 'PK data', 'PK zmiana', 'FK brygada_id']),
        'pracownicy': (40, 1100, 'org', ['PK id', 'FK centrum_id', 'imie', 'nazwisko']),
        'organizacje': (440, 60, 'org', ['PK id', 'nazwa', 'U nip', 'FK kraj_kod', 'typ']),
        'pojazdy': (440, 230, 'prz', ['PK id', 'FK przewoznik_id', 'U nr_rejestracyjny', 'chlodnia']),
        'kierowcy': (440, 380, 'prz', ['PK id', 'FK przewoznik_id', 'imie_nazwisko', 'telefon']),
        'zdarzenia_kamer': (440, 620, 'proc', ['PK id', 'FK kamera_id', 'FK awizacja_id', 'typ', 'nr_odczytany',
                                               'pewnosc', 'czas']),
        'brygady': (440, 900, 'org', ['PK id', 'FK centrum_id', 'nazwa']),
        'brygady_sklad': (440, 1080, 'org', ['PK FK brygada_id', 'PK FK pracownik_id', 'PK od', 'do']),
        'awizacje': (840, 230, 'proc', ['PK id', 'U numer', 'FK centrum_id', 'FK przewoznik_id', 'FK pojazd_id',
                                        'FK kierowca_id', 'FK rampa_id', 'kierunek', 'okno_od', 'okno_do',
                                        'czas_planowany_min', 'status']),
        'operacje_rampowe': (840, 650, 'proc', ['PK id', 'FK U awizacja_id', 'FK brygada_id', 'start', 'koniec',
                                                'palety_obsluzone', 'uszkodzenia', 'awaria']),
        'przestoje': (840, 940, 'proc', ['PK id', 'FK operacja_id', 'FK przyczyna_kod', 'od', 'do']),
        'pozycje_ladunku': (1240, 60, 'proc', ['PK id', 'FK awizacja_id', 'FK towar_id', 'FK typ_palety', 'liczba_palet']),
        'towary': (1240, 260, 'org', ['PK id', 'U nazwa', 'chlodniczy', 'domyslny_min_paleta']),
        'model_czasu': (1240, 430, 'an', ['PK FK towar_id', 'PK kierunek', 'PK FK typ_palety', 'min_na_palete',
                                          'liczba_pomiarow']),
        'kary': (1240, 630, 'proc', ['PK id', 'FK awizacja_id', 'typ', 'naliczono', 'status']),
    }
    W, HH, RH = 320, 30, 21
    fig, ax = plt.subplots(figsize=(16, 12.6), dpi=150)
    ax.set_xlim(0, 1600); ax.set_ylim(1260, 0); ax.axis('off')

    def h(t):
        return HH + RH * len(T[t][3]) + 6

    def kotw(t, strona, frac=0.5):
        x, y = T[t][0], T[t][1]
        return {'l': (x, y + h(t) * frac), 'r': (x + W, y + h(t) * frac),
                't': (x + W * frac, y), 'b': (x + W * frac, y + h(t))}[strona]

    lines = [
        [kotw('organizacje', 'l', .4), kotw('centra', 'r', .3)],
        [kotw('organizacje', 'b', .5), kotw('pojazdy', 't', .5)],
        [kotw('organizacje', 'l', .8), (425, kotw('organizacje', 'l', .8)[1]), (425, kotw('kierowcy', 'l', .5)[1]), kotw('kierowcy', 'l', .5)],
        [kotw('organizacje', 'r', .5), (800, kotw('organizacje', 'r', .5)[1]), (800, kotw('awizacje', 'l', .15)[1]), kotw('awizacje', 'l', .15)],
        [kotw('centra', 't', .5), (200, 30), (1000, 30), kotw('awizacje', 't', .5)],
        [kotw('centra', 'b', .5), kotw('rampy', 't', .5)],
        [kotw('rampy', 'b', .5), kotw('kamery', 't', .5)],
        [kotw('kamery', 'l', .3), (22, kotw('kamery', 'l', .3)[1]), (22, kotw('centra', 'l', .5)[1]), kotw('centra', 'l', .5)],
        [kotw('rampy', 'l', .6), (12, kotw('rampy', 'l', .6)[1]), (12, kotw('przydzial_brygad', 'l', .3)[1]), kotw('przydzial_brygad', 'l', .3)],
        [kotw('rampy', 'r', .5), (400, kotw('rampy', 'r', .5)[1]), (400, 560), (820, 560), (820, kotw('awizacje', 'l', .82)[1]), kotw('awizacje', 'l', .82)],
        [kotw('pojazdy', 'r', .5), (800, kotw('pojazdy', 'r', .5)[1]), (800, kotw('awizacje', 'l', .3)[1]), kotw('awizacje', 'l', .3)],
        [kotw('kierowcy', 'r', .5), (810, kotw('kierowcy', 'r', .5)[1]), (810, kotw('awizacje', 'l', .5)[1]), kotw('awizacje', 'l', .5)],
        [kotw('awizacje', 'r', .1), (1210, kotw('awizacje', 'r', .1)[1]), (1210, kotw('pozycje_ladunku', 'l', .5)[1]), kotw('pozycje_ladunku', 'l', .5)],
        [kotw('pozycje_ladunku', 'b', .5), kotw('towary', 't', .5)],
        [kotw('towary', 'b', .5), kotw('model_czasu', 't', .5)],
        [kotw('awizacje', 'r', .85), (1210, kotw('awizacje', 'r', .85)[1]), (1210, kotw('kary', 'l', .4)[1]), kotw('kary', 'l', .4)],
        [kotw('awizacje', 'b', .5), kotw('operacje_rampowe', 't', .5)],
        [kotw('awizacje', 'b', .15), (888, 600), (790, 600), (790, kotw('zdarzenia_kamer', 'r', .25)[1]), kotw('zdarzenia_kamer', 'r', .25)],
        [kotw('kamery', 'r', .5), (400, kotw('kamery', 'r', .5)[1]), (400, kotw('zdarzenia_kamer', 'l', .3)[1]), kotw('zdarzenia_kamer', 'l', .3)],
        [kotw('operacje_rampowe', 'b', .5), kotw('przestoje', 't', .5)],
        [kotw('operacje_rampowe', 'l', .6), (800, kotw('operacje_rampowe', 'l', .6)[1]), (800, kotw('brygady', 'r', .5)[1]), kotw('brygady', 'r', .5)],
        [kotw('przydzial_brygad', 'r', .7), (400, kotw('przydzial_brygad', 'r', .7)[1]), (400, kotw('brygady', 'l', .4)[1]), kotw('brygady', 'l', .4)],
        [kotw('brygady', 'b', .5), kotw('brygady_sklad', 't', .5)],
        [kotw('brygady_sklad', 'l', .5), kotw('pracownicy', 'r', .5)],
    ]
    for pts in lines:
        xs, ys = zip(*pts)
        ax.plot(xs, ys, color=INK, lw=1.2, zorder=1)
    for t, (x, y, g, cols) in T.items():
        ax.add_patch(Rectangle((x, y), W, h(t), fc='white', ec=INK, lw=1.4, zorder=3))
        ax.add_patch(Rectangle((x, y), W, HH, fc=GRUPY[g], ec=INK, lw=1.4, zorder=3))
        ax.text(x + 10, y + HH / 2, t, va='center', fontsize=12, fontweight='bold', color=INK, zorder=4,
                family='DejaVu Sans Mono')
        for i, c in enumerate(cols):
            parts = c.split(' ')
            klucz = ' '.join(p for p in parts if p in ('PK', 'FK', 'U'))
            nazwa = parts[-1]
            yy = y + HH + 4 + RH * i + RH / 2
            ax.text(x + 10, yy, klucz, va='center', fontsize=9, color=MUTED, fontweight='bold', zorder=4)
            ax.text(x + 78, yy, nazwa, va='center', fontsize=10.5, color=INK, zorder=4, family='DejaVu Sans Mono',
                    fontweight='bold' if 'PK' in klucz else 'normal')
    ax.text(1240, 900, 'Pozostałe tabele (słowniki, historia, analiza):', fontsize=10.5, fontweight='bold', color=INK)
    rest = ['kraje, typy_palet, przyczyny_przestojow,', 'limity_godzinowe, uzytkownicy,', 'historia_statusow, zgloszenia_opoznien,',
            'model_dokumenty, wspolczynniki_brygad,', 'dziennik_audytu']
    for i, r in enumerate(rest):
        ax.text(1240, 930 + i * 24, r, fontsize=10.5, color=INK, family='DejaVu Sans Mono')
    ax.text(1240, 1080, 'PK – klucz główny, FK – klucz obcy,\nU – wartość unikalna', fontsize=10, color=MUTED)
    fig.savefig(OUT / 'rys5_erd.png', bbox_inches='tight', facecolor='white'); plt.close(fig)


def sekwencja():
    fig, ax = plt.subplots(figsize=(16, 8.0), dpi=150)
    ax.set_xlim(0, 1600); ax.set_ylim(800, 0); ax.axis('off')
    U = [('Kamera bramowa', 120), ('Django REST API', 440), ('PostgreSQL\n(wyzwalacze, funkcje)', 800),
         ('Panel dyspozytora\n(React)', 1160), ('Kierowca\n(telefon)', 1480)]
    for n, x in U:
        ax.add_patch(FancyBboxPatch((x - 120, 20), 240, 64, boxstyle='round,pad=0,rounding_size=8',
                                    fc=ACC if 'PostgreSQL' in n else SOFT, ec=INK, lw=1.6))
        ax.text(x, 52, n, ha='center', va='center', fontsize=12, fontweight='bold', color=INK)
        ax.plot([x, x], [84, 790], color=MUTED, lw=1.2, ls='--', zorder=0)
    msgs = [(120, 440, 'POST /api/zdarzenia {wjazd, DW 4KX21, 08:00} + klucz API'),
            (440, 800, 'INSERT INTO zdarzenia_kamer'),
            (800, 800, 'trg_zdarzenie_przypisz: dopasowanie awizacji po numerze'),
            (800, 800, 'trg_zdarzenie_obsluz: status „na_bramie”'),
            (800, 800, 'fn_przydziel_rampe: T × współczynnik × 1,3; najmniejsza luka → R5'),
            (800, 800, 'trg_historia_statusow, trg_audyt'),
            (800, 440, 'wynik: awizacja WRO/2026/…, rampa R5, okno 08:00–09:22'),
            (440, 1480, 'powiadomienie: „Go to dock R5”'),
            (440, 1160, 'aktualizacja stanu placu i ramp'),
            (440, 120, '201 Created')]
    y = 130
    for a, b, t in msgs:
        if a == b:
            ax.add_patch(Rectangle((a - 8, y - 14), 16, 50, fc=ACC, ec=INK, lw=1, zorder=2))
            ax.annotate('', xy=(a + 8, y + 22), xytext=(a + 60, y + 22),
                        arrowprops=dict(arrowstyle='-|>', color=INK, lw=1.3, connectionstyle='arc3,rad=0'))
            ax.plot([a + 8, a + 60, a + 60], [y - 2, y - 2, y + 22], color=INK, lw=1.3)
            ax.text(a + 72, y + 10, t, va='center', fontsize=11, color=INK, bbox=dict(fc='white', ec='none', pad=1))
            y += 66
        else:
            ls = '--' if t.startswith(('wynik', '201')) else '-'
            ax.annotate('', xy=(b, y), xytext=(a, y),
                        arrowprops=dict(arrowstyle='-|>', color=INK, lw=1.4, ls=ls))
            ax.text((a + b) / 2, y - 12, t, ha='center', fontsize=11, color=INK,
                    bbox=dict(fc='white', ec='none', pad=1))
            y += 62
    fig.savefig(OUT / 'rys6_sekwencja.png', bbox_inches='tight', facecolor='white'); plt.close(fig)


if __name__ == '__main__':
    konceptualny(); erd(); sekwencja()
    print('ok')
