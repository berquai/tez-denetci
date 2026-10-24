"""Renk temaları (Metin Dinleyici ile aynı aile). Renkler stil sayfasıyla değil Qt paletiyle verilir."""
from PySide6.QtGui import QColor, QPalette

EDITABLE_ROLES = [
    ("base", "Metin arka planı"),
    ("text", "Yazı rengi"),
    ("win", "Pencere ve paneller"),
    ("btn", "Düğmeler"),
    ("hl", "Seçim ve vurgu"),
]

THEMES = {
    "Kâğıt": dict(win="#f3eee2", text="#302e29", base="#fffaf0", btn="#e7dfcf", hl="#b49a3a"),
    "Sepya": dict(win="#e9dcc3", text="#46351f", base="#f5ead3", btn="#dccaa8", hl="#9c6b30"),
    "Bulut": dict(win="#eceff2", text="#25303a", base="#ffffff", btn="#dde3e9", hl="#4f7cac"),
    "Gece": dict(win="#202124", text="#eee5d5", base="#292a2d", btn="#383a3e", hl="#8a7a3c"),
    "Gece Mavisi": dict(win="#1a2030", text="#e2e7f1", base="#212938", btn="#2e384b", hl="#5a7bbd"),
    "Orman": dict(win="#1c231f", text="#dfe6d8", base="#232b26", btn="#313b34", hl="#6c9a5b"),
    "Yüksek Kontrast": dict(win="#000000", text="#ffffff", base="#000000", btn="#1e1e1e", hl="#ffd400"),
}
CUSTOM = "Özel"
DEFAULT_THEME = "Kâğıt"


def mix(a, b, t):
    a, b = QColor(a), QColor(b)
    return QColor(round(a.red() + (b.red() - a.red()) * t),
                  round(a.green() + (b.green() - a.green()) * t),
                  round(a.blue() + (b.blue() - a.blue()) * t)).name()


def is_dark(color):
    return QColor(color).lightnessF() < 0.5


def palette_for(t):
    p = QPalette()
    hl_text = '#000000' if QColor(t['hl']).lightnessF() > 0.55 else '#ffffff'
    roles = {
        QPalette.Window: t['win'], QPalette.WindowText: t['text'], QPalette.Base: t['base'],
        QPalette.AlternateBase: mix(t['base'], t['win'], .5), QPalette.Text: t['text'], QPalette.Button: t['btn'],
        QPalette.ButtonText: t['text'], QPalette.Highlight: t['hl'], QPalette.HighlightedText: hl_text,
        QPalette.ToolTipBase: t['base'], QPalette.ToolTipText: t['text'], QPalette.BrightText: '#ff5555',
        QPalette.Link: mix(t['hl'], t['text'], .25), QPalette.PlaceholderText: mix(t['text'], t['base'], .5),
        QPalette.Light: mix(t['btn'], '#ffffff', .4), QPalette.Midlight: mix(t['btn'], '#ffffff', .2),
        QPalette.Mid: mix(t['btn'], t['text'], .3), QPalette.Dark: mix(t['btn'], '#000000', .35),
        QPalette.Shadow: '#000000',
    }
    for role, c in roles.items():
        p.setColor(QPalette.All, role, QColor(c))
    dis = mix(t['text'], t['base'], .48)
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        p.setColor(QPalette.Disabled, role, QColor(dis))
    return p


def colors_for(t):
    """Ayrıntı panelinin HTML renkleri: koyu temalarda vurgular koyulaştırılır."""
    dark = is_dark(t['base'])
    base, text = t['base'], t['text']
    if dark:
        return dict(text=text, mute=mix(text, base, .4), now=mix(base, text, .07), fix=mix(base, '#3f7a4f', .28),
                    h=mix(base, '#e05a4a', .45), u=mix(base, '#e0a23c', .42), o=mix(base, '#4f8fd0', .42),
                    ref=mix(t['hl'], text, .35), hata='#ff8a7a', uyari='#f2b45c', oneri='#8cbcea', bilgi=mix(text, base, .35),
                    dele=mix(base, '#e05a4a', .45), ins=mix(base, '#4f8fd0', .42), ok='#86c79a')
    return dict(text=text, mute=mix(text, base, .36), now=mix(base, text, .045), fix=mix(base, '#3f9a55', .13),
                h='#f9c9c3', u='#ffe0a3', o='#cfe2f3', ref=mix(t['hl'], '#000000', .25), hata='#b42318', uyari='#8a4b00',
                oneri='#2f5f8a', bilgi=mix(text, base, .35), dele='#f9c9c3', ins='#cfe2f3', ok='#2e6b3f')
