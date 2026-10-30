# ==============================================================================
# Neon Slither - Client UI & Trải nghiệm người dùng
# Phụ trách: Trần Minh Hải (Thành viên 2)
# Chức năng: Điều phối màn hình (Auth, Lobby, Room, Game, HUD, Chat, Leaderboard)
# ==============================================================================
# ------------------------------------------------------------------------------
# [Nhiệm vụ T2.3 & T2.4 - Phụ trách: Trần Minh Hải]
# - T2.3: Giao diện Sảnh (Lobby): Tìm kiếm phòng, danh sách phòng có cuộn,
#         tạo phòng (2-8 người, 0-4 bot), chuyển quyền chủ phòng (Host transfer).
# - T2.4: Màn hình Hồ sơ & Skin: Chọn 6 loại skin màu Neon, xem điểm kỷ lục cá nhân
#         và cập nhật cấu hình người chơi trước khi vào trận.
# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------
# [Nhiệm vụ T2.5 - Phụ trách: Trần Minh Hải]
# - Thiết kế giao diện hiển thị trong trận (In-game HUD): Điểm số, độ dài rắn,
#   thời gian sống sót, trạng thái bứt tốc (boost indicator).
# - Hộp thoại Chat trong trận: Bật/tắt bằng phím Enter, hiển thị tin nhắn mờ dần.
# - Bảng xếp hạng Top 10 người chơi theo thời gian thực ở góc trên bên phải.
# - Minimap góc dưới: Định vị vị trí bản thân, ranh giới map 3000x3000 và các đối thủ.
# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------
# [Nhiệm vụ T2.6 - Phụ trách: Trần Minh Hải]
# - Màn hình kết thúc trận (Death / Game Over Screen): Hiển thị lý do chết
#   (va tường, va thân đối thủ, va đầu), điểm đỉnh, điểm cuối và thời gian sống.
# - Luồng Hồi sinh nhanh: Phím [R] để hồi sinh tiếp tục trong phòng, [Esc] về sảnh.
# - Màn hình Lịch sử đấu (Match History): Xem 20 lượt chơi gần nhất từ CSDL.
# - Hướng dẫn & Điều khiển: Bật/tắt hộp thoại hướng dẫn luật chơi [F1],
#   chế độ toàn màn hình [F11] và điều hướng form bằng phím [Tab].
# ------------------------------------------------------------------------------
"""Desktop scenes: authentication, lobby, room, arena and result overlays."""
import math
import time
import pygame
from common.config import SKINS, INPUT_RATE, BASE_SEGMENTS
from client.network import Network
from client.graphics import Backdrop, WorldRenderer, snake_art, halo, rgb
from client.widgets import (Buttons, Input, text, panel, pill, font,
                            BG, EDGE, TEXT, MUTED, ACCENT, RED)


