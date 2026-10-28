"""Desktop scenes: authentication, lobby, room, arena and result overlays."""
from pathlib import Path
import json
import math
import time
import pygame
from common.config import SKINS, INPUT_RATE, BASE_SEGMENTS
from client.network import Network
from client.graphics import Backdrop, WorldRenderer, snake_art, halo, rgb
from client.widgets import (Buttons, Input, text, panel, pill, font,
                            BG, PANEL, EDGE, TEXT, MUTED, ACCENT, RED, ROOT)


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
        text(self.canvas,str(self.capacity),(514,626),18,TEXT,True,"center")
        self.buttons.draw(self.canvas,"+",(540,604,33,45),lambda:setattr(self,"capacity",min(8,self.capacity+1)))
        text(self.canvas,"Bot luyện tập",(605,579),13,MUTED)
        self.buttons.draw(self.canvas,"−",(605,604,33,45),lambda:setattr(self,"bots",max(0,self.bots-1)))
        text(self.canvas,str(self.bots),(664,626),18,TEXT,True,"center")
        self.buttons.draw(self.canvas,"+",(690,604,33,45),lambda:setattr(self,"bots",min(4,self.bots+1)))
        text(self.canvas,"Bot do server điều khiển và không tính vào BXH tổng.",(66,691),12,MUTED)
        self.buttons.draw(self.canvas,"Tạo phòng  +",(604,675,171,46),self.create_room,True)
        panel(self.canvas,(822,210,416,537))
        text(self.canvas,"HỒ SƠ CỦA BẠN",(848,234),13,MUTED,True)
        text(self.canvas,f"{self.user['highest_score']:,}",(848,269),40,ACCENT,True)
        text(self.canvas,"ĐIỂM KỶ LỤC",(850,323),11,MUTED)
        pts=[(1124-i*5,307+23*math.sin(i*.13+now)) for i in range(42)]
        snake_art(self.canvas,pts,self.skin,0,12)
        self.fields["profile"].draw(self.canvas,(848,388,365,43))
        text(self.canvas,"Màu rắn",(848,454),13,MUTED)
        for i,color in enumerate(SKINS):
            rect=pygame.Rect(847+i*60,485,44,40)
            if color==self.skin:
                pygame.draw.rect(self.canvas,TEXT,rect.inflate(6,6),2,border_radius=14)
            pygame.draw.rect(self.canvas,rgb(color),rect,border_radius=11)
            self.buttons.items.append((rect,lambda c=color:setattr(self,"skin",c),True))
        self.buttons.draw(self.canvas,"Lưu hồ sơ",(848,549,365,44),lambda:self.send("PROFILE",name=self.fields["profile"].value,skin=self.skin))
        self.buttons.draw(self.canvas,"Bảng xếp hạng",(848,611,177,44),lambda:self.open_modal("rankings"))
        self.buttons.draw(self.canvas,"Lịch sử",(1036,611,177,44),lambda:self.open_modal("history"))
        self.buttons.draw(self.canvas,"Đăng xuất",(848,673,177,42),lambda:self.send("LOGOUT"))
        self.buttons.draw(self.canvas,"Cách chơi",(1036,673,177,42),lambda:self.open_modal("help"))
        text(self.canvas,"Cuộn chuột trên sảnh để xem thêm phòng.",(43,765),11,MUTED)

    def draw_chat_lines(self,rect,lines=9):
        x,y,w,h=rect
        wrapped=[]
        for entry in self.chat:
            prefix=entry["name"]+": "
            words=(prefix+entry["text"]).split()
            line=""
            for word in words:
                if font(13).size(line+" "+word)[0] > w-10 and line:
                    wrapped.append(line); line=word
                else:
                    line=(line+" "+word).strip()
            wrapped.append(line)
        for i,line in enumerate(wrapped[-lines:]):
            text(self.canvas,line,(x,y+i*25),13,TEXT,max_width=w)

    def draw_room(self,now):
        self.header("PHÒNG CHỜ  /  TRÒ CHUYỆN VÀ CHUẨN BỊ")
        text(self.canvas,self.room["name"],(42,129),29,TEXT,True,max_width=860)
        text(self.canvas,f"Mã phòng {self.room['id']} · {self.room['players']}/{self.room['capacity']} người · {self.room['bots']} bot",(43,174),14,MUTED)
        self.buttons.draw(self.canvas,"Rời phòng",(1074,135,164,45),lambda:self.send("LEAVE_ROOM"))
        panel(self.canvas,(42,218,658,455))
        text(self.canvas,"NGƯỜI CHƠI",(69,243),13,MUTED,True)
        for i,member in enumerate(self.room["members"]):
            x=66+(i%2)*315; y=284+(i//2)*88
            panel(self.canvas,(x,y,294,73),(21,36,48),12,None)
            snake_art(self.canvas,[(x+33-j*3,y+35) for j in range(5)],member["color"],0,11)
            text(self.canvas,member["name"],(x+60,y+18),15,TEXT,True,max_width=185)
            text(self.canvas,"CHỦ PHÒNG" if member["id"]==self.room["host"] else "SẴN SÀNG",(x+60,y+44),10,ACCENT)
            if self.room["host"]==self.pid and member["id"]!=self.pid:
                self.buttons.draw(self.canvas,"×",(x+252,y+21,28,30),lambda pid=member["id"]:self.send("KICK",player_id=pid))
        panel(self.canvas,(722,218,516,455))
        text(self.canvas,"TRÒ CHUYỆN TRONG PHÒNG",(748,243),13,MUTED,True)
        if not self.chat:
            text(self.canvas,"Chào đồng đội trước khi bắt đầu nhé.",(748,294),14,MUTED)
        self.draw_chat_lines((748,288,460,292),11)
        self.fields["chat"].draw(self.canvas,(748,608,349,42))
        self.buttons.draw(self.canvas,"Gửi",(1108,608,105,42),self.send_chat,True)
        self.active_fields=["chat"]
        text(self.canvas,"Chuột: điều hướng   /   Space: bứt tốc   /   Enter: chat",(44,711),14,MUTED)
        host=self.room["host"]==self.pid
        self.buttons.draw(self.canvas,"BẮT ĐẦU TRẬN  →" if host else "Chờ chủ phòng bắt đầu…",(880,698,358,53),lambda:self.send("START_GAME"),True,enabled=host)
        text(self.canvas,"Có thể chơi một mình cùng bot hoặc mời thêm người qua mạng LAN.",(44,755),12,MUTED)

    def draw_game(self,now,dt):
        world=self.world.draw(self.canvas,now,dt,self.pid)
        panel(self.canvas,(24,23,302,100),(12,26,37),18)
        text(self.canvas,"NEON SLITHER",(44,38),15,ACCENT,True)
        me=next((s for s in world["snakes"] if s["id"]==self.pid),None) if world else None
        text(self.canvas,str(me["score"] if me else 0),(44,66),32,TEXT,True)
        text(self.canvas,"ĐIỂM",(121,80),11,MUTED,True)
        text(self.canvas,f"{len(me['body']) if me else BASE_SEGMENTS} đốt  ·  {self.rtt} ms",(181,89),11,MUTED)
        if world:
            panel(self.canvas,(1016,23,240,90+min(10,len(world["top"]))*31),(12,26,37),18)
            text(self.canvas,"BẢNG XẾP HẠNG",(1036,42),13,MUTED,True)
            text(self.canvas,self.room["name"],(1036,66),11,MUTED,max_width=193)
            for i,row in enumerate(world["top"]):
                y=107+i*31
                color=ACCENT if row["id"]==self.pid else TEXT
                text(self.canvas,f"{i+1:02}",(1036,y),12,MUTED)
                text(self.canvas,row["name"],(1064,y),13,color,True,max_width=118)
                text(self.canvas,str(row["score"]),(1236,y),13,color,True,"topright")
            self.world.radar(self.canvas,world,self.pid,(1056,569,200,205))
        self.buttons.draw(self.canvas,"Rời trận  Esc",(26,143,154,36),lambda:self.send("LEAVE_ROOM"))
        panel(self.canvas,(411,722,458,53),(12,26,37),18)
        if me and me["boost"]:
            text(self.canvas,"BỨT TỐC  ·  ĐANG TIÊU HAO ĐIỂM",(640,748),13,ACCENT,True,"center")
        elif me and me["score"]<5:
            text(self.canvas,"Ăn đủ 5 điểm để mở bứt tốc",(640,748),14,MUTED,anchor="center")
        else:
            text(self.canvas,"Giữ SPACE hoặc CHUỘT TRÁI để bứt tốc",(640,748),13,TEXT,anchor="center")
        text(self.canvas,"CHUỘT  lái rắn     ENTER  chat     F1  hướng dẫn",(26,780),10,MUTED,anchor="bottomleft")
        if self.chat_open:
            panel(self.canvas,(24,482,426,262),(12,26,37),17)
            self.draw_chat_lines((43,501,384,153),6)
            self.fields["chat"].draw(self.canvas,(43,690,330,38))
            self.buttons.draw(self.canvas,"Gửi",(380,690,53,38),self.send_chat,True)
            self.active_fields=["chat"]
        else:
            for i,entry in enumerate(self.chat[-3:]):
                text(self.canvas,entry["name"]+": "+entry["text"],(27,663+i*23),12,MUTED,max_width=365)
        if self.dead:
            self.draw_death()

    def dim(self):
        overlay=pygame.Surface((1280,800),pygame.SRCALPHA)
        overlay.fill((3,9,16,205)); self.canvas.blit(overlay,(0,0))

    def draw_death(self):
        self.dim()
        self.buttons.items=[]
        self.active_fields=[]
        panel(self.canvas,(364,205,552,374),(16,28,40),25)
        pill(self.canvas,"LƯỢT CHƠI KẾT THÚC",(523,232),RED)
        text(self.canvas,"Một vòng chơi. Thêm kinh nghiệm.",(640,291),22,TEXT,True,"center")
        reason={"wall":"Bạn đã chạm biên đấu trường.","body":"Đầu rắn đã va vào thân đối thủ.","head":"Hai đầu rắn đã va chạm."}.get(self.dead["reason"],"Lượt chơi đã kết thúc.")
        text(self.canvas,reason,(640,328),14,MUTED,anchor="center")
        for i,(value,label) in enumerate([(self.dead["score"],"ĐIỂM CAO NHẤT"),(self.dead["max_length"],"ĐỘ DÀI TỐI ĐA"),(f"{int(self.dead['duration'])}s","THỜI GIAN")]):
            x=463+i*176
            text(self.canvas,value,(x,390),34,ACCENT,True,"center")
            text(self.canvas,label,(x,431),10,MUTED,True,"center")
        self.buttons.draw(self.canvas,"HỒI SINH  R",(398,491,237,51),lambda:self.send("RESPAWN"),True)
        self.buttons.draw(self.canvas,"Về sảnh",(649,491,233,51),lambda:self.send("LEAVE_ROOM"))

    def draw_modal(self):
        self.dim()
        self.buttons.items=[]
        self.active_fields=[]
        panel(self.canvas,(205,109,870,583),(16,28,40),24)
        title={"help":"Cách chơi", "rankings":"Bảng xếp hạng toàn máy chủ", "history":"Lịch sử 20 lượt gần nhất"}[self.modal]
        text(self.canvas,title,(239,141),25,TEXT,True)
        self.buttons.draw(self.canvas,"Đóng",(943,136,100,40),lambda:setattr(self,"modal",None))
        if self.modal=="help":
            rows=[("CHUỘT / WASD / MŨI TÊN","Dẫn đầu rắn về hướng mong muốn."),
                  ("SPACE / GIỮ CHUỘT TRÁI","Tăng tốc khi có ít nhất 5 điểm; mất 1 điểm mỗi 0,18 giây."),
                  ("ĂN HẠT PHÁT SÁNG","Tăng điểm và chiều dài. Hạt từ xác rắn có giá trị cao hơn."),
                  ("TRÁNH TƯỜNG VÀ THÂN ĐỐI THỦ","Không tự cắn đuôi. Va chạm đầu đối đầu có thể làm cả hai chết."),
                  ("ENTER / R / ESC","Chat trong trận / hồi sinh sau khi chết / rời phòng."),
                  ("F11 / F1","Toàn màn hình / mở hướng dẫn. Rắn mới có khiên 2 giây.")]
            for i,(heading,body) in enumerate(rows):
                y=214+i*67
                text(self.canvas,f"0{i+1}",(240,y),17,ACCENT,True)
                text(self.canvas,heading,(280,y),13,TEXT,True)
                text(self.canvas,body,(280,y+26),12,MUTED,max_width=740)
            text(self.canvas,"Muốn chơi LAN: chạy server với --host 0.0.0.0, nhập IP máy chủ tại màn hình đăng nhập.",(242,644),12,ACCENT)
        elif self.modal=="rankings":
            text(self.canvas,"Kỷ lục là điểm cao nhất đạt được trong một lượt. Bot không được lưu.",(240,192),13,MUTED)
            items=self.rankings
            offset=min(self.scroll,max(0,len(items)-9))
            for i,row in enumerate(items[offset:offset+9]):
                y=236+i*44
                panel(self.canvas,(239,y,804,37),(21,36,48) if i%2==0 else (16,28,40),7,None)
                text(self.canvas,f"{offset+i+1:02}",(256,y+10),13,MUTED,True)
                pygame.draw.circle(self.canvas,rgb(row["skin_color"]),(309,y+18),6)
                text(self.canvas,row["display_name"],(331,y+9),15,TEXT,True,max_width=500)
                text(self.canvas,row["highest_score"],(1024,y+9),15,ACCENT,True,"topright")
            text(self.canvas,"Cuộn chuột để xem tối đa 50 người chơi.",(240,651),12,MUTED)
        else:
            items=self.history
            for x,label in [(248,"Điểm cao nhất"),(389,"Đốt tối đa"),(510,"Thời gian"),(631,"Kết thúc"),(790,"Ngày chơi")]:
                text(self.canvas,label,(x,209),13,MUTED)
            if not items:
                text(self.canvas,"Chưa có lịch sử. Hoàn thành một lượt để ghi nhận kết quả.",(640,400),16,MUTED,anchor="center")
            offset=min(self.scroll,max(0,len(items)-9))
            for i,row in enumerate(items[offset:offset+9]):
                y=252+i*41
                text(self.canvas,str(row["score"]),(248,y),15,ACCENT,True)
                text(self.canvas,str(row["max_length"]),(389,y),14)
                text(self.canvas,f"{row['duration_seconds']:.1f}s",(510,y),14)
                text(self.canvas,row["death_reason"],(631,y),13,MUTED)
                text(self.canvas,row["played_at"][:19],(790,y),12,MUTED)
            text(self.canvas,"Điểm được ghi khi chết, rời trận hoặc mất kết nối; dữ liệu có thể trễ một nhịp lưu.",(240,651),11,MUTED)

    def update(self,now,dt):
        if self.net:
            for message in self.net.poll(): self.handle_message(message)
        if self.scene=="lobby" and now-self.last_refresh>3:
            self.send("LIST_ROOMS"); self.last_refresh=now
        if self.scene=="game" and not self.dead and not self.modal and now-self.last_input>=1/INPUT_RATE:
            keys=pygame.key.get_pressed()
            mx,my=self.mouse; x,y=self.world.me_screen
            angle=math.atan2(my-y,mx-x)
            dx=(keys[pygame.K_d] or keys[pygame.K_RIGHT])-(keys[pygame.K_a] or keys[pygame.K_LEFT])
            dy=(keys[pygame.K_s] or keys[pygame.K_DOWN])-(keys[pygame.K_w] or keys[pygame.K_UP])
            if not self.chat_open and (dx or dy): angle=math.atan2(dy,dx)
            hovering=any(r.collidepoint(self.mouse) for r,_,enabled in self.buttons.items if enabled)
            boost=not self.chat_open and (keys[pygame.K_SPACE] or (pygame.mouse.get_pressed()[0] and not hovering))
            if self.connected:
                self.seq+=1
                self.send("PLAYER_INPUT",angle=angle,boost=bool(boost),seq=self.seq)
            self.last_input=now

    def draw(self,now,dt):
        self.buttons.begin(self.mouse)
        self.active_fields=[]
        if self.scene!="game": self.backdrop.draw(self.canvas,now)
        if self.scene=="auth": self.draw_auth(now)
        elif self.scene=="lobby" and self.user: self.draw_lobby(now)
        elif self.scene=="room" and self.room: self.draw_room(now)
        elif self.scene=="game" and self.room: self.draw_game(now,dt)
        if self.modal: self.draw_modal()
        if not self.connected and self.scene!="auth":
            self.dim()
            self.buttons.items=[]
            text(self.canvas,self.connection_note,(640,385),25,RED,True,"center")
            text(self.canvas,"Đang khôi phục kết nối với máy chủ…",(640,426),15,MUTED,anchor="center")
        if now<self.toast_until:
            width=min(1200,font(14).size(self.toast_value)[0]+40)
            panel(self.canvas,((1280-width)//2,14,width,42),(42,24,34) if self.toast_error else (21,51,44),12,RED if self.toast_error else ACCENT)
            text(self.canvas,self.toast_value,(640,35),14,RED if self.toast_error else ACCENT,anchor="center",max_width=width-25)

    def frame(self):
        dt=min(.08,self.clock.tick(60)/1000)
        now=time.monotonic()
        ww,wh=self.window.get_size()
        scale=min(ww/1280,wh/800)
        dx,dy=(ww-1280*scale)/2,(wh-800*scale)/2
        pos=pygame.mouse.get_pos()
        self.mouse=((pos[0]-dx)/scale,(pos[1]-dy)/scale)
        for e in pygame.event.get(): self.event(e)
        self.update(now,dt)
        self.draw(now,dt)
        self.window.fill(BG)
        if ww==1280 and wh==800:
            self.window.blit(self.canvas,(0,0))
        else:
            self.window.blit(pygame.transform.smoothscale(self.canvas,(round(1280*scale),round(800*scale))),(round(dx),round(dy)))
        pygame.display.flip()

    def run(self):
        try:
            while self.running: self.frame()
        finally:
            if self.net: self.net.close()
            pygame.quit()
