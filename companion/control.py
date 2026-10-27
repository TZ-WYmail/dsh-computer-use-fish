#!/usr/bin/env python3
"""Local display-only controls. Never sends desktop input or changes task state."""
import argparse,json,os,socket,stat,tempfile
from pathlib import Path

def main():
    parser=argparse.ArgumentParser(description='DSH 鱼娘显示开关；隐藏不会停止电脑操作')
    parser.add_argument('command',choices=['show','hide','status'],nargs='?',default='status')
    args=parser.parse_args();found=0
    for path in Path(tempfile.gettempdir()).glob(f'dsh-fish-{os.getuid()}-*/control.json'):
        try:
            info=path.lstat()
            if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid() or info.st_mode&0o077:continue
            config=json.loads(path.read_text())
            if Path(config['socket']).parent!=path.parent:continue
            with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as client:
                client.settimeout(2);client.connect(config['socket'])
                stream=client.makefile('r',encoding='utf-8')
                client.sendall((json.dumps({'type':'hello','role':'control','token':config['token']})+'\n').encode())
                json.loads(stream.readline(4096))
                client.sendall((json.dumps({'type':'control','command':args.command})+'\n').encode())
                result=json.loads(stream.readline(4096))
                print('鱼娘：'+('显示' if result['visible'] else '隐藏')+'；'+('已连接' if result['connected'] else '渲染器未连接')+'；'+('定位已校准' if result.get('calibrated') else '定位待校准'))
                found+=1
        except (OSError,ValueError,KeyError,TypeError):continue
    if not found:print('鱼娘尚未运行；请启动 DSH 并在插件配置中启用桌宠。')
    return 0 if found else 1
if __name__=='__main__':raise SystemExit(main())
