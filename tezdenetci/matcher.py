"""Dipnot metnindeki atıfları Kaynak Kütüğü'ndeki kaynaklarla eşleştirir."""
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from rapidfuzz import fuzz
from .common import norm_map, norm


@dataclass
class Citation:
    source: object
    form: str          # 'tam' | 'kisa'
    start: int
    end: int
    exact: bool
    score: float
    loc: str = ''
    loc_start: int = -1
    loc_end: int = -1


LOC_AFTER = re.compile(r'\s*,?\s*((?:s\.|ss\.|Madde|Geçici Madde|Paragraf|Parag\.|par\.|md\.)\s*[\dIVXivx](?:[\d\s\-–,/ve]*[\dIVX])?)(?=\s*(?:[.;,]|$))')


class Matcher:
    def __init__(self, sources):
        self.sources = sources
        self.index = []
        for s in sources:
            for key, form in s.keys:
                if len(key) >= 6:
                    self.index.append((key, form, s))
        self.index.sort(key=lambda x: -len(x[0]))

    def match(self, text):
        nt, idx = norm_map(text)
        cands = []
        for key, form, s in self.index:
            k = nt.find(key)
            while k >= 0:
                e = k + len(key)
                if (k == 0 or nt[k - 1] == ' ') and (e == len(nt) or nt[e] == ' '):
                    cands.append((k, e, form, s, True, 100.0))
                k = nt.find(key, k + 1)
        chosen = self._select(cands)
        # bulanık eşleşme: kalan uzun bölgeler
        covered = [False] * len(nt)
        for k, e, *_ in chosen:
            for j in range(k, e):
                covered[j] = True
        regions = []
        j = 0
        while j < len(nt):
            if not covered[j]:
                a = j
                while j < len(nt) and not covered[j]:
                    j += 1
                if j - a >= 18:
                    regions.append((a, j))
            j += 1
        for a, b in regions:
            seg = nt[a:b]
            best = None
            for key, form, s in self.index:
                if len(key) < 15:
                    continue
                if abs(len(key) - len(seg)) > len(seg) + 40 and len(key) > len(seg):
                    pass
                r = fuzz.partial_ratio_alignment(key, seg, score_cutoff=86)
                if r is None:
                    continue
                cov = (r.dest_end - r.dest_start)
                sc = r.score + (3 if form == 'tam' else 0) + min(cov, 120) / 40
                if best is None or sc > best[0]:
                    best = (sc, r, form, s, key)
            if best:
                sc, r, form, s, key = best
                # anahtarın büyük kısmı bölgede bulunmalı
                if (r.dest_end - r.dest_start) >= 0.75 * len(key) or (r.src_end - r.src_start) >= 0.8 * len(key):
                    chosen.append((a + r.dest_start, a + r.dest_end, form, s, False, r.score))
        chosen.sort()
        cits = []
        for k, e, form, s, exact, score in chosen:
            k2 = k
            while k2 < len(nt) and nt[k2] == ' ':
                k2 += 1
            st = idx[k2]
            en = idx[e - 1] + 1
            # açık kalan tırnağı / parantezi kapat
            seg = text[st:en]
            if seg.count('“') > seg.count('”'):
                m = re.match(r'[,.]?”', text[en:])
                if m:
                    en += m.end()
            if seg.count('(') > seg.count(')') and text[en:en + 1] == ')':
                en += 1
            cits.append(Citation(s, form, st, en, exact, score))
        for i, c in enumerate(cits):
            nxt = cits[i + 1].start if i + 1 < len(cits) else len(text)
            m = LOC_AFTER.match(text, c.end, nxt)
            if m:
                c.loc = m.group(1).strip()
                c.loc_start, c.loc_end = m.start(1), m.end(1)
        return cits

    @staticmethod
    def _select(cands):
        cands.sort(key=lambda x: (-(x[1] - x[0]), 0 if x[2] == 'tam' else 1))
        chosen = []
        for c in cands:
            if all(c[1] <= d[0] or c[0] >= d[1] for d in chosen):
                chosen.append(c)
        return chosen


def align_alnum(a_text, b_text):
    """a ve b metinlerinin harf/rakam karakterlerini eşler: {a_index: b_index}."""
    na, ia = norm_map(a_text)
    nb, ib = norm_map(b_text)
    mapping = {}
    if na == nb:
        for x, y in zip(ia, ib):
            mapping[x] = y
        return mapping
    sm = SequenceMatcher(None, na, nb, autojunk=False)
    for blk in sm.get_matching_blocks():
        for t in range(blk.size):
            ca, cb = blk.a + t, blk.b + t
            if na[ca] != ' ':
                mapping[ia[ca]] = ib[cb]
    return mapping
