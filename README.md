# Google Maps Crawl Kit

Project nhỏ để crawl thêm brand trên Google Maps.

Lệnh chính:

```powershell
python run_free_crawl.py
```

Không chạy trực tiếp `gmaps_chainlock_crawler.py` nếu không được yêu cầu.

## Danh Sách Brand Theo Ngành

Format:

```text
Brand | status | priority nếu là phase 3
```

Status:

```text
đã crawl     Brand phase 1/phase 2 đã crawl xong
chưa crawl   Brand phase 3 sẽ crawl
```

Priority phase 3:

```text
P1  Crawl trước
P2  Crawl sau
```

### F&B / Beverage / Coffee / Tea

#### phase1 | đã crawl

- Aha Cafe | đã crawl
- Cheese Coffee | đã crawl
- Cộng Cà Phê | đã crawl
- Gong Cha | đã crawl
- Guta Cafe | đã crawl
- Highlands Coffee | đã crawl
- Kafa Café | đã crawl
- Katinat | đã crawl
- Koi Thé | đã crawl
- Mixue | đã crawl
- Phê La | đã crawl
- Phúc Long | đã crawl
- Starbucks | đã crawl
- The Coffee House | đã crawl
- Tocotoco | đã crawl
- Trung Nguyên E-Coffee | đã crawl
- Trung Nguyên Legend | đã crawl

#### phase2 | đã crawl

- Bobapop | đã crawl
- Chuk Chuk | đã crawl
- Ding Tea | đã crawl
- Effoc Coffee | đã crawl
- Gemini Coffee | đã crawl
- MayCha | đã crawl
- Milano Coffee | đã crawl
- Oromia Coffee | đã crawl
- Passio | đã crawl
- Royaltea | đã crawl
- Sharetea | đã crawl
- Viva Star Coffee | đã crawl

#### phase3 | chưa crawl

- Cafe Amazon | chưa crawl | P1
- CoCo Fresh Tea & Juice | chưa crawl | P1
- Hồng Trà Ngô Gia | chưa crawl | P1
- Laha Coffee | chưa crawl | P1
- Laika Cafe | chưa crawl | P1
- Napoli Coffee | chưa crawl | P1
- Ông Bầu Coffee | chưa crawl | P1
- Chagee | chưa crawl | P2
- Comebuy | chưa crawl | P2
- Heekcaa | chưa crawl | P2
- Hồng Trà Bông Trà | chưa crawl | P2
- Juice Box | chưa crawl | P2
- LaSiMi | chưa crawl | P2
- Là Việt Coffee | chưa crawl | P2
- Oola | chưa crawl | P2
- Rang Rang Coffee | chưa crawl | P2
- R&B Tea | chưa crawl | P2
- Smoovie | chưa crawl | P2
- Sunday Basic | chưa crawl | P2
- The Alley | chưa crawl | P2
- Three O'Clock | chưa crawl | P2
- Tiger Sugar | chưa crawl | P2
- Tươi Juice | chưa crawl | P2
- Xing Fu Tang | chưa crawl | P2
- Yi He Tang | chưa crawl | P2

### F&B / Restaurant / QSR / Hotpot / BBQ / Pizza

#### phase2 | đã crawl

- Al Fresco's | đã crawl
- Burger King | đã crawl
- Crystal Jade | đã crawl
- Domino's Pizza | đã crawl
- Gogi House | đã crawl
- Haidilao | đã crawl
- Hotpot Story | đã crawl
- Jollibee | đã crawl
- KFC | đã crawl
- Kichi-Kichi | đã crawl
- King BBQ | đã crawl
- Lotteria | đã crawl
- Manwah | đã crawl
- McDonald's | đã crawl
- Pizza 4P's | đã crawl
- Pizza Hut | đã crawl
- Popeyes | đã crawl
- Sumo BBQ | đã crawl
- Sushi Tei | đã crawl
- Texas Chicken | đã crawl
- ThaiExpress | đã crawl
- The Pizza Company | đã crawl

#### phase3 | chưa crawl

- Marukame Udon | chưa crawl | P1
- Mì Cay Sasin | chưa crawl | P1
- Mì Cay Seoul | chưa crawl | P1
- Nét Huế | chưa crawl | P1
- Phở 24 | chưa crawl | P1
- Sukiya | chưa crawl | P1
- Tokyo Deli | chưa crawl | P1
- Ashima | chưa crawl | P2
- BoGi Pizza | chưa crawl | P2
- Buk Buk | chưa crawl | P2
- Capricciosa | chưa crawl | P2
- Chang Kang Kung | chưa crawl | P2
- Cơm Niêu Sài Gòn | chưa crawl | P2
- Daruma | chưa crawl | P2
- Dodo Pizza | chưa crawl | P2
- Hoàng Yến Buffet | chưa crawl | P2
- Hoàng Yến Cuisine | chưa crawl | P2
- Hoàng Yến Hotpot | chưa crawl | P2
- Hutong | chưa crawl | P2
- iSushi | chưa crawl | P2
- Khao Lao | chưa crawl | P2
- Kpub | chưa crawl | P2
- Meiwei | chưa crawl | P2
- Pepper Lunch | chưa crawl | P2
- Phở Thìn by Sol | chưa crawl | P2
- Quán Bụi | chưa crawl | P2
- San Fu Lou | chưa crawl | P2
- Shogun | chưa crawl | P2
- Sumo Yakiniku | chưa crawl | P2
- Sushi Kei | chưa crawl | P2
- Tasaki BBQ | chưa crawl | P2
- Wrap & Roll | chưa crawl | P2

