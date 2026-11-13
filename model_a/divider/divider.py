"""
divider.py — Type 2 package generator (Faz 0.5, v0.2)

Takes a complete BBF (canonical schema) and produces a reduced BBF plus a
soru-cevap (Q&A) document.

Design: the DECISION (what to move, via dice) is kept separate from the TEXT
(turning each decision into a Turkish question/answer). Decision lives in
`_decide`; text in `_to_records`; BBF mutation in `_apply`. Question wording is
template-based and diversified (several variants per field, chosen by seed), so
Model B does not memorise a single phrasing.

Rules:        plan/bolucu-kurallari-v0.2.md
Probabilities: config olasılık Excel, "Özet" sheet (p(taşıma) = p(sormama))

NOTE: Data keys, `islem` values, madde_id and the generated question/answer text
stay Turkish on purpose — they are the data contract shared with
validate_soru_cevap.py and the schema docs. Only the code is English.

CLI:
    python divider.py full_bbf.json --prob olasilik_tablosu_v0.2.xlsx \
        --patent-id TR2025... --out-bbf reduced.json --out-qa soru_cevap.json
"""
from __future__ import annotations
import argparse, copy, hashlib, json, random, re
from dataclasses import dataclass

VERSION = "divider-0.2"

# --- Fixed parameters (plan/bolucu-kurallari-v0.2.md) -------------------------
MAX_INFO = 4
MAX_SK = 2
CLARIFY_RATE = 0.30      # numeric conditions only
UNKNOWN_RATE = 0.20      # packages that have an empty candidate field

# Canonical field -> (code, madde_id). madde_id from v0.1; verify vs kontrol listesi.
FIELD_CODE = {
    "uygulama_alanlari": ("UA", "K12"),
    "alternatifler":     ("AL", "P02"),
    "deney_sonuclari":   ("DS", "K09"),
    "bilinen_belgeler":  ("BB", "K03"),
    "avantajlar":        ("AV", "K06"),
    "onceki_teknik":     ("OT", "K03"),
}
SK_CODE, SK_MADDE = "SK", "P01"          # unsurlar[].kosul
UNKNOWN_FIELDS = ["deney_sonuclari", "alternatifler",
                  "uygulama_alanlari", "bilinen_belgeler"]
SECTION_ORDER = ["onceki_teknik", "unsurlar", "avantajlar", "alternatifler",
                 "uygulama_alanlari", "deney_sonuclari", "bilinen_belgeler"]

# Turkish labels for question text
LABELS = {"UA": "uygulama alanları", "AL": "alternatif yapılanmalar",
          "DS": "deney/test sonuçları", "BB": "bilinen patent/yayınlar",
          "AV": "avantaj", "OT": "önceki teknik / mevcut çözüm"}

# Question templates (Turkish content), several variants per code
MOVE_Q = {
    "SK": ["{ad} için hangi sayısal değer/aralık kullanılıyor?",
           "{ad} hangi değerde olmalı?",
           "{ad} için öngörülen değer nedir?"],
    "UA": ["Buluş hangi alanlarda/sektörlerde kullanılabilir?",
           "Buluşun uygulama alanları nelerdir?",
           "Buluş hangi kullanım alanlarına yöneliktir?"],
    "AL": ["Buluşun alternatif yapılanmaları nelerdir?",
           "Buluşun başka uygulama biçimleri var mı?",
           "Buluş için alternatif çözümler nelerdir?"],
    "DS": ["Buluşla ilgili hangi deney/test sonuçları var?",
           "Yapılan testlerin sonuçları nedir?",
           "Buluşun performansına dair ölçüm sonuçları nelerdir?"],
    "BB": ["Buluşla ilgili bilinen patent/yayınlar nelerdir?",
           "Benzer olduğu düşünülen belgeler var mı?",
           "Konuyla ilgili bilinen önceki belgeler nelerdir?"],
    "AV": ["Buluşun sağladığı avantajlardan biri nedir?",
           "Buluşun önceki tekniğe göre bir üstünlüğü nedir?"],
    "OT": ["Mevcut teknikte bu problem nasıl çözülüyor?",
           "Önceki teknikteki çözümler nelerdir?",
           "Bu alandaki mevcut çözümlerin eksikleri nelerdir?"],
}
# Clarify (netleştirme, SK only): placeholder + question variants per numeric type
CLARIFY = {
    "tek":    ("belirli bir değerde",
               ["{ad} tam olarak hangi değerde?", "{ad} için kesin değer nedir?"]),
    "aralik": ("uygun bir aralıkta",
               ["{ad} hangi aralıkta olmalı?", "{ad} için değer aralığı nedir?"]),
    "oran":   ("belirli bir oranda",
               ["{ad} hangi oranda?", "{ad} için kesin oran nedir?"]),
}


# --- helpers ------------------------------------------------------------------
def _filled(field: dict | None) -> bool:
    return isinstance(field, dict) and field.get("durum") == "dolu" \
        and field.get("deger") not in (None, "", [])

