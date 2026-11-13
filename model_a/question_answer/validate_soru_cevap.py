"""
validate_soru_cevap.py — soru-cevap belgesi doğrulayıcı (şema v0.1)

Bölücünün (bolucu.py) ürettiği soru-cevap belgesini plan/soru-cevap-sema-v0.1.md
kurallarına göre denetler. Netleştirme kontrolü 31.10.2026'da eklendi.

DİKKAT: Bu, şemadaki kontrol listesinden yeniden yazılmış bir referans uygulamadır.
Önceden çalışan bir validate_soru_cevap.py'niz varsa ÜSTÜNE YAZMADAN önce karşılaştırın.

Kullanım:
    python validate_soru_cevap.py soru_cevap.json \
        [--eksiksiz bbf.json] [--eksiltilmis bbf_eksiltilmis.json] \
        [--liste bbf_kontrol_listesi.json]

Çıkış kodu: hata varsa 1, yoksa 0. Uyarılar çıkışı etkilemez.
"""
from __future__ import annotations
import argparse, json, re, sys

SAYI = re.compile(r"\d+(?:[.,]\d+)?")
REF_NO = re.compile(r"\(\s*\d+[a-z]?\s*\)")          # patent referans numarası: (10), (12a)
ISTEM_DILI = re.compile(r"karakterize|istem\s*\d|istemine göre", re.IGNORECASE)
MADDE_ID = re.compile(r"\b[A-Z]\d{2}\b")


class Rapor:
    def __init__(self):
        self.hatalar: list[str] = []
        self.uyarilar: list[str] = []

    def hata(self, kayit_id, mesaj):
        self.hatalar.append(f"[kayıt {kayit_id}] {mesaj}")

    def uyari(self, kayit_id, mesaj):
        self.uyarilar.append(f"[kayıt {kayit_id}] {mesaj}")

    def yazdir(self):
        for u in self.uyarilar:
            print("UYARI:", u)
        for h in self.hatalar:
            print("HATA :", h)
        if not self.hatalar and not self.uyarilar:
            print("Tüm kontroller geçti.")
        elif not self.hatalar:
            print(f"\n{len(self.uyarilar)} uyarı, hata yok.")
        else:
            print(f"\n{len(self.hatalar)} hata, {len(self.uyarilar)} uyarı.")
        return 1 if self.hatalar else 0


# --- yardımcılar --------------------------------------------------------------
def sayilar(metin) -> set[str]:
    return set(SAYI.findall(str(metin or "")))

def bbf_coz(bbf: dict, yol: str):
    """'unsurlar[2].kosul' veya 'uygulama_alanlari' -> değer. Yoksa None."""
    m = re.match(r"unsurlar\[(\d+)\]\.kosul", yol)
    if m:
        unsurlar = (bbf.get("unsurlar") or {}).get("deger") or []
        i = int(m.group(1))
        return unsurlar[i].get("kosul") if i < len(unsurlar) else None
    sarmal = bbf.get(yol)
    return sarmal.get("deger") if isinstance(sarmal, dict) else None

def tip_cikar(metin: str) -> str:
    m = (metin or "").lower()
    if "%" in m or "oran" in m or "ağırlıkça" in m or "hacimce" in m:
        return "oran"
    if re.search(r"\d\s*(?:-|–|ila)\s*\d", m):
        return "aralik"
    return "tek"

# Netleştirme yer tutucu dili -> beklenen tip (bolucu.py _NET ile uyumlu)
YER_TUTUCU_TIP = {
    "oran": ["oran"], "aralık": ["aralik"], "aralik": ["aralik"],
    "değer": ["tek"], "deger": ["tek"], "sıcaklık": ["tek"], "sicaklik": ["tek"],
}


