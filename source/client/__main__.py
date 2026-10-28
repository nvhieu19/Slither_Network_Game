import argparse
import os
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT","1")
from client.app import App


def main():
    parser=argparse.ArgumentParser(description="Neon Slither graphical client")
    parser.add_argument("--host",default="127.0.0.1")
    parser.add_argument("--port",type=int,default=5555)
    parser.add_argument("--username",help="Optional demo autologin")
    parser.add_argument("--password",help="Use only demo credentials in command-line arguments")
    args=parser.parse_args()
    App(args.host,args.port,args.username,args.password).run()


if __name__=="__main__":
    main()
