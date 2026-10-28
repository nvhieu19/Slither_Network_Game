# Neon Slither — Đồ án Lập trình mạng

Game rắn săn mồi nhiều người chơi, client đồ họa **Python + Pygame-CE**, server **Python TCP đa luồng** có quyền quyết định trạng thái. MySQL lưu tài khoản, phòng và lịch sử; SQLite là chế độ demo riêng để thử nhanh.

**Bắt đầu nhanh trên Windows:** giải nén toàn bộ ZIP → vào `source` → chạy `setup.bat` một lần → chạy `demo.bat`. Hai cửa sổ client thật kết nối tới một server thật qua TCP. Tạo phòng ở cửa sổ thứ nhất, tham gia từ cửa sổ thứ hai rồi bấm **Bắt đầu trận**.

## 1. Nội dung bàn giao

| Đường dẫn                                      | Nội dung                                                                                  |
| -------------------------------------------------- | ------------------------------------------------------------------------------------------ |
| `Bao_Cao/Bao_Cao_Ran_San_Moi_Client_Server.docx` | Báo cáo hoàn chỉnh 3 chương, sơ đồ thiết kế, ảnh game và kết quả kiểm thử |
| `source/`                                        | Toàn bộ mã nguồn client, server, giao thức, kiểm thử và công cụ chạy            |
| `database/schema_mysql.sql`                      | Script MySQL tạo CSDL, 3 bảng, khóa ngoại, chỉ mục                                   |
| `docs/PROTOCOL.md`                               | Giao thức TCP, định dạng JSON và quy tắc xử lý                                     |
| `docs/TEST_RESULTS.md`                           | Kết quả đã chạy và những môi trường chưa xác minh                              |
| `docs/load_result.json`                          | Số đo mẫu tải 8 client và 4 bot trên localhost                                       |
| `docs/screenshots/`                              | Ảnh chụp từ giao diện game chạy thật trong kiểm thử                                |
| `README.md`                                      | Hướng dẫn cài đặt, chạy LAN và phân công 5 thành viên                          |

Không có dữ liệu tài khoản thật, mật khẩu cấu hình, thư mục môi trường ảo hoặc gói cài đặt Python trong ZIP. Cần Internet **lúc cài thư viện**; sau đó client và server chơi qua mạng LAN mà không cần dịch vụ bên ngoài.

## 2. Chức năng

- Đăng ký, đăng nhập, băm mật khẩu có salt, phiên đăng nhập và đăng xuất.
- Đổi tên hiển thị, chọn 6 skin; lưu hồ sơ vào CSDL.
- Danh sách phòng, vào nhanh, tạo phòng 2–8 người, thêm 0–4 bot, chủ phòng bắt đầu trận.
- Chat trong phòng và trong trận; chủ phòng mời người khác ra khi đang chờ; tự chuyển chủ phòng khi chủ cũ rời đi.
- Bản đồ 3000 × 3000; rắn lái 360 độ, thân bám theo, ăn mồi và tăng trưởng.
- Bứt tốc có tiêu hao điểm; va tường, va thân đối thủ, va đầu; thân rắn chết biến thành mồi.
- Khiên xuất hiện 2 giây chống va chạm với rắn khác, **không chống tường**; hồi sinh và chơi tiếp.
- Camera bám theo, hiệu ứng sáng, hạt vỡ, minimap, bảng điểm Top 10 và bảng kết quả.
- Bảng xếp hạng tài khoản Top 50 và lịch sử 20 lượt gần nhất, loại trừ bot.
- Tách/gộp gói TCP đúng bằng JSON + LF, heartbeat, giới hạn gói tin, thử kết nối lại tối đa 3 lần.
- Console server: `status`, `rooms`, `kick USERNAME`, `stop`; log có thời điểm và số đo tick.

## 3. Môi trường và cài đặt