# --- ana doğrulama ------------------------------------------------------------
def dogrula(sc: dict, eksiksiz=None, eksiltilmis=None, liste_idler=None) -> Rapor:
    r = Rapor()
    kayitlar = sc.get("kayitlar")
    sentetik = sc.get("kaynak") == "sentetik"

    if not isinstance(kayitlar, list) or not kayitlar:
        r.hata("-", "kayitlar listesi boş veya yok.")
        return r

    # id 1..n sıralı
    for beklenen, k in enumerate(kayitlar, 1):
        if k.get("id") != beklenen:
            r.hata(k.get("id", "?"), f"id sıralı değil (beklenen {beklenen}).")

    # en fazla 1 bilinmiyor
    bilinmiyorlar = [k for k in kayitlar if k.get("islem") == "bilinmiyor"]
    if len(bilinmiyorlar) > 1:
        r.hata("-", f"{len(bilinmiyorlar)} adet 'bilinmiyor' var (en fazla 1).")

    eksiltilmis_metin = json.dumps(eksiltilmis, ensure_ascii=False) if eksiltilmis else ""

    for k in kayitlar:
        kid = k.get("id", "?")
        soru, cevap = k.get("soru", ""), k.get("cevap", "")
        islem = k.get("islem")

        # zorunlu alanlar
        if not soru or not cevap:
            r.hata(kid, "soru veya cevap boş.")
        if sentetik and islem not in ("tasima", "netlestirme", "bilinmiyor"):
            r.hata(kid, f"geçersiz islem: {islem}")

        # istem dili / referans numarası yok
        for ad, metin in (("soru", soru), ("cevap", cevap)):
            if REF_NO.search(metin):
                r.hata(kid, f"{ad} referans numarası içeriyor (ör. (10)).")
            if ISTEM_DILI.search(metin):
                r.hata(kid, f"{ad} istem dili içeriyor (karakterize / isteme göre).")

        # soru cevabı ele vermiyor (ortak sayı)
        ortak = sayilar(soru) & sayilar(cevap)
        for s in ortak:
            if len(s.replace(",", "").replace(".", "")) >= 2:
                r.hata(kid, f"soru cevabı ele veriyor: ortak sayı '{s}'.")
            else:
                r.uyari(kid, f"soru ve cevapta ortak tek haneli sayı '{s}' (yanlış alarm olabilir).")

        # madde_id listede
        if sentetik and liste_idler is not None:
            mid = k.get("madde_id")
            if mid and mid not in liste_idler:
                r.hata(kid, f"madde_id '{mid}' kontrol listesinde yok.")

        if islem in ("tasima", "netlestirme"):
            deger = k.get("tasinan_deger")
            if not deger:
                r.hata(kid, "tasinan_deger yok.")
                continue
            # taşınan sayılar cevapta
            eksik = sayilar(deger) - sayilar(cevap)
            if eksik:
                r.hata(kid, f"taşınan sayı(lar) cevapta yok: {sorted(eksik)}")

            # eksiksiz BBF ile çapraz kontrol
            if eksiksiz:
                gercek = bbf_coz(eksiksiz, k.get("bbf_alani", ""))
                if gercek is not None and sayilar(deger) - sayilar(gercek):
                    r.hata(kid, "tasinan_deger eksiksiz BBF'deki değerle uyuşmuyor.")

            # eksiltilmiş BBF ile çapraz kontrol
            if eksiltilmis:
                kalan = bbf_coz(eksiltilmis, k.get("bbf_alani", ""))
                if islem == "tasima":
                    if kalan not in (None, "", []):
                        r.hata(kid, "taşınan alan eksiltilmiş BBF'de hâlâ dolu.")
                    # tekrar temizliği: taşınan sayı BBF'nin başka yerinde kalmamalı
                    for s in sayilar(deger):
                        if len(s) >= 2 and s in sayilar(eksiltilmis_metin):
                            r.uyari(kid, f"taşınan sayı '{s}' eksiltilmiş BBF'nin başka yerinde geçiyor.")
                elif islem == "netlestirme":
                    yt = k.get("bbf_yer_tutucu")
                    if not yt:
                        r.hata(kid, "netleştirmede bbf_yer_tutucu yok.")
                    elif kalan != yt:
                        r.hata(kid, "yer tutucu eksiltilmiş BBF'de yerinde değil.")

            # --- netleştirmeye özel (31.10.2026) ---
            if islem == "netlestirme":
                if ".kosul" not in k.get("bbf_alani", ""):
                    r.hata(kid, "netleştirme yalnız sayısal koşulda olmalı (bbf_alani kosul değil).")
                yt = (k.get("bbf_yer_tutucu") or "").lower()
                beklenen_tip = tip_cikar(deger)
                uyumlu = any(beklenen_tip in tipler
                             for anahtar, tipler in YER_TUTUCU_TIP.items() if anahtar in yt)
                if yt and not uyumlu:
                    r.uyari(kid, f"yer tutucu dili ('{yt}') değer tipiyle ({beklenen_tip}) uyumsuz olabilir.")

        elif islem == "bilinmiyor":
            # "bilinmiyor" denen bilgi eksiksiz BBF'de de yok olmalı
            if eksiksiz:
                gercek = bbf_coz(eksiksiz, k.get("bbf_alani", ""))
                if gercek not in (None, "", []):
                    r.hata(kid, "'bilinmiyor' denen alan eksiksiz BBF'de dolu.")

    return r


def _yukle(yol):
    return json.load(open(yol, encoding="utf-8")) if yol else None

def _main():
    ap = argparse.ArgumentParser()
    ap.add_argument("soru_cevap")
    ap.add_argument("--eksiksiz")
    ap.add_argument("--eksiltilmis")
    ap.add_argument("--liste")
    a = ap.parse_args()

    sc = _yukle(a.soru_cevap)
    liste_idler = None
    if a.liste:
        liste_idler = set(MADDE_ID.findall(json.dumps(_yukle(a.liste), ensure_ascii=False)))

    r = dogrula(sc, _yukle(a.eksiksiz), _yukle(a.eksiltilmis), liste_idler)
    sys.exit(r.yazdir())

if __name__ == "__main__":
    _main()
