"""Çalışma durumu: incelendi işaretleri, son kayıt, PDF kaymaları, tema.
Tezin yanında '<tez adı>.tezdenetci.json' olarak tutulur; bulut klasöründeyse bilgisayarlar arasında kendiliğinden eşitlenir.
Kimlikler dipnot NUMARASINA değil METNİNE bağlıdır; araya dipnot girse de işaretler yerinde kalır."""
import hashlib
import json
import os
import re
import socket
import time
from ..common import norm

VERSION = 1


def _h(text):
    return hashlib.sha1(norm(text or '')[:400].encode('utf-8')).hexdigest()[:16]


def item_key(A, it):
    if it.kind == 'dipnot':
        return 'dn:' + _h(A.doc.footnotes[it.ref - 1].rt.text)
    if it.kind == 'govde':
        return 'p:' + _h(A.doc.body[it.ref].rt.text)
    if it.kind == 'kaynakca':
        return 'k:' + _h(it.ref.source.kay.text)
    if it.kind == 'eski':
        return 'e:' + _h(it.ref.rt.text)
    return it.kind + ':' + _h(it.title + '|' + (it.findings[0].msg if it.findings else ''))


def finding_key(ikey, f):
    # mesajdaki sayılar (ör. 'ilk kez 12. dipnotta') araya dipnot girince değişir; kimliğe katılmaz
    return ikey + '|' + _h(f.cat + '|' + re.sub(r'\d+', '#', f.msg))


def legacy_finding_key(ikey, f):
    """1.3 ve öncesinin kimliği (sayılar dahil); eski işaretleri taşımak için."""
    return ikey + '|' + _h(f.cat + '|' + f.msg)


def state_path_for(docx):
    if not docx:
        return None
    base = os.path.splitext(docx)[0]
    return base + '.tezdenetci.json'


class WorkState:
    def __init__(self):
        self.reviewed = {}      # finding_key -> zaman damgası
        self.removed = {}       # geri alınan işaretler -> zaman damgası (eşitlemede silinme de taşınsın)
        self.offsets = {}       # pdf adı -> kayma
        self.last = None        # item_key
        self.theme = None
        self.custom_theme = None
        self.updated = 0
        self.machine = socket.gethostname()

    # ---------------------------------------------------------------- birleştirme
    def merge(self, d):
        """Başka bir bilgisayardan gelen durumu birleştirir: işaretler birleşim, kaymalar ve son kayıt daha yeni olandan."""
        if not d:
            return
        for k, t in (d.get('reviewed') or {}).items():
            if self.removed.get(k, 0) >= t:
                continue          # bu işaret daha sonra geri alınmış
            if k not in self.reviewed or t > self.reviewed[k]:
                self.reviewed[k] = t
        newer = d.get('updated', 0) >= self.updated
        for k, v in (d.get('offsets') or {}).items():
            if newer or k not in self.offsets:
                self.offsets[k] = v
        if newer:
            self.last = d.get('last') or self.last
            self.theme = d.get('theme') or self.theme
            self.custom_theme = d.get('custom_theme') or self.custom_theme
            self.updated = max(self.updated, d.get('updated', 0))
        # açıkça geri alınan işaretler
        for k, t in (d.get('removed') or {}).items():
            if k in self.reviewed and self.reviewed[k] <= t:
                del self.reviewed[k]
                self.removed[k] = t
            elif k not in self.reviewed:
                self.removed[k] = max(t, self.removed.get(k, 0))

    def to_dict(self):
        return {'program': 'Tez Denetçi', 'version': VERSION, 'updated': self.updated, 'machine': self.machine,
                'reviewed': self.reviewed, 'removed': self.removed or {}, 'offsets': self.offsets,
                'last': self.last, 'theme': self.theme, 'custom_theme': self.custom_theme}

    # ---------------------------------------------------------------- işaretler
    def mark(self, keys, on=True):
        now = time.time()
        for k in keys:
            if on:
                self.reviewed[k] = now
                self.removed.pop(k, None)
            else:
                self.reviewed.pop(k, None)
                self.removed[k] = now
        self.updated = now

    def migrate(self, pairs):
        """Eski kimlikle işaretlenmiş kayıtları yeni kimliğe taşır. pairs: [(eski, yeni)]"""
        moved = False
        for old, new in pairs:
            if old != new and old in self.reviewed and new not in self.reviewed and new not in self.removed:
                self.reviewed[new] = self.reviewed[old]
                moved = True
        return moved

    def touch(self):
        self.updated = time.time()

    # ---------------------------------------------------------------- dosya
    @staticmethod
    def read(path):
        try:
            with open(path, encoding='utf-8') as fh:
                d = json.load(fh)
            return d if d.get('program') == 'Tez Denetçi' else None
        except (OSError, ValueError):
            return None

    def load(self, path):
        d = self.read(path)
        self.merge(d)
        return d is not None

    def save(self, path):
        """Diskteki (başka bilgisayarda değişmiş olabilecek) sürümle birleştirip atomik yazar."""
        if not path:
            return False
        disk = self.read(path)
        if disk:
            mine = self.to_dict()
            self.merge(disk)
            # kendi son kaydımız ve kaymalarımız korunur
            self.last = mine['last'] or self.last
            self.offsets.update(mine['offsets'])
            self.updated = max(self.updated, mine['updated'])
        tmp = path + '.tmp'
        try:
            with open(tmp, 'w', encoding='utf-8') as fh:
                json.dump(self.to_dict(), fh, ensure_ascii=False, indent=1)
            os.replace(tmp, path)
            return True
        except OSError:
            try:
                os.remove(tmp)
            except OSError:
                pass
            return False
