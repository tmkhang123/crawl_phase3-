# Tom tat project crawl/clean data chuoi cua hang

## 1. Bai toan

Muc tieu cua project la thu thap va lam sach du lieu dia diem cua cac chuoi cua hang/brand tai Viet Nam.

Output cuoi cung mong muon la cac file CSV theo tung brand, moi dong la mot store/POI voi schema co dinh:

```text
brand_id,name,address,city,province,lat,lng
```

Yeu cau quan trong:

- Du lieu phai co dia chi va toa do.
- Khong giu dong ngoai Viet Nam.
- Han che giu nham tenant, cong, bai xe, kho, van phong, cong ty.
- Khong dedupe xuyen brand.
- Moi buoc clean/QA phai audit duoc: keep, suspect, reject.

## 2. Du lieu da co

Project co 2 nguon legacy chinh:

```text
phase_1_2/hybrid_v3_controlled/output/final_46_by_brand/
phase_1_2/raw_legacy/data_chainlock_phase2/
```

Trong do:

- Phase 1: 46 brand.
- Phase 2: 69 brand.
- Tong cong sau khi gom: 115 brand.

Output notebook cu nam o:

```text
phase_1_2/notebook/output_clean_phase1_phase2/
phase_1_2/notebook/output_qa_phase1_phase2/
```

Notebook cu da clean duoc schema va dedupe co ban, nhung van con mot so loi business QA:

- Mot so dong nuoc ngoai nhu Campuchia.
- Mot so dong kho/van phong/cong ty.
- Container brand nhu AEON Mall co the lan tenant/cong/bai xe.
- WinMart/WinMart+ co dau hieu thieu coverage.

## 3. Huong moi cua pipeline

Da tach thanh he thong moi trong:

```text
pipeline/
```

Muc tieu cua `pipeline/` la tro thanh he thong crawl/clean/QA dung tu dau cho cac lan sau, khong chi la cong cu top-up.

Folder chinh:

```text
pipeline/
  config/
  crawler/
  crawler_playwright_legacy/
  clean_qa/
  output/
```

Vai tro:

- `config/`: rule brand, registry, regions.
- `crawler/`: crawler chinh bang Gosom.
- `crawler_playwright_legacy/`: crawler Playwright cu, chi de fallback/tham khao.
- `clean_qa/`: normalize, brand QA, dedupe, audit, export.
- `output/`: output moi cua pipeline.

## 4. Crawler hien tai

Crawler chinh la Gosom grid fast-mode.

File chinh:

```text
pipeline/crawler/run_gosom_grid_crawl.py
pipeline/crawler/run_gosom_crawl.py
```

Y tuong:

- Chia cac vung lon thanh grid.
- Moi grid cell chay search theo brand + toa do + radius.
- Gosom tra ve title, address, latitude, longitude, category, rating, cid/place_id...
- Sau do merge, filter alias/blacklist, dedupe va ghi raw candidate.

Ly do dung grid:

- Search theo quan/huyen co the bi gioi han ket qua.
- Brand lon nhu WinMart/WinMart+ co nhieu store trong do thi.
- Grid giup bat store nho tot hon.

Playwright crawler cu van duoc giu rieng:

```text
pipeline/crawler_playwright_legacy/
```

Nhung flow chinh moi khong dung Playwright truoc, vi Gosom nhanh va de batch hon.

## 5. Clean/QA rule-based

File chinh:

```text
pipeline/clean_qa/run_rule_based_pipeline.py
pipeline/config/brand_policy.json
```

Pipeline clean/QA lam cac viec:

1. Load Phase 1 + Phase 2 legacy.
2. Load them cac file crawl moi dang co dang `*_gosom_raw.csv`.
3. Normalize schema ve 7 cot final.
4. Validate toa do trong bbox Viet Nam.
5. Parse/normalize city/province co ban.
6. Ap dung brand policy:
   - alias hop le;
   - blacklist;
   - reject keyword rieng;
   - rule container brand;
   - rule MayCha;
   - rule non-store nhu kho/van phong/cong ty.
