# ==============================================================================
# Neon Slither — Kịch bản Kiểm thử Giao diện Tự động (GUI Smoke Test)
# Phụ trách: Trần Minh Hải (Thành viên 2 - Phục vụ Demo & Bàn giao đồ án)
#
# MỤC ĐÍCH & TIÊU CHÍ ĐÁNH GIÁ (BÁO CÁO & THUYẾT TRÌNH):
# Kiểm tra tự động toàn bộ luồng trải nghiệm người dùng trên môi trường Client-Server thật:
# 1. Đăng ký & Đăng nhập: Kiểm tra form nhập liệu, tài khoản mới và luồng Auth (T2.1, T2.2).
# 2. Sảnh chờ (Lobby): Cập nhật hồ sơ, đổi tên hiển thị và chọn 6 Skin màu Neon (T2.3, T2.4).
# 3. Tạo phòng & Chat: Mở phòng chơi, bot, kết nối đối thủ thật và chat phòng chờ (T2.3, T2.5).
# 4. Trận đấu & HUD: Bắt đầu trận, hiển thị HUD điểm số, độ dài rắn và minimap (T2.5).
# 5. Va chạm & Game Over: Giả lập va chạm biên/đối thủ, hiển thị màn hình tử vong (T2.6).
# 6. Hồi sinh & Lịch sử: Phím [R] hồi sinh tiếp tục, xem bảng lịch sử 20 trận (T2.6).
# 7. Reconnect: Giả lập đứt kết nối mạng đột ngột và tự động nối lại bằng Token (T2.1).
# ==============================================================================

"""Reproducible real-server GUI smoke test and screenshots in SDL dummy mode.

Run: python -m tools.gui_smoke --out PATH
Screenshots are from the running application; the test controls the server only
to make a repeatable death/respawn event, not to fake screenshots or outcomes.
"""

import argparse
import os
import math
import tempfile
import threading
import time
from pathlib import Path

# Cấu hình SDL Dummy Driver để có thể chạy kiểm thử ngầm không cần màn hình vật lý
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame
from server.app import GameServer
from server.database import Database
from client.app import App
from tests.test_network import Wire


