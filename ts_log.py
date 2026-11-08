#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
日志加时间戳包装器：把任何命令的输出每行前面自动加上时间戳
用法: python3 ts_log.py <你的原命令> [参数...]
环境变量:
  TS_FMT: 时间格式串，默认 %Y-%m-%d %H:%M:%S
          支持所有datetime.strftime格式，额外支持:
            %f   : 6位微秒 (000000-999999)
            %3f  : 3位毫秒 (000-999)
  TZ: 时区，例如 Asia/Shanghai
"""
import os
import sys
import subprocess
import threading
import signal
from datetime import datetime

def now_str(fmt):
    """ 用datetime实现时间格式化，彻底抛弃time.strftime，支持%f/%3f"""
    now = datetime.now()
    # 先处理毫秒占位符%3f（要在%f之前替换，避免冲突）
    if "%3f" in fmt:
        ms = f"{now.microsecond // 1000:03d}"
        fmt = fmt.replace("%3f", ms)
    return now.strftime(fmt)

def stream_pipe(stream, out, prefix_fmt):
    """逐行读取子进程输出，加时间戳后写出"""
    try:
        for line in iter(stream.readline, b''):
            try:
                line = line.decode('utf-8', errors='replace')
            except:
                line = line.decode('latin-1', errors='replace')
            line = line.rstrip('\r\n')
            if line:  # 空行也保留格式，避免丢换行
                ts = now_str(prefix_fmt)
                out.write(f"[{ts}] {line}\n")
                try:
                    out.flush()
                except BrokenPipeError:
                    return
    finally:
        try:
            stream.close()
        except:
            pass

def main():
    # 忽略SIGPIPE，避免管道关闭时的错误（比如被head截断）
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    if len(sys.argv) < 2:
        print(f"用法: {sys.argv[0]} <命令> [参数...]", file=sys.stderr)
        print(f"示例: {sys.argv[0]} ffmpeg -i input.mp4 output.mp4", file=sys.stderr)
        print(f"环境变量: TS_FMT 时间格式，默认 %Y-%m-%d %H:%M:%S，支持%f微秒/%3f毫秒", file=sys.stderr)
        sys.exit(2)
        
    cmd = sys.argv[1:]
    
    # 时间格式，支持环境变量TS_FMT自定义
    fmt = os.environ.get("TS_FMT", "%Y-%m-%d %H:%M:%S")
    
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=sys.stdin,  # 透传标准输入
            universal_newlines=False,
        )
    except FileNotFoundError:
        ts = now_str(fmt)
        print(f"[{ts}] 错误: 命令不存在: {cmd[0]}", file=sys.stderr)
        sys.exit(127)
    except Exception as e:
        ts = now_str(fmt)
        print(f"[{ts}] 启动命令失败: {e}", file=sys.stderr)
        sys.exit(1)
        
    # 单独线程读输出，保证实时性，实时加时间戳写到stdout
    t = threading.Thread(target=stream_pipe, args=(proc.stdout, sys.stdout, fmt), daemon=True)
    t.start()
    
    # 透传信号给子进程
    def signal_handler(sig, frame):
        try:
            proc.send_signal(sig)
        except:
            pass
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # 等待子进程退出
    ret = proc.wait()
    t.join(timeout=1)
    sys.exit(ret)
    
if __name__ == "__main__":
    main()