Khuyến nghị **Python 3.12 64-bit**, Windows 10/11 hoặc Linux có desktop, màn hình từ 1280 × 800. Mã nguồn dùng Python 3.10+; bản bàn giao được kiểm thử với Python 3.12.14 trên Linux. MySQL Server 8.0+ / 8.4 được dùng cho chế độ MySQL. Không cài đồng thời `pygame` và `pygame-ce` trong cùng môi trường.

### Windows

1. Cài Python 3.12, chọn Python Launcher và thêm Python vào PATH.
2. Giải nén ZIP vào thư mục có quyền ghi; mở `source/setup.bat`.
3. Chờ cài xong `pygame-ce==2.5.8` và `mysql-connector-python==26.7.0`.

Cách làm bằng PowerShell nếu không dùng BAT:

```powershell
cd source
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### Linux hoặc macOS

```bash
cd source
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m tools.run_demo --clients 2
```

Có thể dùng `bash setup.sh` để thực hiện hai bước cài đặt. Cần phiên desktop để chơi; SDL dummy chỉ dành cho kiểm thử tự động, không hiển thị cửa sổ.

## 4. Chạy demo nhanh bằng SQLite

Trong `source`, chạy `demo.bat` hoặc:

```powershell
.venv\Scripts\python.exe -m tools.run_demo --clients 2
```

Demo tạo `data/demo.db`, khởi động server ở `127.0.0.1:5555` và đăng nhập hai tài khoản `demo_one`, `demo_two`, mật khẩu dùng riêng cho demo là `SlitherDemo2026`. Demo luôn chọn SQLite, không dùng MySQL trong `.env`. Các tài khoản này **chỉ là tài khoản thử nghiệm**, không dùng lại mật khẩu cho mục đích khác.

Tạo phòng ở một cửa sổ, chọn 0–4 bot, vào phòng từ cửa sổ còn lại, chủ phòng bấm bắt đầu. Thu nhỏ hoặc di chuyển hai cửa sổ để quan sát. Đóng cả hai cửa sổ sẽ dừng demo. Nếu cổng bận: `python -m tools.run_demo --clients 2 --port 5556`.

Chạy riêng từng tiến trình để hiểu kiến trúc:

```powershell
# Terminal 1
.venv\Scripts\python.exe -m server --database sqlite --console
# Terminal 2, và có thể mở thêm Terminal 3
.venv\Scripts\python.exe -m client
```

Server độc lập dùng `data/slither.db`. Client chỉ nhập IP/cổng và tài khoản, không cần mở CSDL. Không mở trực tiếp file `client/app.py`; dùng `python -m client` từ thư mục `source` để import đúng các module.

## 5. Cấu hình MySQL theo đề tài

### Bước 1 — Tạo CSDL

Mở MySQL Workbench, kết nối tới MySQL Server rồi mở và chạy **toàn bộ** `database/schema_mysql.sql`. Script tạo `slither_network` và các bảng:

| Bảng             | Mục đích                                                                                                          |
| ----------------- | -------------------------------------------------------------------------------------------------------------------- |
| `users`         | Tài khoản, hash mật khẩu, tên hiển thị, màu rắn, kỷ lục                                                   |
| `rooms`         | Mã phòng, người tạo, sức chứa, trạng thái, thời gian tạo/đóng                                           |
| `match_history` | Mỗi lượt sống có`run_id` duy nhất, điểm đỉnh/cuối, độ dài tối đa, thời gian và lý do kết thúc |

Hoặc dùng MySQL Command Line Client:

```sql
SOURCE C:/duong_dan/Slither_Network_Game/database/schema_mysql.sql;
```

Tạo người dùng ứng dụng bằng tài khoản quản trị MySQL; thay mật khẩu mẫu:

```sql
CREATE USER 'slither_app'@'localhost' IDENTIFIED BY 'MatKhauRiengCuaBan';
GRANT SELECT, INSERT, UPDATE ON slither_network.* TO 'slither_app'@'localhost';
```

Nếu MySQL nằm trên máy khác, cấu hình host của tài khoản theo máy server game. Máy client game **không truy cập trực tiếp cổng MySQL 3306**.

### Bước 2 — Cấu hình server

Sao chép `source/.env.example` thành `source/.env`, sửa `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_HOST` và `MYSQL_PORT` cho đúng. Ví dụ:

```ini
DATABASE_MODE=mysql
SERVER_HOST=0.0.0.0
SERVER_PORT=5555
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_USER=slither_app
MYSQL_PASSWORD=MatKhauRiengCuaBan
MYSQL_DATABASE=slither_network
```

Không có `.env` thì server mặc định SQLite; để chắc chắn dùng MySQL, chạy:

```powershell
.venv\Scripts\python.exe -m server --database mysql --host 0.0.0.0 --console
```

Console phải có `db=mysql`. Nếu kết nối MySQL thất bại, server báo lỗi và dừng, **không tự chuyển** sang SQLite. `.env` đọc ở phía server; không gửi file này cho máy client.

### Bước 3 — Kiểm tra dữ liệu

Đăng ký tài khoản từ client, tạo phòng và hoàn thành một lượt. Trong Workbench:

```sql
USE slither_network;
SELECT username, display_name, highest_score FROM users;
SELECT id, name, status FROM rooms ORDER BY created_at DESC;
SELECT u.username, h.score, h.final_score, h.max_length,
       h.duration_seconds, h.death_reason, h.played_at
