# ==============================================================================
# Neon Slither — Bộ Widget & Giao diện người dùng (Immediate-Mode UI Kit)
# Phụ trách: Trần Minh Hải (Thành viên 2 — Nhiệm vụ T2.2 & T2.3)
#
# CÁC TÍNH NĂNG ĐÃ TRIỂN KHAI TRONG FILE:
# - T2.2: Ô nhập liệu (Input) hỗ trợ font chữ tiếng Việt có dấu UTF-8, ẩn mật khẩu,
#         con trỏ nhấp nháy Neon, tự động cuộn chữ khi vượt khung và giới hạn ký tự.
# - T2.2: Hệ thống nút bấm Neon (Buttons) hỗ trợ hiệu ứng hover, primary, danger,
#         tự động co chữ có dấu ba chấm (…) và quản lý sự kiện click tức thì.
# - T2.3: Bảng khối (Panel), huy hiệu (Pill) và cơ chế bộ nhớ đệm Font (@lru_cache)
#         đảm bảo giao diện vẽ cực nhanh, không gây giật lag ở 60 FPS.
# ==============================================================================

"""Small immediate-mode UI kit with cached type, clipped text and UTF-8 inputs."""

from functools import lru_cache
from pathlib import Path
import pygame

# Đường dẫn thư mục gốc dự án
ROOT = Path(__file__).resolve().parents[1]

# ------------------------------------------------------------------------------
# HỆ MÀU SẮC CHỦ ĐẠO (NEON CYBERPUNK PALETTE)
# ------------------------------------------------------------------------------
BG = (9, 16, 25)         # Màu nền tối sâu thẳm
PANEL = (16, 27, 39)     # Màu nền của các khung bảng giao diện
EDGE = (39, 56, 70)       # Màu viền bo góc mặc định
TEXT = (233, 244, 248)   # Màu chữ trắng sáng nổi bật
MUTED = (133, 158, 178)  # Màu chữ phụ/mờ dùng cho chú thích
ACCENT = (84, 232, 176)  # Màu xanh ngọc Neon chủ đạo (Mint Neon)
RED = (255, 121, 157)    # Màu hồng đỏ cảnh báo/thất bại/tử vong


# ------------------------------------------------------------------------------
# [T2.2] BỘ NHỚ ĐỆM FONT CHỮ TRÁNH TRÀN BỘ NHỚ RAM (@lru_cache)
# ------------------------------------------------------------------------------
@lru_cache(maxsize=32)
def font(size, bold=False):
    """
    Tải và lưu trữ bộ nhớ đệm (Cache) cho Font chữ DejaVuSans hỗ trợ tiếng Việt.
    Sử dụng @lru_cache giúp game tái sử dụng đối tượng Font đã tạo, không phải
    đọc lại file từ ổ cứng ở mỗi khung hình, tăng tốc độ vẽ lên 60 FPS.
    """
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    font_path = str(ROOT / "assets" / "fonts" / name)
    return pygame.font.Font(font_path, size)


# ------------------------------------------------------------------------------
# [T2.2] VẼ CHỮ CÓ CẮT TỈA TỰ ĐỘNG (TEXT RENDERING & AUTO-ELLIPSIS)
# ------------------------------------------------------------------------------
def text(surface, value, pos, size=18, color=TEXT, bold=False, anchor="topleft", max_width=None):
    """
    Vẽ chuỗi văn bản lên bề mặt Surface với khả năng tự động thêm dấu '…'
    nếu chiều dài văn bản vượt quá chiều rộng cho phép (max_width).
    """
    value = str(value)
    f = font(size, bold)

    # Thuật toán cắt gọn chuỗi và thêm dấu '…' nếu vượt giới hạn max_width
    if max_width and f.size(value)[0] > max_width:
        while value and f.size(value + "…")[0] > max_width:
            value = value[:-1]
        value += "…"

    image = f.render(value, True, color)
    rect = image.get_rect(**{anchor: (int(pos[0]), int(pos[1]))})
    surface.blit(image, rect)
    return rect


# ------------------------------------------------------------------------------
# [T2.3] VẼ KHUNG BẢNG BO GÓC (ROUNDED RECTANGLE PANEL)
# ------------------------------------------------------------------------------
def panel(surface, rect, fill=PANEL, radius=20, border=EDGE):
    """Vẽ một khung hình chữ nhật bo tròn các góc làm nền cho các form và danh sách."""
    rect = pygame.Rect(rect)
    pygame.draw.rect(surface, fill, rect, border_radius=radius)
    if border:
        pygame.draw.rect(surface, border, rect, 1, border_radius=radius)
    return rect


# ------------------------------------------------------------------------------
# [T2.3] VẼ HUY HIỆU TRẠNG THÁI (STATUS PILL BADGE)
# ------------------------------------------------------------------------------
def pill(surface, label, pos, color=ACCENT):
    """Vẽ huy hiệu trạng thái nhỏ bo tròn (ví dụ: 'ĐÃ KẾT NỐI', 'MULTIPLAYER ARENA')."""
    width = font(12, bold=True).size(label)[0] + 22
    rect = pygame.Rect(pos[0], pos[1], width, 28)
    
    # Nền mờ 15% và viền mờ 32% theo tông màu chủ đạo
    bg_color = tuple(int(c * 0.15) for c in color)
    border_color = tuple(int(c * 0.32) for c in color)
    
    panel(surface, rect, bg_color, 14, border_color)
    text(surface, label, rect.center, 12, color, bold=True, anchor="center")