class App:
    def __init__(self, host="127.0.0.1", port=5555, username=None, password=None):
        pygame.init()
        pygame.display.set_caption("NEON SLITHER · Multiplayer Arena")
        self.window = pygame.display.set_mode((1280,800), pygame.RESIZABLE)
        self.canvas = pygame.Surface((1280,800))
        self.clock = pygame.time.Clock()
        self.backdrop = Backdrop()
        self.world = WorldRenderer()
        self.buttons = Buttons()
        self.scene, self.modal = "auth", None
        self.running = True
        self.register_mode = False
        self.net = None
        self.connected = False
        self.pending_auth = None
        self.user = None
        self.room = None
        self.rooms, self.chat, self.rankings, self.history = [], [], [], []
        self.dead = None
        self.skin = SKINS[0]
        self.capacity, self.bots = 8, 2
        self.scroll = 0
        self.toast_value, self.toast_until, self.toast_error = "",0,False
        self.last_input, self.last_refresh, self.seq = 0,0,0
        self.rtt, self.connection_note = 0,"CHƯA KẾT NỐI"
        self.chat_open = False
        self.mouse = (0,0)
        self.fields = {
            "host": Input("Địa chỉ máy chủ",host,limit=100),
            "port": Input("Cổng",str(port),limit=5),
            "username": Input("Tên tài khoản",username or "",limit=24),
            "password": Input("Mật khẩu",password or "",password=True,limit=128),
            "display": Input("Tên hiển thị",limit=20),
            "profile": Input("Tên hiển thị",limit=20),
            "room": Input("Tên phòng", "Đấu trường của tôi",limit=32),
            "chat": Input("Tin nhắn",limit=160),
        }
        self.active_fields = []
        icon = pygame.Surface((32,32),pygame.SRCALPHA)
        pygame.draw.circle(icon,ACCENT,(16,16),13)
        pygame.draw.circle(icon,BG,(21,11),3)
        pygame.display.set_icon(icon)
        pygame.key.set_repeat(350,35)
        if username and password:
            self.authenticate()

    @property
    def pid(self):
        return str(self.user["id"]) if self.user else ""

    def toast(self, value, error=False):
        self.toast_value, self.toast_until, self.toast_error = value,time.monotonic()+5,error

    def send(self, kind, **data):
        if self.net and self.net.connected:
            self.net.send(kind,**data)
        else:
            self.toast("Chưa kết nối với máy chủ.",True)

    def authenticate(self):
        try:
            port = int(self.fields["port"].value)
            if not 1 <= port <= 65535:
                raise ValueError()
        except ValueError:
            self.toast("Cổng cần là số từ 1 đến 65535.",True)
            return
        if not self.fields["username"].value or not self.fields["password"].value:
            self.toast("Hãy nhập tài khoản và mật khẩu.",True)
            return
        self.pending_auth = {"type": "REGISTER" if self.register_mode else "LOGIN",
                             "username": self.fields["username"].value,
                             "password": self.fields["password"].value,
                             "name": self.fields["display"].value or self.fields["username"].value}
        host = self.fields["host"].value.strip()
        if self.net and self.net.connected and self.net.host == host and self.net.port == port:
            self.flush_auth()
        else:
            if self.net:
                self.net.close()
            self.net = Network(host,port)
            self.net.start()

    def flush_auth(self):
        if self.pending_auth:
            request,self.pending_auth=self.pending_auth,None
            self.net.send(request.pop("type"),**request)

    def handle_message(self, message):
        kind=message["type"]
        if kind=="NET_CONNECTED":
            self.connected=True
            self.connection_note="ĐÃ KẾT NỐI"
            self.flush_auth()
        elif kind=="NET_CONNECTING":
            self.connection_note="ĐANG KẾT NỐI"
        elif kind=="NET_RETRY":
            self.connected=False
            self.connection_note=f"KẾT NỐI LẠI {message['attempt']}/3"
        elif kind=="NET_FAILED":
            self.connected=False
            self.connection_note="MẤT KẾT NỐI"
            self.scene="auth"
            self.room=None
            self.user=None
            self.modal=None
            self.pending_auth=None
            self.toast("Không kết nối được. Kiểm tra server, IP và cổng rồi đăng nhập lại.",True)
        elif kind=="AUTH_OK":
            self.user=message["user"]
            self.fields["profile"].value=self.user["display_name"]
            self.skin=self.user["skin_color"]
            self.fields["password"].value=""
            self.scene="lobby"
            self.room=None
            self.dead=None
            self.modal=None
            self.seq=0
            self.world=WorldRenderer()
            if message.get("resumed"):
                self.toast("Đã nối lại. Lượt trước đã kết thúc; hãy vào phòng để chơi tiếp.")
            self.send("LEADERBOARD")
        elif kind in ("AUTH_EXPIRED","LOGGED_OUT"):
            self.scene="auth"
            self.room=None
            self.user=None
            self.modal=None
            if self.net:
                self.net.token=None
            if kind=="AUTH_EXPIRED":
                self.toast("Phiên đã hết hạn. Vui lòng đăng nhập lại.",True)
        elif kind=="ERROR":
            self.toast(message["message"],True)
        elif kind=="LOBBY":
            self.rooms=message["rooms"]
            self.user=message.get("user",self.user)
        elif kind=="PROFILE_OK":
            self.user=message["user"]
            self.toast("Đã lưu tên hiển thị và skin.")
        elif kind=="ROOM_STATE":
            if not self.room or self.room["id"]!=message["id"]:
                self.world=WorldRenderer()
                self.dead=None
                self.seq=0
            self.room=message
            self.chat=message["chat"]
            self.scene="game" if message["status"]=="PLAYING" else "room"
            self.modal=None
        elif kind=="WORLD_STATE":
            if self.room and message.get("room_id")==self.room["id"]:
                self.world.push(message)
                own=next((s for s in message["snakes"] if s["id"]==self.pid),None)
                if own and own["alive"]:
                    self.dead=None
        elif kind=="DEATH":
            if self.room:
                self.dead=message
                if self.user:
                    self.user["highest_score"]=max(self.user["highest_score"],message["score"])
        elif kind=="RESPAWN_OK":
            self.dead=None
            self.world=WorldRenderer()
        elif kind in ("LEFT_ROOM","KICKED"):
            self.scene="lobby"
            self.room=None
            self.dead=None
            self.chat_open=False
            self.modal=None
            self.world=WorldRenderer()
            if kind=="KICKED":
                self.toast(message["message"],True)
            self.send("LEADERBOARD")
        elif kind=="CHAT":
            self.chat.append({"name":message["name"],"text":message["text"]})
            self.chat=self.chat[-40:]
        elif kind=="LEADERBOARD":
            self.rankings=message["rows"]
        elif kind=="HISTORY":
            self.history=message["rows"]
        elif kind=="PONG":
            self.rtt=round((time.monotonic()-message["stamp"])*1000)

    def create_room(self):
        self.send("CREATE_ROOM",name=self.fields["room"].value,capacity=self.capacity,bots=self.bots)

    def open_modal(self,kind):
        if self.scene=="game" and self.connected and self.world.states:
            own=next((s for s in self.world.states[-1][1]["snakes"] if s["id"]==self.pid),None)
            if own:
                self.seq+=1
                self.send("PLAYER_INPUT",angle=own["angle"],boost=False,seq=self.seq)
        self.modal,self.scroll=kind,0
        if kind=="rankings": self.send("LEADERBOARD")
        if kind=="history": self.send("HISTORY")

    def send_chat(self):
        value=self.fields["chat"].value.strip()
        if value:
            self.send("CHAT",text=value)
            self.fields["chat"].value=""
        if self.scene=="game":
            self.chat_open=False

    def toggle_register(self):
        self.register_mode=not self.register_mode

    def event(self,e):
        if e.type==pygame.QUIT:
            self.running=False
        elif e.type==pygame.VIDEORESIZE:
            self.window=pygame.display.set_mode((max(800,e.w),max(500,e.h)),pygame.RESIZABLE)
        elif e.type==pygame.KEYDOWN:
            if e.key==pygame.K_F11:
                if self.window.get_flags()&pygame.FULLSCREEN:
                    self.window=pygame.display.set_mode((1280,800),pygame.RESIZABLE)
                else:
                    self.window=pygame.display.set_mode((0,0),pygame.FULLSCREEN)
            elif e.key==pygame.K_ESCAPE:
                if self.modal:
                    self.modal=None
                elif self.chat_open:
                    self.chat_open=False
                elif self.scene in ("room","game"):
                    self.send("LEAVE_ROOM")
            elif e.key==pygame.K_TAB and self.active_fields:
                active=next((i for i,key in enumerate(self.active_fields) if self.fields[key].active),-1)
                for key in self.fields: self.fields[key].active=False
                self.fields[self.active_fields[(active+1)%len(self.active_fields)]].active=True
            elif e.key==pygame.K_RETURN:
                if self.modal:
                    pass
                elif self.scene=="auth": self.authenticate()
                elif self.scene=="room" or self.chat_open: self.send_chat()
                elif self.scene=="game" and not self.dead:
                    self.chat_open=True
                    self.fields["chat"].active=True
            elif e.key==pygame.K_r and self.scene=="game" and self.dead and not self.chat_open:
                self.send("RESPAWN")
            elif e.key==pygame.K_F1:
                self.open_modal("help")
        elif e.type==pygame.MOUSEWHEEL:
            self.scroll=max(0,self.scroll-e.y)
        for key in self.active_fields:
            self.fields[key].event(e,self.mouse)
        if e.type==pygame.MOUSEBUTTONDOWN and e.button==1:
            self.buttons.click(self.mouse)

    def header(self,subtitle):
        text(self.canvas,"NEON",(42,29),16,ACCENT,True)
        text(self.canvas,"SLITHER",(106,27),22,TEXT,True)
        text(self.canvas,subtitle,(42,65),13,MUTED)
        pill(self.canvas,self.connection_note,(1008,30),ACCENT if self.connected else (255,172,103))
        pygame.draw.line(self.canvas,EDGE,(42,100),(1238,100))

    def draw_auth(self,now):
        self.header("ĐẤU TRƯỜNG RẮN NHIỀU NGƯỜI CHƠI")
        # Procedural hero illustration, consistent with the in-game snake renderer.
        points=[]
        for i in range(85):
            t=i/84
            x=952+155*math.sin(t*math.tau*1.1+now*.13)
            y=300+t*235+43*math.cos(t*math.tau*1.6)
            points.append((x,y))
        angle=math.atan2(points[0][1]-points[1][1],points[0][0]-points[1][0])
        for i in range(22):
            x=735+(i*93)%440; y=250+(i*79)%310
            c=rgb(SKINS[i%6]); halo(self.canvas,(x,y),c,20)
            pygame.draw.circle(self.canvas,c,(x,y),4)
        snake_art(self.canvas,points,SKINS[0],angle,20,boosting=True)
        pill(self.canvas,"MULTIPLAYER ARENA",(742,160))
        text(self.canvas,"Nhỏ bé lúc bắt đầu.",(740,209),25,TEXT,True)
        text(self.canvas,"Dẫn đầu khi sống sót.",(740,249),25,TEXT,True)
        text(self.canvas,"Ăn năng lượng. Uốn lượn. Bứt tốc.",(742,590),17,TEXT)
        text(self.canvas,"Mỗi khúc cua là một lựa chọn.",(742,620),15,MUTED)
        for i,(num,label) in enumerate([("360°","Điều hướng"),("8","Người / phòng"),("LAN","Chơi cùng bạn")]):
            x=745+i*158
            text(self.canvas,num,(x,681),23,ACCENT,True)
            text(self.canvas,label,(x,717),12,MUTED)
        panel(self.canvas,(70,132,558,610),radius=24)
        text(self.canvas,"Tạo tài khoản" if self.register_mode else "Sẵn sàng vào đấu trường?",(108,164),25,TEXT,True)
        text(self.canvas,"Đăng ký lần đầu, sau đó dùng tài khoản trên mọi máy.",(108,204),13,MUTED)
        self.fields["host"].draw(self.canvas,(108,269,340,44))
        self.fields["port"].draw(self.canvas,(464,269,125,44))
        self.fields["username"].draw(self.canvas,(108,350,481,46))
        self.fields["password"].draw(self.canvas,(108,433,481,46))
        self.active_fields=["host","port","username","password"]
        if self.register_mode:
            self.fields["display"].draw(self.canvas,(108,516,481,44))
            self.active_fields.append("display")
        else:
            text(self.canvas,"Tài khoản 3–24 ký tự · Mật khẩu tối thiểu 8 ký tự",(108,501),12,MUTED)
            text(self.canvas,"Chuột để lái · Space để bứt tốc",(108,531),13,ACCENT)
        self.buttons.draw(self.canvas,"TẠO TÀI KHOẢN" if self.register_mode else "ĐĂNG NHẬP  →",(108,584,481,50),self.authenticate,True)
        self.buttons.draw(self.canvas,"Đã có tài khoản? Đăng nhập" if self.register_mode else "Chưa có tài khoản? Đăng ký",(108,651,481,43),self.toggle_register)
        text(self.canvas,"PYTHON + PYGAME  /  TCP CLIENT–SERVER",(70,769),11,MUTED)
        self.buttons.draw(self.canvas,"Hướng dẫn  F1",(1080,753,157,32),lambda:self.open_modal("help"))

    def draw_lobby(self,now):
        self.header("SẢNH CHÍNH  /  CHỌN MỘT ĐẤU TRƯỜNG VÀ BẮT ĐẦU")
        text(self.canvas,"Chào "+self.user["display_name"],(42,127),28,TEXT,True,max_width=720)
        text(self.canvas,"Lập phòng cùng bạn bè hoặc vào nhanh một trận đang mở.",(42,171),15,MUTED)
        self.buttons.draw(self.canvas,"VÀO NHANH  →",(968,130,270,51),lambda:self.send("QUICK_JOIN"),True)
        panel(self.canvas,(42,210,758,290))
        text(self.canvas,"ĐẤU TRƯỜNG ĐANG MỞ",(66,234),13,MUTED,True)
        self.buttons.draw(self.canvas,"Làm mới",(660,225,117,33),lambda:self.send("LIST_ROOMS"))
        if not self.rooms:
            text(self.canvas,"Chưa có phòng nào",(420,333),22,TEXT,True,"center")
            text(self.canvas,"Tạo phòng bên dưới để mời bạn bè vào chơi.",(420,373),14,MUTED,anchor="center")
        visible=self.rooms[min(self.scroll,max(0,len(self.rooms)-3)):][:3]
        for i,r in enumerate(visible):
            y=276+i*68
            panel(self.canvas,(62,y,716,58),(21,36,48),11,border=None)
            pygame.draw.circle(self.canvas,ACCENT if r["status"]=="WAITING" else (108,206,255),(83,y+28),4)
            text(self.canvas,r["name"],(99,y+11),16,TEXT,True,max_width=285)
            text(self.canvas,"Đang chờ" if r["status"]=="WAITING" else "Đang thi đấu",(99,y+35),11,MUTED)
            text(self.canvas,f"{r['players']}/{r['capacity']} người",(446,y+29),14,MUTED,anchor="midleft")
            self.buttons.draw(self.canvas,"Tham gia",(642,y+11,118,36),lambda rid=r["id"]:self.send("JOIN_ROOM",room_id=rid),enabled=r["players"]<r["capacity"])
        panel(self.canvas,(42,520,758,227))
        text(self.canvas,"TẠO PHÒNG CỦA BẠN",(66,541),13,MUTED,True)
        self.fields["room"].draw(self.canvas,(66,604,359,45))
        self.active_fields=["room","profile"]
        text(self.canvas,"Người tối đa",(455,579),13,MUTED)
        self.buttons.draw(self.canvas,"−",(455,604,33,45),lambda:setattr(self,"capacity",max(2,self.capacity-1)))