FROM match_history h JOIN users u ON u.id = h.user_id
ORDER BY h.id DESC LIMIT 20;
```

Công cụ `python -m tools.check_mysql` kiểm tra pool, đăng ký, khóa ngoại, lưu lịch sử và chống ghi trùng. Công cụ tạo một tài khoản có tiền tố `qa_` và một phòng kiểm thử trong CSDL đang cấu hình; các bản ghi được giữ lại để xem. Chỉ chạy với CSDL phát triển của đồ án. Bản bàn giao **chưa được chạy với một MySQL Server thật** trong môi trường xây dựng; cần thực hiện bước này trên máy có MySQL trước buổi bảo vệ.

## 6. Chạy nhiều máy qua LAN

1. Máy A chạy MySQL nếu dùng MySQL; chạy game server với `--host 0.0.0.0`.
2. Trên máy A, xem IPv4 bằng `ipconfig` (Windows) hoặc `ip addr` (Linux), ví dụ `192.168.1.10`.
3. Cho phép Python/server và TCP 5555 qua tường lửa trên mạng nội bộ. Không cần mở cổng 3306 cho máy chơi game.
4. Máy B/C cài thư viện rồi chạy `python -m client --host 192.168.1.10 --port 5555`, hoặc nhập IP/cổng ở màn hình đăng nhập.
5. Mỗi máy đăng ký tài khoản khác nhau, tham gia cùng phòng. `127.0.0.1` chỉ trỏ tới chính máy đang chạy client, không trỏ tới máy A.

Mục tiêu bàn giao là demo và LAN. Giao thức hiện tại chưa có TLS; triển khai Internet cần bổ sung TLS/VPN, cấu hình định tuyến và kiểm thử độ trễ thực tế. Không coi các kết quả localhost là bằng chứng về hiệu năng WAN.

## 7. Điều khiển và luật chơi

| Thao tác                     | Kết quả                                                                       |
| ----------------------------- | ------------------------------------------------------------------------------- |
| Di chuyển chuột             | Rắn hướng về con trỏ; góc quay có giới hạn để chuyển hướng mượt |
| WASD hoặc phím mũi tên    | Điều hướng bằng bàn phím                                                 |
| Giữ Space hoặc chuột trái | Bứt tốc nếu có ít nhất 5 điểm                                           |
| Enter                         | Mở chat trong trận; Enter lần nữa để gửi                                 |
| R sau khi chết               | Hồi sinh trong cùng phòng                                                    |
| Esc                           | Đóng hộp thoại/chat; nếu không có hộp thoại thì rời phòng           |
| F1 / F11                      | Hướng dẫn / toàn màn hình                                                 |
| Tab                           | Chuyển ô nhập liệu                                                          |

- Tốc độ thường 145 px/s, bứt tốc 245 px/s; cứ 0,18 giây bứt tốc mất 1 điểm và để lại mồi phía đuôi.
- Mồi thường +1, mồi từ xác rắn +2. Thân ban đầu 18 đốt, tăng 1 đốt mỗi 2 điểm, tối đa 180 đốt.
- Chạm tường hoặc đầu chạm thân đối thủ thì chết. Không tự va chạm với thân mình. Đầu đối đầu được xét đồng thời; cả hai có thể chết.
- Điểm kỷ lục và trường `score` trong lịch sử là **điểm cao nhất từng đạt trong lượt**; `final_score` là điểm khi kết thúc sau tiêu hao bứt tốc.
- Rời phòng/mất kết nối kết thúc lượt hiện tại. Reconnect dùng token còn hạn để trở về sảnh; không tiếp tục con rắn cũ. Khi server khởi động lại, token cũ hết hiệu lực và phải đăng nhập lại.
- Không có tạm dừng toàn trận. Mở hướng dẫn hoặc chat không dừng các người chơi khác.

## 8. Kiến trúc và đường dẫn mã nguồn

| Module                 | Trách nhiệm                                                              |
| ---------------------- | -------------------------------------------------------------------------- |
| `client/app.py`      | Chuyển màn hình, xử lý input, HUD, phòng, chat, bảng kết quả      |
| `client/graphics.py` | Nội suy, camera, rắn, mồi, minimap, hiệu ứng hạt                     |
| `client/widgets.py`  | Bộ widget, font có dấu, nút, ô nhập và giới hạn hiển thị        |
| `client/network.py`  | Thread nền gửi/nhận, heartbeat, hàng đợi, reconnect                  |
| `common/protocol.py` | JSON UTF-8 kết thúc LF, buffer, giới hạn frame, kiểm tra số          |
| `common/config.py`   | Tham số chung của trò chơi và giao thức                              |
| `server/app.py`      | Session, phòng, phân quyền chủ phòng, tick, broadcast và ghi DB nền |
| `server/engine.py`   | Luật vật lý, spatial grid, va chạm đồng thời, bot, snapshot         |
| `server/database.py` | PBKDF2, repository MySQL/SQLite, transaction, connection pool              |
| `server/__main__.py` | Cấu hình môi trường, CLI và console quản trị cục bộ              |
| `tests/`             | Kiểm thử giao thức, engine, CSDL và TCP thật                          |
| `tools/`             | Demo, kiểm thử GUI, tải nhỏ và kiểm tra MySQL                        |

Server tính vật lý 30 Hz, gửi snapshot 15 Hz. Client gửi input tối đa 30 Hz và đặt mục tiêu vẽ 60 FPS. Nội suy trễ khoảng 100 ms giữa các snapshot. Đây là cấu hình triển khai có chủ ý, điều chỉnh từ đề xuất 30/60 Hz trong tài liệu tham khảo để hạn chế chi phí truyền toàn bộ JSON. Không có client-side prediction hoặc lag compensation cho va chạm.

Mỗi kết nối có thread đọc/ghi riêng. Snapshot chưa gửi được thay bằng snapshot mới nhất; gói điều khiển có hàng đợi giới hạn. Ghi lịch sử qua một worker riêng, tối đa 3 lần thử. Server dùng một khóa trạng thái để đồng bộ quản lý phòng và engine; không giữ khóa khi gửi socket. Một tiến trình server sở hữu một CSDL đồ án và các phòng đang chạy.

## 9. Phân công 5 thành viên

Tài liệu tham khảo chỉ ghi Thành viên 1–5, không có họ tên/MSSV. Bảng này giữ đúng 5 vai trò để nhóm tự gắn danh tính; đây là **phân công đề xuất cho việc tiếp nhận, kiểm tra và bảo vệ dự án**, không phải xác nhận ai đã tự viết phần nào.

| Thành viên                        | Phần phụ trách             | Công việc cụ thể                                                                                                                                                             | File chính                                                                                                                                     | Tiêu chí bàn giao và phần cần thuyết trình                                                                                |
| ----------------------------------- | ----------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| **1 — Client gameplay**      | Đồ họa và điều khiển   | T1.1 Chuột/keyboard; T1.2 góc atan2; T1.3 nội suy và camera; T1.4 thân rắn/mắt; T1.5 glow, mồi và hạt vỡ; T1.6 hiển thị boost                                       | `client/graphics.py`, phần input trong `client/app.py`                                                                                     | Chạy trận có nhiều rắn, giải thích nội suy, tọa độ world/screen, render không thay đổi trạng thái server          |
| **2 — UI và trải nghiệm** | Auth, lobby, room, HUD        | T2.1 luồng màn hình; T2.2 form có dấu và kiểm tra ô nhập; T2.3 danh sách phòng có cuộn; T2.4 hồ sơ/skin; T2.5 chat, leaderboard, minimap; T2.6 death/history/help | `client/app.py`, `client/widgets.py`, `tools/gui_smoke.py`                                                                                | Demo đăng ký → phòng → game → hồi sinh → sảnh; kiểm tra F11, Tab, lỗi đầu vào và bố cục                         |
| **3 — Lập trình mạng**    | Socket và giao thức         | T3.1 bảng gói tin; T3.2 encode/decode; T3.3 phân mảnh/gộp frame; T3.4 thread mạng, hàng đợi; T3.5 heartbeat, reconnect, session token                                   | `common/protocol.py`, `client/network.py`, phần `Session` trong `server/app.py`, `tests/test_protocol.py`, `tests/test_network.py` | Giải thích TCP là luồng byte, biểu diễn một gói JSON, chứng minh 2 client thật và lỗi mất kết nối                  |
| **4 — Server và vật lý**  | Trọng tài trận đấu       | T4.1 quản lý phòng/host; T4.2 fixed tick; T4.3 spatial grid; T4.4 ăn mồi, tăng trưởng; T4.5 boost, va chạm, xác rắn; T4.6 bot, broadcast, giới hạn tải             | `server/engine.py`, `server/app.py`, `common/config.py`, `tests/test_engine.py`, `tools/load_test.py`                                 | Giải thích vì sao client không tự cộng điểm; demo va tường, đầu đối đầu, host transfer và tick metrics           |
| **5 — CSDL và báo cáo**   | MySQL, thống kê, tài liệu | T5.1 schema/FK/index; T5.2 pool/repository; T5.3 PBKDF2; T5.4 transaction, unique run_id; T5.5 Top 50/history; T5.6 báo cáo/sơ đồ, hướng dẫn và đóng gói             | `database/schema_mysql.sql`, `server/database.py`, `tests/test_database.py`, `tools/check_mysql.py`, báo cáo và README               | Cài MySQL thật, chạy check_mysql, xem bản ghi sau trận; giải thích ERD, chỉ mục, lưu kỷ lục và giới hạn kiểm thử |

Phối hợp tích hợp: TV3 chốt schema gói tin với TV1/2/4 trước; TV4 thống nhất cấu trúc kết quả với TV5; TV1/2 chỉ đọc snapshot; TV5 kiểm tra MySQL; cả nhóm chạy lại bộ test và demo trên ít nhất hai máy trong cùng LAN. Khi thay luật, sửa `common/config.py`, cập nhật README/báo cáo và chạy lại kiểm thử liên quan.

## 10. Kiểm thử và kết quả đã xác minh

Trong thư mục `source`:

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -v
.venv\Scripts\python.exe -m tools.gui_smoke --out data/screenshots
.venv\Scripts\python.exe -m tools.load_test --seconds 10
```

