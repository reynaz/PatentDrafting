"""
Ön araştırma raporu şemasını (on_arastirma_raporu.schema.json) üretir. Sürüm 0.1 (taslak, 21.10.2026)

Dayanak:
- SMKY m.97/3: yenilik ve buluş basamağı için dikkate alınabilecek dokümanlar listelenir
- SMKY m.97/4: her dokümanın hangi istemle ilgili olduğu ve gerekirse hangi kısmının ilgili olduğu
- SMKY m.97/5: rüçhan/başvuru tarihine göre ayırt etme  -> arama filtresi (kesim_tarihi) ile karşılanır
- SMKY m.97/7: uluslararası sınıflandırma (IPC)
- TÜRKPATENT kılavuzu s.21-22: X / Y / A (P, E, O, T, L) kategorileri

Resmî rapordan farkı: rapor istem yazılmadan ÖNCE, BBF'den hazırlanır.
- "ilgili istem" yerine "ilgili unsur" (BBF unsurlar[].ad)
- Kesim tarihinden sonraki belgeler arama aşamasında elendiği için yalnızca X / Y / A kullanılır
- Yalnızca belge özetleri görüldüğü için kategori "önerilen kategori"dir

Kim doldurur: KOD -> bulus, ipc_siniflari, arama_bilgisi, belgeler[].numara/baslik/yayin_tarihi/ipc/benzerlik_skoru
              LLM -> belgeler[].kategori/kategori_gerekcesi/ilgili_unsurlar/karsilastirma/y_birlikte, genel_degerlendirme
"""
import json
from pathlib import Path

SCHEMA_VERSION = "0.1"
TEXT = {"type": "string", "minLength": 1}
DATE = {"type": "string", "pattern": r"^\d{4}-\d{2}-\d{2}$"}
UYARI = ("Bu rapor otomatik bir ön araştırmadır; resmî araştırma raporu değildir. "
         "Kategoriler yalnızca belge özetlerine dayanan önerilerdir.")

BELGE = {
    "type": "object",
    "additionalProperties": False,
    "required": ["sira", "numara", "baslik", "yayin_tarihi", "benzerlik_skoru",
                 "kategori", "kategori_gerekcesi", "ilgili_unsurlar", "karsilastirma"],
    "properties": {
        "sira": {"type": "integer", "minimum": 1, "description": "[KOD] Reranker sırası (1 = en yakın)"},
        "numara": {**TEXT, "description": "[KOD] Yayın numarası (örn. EP1234567A1). Yalnızca arama sonucundan; asla uydurulmaz."},
        "baslik": {**TEXT, "description": "[KOD] Belgenin başlığı (veri tabanındaki dilde)"},
        "yayin_tarihi": {**DATE, "description": "[KOD] Yayın tarihi; kesim_tarihi'nden önce olmalı"},
        "ipc": {"type": "array", "items": TEXT, "description": "[KOD] Belgenin IPC sınıfları"},
        "benzerlik_skoru": {"type": "number", "minimum": 0, "maximum": 1, "description": "[KOD] Reranker skoru"},
        "kategori": {"type": "string", "enum": ["X", "Y", "A"],
                     "description": "[LLM] Önerilen kategori. X: buluşun tüm ana özelliklerini tek başına içerir | "
                                    "Y: başka belge(ler)le birlikte tüm özellikleri içerir | "
                                    "A: genel teknik bilgi verir, patent almaya engel değil (Kılavuz s.21-22)"},
        "kategori_gerekcesi": {**TEXT, "description": "[LLM] 1-2 cümle: kategori neden bu?"},
        "ilgili_unsurlar": {"type": "array", "items": TEXT, "uniqueItems": True,
                            "description": "[LLM] Belgede karşılığı olan BBF unsurlarının adları (BBF'deki adla birebir). "
                                           "X ve Y'de boş olamaz."},
        "karsilastirma": {
            "type": "object", "additionalProperties": False, "required": ["benzerlik", "fark"],
            "properties": {
                "benzerlik": {**TEXT, "description": "[LLM] Belgenin buluşla ortak yanları"},
                "fark": {**TEXT, "description": "[LLM] Buluşun bu belgede olmayan yanları"},
            },
        },
        "y_birlikte": {"type": "array", "items": TEXT, "uniqueItems": True,
                       "description": "[LLM] Yalnızca kategori=Y: birlikte ele alınması gereken diğer belgelerin numaraları "
                                      "(bu rapordaki belgelerden)"},
    },
}

SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://istem-proje/schemas/on_arastirma_raporu.schema.json",
    "title": "Ön Araştırma Raporu",
    "description": f"Sürüm {SCHEMA_VERSION}. Model A'nın 4-6. adımlarının çıktısı, Model B girdisi. "
                   "Dayanak: SMKY m.97/3-7, TÜRKPATENT kılavuzu s.21-22. İstem yerine BBF unsurlarına göre düzenlenir.",
    "type": "object",
    "additionalProperties": False,
    "required": ["sema_surumu", "bulus", "arama_bilgisi", "belgeler", "genel_degerlendirme", "uyari"],
    "properties": {
        "sema_surumu": {"const": SCHEMA_VERSION},
        "bulus": {
            "type": "object", "additionalProperties": False, "required": ["baslik", "arama_ozeti"],
            "description": "[KOD] BBF'den kopyalanır",
            "properties": {"baslik": TEXT, "arama_ozeti": TEXT},
        },
        "ipc_siniflari": {"type": "array", "items": TEXT,
                          "description": "[KOD] Buluşun IPC sınıfları (SMKY m.97/7). Veri üretiminde patentin kendi sınıfları."},
        "arama_bilgisi": {
            "type": "object", "additionalProperties": False,
            "required": ["veri_tabani", "sorgu_metni", "embedding_modeli", "aday_sayisi", "kesim_tarihi", "arama_tarihi"],
            "description": "[KOD] Aramanın tekrarlanabilmesi için",
            "properties": {
                "veri_tabani": {**TEXT, "description": "örn. 'Google Patents Public Data (BigQuery), IPC filtreli'"},
                "sorgu_metni": {**TEXT, "description": "Embedding'e verilen metin (arama_ozeti)"},
                "embedding_modeli": TEXT,
                "reranker": {"type": ["string", "null"]},
                "aday_sayisi": {"type": "integer", "minimum": 1, "description": "Reranker'a giren aday sayısı (örn. 100)"},
                "kesim_tarihi": {**DATE, "description": "Bu tarihten sonra yayımlanan belgeler elendi "
                                                      "(veri üretiminde rüçhan/başvuru tarihi, gerçek kullanımda arama tarihi)"},
                "arama_tarihi": DATE,
            },
        },
        "belgeler": {"type": "array", "items": BELGE, "maxItems": 10,
                     "description": "En yakın 5-8 belge, sira'ya göre. Uygun belge yoksa boş liste."},
        "genel_degerlendirme": {**TEXT, "description": "[LLM] 2-4 cümle: en yakın belge, buluşun öne çıkan farkı, "
                                                      "yenilik açısından dikkat edilecek unsurlar"},
        "uyari": {"const": UYARI},
    },
}

if __name__ == "__main__":
    out = Path(__file__).parent / "on_arastirma_raporu.schema.json"
    out.write_text(json.dumps(SCHEMA, ensure_ascii=False, indent=2), encoding="utf-8")
    print("yazıldı:", out)
