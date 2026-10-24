"""Açık Word belgesinde ilgili dipnota ya da metne gider (yalnızca Windows, pywin32 ile)."""
import os
import re
import sys

WD_ACTIVE_END_PAGE = 3          # wdActiveEndPageNumber
WD_ACTIVE_END_ADJ_PAGE = 1      # wdActiveEndAdjustedPageNumber (sayfa numaralandırması dikkate alınır)


class WordLinkError(Exception):
    pass


def available():
    if sys.platform != 'win32':
        return False, 'Word bağlantısı yalnızca Windows’ta çalışır.'
    try:
        import win32com.client  # noqa: F401
        return True, ''
    except ImportError:
        return False, 'pywin32 kurulu değil. kurulum.bat dosyasını yeniden çalıştırın.'


def _norm(s):
    return re.sub(r'\s+', ' ', (s or '').replace('\r', ' ').replace('\x02', '')).strip()


def _word_and_doc(path):
    import win32com.client
    try:
        word = win32com.client.GetActiveObject('Word.Application')
    except Exception:
        word = win32com.client.Dispatch('Word.Application')
    target = os.path.normcase(os.path.abspath(path))
    doc = None
    for i in range(1, word.Documents.Count + 1):
        d = word.Documents(i)
        try:
            if os.path.normcase(os.path.abspath(d.FullName)) == target:
                doc = d
                break
        except Exception:
            continue
    if doc is None:
        doc = word.Documents.Open(os.path.abspath(path))
    word.Visible = True
    return word, doc


def _show(word, doc, rng):
    doc.Activate()
    rng.Select()
    try:
        word.ActiveWindow.ScrollIntoView(word.Selection.Range, True)
    except Exception:
        pass
    try:
        word.Activate()
    except Exception:
        pass
    try:
        import win32gui
        import win32con
        hwnd = word.ActiveWindow.Hwnd
        win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
        win32gui.SetForegroundWindow(hwnd)
    except Exception:
        pass
    try:
        adj = word.Selection.Information(WD_ACTIVE_END_ADJ_PAGE)
        phys = word.Selection.Information(WD_ACTIVE_END_PAGE)
        return adj, phys
    except Exception:
        return None, None


def goto_footnote(path, num, text_hint='', target='ref'):
    """num. dipnota gider. target='ref' metindeki numarayı, 'text' dipnot metnini seçer.
    Word'deki sıra kaymışsa dipnot metnine bakarak doğru olanı bulur. (sayfa, fiziksel sayfa, not) döndürür."""
    ok, msg = available()
    if not ok:
        raise WordLinkError(msg)
    word, doc = _word_and_doc(path)
    fns = doc.Footnotes
    n = fns.Count
    hint = _norm(text_hint)[:60]
    chosen = None
    note = ''
    if 1 <= num <= n:
        f = fns(num)
        if not hint or _norm(f.Range.Text)[:60] == hint:
            chosen = f
    if chosen is None and hint:
        for i in range(1, n + 1):
            f = fns(i)
            if _norm(f.Range.Text)[:60] == hint:
                chosen = f
                note = f'Word’de bu dipnot {i}. sırada (tarama sonrası belge değişmiş; yeniden taramak iyi olur).'
                break
    if chosen is None:
        if 1 <= num <= n:
            chosen = fns(num)
            note = 'Dipnot metni taramadakinden farklı; belge değişmiş olabilir.'
        else:
            raise WordLinkError(f'Word belgesinde {num}. dipnot yok (toplam {n}). Belge değişmiş olabilir; yeniden tarayın.')
    rng = chosen.Reference if target == 'ref' else chosen.Range
    adj, phys = _show(word, doc, rng)
    return adj, phys, note


def goto_text(path, snippet):
    """Gövde metninde verilen parçayı bulup seçer."""
    ok, msg = available()
    if not ok:
        raise WordLinkError(msg)
    word, doc = _word_and_doc(path)
    snip = _norm(snippet)
    # Word Find en çok 255 karakter alır; özel karakterleri kaçır
    snip = snip[:120].replace('^', '^^')
    for cand in (snip, snip[:60], snip[:35]):
        if not cand.strip():
            continue
        rng = doc.Content
        fnd = rng.Find
        fnd.ClearFormatting()
        # konumsal: FindText, MatchCase, MatchWholeWord, MatchWildcards, MatchSoundsLike, MatchAllWordForms, Forward, Wrap
        if fnd.Execute(cand, True, False, False, False, False, True, 0):
            adj, phys = _show(word, doc, rng)
            return adj, phys, ''
    raise WordLinkError('Metin Word belgesinde bulunamadı; belge taramadan sonra değişmiş olabilir.')
