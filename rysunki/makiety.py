import pathlib
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle

OUT = pathlib.Path(__file__).resolve().parent
INK, MUTED, LINE, BG = '#1b2129', '#5a6571', '#c4cbd3', '#f4f5f7'
ACC, OK, BAD, WARN, INFO = '#e0a100', '#1d8048', '#c2392b', '#d98a00', '#2f6db3'


def ekran(tytul, menu, aktywne, h=1000):
    fig, ax = plt.subplots(figsize=(16, h / 100), dpi=130)
    ax.set_xlim(0, 1600); ax.set_ylim(h, 0); ax.axis('off')
    ax.add_patch(Rectangle((0, 0), 1600, h, fc=BG, ec=LINE, lw=2))
    ax.add_patch(Rectangle((0, 0), 1600, 64, fc=INK))
    ax.text(28, 32, 'DockFlow', color='white', fontsize=18, fontweight='bold', va='center')
    ax.text(250, 32, tytul, color='#c9d1da', fontsize=14, va='center')
    ax.text(1572, 32, 'CD Bielany  ·  user ▾', color='#c9d1da', fontsize=12, va='center', ha='right')
    if menu:
        ax.add_patch(Rectangle((0, 64), 240, h - 64, fc='white', ec=LINE))
        for i, m in enumerate(menu):
            y = 110 + i * 52
            if m == aktywne:
                ax.add_patch(Rectangle((0, y - 22), 240, 44, fc='#fdf3d8', ec='none'))
                ax.add_patch(Rectangle((0, y - 22), 5, 44, fc=ACC, ec='none'))
            ax.text(28, y, m, fontsize=13, va='center', color=INK, fontweight='bold' if m == aktywne else 'normal')
    return fig, ax


def karta(ax, x, y, w, h, fc='white', ec=LINE, lw=1.4, r=10):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle=f'round,pad=0,rounding_size={r}', fc=fc, ec=ec, lw=lw))


def przycisk(ax, x, y, w, h, t, fc=ACC, fg=INK, fs=13):
    karta(ax, x, y, w, h, fc=fc, ec=fc, r=8)
    ax.text(x + w / 2, y + h / 2, t, ha='center', va='center', fontsize=fs, fontweight='bold', color=fg)


def pole(ax, x, y, w, etykieta, wartosc):
    ax.text(x, y, etykieta, fontsize=11, color=MUTED)
    karta(ax, x, y + 12, w, 44, r=6)
    ax.text(x + 14, y + 34, wartosc, fontsize=13, va='center', color=INK)


