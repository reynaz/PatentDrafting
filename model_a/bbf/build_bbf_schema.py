"""
Kanonik BBF şemasını (bbf.schema.json) üretir.  Faz 0.2 — sürüm 0.1 (taslak)

Tasarım kararları:
- Her üst düzey alan aynı sarmalayıcıyı kullanır: {deger, durum, kaynak}
    durum: dolu | turetildi | sorulmamis | bos_birakilmis
- Buluşun çekirdeği TEK LİSTE: `unsurlar`, her öğe `tur` etiketi taşır (parca | adim | bilesen)
- Kişisel / idari / ticari bilgiler şemada YOK ve sistemde hiçbir yerde tutulmaz (17.10.2026 kararı)
- Referans numarası ve istem dili YOK (validate_bbf.py kontrol eder)
Alan açıklamaları Model A ve normalizer prompt'larına doğrudan girer; bu yüzden Türkçe ve talimat niteliğinde.
"""
import json
from pathlib import Path

SCHEMA_VERSION = "0.1"

DURUM = {
    "type": "string",
    "enum": ["dolu", "turetildi", "sorulmamis", "bos_birakilmis"],
    "description": "dolu: kaynakta doğrudan var | turetildi: başka bir bölümden çıkarıldı (kaynak zorunlu) | "
                   "sorulmamis: kaynak form bu bilgiyi sormuyor | bos_birakilmis: soruluyor ama boş",
}


def field(value_schema: dict, description: str) -> dict:
    """Her alan için {deger, durum, kaynak} sarmalayıcısı."""
    return {
        "type": "object",
        "description": description,
        "additionalProperties": False,
        "required": ["deger", "durum"],
        "properties": {
            "deger": {"anyOf": [value_schema, {"type": "null"}]},
            "durum": DURUM,
            "kaynak": {"type": ["string", "null"],
                       "description": "durum=turetildi ise: bilginin alındığı bölümün adı veya kısa alıntı"},
        },
    }


TEXT = {"type": "string", "minLength": 1}
STR_LIST = {"type": "array", "items": TEXT}

UNSUR = {
    "type": "object",
    "additionalProperties": False,
    "required": ["tur", "ad", "islev", "yeni", "zorunlu"],
    "properties": {
        "tur": {"type": "string", "enum": ["parca", "adim", "bilesen"],
                "description": "parca: fiziksel bileşen (gövde, valf) | adim: sırayla yapılan işlem | "
                               "bilesen: karışımın içeriği"},
        "ad": {**TEXT, "description": "Unsurun adı. Belge boyunca AYNI ad kullanılmalı (terim sözlüğü)."},
        "islev": {**TEXT, "description": "Unsurun buluştaki görevi; buluşçu dilinde, 1-2 cümle"},
        "yeni": {"type": "boolean", "description": "true: önceki teknikte yok, buluşun yenilik getiren kısmı"},
        "zorunlu": {"type": "boolean",
                    "description": "true: çıkarılırsa buluş çalışmaz (bağımsız isteme aday) | "
                                   "false: çıkarılsa da buluş işler (bağımlı isteme aday)"},
        "sira": {"type": ["integer", "null"], "minimum": 1,
                 "description": "Yalnızca tur=adim için zorunlu: işlem sırası"},
        "kosul": {"type": ["string", "null"],
                  "description": "Sayısal değer/aralık/koşul: '120-150 °C, 30 dk' (adım), "
                                 "'ağırlıkça %60-70' (bileşen), '0,2-0,5 mm' (parça). Uydurma; yoksa null"},
        "baglantilar": {"type": "array", "items": TEXT,
                        "description": "tur=parca için: bağlı/etkileştiği diğer unsurların adları"},
    },
}

SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://istem-proje/schemas/bbf.schema.json",
    "title": "Kanonik Buluş Bildirim Formu (BBF)",
    "description": f"Sürüm {SCHEMA_VERSION}. Model A çıktısı, normalizer çıktısı ve Model B girdisi bu şemaya uyar. "
                   "Kişisel/idari/ticari bilgi içermez. İstem dili ('…ile karakterize edilmektedir') ve "
                   "şekil referans numaraları ('gövde (1)') kullanılmaz.",
    "type": "object",
    "additionalProperties": False,
    "required": ["sema_surumu", "baslik", "bulus_turu", "teknik_alan", "onceki_teknik", "teknik_problem",
                 "unsurlar", "detayli_aciklama", "sekiller", "avantajlar"],
    "properties": {
        "sema_surumu": {"const": SCHEMA_VERSION},

        # ---- Zorunlu çekirdek
        "baslik": field(TEXT, "Buluşun kısa ve tanımlayıcı adı; marka içermez."),
        "bulus_turu": field({"type": "array", "minItems": 1, "uniqueItems": True,
                             "items": {"enum": ["cihaz", "yontem", "bilesim", "kullanim"]}},
                            "Buluşun koruma kategorisi; birden fazla olabilir. Veri üretiminde kod "
                            "(bağımsız istemler) belirler, gerçek kullanımda normalizer."),
        "teknik_alan": field(TEXT, "Buluşun ilgili olduğu teknik alan; 1-3 cümle, genel."),
        "onceki_teknik": field(TEXT, "Mevcut çözümler/uygulamalar ve nasıl çalıştıkları."),
        "teknik_problem": field(TEXT, "Mevcut çözümlerin eksikleri ve buluşun çözdüğü teknik problem."),
        "unsurlar": field({"type": "array", "minItems": 1, "items": UNSUR},
                          "Buluşun çekirdeği: parçalar, adımlar veya bileşenler (tek liste, tur etiketiyle)."),
        "detayli_aciklama": field(TEXT, "Buluşun nasıl yapıldığı ve çalıştığı; buluşçu dilinde, ayrıntılı."),
        "sekiller": field({"type": "array",
                           "items": {"type": "object", "additionalProperties": False,
                                     "required": ["no", "aciklama"],
                                     "properties": {"no": {"type": "integer", "minimum": 1},
                                                    "aciklama": TEXT}}},
                          "Her şeklin ne gösterdiği; referans numarası olmadan. Şekil yoksa deger=[]."),
        "avantajlar": field(STR_LIST, "Buluşun mevcut çözümlere göre somut avantajları (madde madde)."),

        # ---- Opsiyonel ama faydalı
        "kisa_aciklama": field(TEXT, "Buluşun 2-4 cümlelik özeti."),
        "alternatifler": field(STR_LIST, "Aynı işi gören alternatif yapı/malzeme/yöntemler, başka kullanım biçimleri."),
        "uygulama_alanlari": field(STR_LIST, "Buluşun kullanılabileceği sektör ve uygulamalar."),
        "deney_sonuclari": field(TEXT, "Yapılan test/deney ve sonuçları (sayısal ise birimiyle)."),
        "bilinen_belgeler": field({"type": "array",
                                   "items": {"type": "object", "additionalProperties": False,
                                             "required": ["numara", "fark"],
                                             "properties": {"numara": TEXT,
                                                            "ozet": {"type": ["string", "null"]},
                                                            "fark": TEXT}}},
                                  "Buluşçunun bildiği en yakın patent/yayınlar ve buluştan farkı. "
                                  "Numara yalnızca gerçek kaynaktan; asla uydurulmaz."),
        "anahtar_kavramlar": field({"type": "object", "additionalProperties": False,
                                    "required": ["tr", "en"],
                                    "properties": {"tr": STR_LIST, "en": STR_LIST}},
                                   "Arama için Türkçe ve İngilizce terimler."),
        "arama_ozeti": field(TEXT, "Ön araştırma araması için buluşun teknik çekirdeği, 3-4 cümle."),
        "ek_bilgiler": field({"type": "array",
                              "items": {"type": "object", "additionalProperties": False,
                                        "required": ["orijinal_baslik", "icerik"],
                                        "properties": {"orijinal_baslik": TEXT, "icerik": TEXT}}},
                             "Şemada karşılığı olmayan TEKNİK bilgiler; orijinal başlığıyla. Hiçbir bilgi atılmaz."),
    },
}

out = Path(__file__).with_name("bbf.schema.json")
out.write_text(json.dumps(SCHEMA, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"yazıldı: {out.name} (sürüm {SCHEMA_VERSION}, {len(SCHEMA['properties']) - 1} alan)")
