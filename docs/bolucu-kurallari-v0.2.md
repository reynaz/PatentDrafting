# Bölücü Kuralları v0.2 (Faz 0.5, 31.10.2026)

Bölücü, **eksiksiz BBF**'i alır; bazı opsiyonel bilgileri çıkarıp soru-cevaba taşır; geriye **eksiltilmiş BBF** + **soru-cevap** belgesi kalır (Tür 2 paketi). Bu belge yalnız *paket kurma* kurallarıdır. Olasılık değerleri burada DEĞİL: `configs/bbf_olasilik_tablosu_v0.2.xlsx` Özet sayfasında ölçülür (Laplace). v0.1 belgesindeki olasılıklar geçersizdir.

## Girdi / çıktı
- Girdi: eksiksiz BBF (kanonik şema, `{deger, durum, kaynak}`; `durum` ∈ dolu | turetildi | sorulmamis | bos_birakilmis).
- Çıktı: eksiltilmiş BBF (aynı şema) + soru-cevap (`soru-cevap-sema-v0.1`).
- Rastgelelik: tohum = patent numarasından türetilir (tekrarlanabilirlik).

## Taşınabilir alanlar ve olasılık
p(taşıma), Özet sayfasındaki p(sormama)'ya eşittir. Kod bunu Excel'den okur; elle yazılmaz.

| Alan (kanonik) | Kod | Birim | madde_id* |
|---|---|---|---|
| `unsurlar[].kosul` | SK | her unsur ayrı (yalnız kosul'u dolu olanlar) | P01 |
| `uygulama_alanlari` | UA | alanın tamamı = 1 bilgi | K12 |
| `alternatifler` | AL | alanın tamamı = 1 bilgi | P02 |
| `deney_sonuclari` | DS | alanın tamamı = 1 bilgi | K09 |
| `bilinen_belgeler` | BB | alanın tamamı = 1 bilgi | K03 |
| `avantajlar` | AV | en fazla 1 öğe; BBF'de en az 1 öğe kalır | K06 |
| `onceki_teknik` | OT | alanın tamamı = 1 bilgi | K03 |

*madde_id eşlemesi v0.1'den; `kontrol_listesi_taslak.xlsx` ile doğrulanmalı (BB ve OT aynı K03 görünüyor — kontrol et).

## Paket kurma kuralları
1. **Aday üretimi:** her *dolu* taşınabilir alan bir adaydır. SK'de her kosul'u dolu unsur ayrı aday. AV yalnız 2+ öğesi varsa aday.
2. **Zar:** her aday için p(taşıma) ile Bernoulli.
3. **En fazla 2 SK** (31.10 onaylandı).
4. **En fazla 4 bilgi** (SK ≤ 2 korunur).
5. **En az 1 bilgi (boş paket yok):** hiçbir zar tutmazsa p ağırlıklı 1 bilgi seçilir.
6. **Netleştirme (yalnız SK):** seçilen SK'lerin ~%30'u. Yer tutucu/soru değerin tipine göre (tek/aralık/oran); cevap asıl değeri aynen taşır.
7. **Bilinmiyor:** eksiksiz BBF'de boş olan aday alanlardan (UA, AL, DS, BB). Boş aday alanı olan paketlerin ~%20'sinde, en fazla 1. 1–4'e dahil değil.
8. **Eksiltilmiş BBF:** taşınan alan `deger=null, durum=sorulmamis` (unsurda yalnız `kosul=null`). Netleştirmede `deger` = yer tutucu, `durum=dolu`. Tekrar temizliği.
9. **Sıra:** soru-cevap kayıtları BBF bölüm sırasıyla.

## Oran parametreleri
`MAX_BILGI=4`, `MAX_SK=2`, `NETLESTIRME_ORANI=0.30` (yalnız SK), `BILINMIYOR_ORANI=0.20` (boş aday alanı olan paketlerde). Hepsi `configs/pipeline.yaml`'dan okunur.

## Doğrulama
Çıktı `validate_soru_cevap.py` ve `validate_bbf.py`'den geçmeli.