def portal():
    fig, ax = ekran('Carrier portal', ['My bookings', 'Book a slot', 'Vehicles', 'Drivers', 'Delay report', 'Penalties'],
                    'Book a slot', h=820)
    ax.text(280, 110, 'Book a time slot', fontsize=22, fontweight='bold', color=INK)
    karta(ax, 280, 140, 560, 640)
    pole(ax, 310, 170, 500, 'Distribution centre', 'CD Bielany Wrocławskie')
    pole(ax, 310, 250, 240, 'Date', 'Tue, 06.10.2026')
    pole(ax, 570, 250, 240, 'Direction', 'Unloading ▾')
    pole(ax, 310, 330, 500, 'Vehicle / driver', 'DW 4KX21  ·  J. Kowalczyk ▾')
    ax.text(310, 412, 'Cargo', fontsize=14, fontweight='bold', color=INK)
    pole(ax, 310, 450, 240, 'Goods', 'Beverages ▾')
    pole(ax, 570, 450, 110, 'Pallet type', 'EUR ▾')
    pole(ax, 700, 450, 110, 'Pallets', '22')
    ax.text(310, 540, '+ Add another cargo line', fontsize=12, color=INFO)
    karta(ax, 310, 570, 500, 90, fc='#fdf3d8', ec='#f0d38a')
    ax.text(330, 598, 'Estimated handling time', fontsize=12, color=MUTED)
    ax.text(330, 632, '6 min docs + 22 × 2.7 min = 66 min  →  75 min slot', fontsize=12.5, color=INK, fontweight='bold')
    ax.text(310, 700, 'Slot length is calculated from measured handling times.', fontsize=11, color=MUTED)

    ax.text(880, 110, 'Available slots', fontsize=22, fontweight='bold', color=INK)
    karta(ax, 880, 140, 690, 640)
    ax.text(910, 175, 'Time', fontsize=12, color=MUTED); ax.text(1060, 175, 'Dock', fontsize=12, color=MUTED)
    ax.text(1180, 175, 'Length', fontsize=12, color=MUTED); ax.text(1320, 175, 'Hour load', fontsize=12, color=MUTED)
    sloty = [('07:15', 'R3', '75 min', 11, False), ('08:45', 'R6', '75 min', 12, True), ('09:30', 'R7', '75 min', 9, False),
             ('10:00', 'R2', '75 min', 8, False), ('11:15', 'R4', '75 min', 7, False), ('13:30', 'R1', '75 min', 6, False),
             ('15:00', 'R8', '75 min', 5, False)]
    for i, (t, r, l, load, full) in enumerate(sloty):
        y = 200 + i * 66
        sel = t == '09:30'
        karta(ax, 900, y, 650, 54, fc='#fdf3d8' if sel else 'white', ec=ACC if sel else LINE, lw=2 if sel else 1)
        ax.text(920, y + 27, t, fontsize=15, va='center', fontweight='bold', color=MUTED if full else INK)
        ax.text(1060, y + 27, r, fontsize=14, va='center', color=MUTED if full else INK)
        ax.text(1180, y + 27, l, fontsize=13, va='center', color=MUTED if full else INK)
        ax.add_patch(Rectangle((1320, y + 21), 120, 12, fc='#e6e9ed'))
        ax.add_patch(Rectangle((1320, y + 21), 120 * load / 12, 12, fc=BAD if full else (WARN if load > 9 else OK)))
        ax.text(1455, y + 27, 'full' if full else f'{load}/12', fontsize=12, va='center', color=BAD if full else MUTED)
    przycisk(ax, 1330, 690, 220, 60, 'Book 09:30 · R7')
    fig.savefig(OUT / 'makieta_portal.png', bbox_inches='tight', facecolor='white'); plt.close(fig)


def tablet():
    fig, ax = ekran('Dock tablet', None, None)
    ax.text(40, 115, 'Dock R5', fontsize=34, fontweight='bold', color=INK)
    ax.text(340, 118, 'Team C  ·  shift 1 (06:00–14:00)', fontsize=16, color=MUTED, va='center')
    karta(ax, 40, 160, 760, 360)
    ax.text(70, 205, 'Current truck', fontsize=14, color=MUTED)
    ax.text(70, 255, 'DW 4KX21', fontsize=32, fontweight='bold', color=INK)
    for i, (k, v) in enumerate([('Booking', 'WRO/2026/04512'), ('Carrier', 'TransKarp (PL)'), ('Cargo', 'Beverages · 22 EUR pallets'),
                                ('Planned', '08:00 – 09:22  (66 min + 30%)')]):
        ax.text(70, 315 + i * 48, k, fontsize=14, color=MUTED); ax.text(250, 315 + i * 48, v, fontsize=15, color=INK)
    karta(ax, 840, 160, 720, 360)
    ax.text(870, 205, 'Operation time', fontsize=14, color=MUTED)
    ax.text(1200, 320, '00:42:10', fontsize=64, fontweight='bold', color=INK, ha='center', va='center')
    ax.add_patch(Rectangle((880, 410), 640, 18, fc='#e6e9ed'))
    ax.add_patch(Rectangle((880, 410), 640 * 0.64, 18, fc=OK))
    ax.text(880, 455, '64% of planned time', fontsize=13, color=MUTED)
    przycisk(ax, 40, 560, 760, 150, 'START', fc='#d7e9dd', fg='#8aa595', fs=40)
    przycisk(ax, 840, 560, 720, 150, 'STOP', fc=BAD, fg='white', fs=40)
    karta(ax, 40, 750, 500, 200)
    ax.text(70, 790, 'Pallets handled', fontsize=14, color=MUTED)
    for i, t in enumerate(['−', '22', '+']):
        przycisk(ax, 70 + i * 150, 820, 130, 90, t, fc='#eef0f2' if t != '22' else 'white', fs=30)
    karta(ax, 580, 750, 480, 200)
    ax.text(610, 790, 'Damages', fontsize=14, color=MUTED)
    przycisk(ax, 610, 820, 200, 90, '0', fc='white', fs=30); przycisk(ax, 830, 820, 200, 90, 'Add photo', fc='#eef0f2', fs=16)
    karta(ax, 1100, 750, 460, 200)
    ax.text(1130, 790, 'Report downtime', fontsize=14, color=MUTED)
    for i, t in enumerate(['No free forklift', 'Waiting for documents', 'Forklift breakdown']):
        przycisk(ax, 1130, 812 + i * 44, 400, 38, t, fc='#fdf3d8' if i == 0 else '#eef0f2', fs=13)
    fig.savefig(OUT / 'makieta_tablet.png', bbox_inches='tight', facecolor='white'); plt.close(fig)