# ------------------------------------------------------------------------------
# [T2.2] Ô NHẬP LIỆU VĂN BẢN (TEXT INPUT CONTROLLER)
# ------------------------------------------------------------------------------
class Input:
    """
    Thành phần ô nhập liệu văn bản hoàn chỉnh (Trần Minh Hải - T2.2)
    - Hỗ trợ gõ tiếng Việt có dấu đầy đủ bằng sự kiện pygame.TEXTINPUT.
    - Hỗ trợ chế độ ẩn mật khẩu dạng dấu chấm tròn (•).
    - Con trỏ nhấp nháy Neon và tự động cuộn chữ sang trái khi gõ dài.
    - Giới hạn tối đa ký tự (limit) để chống tấn công tràn dữ liệu.
    """

    def __init__(self, label, value="", password=False, limit=32):
        self.label = label
        self.value = value
        self.password = password
        self.limit = limit
        self.active = False
        self.rect = pygame.Rect(0, 0, 0, 0)

    def event(self, e, point):
        """Xử lý sự kiện chuột click kích hoạt và phím nhập văn bản."""
        # Kích hoạt ô nhập khi click chuột trái vào trong khung
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            self.active = self.rect.collidepoint(point)

        if not self.active:
            return

        # Phím xóa lùi Backspace
        if e.type == pygame.KEYDOWN and e.key == pygame.K_BACKSPACE:
            self.value = self.value[:-1]

        # Nhận chuỗi ký tự UTF-8 (hỗ trợ đầy đủ bộ gõ Unikey / EVKey tiếng Việt)
        elif e.type == pygame.TEXTINPUT:
            printable_text = "".join(c for c in e.text if c.isprintable())
            self.value = (self.value + printable_text)[:self.limit]

    def draw(self, surface, rect):
        """Vẽ ô nhập, nhãn tiêu đề, giá trị hiển thị và con trỏ nhấp nháy."""
        self.rect = pygame.Rect(rect)
        
        # 1. Vẽ nhãn hướng dẫn phía trên ô nhập
        text(surface, self.label, (rect[0], rect[1] - 23), 13, MUTED)
        
        # 2. Khung viền (sáng màu ACCENT khi đang focus gõ chữ)
        panel(surface, rect, (10, 20, 30), 10, ACCENT if self.active else EDGE)

        # 3. Ẩn mật khẩu bằng ký tự '•' nếu trường yêu cầu bảo mật
        display_value = "•" * len(self.value) if self.password else self.value

        # Tự động cuộn sang trái khi chữ quá dài so với chiều rộng ô nhập
        while display_value and font(16).size(display_value)[0] > rect[2] - 34:
            display_value = display_value[1:]

        text(surface, display_value, (rect[0] + 14, rect[1] + rect[3] / 2), 16, TEXT, anchor="midleft")

        # 4. Hiệu ứng con trỏ nhấp nháy Neon mỗi chu kỳ 520ms (Blinking Cursor)
        if self.active and (pygame.time.get_ticks() % 1000 < 520):
            cursor_x = rect[0] + 16 + font(16).size(display_value)[0]
            pygame.draw.line(
                surface,
                ACCENT,
                (cursor_x, rect[1] + 13),
                (cursor_x, rect[1] + rect[3] - 13),
                2
            )


# ------------------------------------------------------------------------------
# [T2.2, T2.3] HỆ THỐNG QUẢN LÝ NÚT BẤM (IMMEDIATE-MODE BUTTON MANAGER)
# ------------------------------------------------------------------------------
class Buttons:
    """
    Quản lý nút bấm tức thì (Trần Minh Hải - T2.2, T2.3)
    - Quản lý danh sách nút bấm được vẽ trong khung hình hiện tại.
    - Nhận diện trạng thái rê chuột (Hover) và tính toán màu sắc tương ứng.
    - Phân loại nút: Primary (nổi bật), Normal (thường), Danger (cảnh báo đỏ) hoặc Disabled.
    - Bắt sự kiện click chính xác theo thứ tự từ trên xuống dưới.
    """

    def __init__(self):
        self.items = []
        self.mouse = (0, 0)

    def begin(self, mouse):
        """Khởi động lại danh sách nút ở đầu mỗi khung hình và lưu vị trí chuột."""
        self.items = []
        self.mouse = mouse

    def draw(self, surface, label, rect, callback, primary=False, enabled=True, danger=False):
        """Vẽ một nút bấm lên màn hình với đầy đủ hiệu ứng tương tác."""
        rect = pygame.Rect(rect)
        hover = enabled and rect.collidepoint(self.mouse)
        color = RED if danger else ACCENT

        # Xác định màu nền của nút tùy theo trạng thái
        if primary:
            fill = color
        elif hover:
            fill = (31, 51, 65)
        else:
            fill = (23, 37, 51)

        if not enabled:
            fill = (25, 34, 43)

        # Viền nút sáng lên khi di chuột vào (Hover Effect)
        border_color = None if primary else (color if hover else EDGE)
        panel(surface, rect, fill, 11, border=border_color)

        # Màu chữ của nút
        if primary:
            text_color = BG
        elif enabled:
            text_color = TEXT
        else:
            text_color = MUTED

        max_w = (rect.w - 18) if rect.w >= 42 else None
        text(surface, label, rect.center, 15, text_color, bold=True, anchor="center", max_width=max_w)

        # Lưu lại nút bấm vào danh sách chờ xử lý click
        self.items.append((rect, callback, enabled))

    def click(self, point):
        """Kiểm tra và kích hoạt hàm callback của nút bấm khi người dùng click chuột."""
        # Duyệt ngược danh sách để ưu tiên các nút được vẽ đè lên trên cùng
        for rect, callback, enabled in reversed(self.items):
            if enabled and rect.collidepoint(point):
                callback()
                return True
        return False