7. Dedupe trong cung brand bang:
   - normalized text key;
   - Haversine distance;
   - fuzzy name/address.
8. Export:
   - by brand;
   - master keep;
   - suspect rows;
   - rejected rows;
   - audit summary.

Output clean/QA moi:

```text
pipeline/output/rule_based_with_crawled_data/
```

## 6. Nhung viec da lam

Da lam:

- Gom Phase 1+2 vao `phase_1_2/`.
- Don project root cho gon.
- Tao folder `pipeline/` lam he thong moi.
- Tach crawler Gosom va crawler Playwright legacy.
- Tao rule-based clean/QA pipeline.
- Tao `brand_policy.json` de quan ly alias/blacklist/rule.
- Tao wrapper chay don gian:

```text
pipeline/run_crawl_normal.py
pipeline/run_crawl_proxy.py
pipeline/run_clean_qa.py
pipeline/run_clean_qa_with_crawled_data.py
```

- Chay merge WinMart+ Gosom crawl cu vao baseline:
  - WinMart+ baseline cu: 1,675 rows.
  - WinMart+ sau merge Gosom: 2,583 rows.
- Kiem tra output moi:
  - 115 brand.
  - Khong thieu name/address/lat/lng.
  - Khong co toa do ngoai bbox Viet Nam.
  - Cac dong Campuchia cua BreadTalk/Paris Baguette/Pizza 4P's/The Pizza Company da bi loai khoi keep.

## 7. Tinh trang hien tai

Output tot nhat hien tai:

```text
pipeline/output/rule_based_with_gosom_winmart/
```

Tuy nhien day moi merge them WinMart+ crawl cu, chua crawl them WinMart.

Can lam tiep:

1. Crawl WinMart bang pipeline moi.
2. Clean/QA lai voi tat ca crawled data.
3. Kiem tra `winmart.csv`, `winmart_plus.csv`, `winmart_family.csv`.
4. Neu on, crawl tiep nhom priority.

Lenh crawl WinMart:

```powershell
python pipeline\run_crawl_proxy.py --chains "WinMart"
```

Lenh clean/QA sau khi crawl:

```powershell
python pipeline\run_clean_qa_with_crawled_data.py
```

Lenh crawl nhom priority:

```powershell
python pipeline\run_crawl_proxy.py --chains "Circle K,Highlands Coffee,KFC,Lotteria"
```

Nhom priority hien tai:

```text
Circle K, Highlands Coffee, KFC, Lotteria
```

## 8. Quyet dinh quan trong

- Khong xoa du lieu cu; dung lam baseline.
- Khong merge output crawl thang vao final; tat ca phai qua clean/QA.
- Khong dedupe xuyen brand.
- Bo `ward` trong output final de schema gon va on dinh hon.
- `city` dung truoc `province`.
- `brand_id` de trong theo format yeu cau hien tai.
- Gosom la crawler chinh.
- Playwright crawler chi la fallback/legacy.

## 9. Rui ro con lai

Du lieu Google Maps khong bao dam du 100%.

Rui ro con lai:

- Mot so store co the khong ton tai tren Google Maps.
- Mot so brand lon co the thieu coverage o tinh/quan nho.
- Mot so dong nghi ngo co the nam trong `qa_suspect_rows.csv`, can review thu cong.
- Mot so city/province co the can polish them, vi address Google Maps khong dong nhat.
- Cac con so "tong so store tren web" can nguon chinh chu de doi soat, khong nen tin cac con so research chung chung.

## 10. Huong phat trien tiep

Sau khi Phase 1+2 on:

- Tao job queue bang SQLite.
- Tao mot lenh `run_all.py`.
- Cho phep them brand vao config roi tu crawl/resume/clean/QA.
- Them bao cao coverage theo brand.
- Them dashboard/audit report de xem keep/suspect/reject nhanh.
- Neu co official locator/API cua brand, dung de doi soat coverage, khong merge mu quang.
