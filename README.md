# PatentDrafting

Patentten yapay zekâ destekli patent yazımı. İki model:

- **Model A** — patentten eğitim verisi üretir (buluş bildirim formu, soru-cevap, ön araştırma raporu). API ile, ince ayarsız.
- **Model B** — bu paketlerden patent (istem + tarifname) üretir. İnce ayarlı, istem üretiminde RAG.

Amaç: ürettiğimiz patent belgesinin mevcut LLM'lerden (Claude, Gemini) daha iyi olması ve bir makale çıkması.

İki kök ayrıdır; tek arayüz `data/exports/*.jsonl`. `model_b`, `model_a` kodunu import etmez.

---

## Uçtan uca akış

```
MODEL A (veri üretimi)
  S1 preprocessing ─ ham PDF → metin, claim/tarifname, atıf listesi, bibliyo
  S2 dataset_assignment ─ her patente rol: paket_turu(1/2), raporsuz, train/test  → assignment.json
  S3 search → filter ─ rapor için aday patent getir, ele
  S4 report ─ ön araştırma raporu üret + doğrula
  S5 bbf (Model A) ─ patent → eksiksiz BBF (kanonik JSON)
  S6 divider ─ eksiksiz BBF → eksiltilmiş BBF + soru-cevap   (yalnız Tür 2)
  S7 question_answer ─ soru-cevabı doğrula (JSON Schema + anlamsal)
  S8 quality ─ tüm paket için toplu kalite kapısı            → quality.json
  S9 export ─ geçen patentler → modelb_train.jsonl / modelb_test.jsonl
                                     │
                                     ▼  (tek arayüz)
MODEL B (eğitim + değerlendirme)
  B1 rag ─ istem havuzu (ayrı patentler) → embedding (Qwen3-Embedding-8B) → FAISS
  B2 training ─ modelb_train.jsonl ile ince ayar (paket → patent)
  B3 evaluation/infer ─ modelb_test.jsonl + RAG(istem) → üretilen patent
  B4 evaluation/score ─ üretilen vs orijinal; RAG koşulları A-E × {ince ayarlı, ayarsız}; Claude/Gemini kıyası
```

### İki paket türü
- **Tür 1:** eksiksiz BBF + rapor. Soru-cevap yok. Bölücü çalışmaz.
- **Tür 2:** eksiltilmiş BBF + soru-cevap + rapor. Bölücü BBF'den bazı bilgileri çıkarıp soru-cevaba taşımış.

Model B her ikisini de görsün diye eğitim seti karışıktır (oran `pipeline.yaml`'da, varsayılan %50/%50). Gerçek kullanımda (Faz 7) kullanıcının yüklediği BBF + soru-cevap normalizer ile aynı biçime çevrilip Model B'ye verilir.

### Taşıma olasılıkları (S6, 32 formdan Laplace ile ölçüldü)
`model_a/configs/bbf_olasilik_tablosu_v0.2.xlsx` → Özet. p(taşıma) = p(sormama):
DS 0,88 · SK 0,85 · AL 0,50 · UA 0,29 · AV 0,09 · BB 0,06 · OT 0,06.
Okunuşu: formların çoğu DS ve SK'yi sormuyor → bunlar neredeyse hep soru-cevaba taşınır; AV/BB/OT'yi herkes soruyor → neredeyse hiç taşınmaz.

---

## Çalıştırma

```bash
# Model A — bir IPC alanı için S1-S9
python -m model_a.pipeline.runner --alan A47 --asama S1-S9
# çıktısı olan aşamayı atlar (resume); takılanlar: --rerun-failed

# Model B — Colab (GPU)
python -m model_b.training.finetune
python -m model_b.evaluation.run_conditions   # A-E × {ince ayarlı, ayarsız}
```

Tek aşamayı elle çalıştırma (örnek, S6):
```bash
python model_a/divider/divider.py full_bbf.json \
  --prob model_a/configs/bbf_olasilik_tablosu_v0.2.xlsx \
  --patent-id TR2025_000123 --out-bbf reduced.json --out-qa soru_cevap.json
python model_a/question_answer/validate_soru_cevap.py soru_cevap.json \
  --eksiksiz full_bbf.json --eksiltilmis reduced.json --liste bbf_kontrol_listesi.json
```

### Nerede çalışır
- **Mac (CPU):** S1, S2, S6, S7, S8, S9 ve skorlama.
- **Colab (GPU):** S3/S4 embedding, B1 embedding/FAISS, B2 ince ayar, B3 çıkarım. `*/notebooks/`.

---

## Yapı

```
model_a/   pipeline/ (runner, stages, paths, llm[fake|cache|live], contracts)
           preprocessing/ dataset_assignment/ search/ report/ bbf/
           divider/ question_answer/ quality/ export/
           schemas/ configs/ notebooks/ tests/
model_b/   rag/ training/ evaluation/ configs/ notebooks/ tests/
docs/      şema ve kural belgeleri (soru-cevap-sema, bolucu-kurallari)
data/      raw/ processed/<patent_id>/ exports/ reports/   (git dışı)
```

Her aşama = çekirdek mantık + `*_stage.py` (pipeline bağlayıcı) + `tests/`. Gelişen kod aşamanın `experimental/` klasöründe (runner'a ve testlere dahil değil).

## İlkeler
- **patent_id her şeyi bağlar.** Her aşama `data/processed/<patent_id>/` okur/yazar; süreç resume edilebilir.
- **Şema = sözleşme, doğrulayıcı = kapı.** Geçmeyen veri bir sonraki aşamaya girmez.
- **assignment.json = manifest.** Rol + split + seed tek kayıtta, tekrarlanabilir.
- **İngilizce kod, Türkçe veri sözleşmesi** (şema anahtarları, islem değerleri, soru/cevap metinleri).
- **Model A cache'li** (~$20 bütçe; çıktısı olan patent yeniden çağrılmaz).

## Açık kararlar (isim değil, içerik)
- `export` satır şeması: bir eğitim örneği hangi alanları taşıyacak (eksiltilmiş BBF + soru-cevap + rapor + hedef patent)?
- `quality` kopya ölçüsü/eşiği (n-gram / LCS) ve kapsama bölme (kod / LLM)?
- `bbf` madde_id: BB ve OT ikisi de K03; kontrol listesiyle doğrula.