### Bakery / Dessert

#### phase2 | đã crawl

- ABC Bakery | đã crawl
- Baskin Robbins | đã crawl
- Bonchon | đã crawl
- BreadTalk | đã crawl
- Dairy Queen | đã crawl
- Dunkin' | đã crawl
- Paris Baguette | đã crawl
- Tous les Jours | đã crawl

#### phase3 | chưa crawl

- Brodard Bakery | chưa crawl | P1
- Givral Bakery | chưa crawl | P2
- Savouré Bakery | chưa crawl | P2

### Retail / Supermarket / Convenience

#### phase1 | đã crawl

- 7-Eleven | đã crawl
- AEON Mall | đã crawl
- AEON MaxValu | đã crawl
- Annam Gourmet | đã crawl
- Bách Hóa Xanh | đã crawl
- Cheers | đã crawl
- Circle K | đã crawl
- Coop Food | đã crawl
- Coopmart | đã crawl
- Family Mart | đã crawl
- Farmers Market | đã crawl
- GO! | đã crawl
- GS25 | đã crawl
- Kingfoodmart | đã crawl
- Lotte Mart | đã crawl
- mini Go! | đã crawl
- Ministop | đã crawl
- MM Mega Market | đã crawl
- Satrafoods | đã crawl
- Tops Market | đã crawl
- Vissan | đã crawl
- WinMart | đã crawl
- WinMart+ | đã crawl

#### phase3 | chưa crawl

- BRG Intershop | chưa crawl | P1
- BRGMart | chưa crawl | P1
- Co.opSmile | chưa crawl | P1
- FujiMart | chưa crawl | P1
- LanChi Mart | chưa crawl | P1
- TH true mart | chưa crawl | P1

### Pharmacy / Beauty / Health / Mother & Baby

#### phase1 | đã crawl

- Guardian | đã crawl
- Matsumoto Kiyoshi | đã crawl
- Nhà thuốc An Khang | đã crawl
- Nhà thuốc Long Châu | đã crawl
- Pharmacity | đã crawl
- Watsons | đã crawl

#### phase2 | đã crawl

- AVAKids | đã crawl
- Beauty Box | đã crawl
- Bibo Mart | đã crawl
- Con Cung | đã crawl
- Hasaki | đã crawl
- Kids Plaza | đã crawl
- Medicare | đã crawl
- Sociolla | đã crawl

### Electronics / Mobile

#### phase2 | đã crawl

- CellphoneS | đã crawl
- Di Dong Viet | đã crawl
- Dien May Xanh | đã crawl
- FPT Shop | đã crawl
- Hoang Ha Mobile | đã crawl
- The Gioi Di Dong | đã crawl
- TopZone | đã crawl
- Viettel Store | đã crawl

#### phase3 | chưa crawl

- Điện máy Chợ Lớn | chưa crawl | P1
- MediaMart | chưa crawl | P1
- Nguyễn Kim | chưa crawl | P1
- ShopDunk | chưa crawl | P1

### Fashion / Lifestyle / Jewelry

#### phase2 | đã crawl

- An Phuoc | đã crawl
- Canifa | đã crawl
- Coolmate | đã crawl
- Daiso | đã crawl
- DOJI | đã crawl
- Miniso | đã crawl
- Owen | đã crawl
- PNJ | đã crawl
- Routine | đã crawl
- Uncle Bills | đã crawl
- Yody | đã crawl

#### phase3 | chưa crawl

- Aristino | chưa crawl | P1
- Biluxury | chưa crawl | P1
- Biti's | chưa crawl | P1
- Elise | chưa crawl | P1
- H&M | chưa crawl | P1
- Ivy Moda | chưa crawl | P1
- Muji | chưa crawl | P1
- TokyoLife | chưa crawl | P1
- Uniqlo | chưa crawl | P1
- Zara | chưa crawl | P1
- Biti's Hunter | chưa crawl | P2
- Nem Fashion | chưa crawl | P2

### Bookstore

#### phase3 | chưa crawl

- Fahasa | chưa crawl | P1
- Nhà sách Phương Nam | chưa crawl | P1
- ADCBook | chưa crawl | P2
- Nhã Nam | chưa crawl | P2
- Nhà sách Cá Chép | chưa crawl | P2

## File Cần Xem

```text
brands_to_crawl.txt                      Danh sách brand phase 3 sẽ crawl, mỗi dòng một brand
already_crawled_brands.csv               Brand phase 1/phase 2 đã crawl
phase3_candidates_from_user_research.csv Brand phase 3 chưa crawl, có priority
run_free_crawl.py                        File chạy crawl
```

Các file còn lại là file hệ thống:

```text
gmaps_chainlock_crawler.py               Engine crawl
districts.json                           Danh sách 696 vùng crawl
brand_registry.csv                       File tự sinh từ brands_to_crawl.txt
sample_phase2_last10.csv                 File mẫu output
requirements.txt                         Thư viện cần cài
output/                                  Folder kết quả
```

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

Nếu thấy lỗi kiểu này:

```text
BrowserType.launch: Executable doesn't exist
```

thì máy chưa cài Chromium cho Playwright. Chạy:

```powershell
python -m playwright install chromium
```

Nếu đã lỡ chạy ra nhiều file CSV rỗng/progress đủ 696 vùng, xoá folder `output/` rồi chạy lại từ đầu. Không resume trên output đó.

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
