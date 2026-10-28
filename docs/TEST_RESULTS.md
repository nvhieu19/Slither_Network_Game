 

# Kết quả kiểm thử bản bàn giao

## Môi trường  

- Linux x86_64, Python 3.12.14, Pygame-CE 2.5.8, SDL 2.32.10.
- MySQL Connector/Python 26.7.0 đã cài; không có dịch vụ MySQL Server để kiểm thử tích hợp trong môi trường này.
- CSDL kiểm thử là SQLite tạm, TCP thật trên localhost, GUI dùng `SDL_VIDEODRIVER=dummy`.

## Bộ kiểm thử chức năng

Lệnh: `python -m unittest discover -s tests -v`.

| Nhóm             |       Số ca | Kết quả                                                                                            |
| ----------------- | -----------: | ---------------------------------------------------------------------------------------------------- |
| Giao thức        |            5 | Đạt: Unicode, phân mảnh/gộp, JSON lỗi, kích thước, số hữu hạn                            |
| Vật lý          |           13 | Đạt: di chuyển, ăn mồi, boost, va tường/thân/đầu, khiên, hồi sinh, grid, giới hạn mồi |
| Repository SQLite |            4 | Đạt: hash/salt, validation, idempotency, kỷ lục, lưu hồ sơ                                    |
| TCP tích hợp    |            7 | Đạt: auth, room, chat, host, capacity/kick/host transfer, snapshot, forged input, history, resume  |
| **Tổng**   | **29** | **Đạt toàn bộ**                                                                            |

Chi tiết stdout/stderr nằm trong `test_run.txt`. Các bài test dùng thư mục tạm và không ghi đè dữ liệu người dùng.

## Giao diện và reconnect

Lệnh: `python -m tools.gui_smoke --out ../docs/screenshots`.

Đã xác minh luồng đăng ký → lưu hồ sơ → tạo/tham gia phòng với 2 kết nối TCP → chat → bắt đầu game → nhận snapshot → chết do tường → hồi sinh → rời phòng → xem lịch sử → ngắt socket → tự resume về sảnh.

Ảnh được chụp từ canvas Pygame thật. Công cụ đặt các rắn gần nhau trên server kiểm thử để ảnh trận đấu dễ quan sát, sau đó đưa đầu rắn tới biên để kiểm tra chết. Đây là dữ liệu kiểm thử có kiểm soát, không phải minh chứng về một trận đấu tự nhiên kéo dài. `gui_test_run.txt` chứa kết quả.

## Mẫu tải ngắn

Dữ liệu gốc: `load_result.json`. Lệnh: `python -m tools.load_test --seconds 10`.

| Chỉ số                           | Giá trị quan sát |
| ---------------------------------- | ------------------: |
| Kết nối client thật             |                   8 |
| Bot phía server                   |                   4 |
| Thời lượng                      |         10,05 giây |
| Tick vật lý cấu hình           |               30 Hz |
| Snapshot cấu hình                |               15 Hz |
| Thời gian tick trung vị          |            3,672 ms |
| Thời gian tick p95                |            5,469 ms |
| Kích thước snapshot trung bình |         20.550 byte |
| Snapshot nhận mỗi client         |            151–152 |
| Lỗi worker                        |                   0 |

Thời gian tick được lấy mẫu khoảng 50 ms/lần từ `server.tick_ms`; đây là thời gian xử lý một vòng server gồm mô phỏng và bước xếp gói gửi, không phải độ trễ end-to-end. p95 là phân vị theo mẫu lấy được. Số snapshot có thể bao gồm bản đầu tiên đang chờ trước lúc bắt đầu khoảng đo.

Ước lượng từ snapshot quan sát: 20.550 × 15 ≈ 308.250 byte/s/client, khoảng 301 KiB/s, chưa tính header TCP/IP. Với 8 client, tổng payload khoảng 2,35 MiB/s. Đây là phép tính từ mẫu ngắn, không phải phép đo lưu lượng trên NIC.

## Chưa xác minh

- MySQL Server thật, Windows/macOS desktop, hai máy vật lý qua LAN, mạng Internet, mất gói có mô phỏng và tải kéo dài.
- Khi MySQL ngừng lâu hơn ba lần thử ghi, kết quả lượt có thể không được lưu; có log lỗi nhưng chưa có outbox trên đĩa.
- Chưa cam kết 60 FPS trên mọi GPU/CPU, 64 kết nối đồng thời hoặc 16 phòng đầy. Đây là giới hạn cấu hình, không phải thông lượng đã được đo.

Trước buổi bảo vệ: TV5 chạy `python -m tools.check_mysql` với MySQL đồ án; TV3 và TV4 thực hiện demo trên hai máy LAN; TV1/TV2 kiểm tra F11, các nút, nhập liệu tiếng Việt và resize trên hệ điều hành sử dụng thực tế.
