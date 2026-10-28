# Giao thức Neon Slither phiên bản 1

## Truyền tải và đóng khung

TCP IPv4, cổng mặc định 5555. Mỗi thông điệp là một JSON object UTF-8, kết thúc bằng một byte LF (`0x0A`). Newline trong nội dung chuỗi được JSON escape. Một lần `recv()` có thể chứa một phần hoặc nhiều thông điệp. `FrameDecoder` giữ buffer, chỉ tách tại LF và giữ phần dư cho lần nhận sau.

Client → server: tối đa 8.192 byte/frame. Server → client: tối đa 262.144 byte/frame. Thiếu `type`, JSON sai, UTF-8 sai, NaN/Infinity hoặc frame quá giới hạn làm đóng kết nối. Lỗi nghiệp vụ trả `ERROR` và giữ kết nối. Server giới hạn 150 gói/giây/kết nối; tối đa 64 kết nối và 16 phòng. `TCP_NODELAY` bật ở hai phía.

## Gói tin

| Chiều | type | Trường chính | Kết quả / điều kiện |
|---|---|---|---|
| S→C | HELLO | protocol | Thông báo phiên bản 1 |
| C→S | REGISTER | username, password, name | Tạo tài khoản; thành công trả AUTH_OK rồi LOBBY |
| C→S | LOGIN | username, password | Chỉ một kết nối sử dụng một tài khoản |
| C→S | RESUME | token | Token hợp lệ khôi phục tài khoản về sảnh, quay vòng token |
| S→C | AUTH_OK | user, token, resumed | user chỉ chứa thông tin công khai, không có password_hash |
| S→C | AUTH_EXPIRED | — | Client phải đăng nhập lại |
| C→S | LOGOUT | — | Xóa token, rời phòng, trả LOGGED_OUT |
| C→S | LIST_ROOMS | — | Trả LOBBY |
| S→C | LOBBY | rooms, user | Phòng chờ và phòng đang chơi còn được liệt kê |
| C→S | PROFILE | name, skin | Chỉ sửa tại sảnh; trả PROFILE_OK |
| C→S | CREATE_ROOM | name, capacity, bots | capacity 2–8, bots 0–4; người tạo là chủ phòng |
| C→S | JOIN_ROOM | room_id | Kiểm tra tồn tại và số chỗ trống |
| C→S | QUICK_JOIN | — | Chọn phòng còn chỗ; nếu chưa có thì tạo phòng mới |
| S→C | ROOM_STATE | id, name, host, capacity, bots, status, members, chat | WAITING hoặc PLAYING; chỉ thành viên phòng nhận |
| C→S | START_GAME | — | Chỉ host; tạo Arena, spawn rắn và bot |
| C→S | PLAYER_INPUT | angle, boost, seq | angle hữu hạn; boost boolean; seq tăng; không nhận vị trí/điểm từ client |
| S→C | WORLD_STATE | room_id, tick, size, snakes, food, top | Toàn bộ snapshot 15 Hz |
| S→C | DEATH | id, run_id, reason, score, final_score, max_length, duration, bot | Thông báo kết thúc một lượt |
| C→S | RESPAWN | — | Chỉ tạo rắn mới nếu rắn cũ đã chết |
| S→C | RESPAWN_OK | — | Client xóa bộ đệm render cũ |
| C→S | CHAT | text | 1–160 ký tự, cách nhau ít nhất 0,5 giây |
| S→C | CHAT | name, text | Server gắn tên người gửi từ session |
| C→S | KICK | player_id | Chỉ host, chỉ phòng chờ, không tự kick |
| S→C | KICKED | message | Người bị kick trở về sảnh |
| C→S | LEAVE_ROOM | — | Kết thúc lượt, thu hồi rắn, trả LEFT_ROOM và LOBBY |
| C→S | LEADERBOARD | — | Trả tối đa 50 hồ sơ xếp theo highest_score |
| C→S | HISTORY | — | Trả 20 lượt gần nhất của chính session |
| C→S | PING | stamp | Heartbeat và đo RTT |
| S→C | PONG | stamp | Phản hồi mốc thời gian của client |
| S→C | ERROR | message | Mô tả lỗi nghiệp vụ, không chứa mật khẩu/cấu hình DB |

`NET_CONNECTED`, `NET_CONNECTING`, `NET_RETRY`, `NET_FAILED` là sự kiện **nội bộ client**, không đi qua TCP.

## Ví dụ thông điệp

```json
{"type":"PLAYER_INPUT","angle":1.25,"boost":true,"seq":42}
```

```json
{"type":"CREATE_ROOM","name":"Nhóm lập trình mạng","capacity":8,"bots":2}
```

`snakes` trong WORLD_STATE chứa id, name, color, score, peak, alive, boost, shield, angle, bot, reason, age và mảng `body` gồm các cặp [x,y]. `food` gồm các mảng `[food_id,x,y,value,color]`. `top` chỉ chứa id/name/score/color của tối đa 10 rắn sống.

## Quyền quyết định và thứ tự

ID người chơi lấy từ session đã đăng nhập. Client không tự chọn người gửi, không cung cấp vị trí để server chấp nhận, không tự tính điểm hoặc yêu cầu ghi DB. `seq` cũ bị bỏ; input quá gần nhau dưới 1/90 giây bị bỏ. Giới hạn tốc độ/quay/collision nằm trên server.

Thread reader giải mã yêu cầu; server khóa trạng thái khi thay đổi phòng hoặc engine. Thread writer riêng thực hiện `sendall`. Gói điều khiển theo FIFO tối đa 128 mục; world chưa gửi được thay bằng bản mới nhất. TCP vẫn giữ thứ tự và có head-of-line blocking; thay snapshot chưa gửi không loại bỏ gói đã nằm trong kernel TCP buffer.

## Kết nối lại

Client gửi PING mỗi 2 giây, phát hiện im lặng quá 8 giây và thử nối lại 3 lần với khoảng đợi 1/2/3 giây. Server đóng kết nối im lặng quá 15 giây. Token ngẫu nhiên giữ trong RAM và còn hạn 120 giây sau ngắt kết nối. Token quay vòng sau resume, bị hủy khi logout; server restart làm mất token.

Mất kết nối kết thúc lượt và ghi điểm. Resume đưa về lobby; người dùng tham gia lại phòng và nhận một con rắn mới. Không lưu mật khẩu ở client; token không lưu ra đĩa. Chưa có TLS ở phiên bản này, vì vậy giao thức được thiết kế cho demo/LAN tin cậy.