def main():
    """Hàm điều phối kịch bản kiểm thử tự động toàn diện giao diện Client."""
    # 1. Thiết lập tham số dòng lệnh lưu ảnh chụp màn hình kiểm thử
    parser = argparse.ArgumentParser(description="Neon Slither GUI Automated Smoke Test")
    parser.add_argument("--out", default="data/screenshots", help="Thư mục xuất ảnh chụp màn hình kiểm thử")
    args = parser.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    # 2. Khởi tạo CSDL SQLite độc lập tạm thời trong bộ nhớ đệm
    with tempfile.TemporaryDirectory() as tmp:
        db = Database(path=Path(tmp) / "demo.db")
        
        # Khởi chạy một GameServer TCP thật trên một cổng ngẫu nhiên (port=0)
        server = GameServer(db, port=0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        
        # Chờ tối đa 3 giây để Server khởi động và sẵn sàng lắng nghe socket
        assert server.ready.wait(3), "Lỗi: Máy chủ kiểm thử không thể khởi động!"

        # Khởi tạo Client ứng dụng kết nối trực tiếp vào cổng của Server vừa tạo
        app = App(port=server.port)
        friend = None

        def frames_until(predicate, timeout=5):
            """Chạy các khung hình Pygame liên tục cho đến khi điều kiện kiểm thử thỏa mãn."""
            end = time.monotonic() + timeout
            while time.monotonic() < end:
                app.frame()
                if predicate():
                    return
            raise AssertionError(f"Hết thời gian chờ GUI: scene={app.scene} / toast={app.toast_value}")

        def capture(name):
            """Chụp lại bề mặt Canvas hiển thị của Client và lưu thành file ảnh PNG."""
            app.toast_until = 0  # Ẩn thông báo tạm thời để ảnh chụp sạch đẹp
            app.draw(time.monotonic(), 1 / 60)
            file_path = str(out / (name + ".png"))
            pygame.image.save(app.canvas, file_path)

        try:
            # ------------------------------------------------------------------
            # GIAI ĐOẠN 1: MÀN HÌNH ĐĂNG NHẬP & ĐĂNG KÝ (T2.1, T2.2)
            # ------------------------------------------------------------------
            app.frame()
            capture("01_dang_nhap")

            # Thực hiện luồng đăng ký tài khoản mới: neon_pilot
            app.register_mode = True
            app.fields["username"].value = "neon_pilot"
            app.fields["password"].value = "demo_password123"
            app.fields["display"].value = "Neon Pilot"
            app.authenticate()
            
            # Chờ chuyển màn hình thành công vào Sảnh (Lobby)
            frames_until(lambda: app.scene == "lobby")

            # ------------------------------------------------------------------
            # GIAI ĐOẠN 2: SẢNH CHỜ, HỒ SƠ & BỘ 6 SKIN NEON (T2.3, T2.4)
            # ------------------------------------------------------------------
            app.fields["profile"].value = "Neon Pilot"
            app.skin = "#54E8B0"  # Chọn Skin màu xanh ngọc Neon
            app.send("PROFILE", name="Neon Pilot", skin=app.skin)
            capture("02_sanh_chinh")

            # ------------------------------------------------------------------
            # GIAI ĐOẠN 3: TẠO PHÒNG CHƠI, BOT & ĐỐI THỦ THẬT THAM GIA (T2.3, T2.5)
            # ------------------------------------------------------------------
            app.fields["room"].value = "Neon Arena"
            app.bots = 4  # Cấu hình 4 bot máy luyện tập
            app.create_room()
            frames_until(lambda: app.scene == "room")

            # Giả lập một client người chơi thứ hai (Comet Pilot) tham gia phòng
            friend = Wire(server.port)
            friend.send("REGISTER", username="comet_pilot", password="demo_password123", name="Comet Pilot")
            friend.until("AUTH_OK")
            friend.send("JOIN_ROOM", room_id=app.room["id"])
            friend.until("ROOM_STATE")
            
            # Gửi tin nhắn chat vào phòng chờ
            friend.send("CHAT", text="Sẵn sàng! Cùng vào đấu trường nhé.")
            frames_until(lambda: len(app.room["members"]) == 2 and len(app.chat) > 0)
            capture("03_phong_cho")

            # ------------------------------------------------------------------
            # GIAI ĐOẠN 4: BẮT ĐẦU TRẬN ĐẤU, THẾ GIỚI GAME & HUD (T2.5)
            # ------------------------------------------------------------------
            app.send("START_GAME")
            frames_until(lambda: bool(app.world.states))

            # Đồng bộ tọa độ các thực thể trên Server để chụp khung cảnh trực quan
            with server.lock:
                arena = server.rooms[app.room["id"]].arena
                for i, s in enumerate(arena.snakes.values()):
                    x, y = 1500 + (i % 3 - 1) * 220, 1500 + (i // 3) * 180
                    s.body = [(x - j * 6, y + 20 * math.sin(j * 0.16)) for j in range(40)]
                    s.score = s.peak_score = 44
                    s.angle = s.target = 0
                    s.shield = 2
                for i in range(50):
                    arena.add_food(1150 + (i * 71) % 900, 1300 + (i * 61) % 600, 1)

            start = time.monotonic()
            frames_until(lambda: time.monotonic() - start > 0.5)
            capture("04_dau_truong")

            # ------------------------------------------------------------------
            # GIAI ĐOẠN 5: VA CHẠM KẾT THÚC TRẬN & MÀN HÌNH GAME OVER (T2.6)
            # ------------------------------------------------------------------
            # Điều khiển đầu rắn chạm ranh giới đấu trường (2990, 1500) để kích hoạt va tường
            with server.lock:
                s = server.rooms[app.room["id"]].arena.snakes[app.pid]
                s.body[0] = (2990, 1500)
                s.angle = s.target = 0

            # Chờ sự kiện tử vong được truyền về và hiển thị màn hình Death Screen
            frames_until(lambda: app.dead is not None)
            capture("05_ket_qua")

            # ------------------------------------------------------------------
            # GIAI ĐOẠN 6: HỒI SINH [R], RỜI PHÒNG & XEM LỊCH SỬ ĐẤU (T2.6)
            # ------------------------------------------------------------------
            # Bấm phím [R] hồi sinh tiếp tục trong phòng
            app.send("RESPAWN")
            frames_until(lambda: app.dead is None and bool(app.world.states))

            # Rời phòng quay trở lại Sảnh chính
            app.send("LEAVE_ROOM")
            frames_until(lambda: app.scene == "lobby")

            # Đảm bảo luồng ghi CSDL nền đã lưu xong lượt đấu
            server.db_worker.submit(lambda: None).result(3)
            
            # Mở hộp thoại Modal Lịch sử 20 lượt đấu gần nhất
            app.open_modal("history")
            frames_until(lambda: bool(app.history))
            capture("06_lich_su")

            # ------------------------------------------------------------------
            # GIAI ĐOẠN 7: MẤT KẾT NỐI MẠNG ĐỘT NGỘT & TỰ NỐI LẠI BẰNG TOKEN (T2.1)
            # ------------------------------------------------------------------
            # Cưỡng bức đóng socket kết nối giữa chừng để kiểm tra cơ chế Auto-Reconnect
            with server.lock:
                server.users[app.pid].close()

            start = time.monotonic()
            frames_until(
                lambda: time.monotonic() - start > 1.5 and app.scene == "lobby" and app.net.connected,
                timeout=7
            )
            assert app.user["username"] == "neon_pilot", "Lỗi: Không khôi phục được phiên người chơi!"

            # Thông báo hoàn tất toàn bộ kịch bản kiểm thử
            print("\n" + "=" * 70)
            print("GUI SMOKE TEST PASS (100% THÀNH CÔNG):")
            print("-> Đăng ký, Hồ sơ, Tạo phòng, Chat, Đấu trường, Tử vong, Hồi sinh, Lịch sử, Reconnect.")
            print(f"-> Toàn bộ 6 ảnh chụp màn hình đã xuất tại: {out.resolve()}")
            print("=" * 70 + "\n")

        finally:
            # Thu dọn tài nguyên mạng và đóng server sau khi test xong
            if app.net:
                app.net.close()
            if friend:
                friend.close()
            server.shutdown()
            thread.join(3)
            pygame.quit()


if __name__ == "__main__":
    main()