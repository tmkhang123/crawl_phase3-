# Pipeline Crawl/Clean/QA Moi

Folder nay la he thong moi dung cho cac lan crawl tiep theo.
Muc tieu: ai muon crawl brand nao thi them brand/config, chay crawler, sau do clean + QA theo rule chung.

## Folder chinh

```text
pipeline/
  config/
    brand_policy.json
    brand_registry_phase1.csv
    brand_registry_phase2.csv
    regions/

  crawler/
    run_gosom_crawl.py
    run_gosom_grid_crawl.py
    run_gosom_hybrid_topup.py
    build_grid_regions.py

  crawler_playwright_legacy/
    raw_gmaps_chainlock_dedup.py
    run_grid_proxy_boost.py

  clean_qa/
    run_rule_based_pipeline.py
    build_gosom_coverage_benchmark.py

  output/
```

## Lenh crawl chinh

### Cach moi: discovery -> crawl theo policy

Dung khi muon crawl nhieu brand ma khong muon tu quyet tung brand lon/nho.

Neu khong muon go brand tren terminal, sua file:

```text
pipeline/brands_to_crawl.txt
```

Moi dong ghi 1 brand, roi chay:

```powershell
python pipeline\run_from_txt.py
```

Lenh nay tu doc file txt va chay discovery.
Discovery mac dinh phu toan quoc theo kieu nhe:

```text
63 tinh/thanh x toi thieu 3 diem truy van moi tinh
```

Buoc 1: discovery nhe de xem brand co tin hieu o vung nao.

```powershell
python pipeline\run_discovery.py --chains "WinMart,AEON Mall,KFC"
```

Discovery khong phai final data. No chi lay tin hieu nhanh de quyet dinh brand nao can grid rong,
brand nao chi can crawl nhe.

Output:

```text
pipeline/output/discovery/discovery_summary.csv
pipeline/output/discovery/crawl_plan.csv
```

`crawl_plan.csv` tu chia route:

```text
grid_dense       brand cuc quan trong, crawl grid rong
grid_large       brand lon, crawl grid cac vung lon + vung co tin hieu
grid_signal      brand vua, crawl grid it vung hon
center_lite      brand nho, chi crawl center nhe
center_container brand kieu AEON Mall/Lotte Mart/GO, crawl nhe va QA chat
center_ambiguous brand ten de nhieu, crawl nhe va QA chat
```

Buoc 2a: crawl theo policy, khong proxy.

```powershell
python pipeline\run_crawl_by_policy_normal.py
```

Buoc 2b: crawl theo policy, co proxy rotating, mac dinh 5 worker.

```powershell
python pipeline\run_crawl_by_policy_proxy.py
```

Co the chi chay mot nhom route:

```powershell
python pipeline\run_crawl_by_policy_proxy.py --routes "grid_dense,grid_large"
```

Hoac chi chay mot vai brand:

```powershell
python pipeline\run_crawl_by_policy_proxy.py --chains "WinMart,WinMart+"
```

Sau khi crawl xong, chay clean + QA:

```powershell
python pipeline\run_clean_qa_with_crawled_data.py
```

### Cach truc tiep: crawl brand cu the

Ban thuong, khong proxy:

```powershell
python pipeline\run_crawl_normal.py --chains "WinMart"
```

Mac dinh:

```text
concurrency=1
output=pipeline/output/crawl_normal/
```

Ban proxy rotating, uu tien toc do:

```powershell
python pipeline\run_crawl_proxy.py --chains "WinMart"
```

Mac dinh:

```text
concurrency=5
output=pipeline/output/crawl_proxy/
```

`run_crawl_proxy.py` doc proxy theo thu tu:

```text
--proxy-url
GMAPS_PROXY_URL trong .env
```

Neu proxy chay loi nhieu, ha worker:

```powershell
python pipeline\run_crawl_proxy.py --chains "WinMart" --concurrency 3
python pipeline\run_crawl_proxy.py --chains "WinMart" --concurrency 2
```

Moi output co progress rieng:

```text
<output>/grid/gosom_progress.csv
```

Rerun cung output se skip vung da completed.

## Vai tro tung nhom

`config/`

Chua rule va danh sach brand/vung. Khi can sua alias, blacklist, rule reject/suspect thi sua trong `config/brand_policy.json`.

`crawler/`

Chua code crawl Google Maps dang dung chinh bang Gosom:

- `run_gosom_grid_crawl.py`: runner de crawl brand bang grid fast-mode.
- `run_gosom_crawl.py`: engine gosom tong quat, duoc wrapper goi ben duoi.
- `run_gosom_hybrid_topup.py`: alias cu de cac lenh dang chay/lenh cu khong bi gay. Khong dung file nay cho flow moi.
- `build_grid_regions.py`: tao grid regions.

`crawler_playwright_legacy/`

Chua code Playwright cu de tham khao/fallback. Day khong phai luong crawl chinh cua pipeline moi.

`clean_qa/`

Chua logic clean, QA, dedupe, audit. Final output van la 7 cot:

```text
brand_id,name,address,city,province,lat,lng
```

`output/`

Noi de output moi cua pipeline sau nay. Khong ghi de vao `phase_1_2`.

## Du lieu phase 1+2 cu nam o dau?

Da duoc gom rieng vao:

```text
phase_1_2/
```

Trong do co:

- notebook clean/QA cu;
- raw phase 2;
- output phase 1;
- output QA/clean cu;
- gosom WinMart+ crawl bo sung cu;
- replay pipeline cu.

## Khi can crawl brand moi

Tam thoi dung crawler trong `pipeline/crawler/`.
Sau khi crawl xong, dua raw output qua module trong `pipeline/clean_qa/`.

## Quy trinh lam day data Phase 1+2 hien tai

Buoc 1: crawl WinMart truoc, vi day la brand dang thieu ro nhat.

```powershell
python pipeline\run_crawl_proxy.py --chains "WinMart"
```

Output crawl nam trong:

```text
pipeline/output/crawl_proxy/
```

Script nay co `gosom_progress.csv`, nen neu dung giua chung thi chay lai cung lenh,
nhung vung da xong se duoc bo qua.

Buoc 2: neu WinMart on, crawl tiep nhom brand quan trong.

```powershell
python pipeline\run_crawl_proxy.py --chains "Circle K,Highlands Coffee,KFC,Lotteria"
```

Nhom nay gom:

```text
Circle K, Highlands Coffee, KFC, Lotteria
```

Output crawl nam trong:

```text
pipeline/output/crawl_proxy/
```

Buoc 3: clean + QA lai toan bo Phase 1+2 kem tat ca file crawl co san.

```powershell
python pipeline\run_clean_qa_with_crawled_data.py
```

Output candidate final nam trong:

```text
pipeline/output/rule_based_with_crawled_data/
```

Day la folder nen kiem tra truoc khi chot final.

Chay clean + QA cho du lieu phase 1+2 da gom vao `phase_1_2`:

```powershell
python pipeline\run_clean_qa.py
```

Output moi nam trong:

```text
pipeline/output/
```

Buoc tiep theo cua he thong moi la them job queue:

```text
pipeline/jobs.sqlite
pipeline/run_all.py
```

Luc do chi can them brand vao config, he thong tu crawl + resume + clean + QA.
