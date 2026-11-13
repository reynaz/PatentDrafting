# Soru-Cevap Şeması v0.1 (Faz 0.4 · taslak, 24.10.2026; netleştirme 31.10.2026 güncellendi)

## Ne işe yarıyor?
Tür 2 paketlerindeki soru-cevap belgesinin biçimi. Bölücü bu biçimde yazar, Faz 4 kontrolleri buna dayanır, Model B bunun bir kısmını görür. Gerçek kullanımda (Faz 7) kullanıcının yüklediği soru-cevap belgesi de normalizer ile aynı biçime çevrilir.

## Adlandırma
- **Eksiksiz BBF:** patentteki bütün bilgiyi içeren BBF (BBF yazarının çıktısı).
- **Eksiltilmiş BBF:** bölücünün bazı opsiyonel bilgileri çıkarıp soru-cevaba taşıdığı BBF.
- **Tür 2 paketi:** eksiltilmiş BBF + soru-cevap + ön araştırma raporu (Tür 1 paketi: eksiksiz BBF + rapor).

Doğrulayıcı: `python validate_soru_cevap.py soru_cevap.json --eksiksiz bbf.json --eksiltilmis bbf_eksiltilmis.json --liste bbf_kontrol_listesi.json`

## Yapı
```json
{ "sema_surumu": "0.1", "kaynak": "sentetik", "patent_id": "...", "bolucu_surumu": "...",
  "kayitlar": [ { "id": 1, "soru": "...", "cevap": "...",
                  "islem": "tasima | netlestirme | bilinmiyor", "madde_id": "P01",
                  "bbf_alani": "unsurlar[1].kosul", "unsur_ad": "yaylı kilit dili",
                  "tasinan_deger": "kilit kuvveti 40-60 N", "bbf_yer_tutucu": null,
                  "soru_kaynagi": "llm | sablon | gercek" } ] }
```

| Alan | Zorunlu | Model B görür mü | Açıklama |
|---|---|---|---|
| `id`, `soru`, `cevap` | Her zaman | **Evet** (yalnız soru + cevap, sırayla) | |
| `islem` | Sentetikte | Hayır | Bilgiye ne yapıldı: taşıma / netleştirme / bilinmiyor |
| `madde_id` | Sentetikte | Hayır | BBF kontrol listesi maddesi (P01, K09…) |
| `bbf_alani`, `unsur_ad` | Taşıma/netleştirmede | Hayır | Bilginin eksiksiz BBF'deki yeri |
| `tasinan_deger` | Taşıma/netleştirmede | Hayır | Orijinal değer; doğrulama için |
| `bbf_yer_tutucu` | Netleştirmede | Hayır | BBF'ye konan belirsiz ifade |
| `soru_kaynagi` | Sentetikte | Hayır | llm / şablon / gerçek |

Üst bilgi Model B'ye gitmez; gitse bilginin nereden çıkarıldığına dair ipucu olur. `model_b_gorunumu()` yalnız `{soru, cevap}` listesini üretir.

## Üç işlem
- **Taşıma:** bilgi eksiltilmiş BBF'den tamamen çıkar (`deger: null`, `durum: sorulmamis`; unsur içindeyse yalnız `kosul` null), soru-cevapta sorulur. Bütün taşınabilir alanlarda olabilir.
- **Netleştirme:** bilgi eksiltilmiş BBF'de **belirsiz/genel** halde kalır (`bbf_yer_tutucu`), kesin değeri soru-cevapta sorulur. **Yalnız sayısal koşullarda** (bkz. aşağıdaki karar).
- **Bilinmiyor:** eksiksiz BBF'de de boş olan bir aday alan sorulur, cevap "bilmiyoruz / henüz yok".

## Netleştirme kuralı (31.10.2026 kararı: dar + sayısal tipe göre çeşitli)
Netleştirme yalnız sayısal koşullarda (`unsurlar[].kosul`) uygulanır. Metin alanlarında (uygulama alanları, önceki teknik, alternatifler…) netleştirme yok; bu alanlar ya tam taşınır ya BBF'de kalır. Gerekçe: metin netleştirmesini (ör. "savunma sanayii" → "İHA") otomatik doğrulamak zor ve üretimde modelin makul bir alt alan uydurması gerekir; pilotta bu risk alınmadı.

**Yer tutucu ve soru, asıl değerin tipine göre değişir; cevap asıl değeri aynen taşır (kesinlik uydurulmaz).** Değerin tipi, `kosul` metninden çıkarılır (şema değişmez): içinde "-"/"ila"/"–" varsa aralık, "%"/"oran"/"ağırlıkça" varsa oran, yoksa tek değer.

| Asıl değer | BBF yer tutucu (örnek) | Soru (örnek) | Cevap |
|---|---|---|---|
| Tek sayı ("120 °C") | "belirli bir sıcaklıkta" | "Hangi sıcaklıkta?" | "120 °C" |
| Aralık ("40-60 N") | "uygun bir kuvvette" | "Hangi kuvvet aralığında?" | "40-60 N" |
| Oran ("ağırlıkça %5-10") | "belirli bir oranda" | "Hangi oranda?" | "%5-10" |

Kural: cevap, BBF'deki asıl değerin tipini korur (tek→tek, aralık→aralık, oran→oran). Patentte aralık varsa netleştirme onu tek değere indirmez.

## Kontroller (`validate_soru_cevap.py`)
Şema · id 1..n · sentetikte üst bilgi dolu · en fazla 1 bilinmiyor · **soru cevabı ele vermiyor** (ortak sayı yok) · istem dili / referans numarası yok · **taşınan sayılar cevapta** · madde_id listede · eksiksiz BBF ile eksiltilmiş BBF verilirse: taşınan değer doğru, **eksiltilmiş BBF'de bilgi kalmamış**, netleştirmede yer tutucu yerinde, **taşınan sayılar eksiltilmiş BBF'nin başka yerinde yok** (tekrar temizliği), **"bilinmiyor" denen bilgi eksiksiz BBF'de de yok**.

Netleştirmeye özel: `islem = netlestirme` ise `bbf_alani` bir `kosul` olmalı (sayısal), `bbf_yer_tutucu` dolu ve eksiltilmiş BBF'de o yer tutucu duruyor olmalı, `tasinan_deger`'in tipi (tek/aralık/oran) ile yer tutucu dili uyumlu olmalı.

## Açık
- Model B'ye biçim: JSON listesi mi, "Soru 1 / Cevap" metni mi? (Model B ekibiyle)
- Netleştirme kapsamı: pilot için dar (yalnız sayısal). Metin alanlarına genişletme ikinci sürüme bırakıldı.
