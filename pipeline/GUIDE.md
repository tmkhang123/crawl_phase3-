

## 1. Cai dat lan dau

Mo terminal tai folder project:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r pipeline\requirements.txt
python -m playwright install chromium
```

Neu may da co `.venv` roi thi chi can activate:

```powershell
.\.venv\Scripts\Activate.ps1
```

## 2. Crawl nhanh mot brand cu the

Khong proxy:

```powershell
python pipeline\run_crawl_normal.py --chains "KFC"
```

Co proxy:

```powershell
python pipeline\run_crawl_proxy.py --chains "KFC"
```

Neu dung proxy, tao file `.env` o goc project va them:

```text
GMAPS_PROXY_URL=http://user:pass@host:port
```

Neu proxy loi nhieu thi ha worker:

```powershell
python pipeline\run_crawl_proxy.py --chains "KFC" --concurrency 3
```

Output crawl nam trong:

```text
pipeline/output/crawl_normal/
pipeline/output/crawl_proxy/
```

Moi output co file progress:

```text
<output>/grid/gosom_progress.csv
```

Neu bi dung giua chung, chay lai cung lenh. Cac vung da xong se duoc skip.

## 3. Cach de nhat: them brand vao file txt

Mo file:

```text
pipeline/brands_to_crawl.txt
```

Moi dong ghi 1 brand:

```text
KFC
Lotteria
Highlands Coffee
```

Sau do chay discovery:

```powershell
python pipeline\run_from_txt.py
```

Lenh nay se doc `pipeline/brands_to_crawl.txt`.
Mac dinh discovery se phu toan quoc theo kieu nhe:

```text
63 tinh/thanh x toi thieu 3 diem truy van moi tinh
```

No nhe hon 696 quan/huyen, nhung phu rong hon viec chi quet HCM/HN/Da Nang.
Sau khi chay xong, script tao:

```text
pipeline/output/discovery/discovery_summary.csv
pipeline/output/discovery/crawl_plan.csv
```

Sau khi co plan, crawl khong proxy:

```powershell
python pipeline\run_crawl_by_policy_normal.py
```

Hoac crawl co proxy:

```powershell
python pipeline\run_crawl_by_policy_proxy.py
```

Neu muon bo qua discovery va crawl truc tiep tat ca brand trong txt:

```powershell
python pipeline\run_from_txt.py --mode normal
```

Co proxy:

```powershell
python pipeline\run_from_txt.py --mode proxy
```

## 4. Crawl nhieu brand theo cach thong minh

Buoc 1: discovery nhe.

```powershell
python pipeline\run_discovery.py --chains "KFC,Lotteria,Highlands Coffee"
```

Discovery mac dinh phu toan quoc theo kieu:

```text
63 tinh/thanh x toi thieu 3 diem truy van moi tinh
```

Discovery se tao:

```text
pipeline/output/discovery/discovery_summary.csv
pipeline/output/discovery/crawl_plan.csv
```

Buoc 2: crawl theo plan.

Khong proxy:

```powershell
python pipeline\run_crawl_by_policy_normal.py
```

Co proxy:

```powershell
python pipeline\run_crawl_by_policy_proxy.py
```

Neu chi muon crawl brand nao do trong plan:

```powershell
python pipeline\run_crawl_by_policy_normal.py --chains "KFC,Lotteria"
```

## 5. Clean va QA sau khi crawl

Sau khi crawl xong, chay:

```powershell
python pipeline\run_clean_qa_with_crawled_data.py
```

Output can xem:

```text
pipeline/output/rule_based_with_crawled_data/master_keep.csv
pipeline/output/rule_based_with_crawled_data/by_brand/
pipeline/output/rule_based_with_crawled_data/audit_summary.csv
pipeline/output/rule_based_with_crawled_data/qa_suspect_rows.csv
pipeline/output/rule_based_with_crawled_data/qa_rejected_rows.csv
```

File giao chinh la cac CSV trong:

```text
pipeline/output/rule_based_with_crawled_data/by_brand/
```

Schema final:

```text
brand_id,name,address,city,province,lat,lng
```

## 6. Khi nao dung script nao?

```text
run_from_txt.py                  Doc pipeline/brands_to_crawl.txt va chay discovery/crawl
run_crawl_normal.py              Crawl 1 vai brand, khong proxy
run_crawl_proxy.py               Crawl 1 vai brand, co proxy
run_discovery.py                 Do nhe de biet brand nen crawl rong hay nhe
run_crawl_by_policy_normal.py    Crawl theo crawl_plan, khong proxy
run_crawl_by_policy_proxy.py     Crawl theo crawl_plan, co proxy
run_clean_qa_with_crawled_data.py Clean + QA + dedupe sau crawl
```

## 7. Luu y quan trong

- Khong lay raw crawl lam final truc tiep.
- Luon chay clean/QA sau crawl.
- Brand nho khong nen crawl grid rong.
- Brand lon nhu WinMart, Circle K, Highlands, KFC co the crawl grid rong.
- Brand container nhu AEON Mall, Lotte Mart, GO de bi dinh tenant/cong/bai xe, nen can QA chat.
- Neu output dang mo trong Excel/VS Code va script bao permission error, dong file CSV do roi chay lai.
