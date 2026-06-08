# Google Maps Crawl Kit

Project nhỏ để crawl thêm brand trên Google Maps.

Lệnh chính:

```powershell
python run_free_crawl.py
```

Không chạy trực tiếp `gmaps_chainlock_crawler.py` nếu không được yêu cầu.

## File Cần Xem

```text
brands_to_crawl.txt                 Danh sách brand sẽ crawl, mỗi dòng một brand
crawl_status_by_industry.txt         Tất cả brand phase 1-3, chia theo ngành, có trạng thái
phase3_priority_plan.txt             Brand phase 3 chia theo P1/P2
already_crawled_brands.csv           Brand đã crawl ở phase 1 và phase 2
phase3_candidates_from_user_research.csv  Brand phase 3 chưa crawl
run_free_crawl.py                    File chạy crawl
```

Các file còn lại là file hệ thống:

```text
gmaps_chainlock_crawler.py           Engine crawl
districts.json                       Danh sách 696 vùng crawl
brand_registry.csv                   File tự sinh từ brands_to_crawl.txt
sample_phase2_last10.csv             File mẫu output
requirements.txt                     Thư viện cần cài
output/                              Folder kết quả
```

## Trạng Thái Brand

Xem file:

```text
crawl_status_by_industry.txt
```

Format:

```text
Brand | phase | status
```

Status chỉ có nghĩa đơn giản:

```text
đã crawl
chưa crawl
```

Phase 1 và phase 2 là các brand đã crawl. Phase 3 là các brand chưa crawl.

## Ưu Tiên Phase 3

Xem file:

```text
phase3_priority_plan.txt
```

Trong đó:

```text
P1  Crawl trước
P2  Crawl sau
```

File `brands_to_crawl.txt` đã được sắp theo thứ tự P1 trước, P2 sau.

## Setup Lần Đầu

Mở terminal trong folder này:

```powershell
cd free_crawl_kit
```

Cài thư viện:

```powershell
python -m pip install -r requirements.txt
python -m playwright install chromium
```

Nếu muốn dùng virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install -r requirements.txt
python -m playwright install chromium
```

## Chạy Thử

Nên chạy thử vài vùng trước:

```powershell
python run_free_crawl.py --sample-regions 5
```

Nếu ổn thì chạy full:

```powershell
python run_free_crawl.py
```

Nếu máy hoặc mạng chậm:

```powershell
python run_free_crawl.py --concurrency 1 --goto-timeout 60000
```

Nếu muốn chạy tiếp từ một brand:

```powershell
python run_free_crawl.py --start-at "Tên Brand"
```

## Thêm Brand Mới

Mở:

```text
brands_to_crawl.txt
```

Thêm mỗi brand một dòng:

```text
Coffee ABC
Pizza ABC
Bakery ABC
```

Sau đó chạy lại:

```powershell
python run_free_crawl.py
```

## Output

Kết quả nằm trong:

```text
output/
```

File cần lấy thường nằm ở:

```text
output/csv_only/{brand_slug}_gmaps_chainlock.csv
```

Schema CSV:

```text
brand_id,name,address,city,province,lat,lng
```

## Resume

Nếu bị tắt máy hoặc đóng terminal, chỉ cần chạy lại:

```powershell
python run_free_crawl.py
```

Crawler sẽ bỏ qua vùng đã xong dựa trên progress log.
