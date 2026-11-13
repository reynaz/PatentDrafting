"""
Kanonik BBF doğrulayıcı — Faz 4 kalite kapısının ilk parçası.
Kullanım: python validate_bbf.py dosya1.json [dosya2.json ...]

1) JSON Schema kontrolü (bbf.schema.json)
2) Şemanın ifade edemediği kurallar:
   - durum ↔ deger tutarlılığı (dolu/turetildi → deger var; sorulmamis/bos_birakilmis → deger null)
   - turetildi → kaynak zorunlu
   - tur=adim → sira dolu, sıralar 1..n ve tekrarsız
   - bulus_turu ↔ unsurlar tutarlılığı (yontem → en az bir adim, cihaz → en az bir parca, bilesim → bilesen)
   - unsur adları tekil (terim sözlüğü)
   - sızıntı: istem dili ve şekil referans numarası yok
"""
import json
import re
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

SCHEMA = json.loads(Path(__file__).with_name("bbf.schema.json").read_text(encoding="utf-8"))
VALIDATOR = Draft202012Validator(SCHEMA)

CLAIM_LANGUAGE = re.compile(r"karakterize\s+edil|ile\s+karakterize|özelliği\s*;|istem\s+\d+['’]?\s*[ey]e\s+göre", re.I)
REF_NUMERAL = re.compile(r"[a-zçğıöşü]\s\((\d{1,3}[a-z]?)(\s*[,-]\s*\d{1,3}[a-z]?)*\)", re.I)
TYPE_NEEDS = {"yontem": "adim", "cihaz": "parca", "bilesim": "bilesen"}


def _texts(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _texts(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _texts(v)


def validate(doc: dict) -> list[str]:
    errors = [f"şema: {'/'.join(map(str, e.path)) or '(kök)'}: {e.message}"
              for e in sorted(VALIDATOR.iter_errors(doc), key=lambda e: list(e.path))]
    if errors:
        return errors  # yapı bozuksa ek kurallar anlamsız

    for name, f in doc.items():
        if not isinstance(f, dict) or "durum" not in f:
            continue
        has_val = f["deger"] not in (None, "", [])
        if f["durum"] in ("dolu", "turetildi") and f["deger"] is None:
            errors.append(f"{name}: durum={f['durum']} ama deger null")
        if f["durum"] in ("sorulmamis", "bos_birakilmis") and has_val:
            errors.append(f"{name}: durum={f['durum']} ama deger dolu")
        if f["durum"] == "turetildi" and not f.get("kaynak"):
            errors.append(f"{name}: durum=turetildi ama kaynak yok")

    unsurlar = doc["unsurlar"]["deger"] or []
    adimlar = [u for u in unsurlar if u["tur"] == "adim"]
    if any(u.get("sira") is None for u in adimlar):
        errors.append("unsurlar: tur=adim olan her öğede sira dolu olmalı")
    else:
        siralar = sorted(u["sira"] for u in adimlar)
        if siralar and siralar != list(range(1, len(siralar) + 1)):
            errors.append(f"unsurlar: adım sıraları 1..n ve tekrarsız olmalı, bulunan: {siralar}")

    turler = {u["tur"] for u in unsurlar}
    for bt in doc["bulus_turu"]["deger"] or []:
        need = TYPE_NEEDS.get(bt)
        if need and need not in turler:
            errors.append(f"bulus_turu={bt} ama unsurlarda hiç tur={need} yok")

    adlar = [u["ad"].strip().lower() for u in unsurlar]
    dup = {a for a in adlar if adlar.count(a) > 1}
    if dup:
        errors.append(f"unsurlar: aynı ad birden fazla kez kullanılmış: {sorted(dup)}")

    for t in _texts({k: v for k, v in doc.items() if k != "sema_surumu"}):
        if CLAIM_LANGUAGE.search(t):
            errors.append(f"sızıntı: istem dili bulundu → '{CLAIM_LANGUAGE.search(t).group(0)}'")
        if REF_NUMERAL.search(t):
            errors.append(f"sızıntı: şekil referans numarası bulundu → '{REF_NUMERAL.search(t).group(0)}'")
    return errors


if __name__ == "__main__":
    bad = 0
    for p in sys.argv[1:]:
        errs = validate(json.loads(Path(p).read_text(encoding="utf-8")))
        print(f"{'GEÇTİ ' if not errs else 'KALDI '} {p}")
        for e in errs:
            print("   -", e)
        bad += bool(errs)
    sys.exit(1 if bad else 0)