def dyspozytor():
    fig, ax = ekran('Dispatcher', ['Yard & docks', 'Gate', 'Waiting list', 'Bookings', 'Alerts'], 'Yard & docks', h=780)
    ax.text(280, 110, 'Yard & docks  ·  Tue 06.10.2026, 09:42', fontsize=22, fontweight='bold', color=INK)
    stany = [('R1', 'LOADING', 'DW 7PL22 · team A', 0.55, OK), ('R2', 'FREE', 'next 10:30', 0, MUTED),
             ('R3', 'LOADING', 'B-KX 4410 · Team A', 0.82, OK), ('R4', 'DOCKED', '5A2 1123 · prep 6 min', 0.05, INFO),
             ('R5', 'LOADING', 'DW 4KX21 · Team C', 0.64, OK), ('R6', 'OVERRUN', 'AA4521KC · Team C', 1.12, BAD),
             ('R7', 'FREE', 'next 09:55', 0, MUTED), ('R8', 'LOADING', 'LTU 482 · Team E', 0.31, OK),
             ('R9', 'DOCKED', 'B 22 XKT · docs 14 min', 0.1, WARN), ('R10 (cold)', 'LOADING', 'DW 1MR77 · Team E', 0.77, OK),
             ('R11 (cold)', 'FREE', 'next 10:15', 0, MUTED), ('R12 (cold)', 'LOADING', 'BC1290KA · Team B', 0.48, OK)]
    for i, (r, s, d, p, c) in enumerate(stany):
        x = 280 + (i % 4) * 240; y = 140 + (i // 4) * 200
        karta(ax, x, y, 220, 180, ec=c if s != 'FREE' else LINE, lw=2.4 if s == 'OVERRUN' else 1.4)
        ax.text(x + 18, y + 36, r, fontsize=18 if '(' in r else 20, fontweight='bold', color=INK)
        ax.text(x + 18, y + 70, s, fontsize=11, fontweight='bold', color=c)
        ax.text(x + 18, y + 98, d, fontsize=10, color=INK)
        if p:
            ax.add_patch(Rectangle((x + 18, y + 122), 184, 12, fc='#e6e9ed'))
            ax.add_patch(Rectangle((x + 18, y + 122), 184 * min(p, 1), 12, fc=c))
            ax.text(x + 18, y + 158, f'{int(p * 100)}% of plan', fontsize=11, color=MUTED)
    karta(ax, 1260, 140, 310, 330)
    ax.text(1285, 178, 'Waiting list', fontsize=16, fontweight='bold', color=INK)
    for i, (t, d) in enumerate([('AA1734CE (UA)', 'late 70 min · needs 183 min'), ('B-RT 9921 (DE)', 'early · own slot 10:30')]):
        karta(ax, 1280, 200 + i * 110, 270, 96, fc='#fdf3d8' if i == 0 else 'white')
        ax.text(1298, 236 + i * 110, t, fontsize=13, fontweight='bold', color=INK)
        ax.text(1298, 270 + i * 110, d, fontsize=10, color=MUTED)
    ax.text(1285, 445, 'auto-assigned when a gap appears', fontsize=10, color=MUTED)
    karta(ax, 1260, 490, 310, 250)
    ax.text(1285, 528, 'Alerts', fontsize=16, fontweight='bold', color=INK)
    for i, (t, c) in enumerate([('R6: over plan +12%', BAD), ('Gate: unknown WX 1234A', WARN),
                                ('No-show: WRO/2026/04533', MUTED)]):
        ax.add_patch(Rectangle((1280, 556 + i * 58), 6, 40, fc=c))
        ax.text(1298, 576 + i * 58, t, fontsize=11.5, color=INK, va='center')
    fig.savefig(OUT / 'makieta_dyspozytor.png', bbox_inches='tight', facecolor='white'); plt.close(fig)


def raport():
    fig, ax = ekran('Manager reports', ['Dashboard', 'Monthly report', 'Teams', 'Carriers', 'Time model', 'Export CSV'],
                    'Monthly report', h=800)
    ax.text(280, 110, 'Monthly report  ·  September 2026', fontsize=22, fontweight='bold', color=INK)
    for i, (k, v, s) in enumerate([('Avg. stay on site', '147 min', 'waiting 54 · handling 71'),
                                   ('No-show rate', '2.9%', '316 of 11 057 bookings'),
                                   ('Operations measured', '100%', '10 741 operations'),
                                   ('Teams over threshold', '1', 'coefficient > 1.20')]):
        x = 280 + i * 325
        karta(ax, x, 140, 305, 120)
        ax.text(x + 20, 168, k, fontsize=12, color=MUTED)
        ax.text(x + 20, 210, v, fontsize=24, fontweight='bold', color=BAD if i == 3 else INK)
        ax.text(x + 20, 245, s, fontsize=11, color=MUTED)
    karta(ax, 280, 285, 620, 470)
    ax.text(305, 320, 'Team efficiency coefficient', fontsize=16, fontweight='bold', color=INK)
    wsp = [('A', .92), ('B', 1.42), ('C', .97), ('D', 1.02), ('E', .99), ('F', .97)]
    base, top = 700, 380
    def yv(v): return base - (v / 1.6) * (base - top)
    for v in (0.5, 1.0, 1.5):
        ax.plot([340, 870], [yv(v), yv(v)], color='#e6e9ed', lw=1)
        ax.text(330, yv(v), f'{v:.1f}', fontsize=10, color=MUTED, ha='right', va='center')
    ax.plot([340, 870], [yv(1.2), yv(1.2)], color=BAD, lw=1.4, ls='--')
    ax.text(870, yv(1.2) - 10, 'threshold 1.20', fontsize=10, color=BAD, ha='right')
    for i, (b, v) in enumerate(wsp):
        x = 370 + i * 82
        ax.add_patch(Rectangle((x, yv(v)), 50, base - yv(v), fc=BAD if v > 1.2 else '#9fb0c2'))
        ax.text(x + 25, yv(v) - 10, f'{v:.2f}', ha='center', fontsize=11, fontweight='bold', color=INK)
        ax.text(x + 25, base + 22, b, ha='center', fontsize=13, color=INK)
    karta(ax, 930, 285, 640, 470, fc='#fff7f5', ec='#f0b8b0')
    ax.text(955, 320, 'Team B – why 42% slower?', fontsize=16, fontweight='bold', color=INK)
    wiersze = [('Preparation (dock → start)', '31 min', 'expected 8 min'), ('Handling per pallet', '4.26 min', 'avg 3.6 min'),
               ('Delays on afternoon shift', '80%', 'of all late operations'),
               ('Main downtime reason', 'No free forklift', '90% of reports')]
    for i, (k, v, s) in enumerate(wiersze):
        y = 370 + i * 78
        ax.text(955, y, k, fontsize=12, color=MUTED)
        ax.text(955, y + 32, v, fontsize=16, fontweight='bold', color=INK)
        ax.text(1290, y + 32, s, fontsize=12, color=MUTED)
    karta(ax, 955, 680, 590, 56, fc='white')
    ax.text(975, 708, 'Recommendation: one more forklift on afternoon shift', fontsize=12, color=INK, va='center')
    fig.savefig(OUT / 'makieta_raport.png', bbox_inches='tight', facecolor='white'); plt.close(fig)


if __name__ == '__main__':
    portal(); tablet(); dyspozytor(); raport()
    print('ok')