- **29/29 kiểm thử đạt**, gồm giao thức, vật lý, SQLite và TCP thật.
- GUI smoke đạt luồng đăng ký, lưu hồ sơ, tạo/tham gia phòng, chat, game, death, respawn, history và reconnect.
- Mẫu tải localhost: 8 client + 4 bot trong 10,05 giây, tick trung vị 3,672 ms, p95 5,469 ms, snapshot trung bình 20.550 byte, không có lỗi worker. Đây là mẫu ngắn trong môi trường kiểm thử, không phải cam kết cho mọi máy.
- Đã kiểm tra ảnh render bằng SDL dummy. Chưa kiểm chứng thao tác thủ công trên Windows/macOS, hai máy LAN thật, MySQL Server thật, Internet hoặc tải kéo dài.

`tools/gui_smoke.py` chủ động đặt vị trí/điểm đầu vào trên **server kiểm thử riêng** để chụp các thành phần giao diện trong cùng một khung hình và ép sự kiện chết tái lập được. Nó không thêm API gian lận vào server thật. Các ảnh đó minh họa UI; không dùng làm dữ liệu đo hiệu năng.

## 11. Lỗi thường gặp

| Hiện tượng                             | Cách xử lý                                                                                                                                 |
| ----------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| `No module named pygame`                | Dùng đúng Python trong`.venv`; cài `requirements.txt`; không cài trùng `pygame`                                                  |
| Không đăng nhập được               | Chạy server trước; kiểm tra IP/cổng; dùng nút Đăng ký nếu chưa có tài khoản                                                    |
| `Address already in use`                | Đóng server cũ hoặc đổi cổng đồng thời ở server/client                                                                             |
| Máy khác không kết nối LAN           | Server phải bind`0.0.0.0`; nhập IP LAN thật; kiểm tra firewall TCP 5555 và Wi-Fi client isolation                                      |
| MySQL access denied / unknown database    | Import SQL, kiểm tra user/host/password, cổng và quyền trong`.env`                                                                      |
| MySQL dừng giữa trận                   | Xem`source/data/server.log`; ghi lịch sử thử lại 3 lần, chưa có outbox bền vững, nên không bảo đảm lưu khi DB lỗi kéo dài |
| Bảng xếp hạng chưa đổi ngay         | Kỷ lục được lưu khi lượt kết thúc; đợi một nhịp lưu rồi mở lại bảng                                                        |
| Mở 2 cửa sổ nhưng cùng tài khoản   | Mỗi kết nối cần một tài khoản khác nhau                                                                                               |
| Mất mạng quay về sảnh                 | Thiết kế reconnect không giữ lượt đang chơi; vào lại phòng để tạo lượt mới                                                   |
| Rắn vẫn di chuyển khi mở hướng dẫn | Trận multiplayer không có pause toàn cục                                                                                                 |

## 12. Giới hạn và hướng mở rộng

Full snapshot JSON đơn giản để học và gỡ lỗi nhưng tốn băng thông khi có nhiều thực thể. Tối ưu tiếp theo có thể là AOI/delta snapshot, mã hóa nhị phân, TLS, heartbeat thích nghi, quản trị có phân quyền, outbox bền vững và đo tải dài hạn. Tài khoản chưa có khôi phục mật khẩu hoặc MFA. Log/SQL được quản lý trên máy server; không có dịch vụ cloud bắt buộc.

Font DejaVu được đóng gói với giấy phép tại `source/assets/fonts/LICENSE.txt`. Đồ họa game được vẽ bằng code, không dùng hình thương mại bên ngoài. Các tài liệu gốc dùng để tham khảo yêu cầu; báo cáo mới giải thích đúng bản triển khai này.
