"""Ortak yardımcılar: zengin metin (italik bilgili), Türkçe duyarlı normalleştirme, sıralama."""
import re
import unicodedata
from dataclasses import dataclass, field

FOLD = str.maketrans({'â': 'a', 'î': 'i', 'û': 'u', 'Â': 'a', 'Î': 'i', 'Û': 'u',
                      'İ': 'i', 'I': 'i', 'ı': 'i', 'é': 'e', 'è': 'e', 'ê': 'e', 'á': 'a',
                      'à': 'a', 'ó': 'o', 'ò': 'o', 'ô': 'o', 'ú': 'u', 'ñ': 'n', 'ë': 'e', 'ï': 'i'})
QUOTES_OPEN = '“‘"«'
QUOTES_CLOSE = '”’"»'
QUOTE_CHARS = set('“”‘’"«»\'')
PARENS = set('()[]')
EDGE_PUNCT = set(',.;:!?…')


def nfc(s):
    return unicodedata.normalize('NFC', s or '')


def tr_lower(s):
    return s.replace('İ', 'i').replace('I', 'ı').lower()


def tr_upper_char(c):
    return {'i': 'İ', 'ı': 'I'}.get(c, c.upper())


def norm_map(s):
    """Harf/rakam dışını tek boşluğa indirir, büyük-küçük ve i/ı farkını yok sayar.
    Dönüş: (normalleşmiş metin, her normal karakterin özgün indeksi)."""
    out, idx = [], []
    for i, c in enumerate(s):
        c2 = c.translate(FOLD).lower()
        if len(c2) == 1 and c2.isalnum():
            out.append(c2)
            idx.append(i)
        elif out and out[-1] != ' ':
            out.append(' ')
            idx.append(i)
    while out and out[-1] == ' ':
        out.pop(); idx.pop()
    return ''.join(out), idx


def norm(s):
    return norm_map(s)[0]


@dataclass
class RText:
    """Karakter düzeyinde italik bilgisi taşıyan metin."""
    text: str = ''
    ital: list = field(default_factory=list)

    @classmethod
    def from_runs(cls, runs):
        t, it = [], []
        for s, i in runs:
            s = nfc(s)
            t.append(s)
            it.extend([bool(i)] * len(s))
        return cls(''.join(t), it)

    @classmethod
    def plain(cls, s):
        s = nfc(s)
        return cls(s, [False] * len(s))

    def __len__(self):
        return len(self.text)

    def copy(self):
        return RText(self.text, list(self.ital))

    def slice(self, a, b):
        return RText(self.text[a:b], self.ital[a:b])

    def __add__(self, o):
        return RText(self.text + o.text, self.ital + o.ital)

    def replace(self, a, b, new):
        return RText(self.text[:a] + new.text + self.text[b:], self.ital[:a] + new.ital + self.ital[b:])

    def strip(self):
        a, b = 0, len(self.text)
        while a < b and self.text[a].isspace():
            a += 1
        while b > a and self.text[b - 1].isspace():
            b -= 1
        return self.slice(a, b)

    def segments(self):
        """[(metin, italik)] ardışık parçalar."""
        segs = []
        for c, i in zip(self.text, self.ital):
            if segs and segs[-1][1] == i:
                segs[-1][0] += c
            else:
                segs.append([c, i])
        return [(s, i) for s, i in segs]

    def to_html(self, marks=None):
        """marks: [(a,b,css_class)] vurgulanacak aralıklar."""
        import html
        marks = marks or []
        cls_at = [None] * len(self.text)
        for a, b, c in marks:
            for k in range(max(0, a), min(b, len(self.text))):
                cls_at[k] = c
        out, cur = [], None
        for k, ch in enumerate(self.text):
            key = (self.ital[k], cls_at[k])
            if key != cur:
                if cur is not None:
                    if cur[0]:
                        out.append('</i>')
                    if cur[1]:
                        out.append('</mark>')
                if key[1]:
                    out.append(f'<mark class="{key[1]}">')
                if key[0]:
                    out.append('<i>')
                cur = key
            out.append(html.escape(ch))
        if cur is not None:
            if cur[0]:
                out.append('</i>')
            if cur[1]:
                out.append('</mark>')
        return ''.join(out)

    def to_marked(self):
        return ''.join(f'*{s}*' if i else s for s, i in self.segments())


TR_ALPHA = 'abcçdefgğhıijklmnoöpqrsştuüvwxyz'
TR_ORDER = {c: i for i, c in enumerate(TR_ALPHA)}


def tr_sort_key(s):
    s = nfc(s)
    s = s.replace('â', 'a').replace('î', 'i').replace('û', 'u').replace('Â', 'A').replace('Î', 'İ')
    key = []
    for c in tr_lower(s):
        if c in TR_ORDER:
            key.append(100 + TR_ORDER[c])
        elif c.isdigit():
            key.append(10 + int(c))
        elif c.isspace():
            key.append(1)
        elif c.isalpha():
            c2 = unicodedata.normalize('NFD', c)[0]
            key.append(100 + TR_ORDER.get(c2, 60))
    return key


PAGE_RE = re.compile(r'(\d+)\s*[-–]\s*(\d+)|(\d+)')


def parse_pages(loc):
    """'s. 61, 69' / 's. 293-295' -> [(61,61),(69,69)] / [(293,295)]"""
    res = []
    for m in PAGE_RE.finditer(loc or ''):
        if m.group(1):
            res.append((int(m.group(1)), int(m.group(2))))
        else:
            res.append((int(m.group(3)), int(m.group(3))))
    return res


_URL = re.compile(r'(https?://\S+|www\.\S+|\b10\.\d{4,9}/\S+|DOI:\s*\S+)', re.I)


def curly(rt):
    """Dışarı çıkan her metin için son güvenlik: düz/ters tırnak ve kesmeleri eğri biçime çevirir.
    Web adresleri ve DOI'lere dokunmaz. RText ya da str alır, aynı türde döndürür."""
    is_str = isinstance(rt, str)
    t = list(rt if is_str else rt.text)
    skip = set()
    for m in _URL.finditer(''.join(t)):
        skip.update(range(m.start(), m.end()))
    for k, c in enumerate(t):
        if k in skip:
            continue
        prev = t[k - 1] if k > 0 else ' '
        nxt = t[k + 1] if k + 1 < len(t) else ' '
        if c in "'´`′":
            if prev.isalnum() or nxt.isalnum() or c == "'":
                # kelime başında açılış tek tırnağı, aksi hâlde kesme / kapanış
                t[k] = '‘' if (c == "'" and (prev.isspace() or prev in '([{“—–') and nxt.isalnum()) else '’'
        elif c == '"':
            t[k] = '“' if (prev.isspace() or prev in '([{—–-/') or k == 0 else '”'
        elif c == '‘' and prev.isalpha() and nxt.isalpha():
            t[k] = '’'
        elif c == '“' and prev.isalnum() and (nxt.isspace() or nxt in ',.;:)'):
            t[k] = '”'
        elif c == '”' and prev.isspace() and nxt.isalnum():
            t[k] = '“'
    s = ''.join(t)
    return s if is_str else RText(s, rt.ital)