def _empty(field: dict | None) -> bool:
    return not isinstance(field, dict) or field.get("durum") in ("sorulmamis", "bos_birakilmis") \
        or field.get("deger") in (None, "", [])

def _item_count(value) -> int:
    return len(value) if isinstance(value, list) else 1

def numeric_type(text: str) -> str:
    """Infer numeric type from the kosul text: 'oran' | 'aralik' | 'tek'."""
    t = (text or "").lower()
    if "%" in t or "oran" in t or "ağırlıkça" in t or "hacimce" in t:
        return "oran"
    if re.search(r"\d\s*(?:-|–|ila)\s*\d", t):
        return "aralik"
    return "tek"


@dataclass
class Candidate:
    code: str                 # SK|UA|AL|DS|BB|AV|OT
    field: str                # canonical field name
    bbf_path: str             # "uygulama_alanlari" / "unsurlar[2].kosul"
    madde_id: str
    value: str                # full field value
    moved_value: str          # what actually moves (AV: first item; else value)
    p: float
    unsur_idx: int | None = None
    unsur_name: str | None = None

@dataclass
class PlanItem:
    candidate: Candidate
    islem: str                # "tasima" | "netlestirme"


# --- divider ------------------------------------------------------------------
class Divider:
    def __init__(self, p: dict[str, float]):
        self.p = p            # {'SK':0.85, 'UA':0.29, ...} with p(move) = p(not asked)

    @classmethod
    def from_excel(cls, path: str) -> "Divider":
        """Read p(sormama) from the 'Özet' sheet."""
        from openpyxl import load_workbook
        ws = load_workbook(path, data_only=True)["Özet"]
        p = {}
        for row in ws.iter_rows(values_only=True):
            if not row:
                continue
            code = str(row[1]).strip() if row[1] else ""
            if code in {"SK", "UA", "AL", "DS", "BB", "AV", "OT"}:
                # Özet: Alan | Kod | Soruyor | Sormuyor | p(sormama) | GA alt | GA üst | p(taşıma)
                val = row[7] if len(row) > 7 and row[7] is not None else row[4]
                p[code] = float(val)
        missing = {"SK", "UA", "AL", "DS", "BB", "AV", "OT"} - p.keys()
        if missing:
            raise ValueError(f"Codes not found in 'Özet': {missing}")
        return cls(p)

    # --- candidate collection ---
    def _candidates(self, bbf: dict) -> list[Candidate]:
        out: list[Candidate] = []
        unsurlar = (bbf.get("unsurlar") or {}).get("deger") or []
        for i, u in enumerate(unsurlar):
            kosul = u.get("kosul")
            if kosul:
                out.append(Candidate(SK_CODE, "unsurlar", f"unsurlar[{i}].kosul",
                                     SK_MADDE, str(kosul), str(kosul), self.p["SK"],
                                     unsur_idx=i, unsur_name=u.get("ad")))
        for field, (code, madde) in FIELD_CODE.items():
            wrap = bbf.get(field)
            if not _filled(wrap):
                continue
            value = wrap["deger"]
            if code == "AV":
                if _item_count(value) < 2:        # at least one advantage must stay
                    continue
                moved = value[0] if isinstance(value, list) else value
            else:
                moved = value
            out.append(Candidate(code, field, field, madde, str(value), str(moved),
                                 self.p[code]))
        return out

    # --- decision (dice) ---
    def _decide(self, cands: list[Candidate], bbf: dict,
                rng: random.Random) -> tuple[list[PlanItem], str | None]:
        chosen = [c for c in cands if rng.random() < c.p]

        # cap SK at 2
        sk = [c for c in chosen if c.code == "SK"]
        if len(sk) > MAX_SK:
            keep = self._weighted_sample(sk, MAX_SK, rng)
            chosen = [c for c in chosen if c.code != "SK"] + keep

        # cap total at 4 (keep SK<=2)
        if len(chosen) > MAX_INFO:
            sk = [c for c in chosen if c.code == "SK"]
            rest = [c for c in chosen if c.code != "SK"]
            rest = self._weighted_sample(rest, max(MAX_INFO - len(sk), 0), rng)
            chosen = sk + rest

        # at least 1 (no empty package)
        if not chosen and cands:
            chosen = self._weighted_sample(cands, 1, rng)

        # 30% of chosen SK become netleştirme
        sk_chosen = [c for c in chosen if c.code == "SK"]
        n_clarify = round(len(sk_chosen) * CLARIFY_RATE)
        clarify_ids = {id(c) for c in rng.sample(sk_chosen, n_clarify)} if n_clarify else set()

        plan = [PlanItem(c, "netlestirme" if id(c) in clarify_ids else "tasima")
                for c in chosen]

        # bilinmiyor: an empty candidate field, max 1
        empties = [f for f in UNKNOWN_FIELDS if _empty(bbf.get(f))]
        unknown = rng.choice(empties) if empties and rng.random() < UNKNOWN_RATE else None
        return plan, unknown

    @staticmethod
    def _weighted_sample(cands, k, rng):
        if k <= 0 or not cands:
            return []
        if k >= len(cands):
            return list(cands)
        pool, picked = list(cands), []
        for _ in range(k):
            total = sum(c.p for c in pool) or 1.0
            threshold, acc = rng.random() * total, 0.0
            for c in pool:
                acc += c.p
                if acc >= threshold:
                    picked.append(c); pool.remove(c); break
        return picked

    # --- BBF mutation ---
    def _apply(self, reduced: dict, plan: list[PlanItem]) -> None:
        for item in plan:
            c = item.candidate
            if c.code == "SK" and item.islem == "netlestirme":
                placeholder = CLARIFY[numeric_type(c.value)][0]
                reduced["unsurlar"]["deger"][c.unsur_idx]["kosul"] = placeholder
            elif c.code == "SK":
                reduced["unsurlar"]["deger"][c.unsur_idx]["kosul"] = None
            elif c.code == "AV":
                kept = [o for o in reduced[c.field]["deger"] if str(o) != str(c.moved_value)]
                reduced[c.field]["deger"] = kept or reduced[c.field]["deger"]
            else:
                reduced[c.field]["deger"] = None
                reduced[c.field]["durum"] = "sorulmamis"

    # --- text (decision -> Turkish question/answer) ---
    def _to_records(self, plan: list[PlanItem], unknown: str | None,
                    rng: random.Random) -> list[dict]:
        records = []
        for item in plan:
            c = item.candidate
            if item.islem == "netlestirme":
                ntype = numeric_type(c.value)
                placeholder, q_variants = CLARIFY[ntype]
                q = rng.choice(q_variants).format(ad=c.unsur_name or "ilgili unsur")
                records.append(dict(
                    soru=q, cevap=str(c.moved_value), islem="netlestirme",
                    madde_id=c.madde_id, bbf_alani=c.bbf_path, unsur_ad=c.unsur_name,
                    tasinan_deger=str(c.moved_value), bbf_yer_tutucu=placeholder,
                    soru_kaynagi="sablon"))
            else:
                if c.code == "SK":
                    q = rng.choice(MOVE_Q["SK"]).format(ad=c.unsur_name or "ilgili unsur")
                else:
                    q = rng.choice(MOVE_Q[c.code])
                records.append(dict(
                    soru=q, cevap=str(c.moved_value), islem="tasima",
                    madde_id=c.madde_id, bbf_alani=c.bbf_path, unsur_ad=c.unsur_name,
                    tasinan_deger=str(c.moved_value), soru_kaynagi="sablon"))
        if unknown:
            code, madde = FIELD_CODE[unknown]
            records.append(dict(
                soru=f"Buluşun {LABELS[code]} hakkında bilgi var mı?",
                cevap="Bu konuda henüz bir bilgimiz yok.",
                islem="bilinmiyor", madde_id=madde, bbf_alani=unknown,
                soru_kaynagi="sablon"))

        def order(r):
            root = r["bbf_alani"].split("[")[0]
            return SECTION_ORDER.index(root) if root in SECTION_ORDER else 99
        records.sort(key=order)
        for i, r in enumerate(records, 1):
            r_clean = {k: v for k, v in r.items() if v is not None}
            r.clear(); r["id"] = i; r.update(r_clean)
        return records

    # --- main ---
    def split(self, full_bbf: dict, patent_id: str = "") -> tuple[dict, dict]:
        seed = int(hashlib.sha256(
            (patent_id or json.dumps(full_bbf, sort_keys=True)).encode()).hexdigest(), 16)
        rng = random.Random(seed)

        plan, unknown = self._decide(self._candidates(full_bbf), full_bbf, rng)
        reduced = copy.deepcopy(full_bbf)
        self._apply(reduced, plan)
        records = self._to_records(plan, unknown, rng)

        soru_cevap = {
            "sema_surumu": "0.1", "kaynak": "sentetik",
            "patent_id": patent_id, "bolucu_surumu": VERSION,
            "kayitlar": records,
        }
        return reduced, soru_cevap


# --- CLI ----------------------------------------------------------------------
def _main():
    ap = argparse.ArgumentParser()
    ap.add_argument("full_bbf")
    ap.add_argument("--prob", default="olasilik_tablosu_v0.2.xlsx")
    ap.add_argument("--patent-id", default="")
    ap.add_argument("--out-bbf", default="reduced_bbf.json")
    ap.add_argument("--out-qa", default="soru_cevap.json")
    a = ap.parse_args()

    bbf = json.load(open(a.full_bbf, encoding="utf-8"))
    d = Divider.from_excel(a.prob)
    reduced, qa = d.split(bbf, patent_id=a.patent_id)
    json.dump(reduced, open(a.out_bbf, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    json.dump(qa, open(a.out_qa, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"{len(qa['kayitlar'])} record(s) -> {a.out_qa}")

if __name__ == "__main__":
    _main()
