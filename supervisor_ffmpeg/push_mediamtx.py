#!/usr/bin/env python3
import os
import sys
from pathlib import Path
import subprocess
import re
import argparse
import shlex

# ================= 配置区 =================

# 支持的视频格式 (小写)
ALLOWED_EXTS = {'.mp4', '.mkv', '.mov', '.flv'}

# =========================================

# 设置当前进程的环境变量 TZ
os.environ['TZ'] = 'Asia/Shanghai'


def natural_sort_key(text: str):
    """
    自然排序键值函数
    将字符串拆分为数字和非数字部分，数字部分转为 int 进行比较
    """
    return [int(c) if c.isdigit() else c.lower() for c in re.split(r'(\d+)', text)]

def generate_playlist(root_dir: str, output_file: str, allowed_exts: set, recursive: int = 1):
    """
    生成播放列表
    :param root_dir: 视频根目录
    :param output_file: 输出列表文件路径
    :param allowed_exts: 允许的文件扩展名集合
    :param recursive: 递归开关。0=仅当前目录(不进入子文件夹), 1=递归所有子目录
    """
    root_path = Path(root_dir)
    
    # 1. 基础检查
    if not root_path.is_dir():
        print(f"❌ 错误: 目录不存在 -> {root_dir}")
        return False
    
    all_videos = []
    
    # 2. 根据开关选择扫描方式
    if recursive:
        # --- 模式 1: 递归扫描 ---
        # rglob("**/*") 会递归查找所有子目录
        for file_path in root_path.rglob("*"):
            if file_path.is_file() and file_path.suffix.lower() in allowed_exts:
                all_videos.append(file_path)
    else:
        # --- 模式 0: 仅当前目录 (非递归) ---
        # iterdir() 只列出当前层级，不进入子目录
        for file_path in root_path.iterdir():
            if file_path.is_file() and file_path.suffix.lower() in allowed_exts:
                all_videos.append(file_path)
            
    if not all_videos:
        mode_str = "及其子目录" if recursive else "(仅当前层级)"
        print(f"⚠️ 未在 {root_dir} {mode_str}中找到支持格式的视频")
        return False

    # 3. 核心排序逻辑：双重排序
    # 即使是不递归，这个排序逻辑也兼容（此时 dir_parts 为空元组，只比较文件名）
    def sort_key(file_path: Path):
        # 获取相对于根目录的路径
        rel_path = file_path.relative_to(root_path)
        
        # 分解路径：parts 返回元组，例如 ('SubDir', 'video.mp4')
        parts = rel_path.parts
        dir_parts = parts[:-1]  # 目录部分
        file_name = parts[-1]   # 文件名
        
        # 构建排序键：(目录路径的自然排序键, 文件名的自然排序键)
        dir_key = tuple(natural_sort_key(part) for part in dir_parts)
        file_key = natural_sort_key(file_name)
        
        return (dir_key, file_key)

    # 执行排序
    all_videos.sort(key=sort_key)

    # 4. 写入播放列表
    try:
        with open(output_file, 'w', encoding='utf-8') as f_out:
            for file_path in all_videos:
                # 获取绝对路径
                abs_path = file_path.resolve()
                # 写入 FFmpeg concat 格式
                f_out.write(f"file '{abs_path}'\n")
        
        mode_str = "递归" if recursive else "非递归(仅当前目录)"
        print(f"✅ [{mode_str}] 列表已生成: {output_file}")
        print(f"   共找到 {len(all_videos)} 个视频文件")
        
        # 打印前5个预览
        print("   📋 列表前5项预览:")
        for i, p in enumerate(all_videos[:5]):
            rel = p.relative_to(root_path)
            print(f"      {i+1}. {rel}")
        if len(all_videos) > 5:
            print(f"      ... 还有 {len(all_videos)-5} 个文件")
            
        return True
        
    except IOError as e:
        print(f"❌ 写入文件失败: {e}")
        return False


def push_video(playlist, rtmp_url):
    
    # 不重新编码
    video_cmd = [
        "ffmpeg", 
        "-hide_banner", "-loglevel", "error",
        "-re", 
        "-f", "concat", "-safe", "0", 
        "-stream_loop", "-1",
        "-i", playlist,
        "-c:v", "copy",
        "-c:a", "aac",
        "-f", "flv",
        rtmp_url
    ]
    '''
    # 重新编码
    # webrtc 播放时没有声音，向 mediamtx 推流时把 "-c:a aac" 改成 "-c:a libopus"
    video_cmd = [
        "ffmpeg", 
        "-hide_banner", "-loglevel", "error",
        "-re", 
        "-f", "concat", "-safe", "0", 
        "-stream_loop", "-1",
        "-i", playlist,
        "-vf", "scale=1920:1080",
        "-c:v", "libx264", "-preset", "ultrafast", "-tune", "zerolatency", "-pix_fmt", "yuv420p",
        "-r", "30",  "-fps_mode", "cfr", 
        "-bf", "0", "-g", "30", "-keyint_min", "30", "-sc_threshold", "0",
        #"-b:v", "2M", "-minrate", "1M", "-maxrate", "3M", "-bufsize", "6M",
        "-c:a", "aac", "-b:a", "128k",
        "-f", "flv",
        rtmp_url
    ]
    '''
    return video_cmd


# ffmpeg -hide_banner -loglevel warning  -f v4l2 -input_format mjpeg -video_size 1280x720 -framerate 30 -i /dev/video0    -f lavfi -i anullsrc=channel_layout=stereo:sample_rate=48000    -c:v libx264 -tune zerolatency -preset ultrafast -pix_fmt yuv420p    -b:v 4M -minrate 3M -maxrate 5M -bufsize 10M    -c:a aac -b:a 128k    -map 0:v -map 1:a    -vf "drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:text='%{localtime\:%Y-%m-%d %a %X}':x=120:y=350:fontsize=80:fontcolor=black:borderw=1:bordercolor=white"    -af "highpass=f=100,afftdn=nr=15:nf=-50:tn=1,acompressor=threshold=-20dB:ratio=4:attack=200:release=1000"    -r 30 -g 60 -keyint_min 60    -f flv "rtmp://127.0.0.1:1935/show-rtc/abc123456"

def push_camera(cam_device, push_rtmp_url):
    # 使用时 shell=False 或者 省略（缺省值为 False）
    '''
    #音频设置为无声的音频
    "-f", "lavfi",
    "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
    #音频降噪设置
    "-af", "highpass=f=100,afftdn=nr=15:nf=-50:tn=1,acompressor=threshold=-20dB:ratio=4:attack=200:release=1000",
    
    camera_cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel", "error",
        "-f", "v4l2", "-input_format", "mjpeg", "-video_size", "1280x720", "-framerate", "30",
        "-i", cam_device,
        "-f", "lavfi",
        "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
        "-c:v", "libx264", "-tune", "zerolatency", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
        "-b:v", "4M", "-minrate", "3M", "-maxrate", "5M", "-bufsize", "10M",
        "-c:a", "aac", "-b:a", "128k",
        "-map", "0:v", "-map", "1:a",
        "-vf", "drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:text='%{localtime\:%Y-%m-%d %a %X}':x=20:y=20:fontsize=30:fontcolor=black:borderw=1:bordercolor=white",
        "-af", "highpass=f=100,afftdn=nr=15:nf=-50:tn=1,acompressor=threshold=-20dB:ratio=4:attack=200:release=1000",
        "-r", "30", "-g", "30", "-keyint_min", "30",
        "-f", "flv",
        push_rtmp_url
    ]
    '''
    #视频无音频模式
    camera_cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel", "error",
        "-f", "v4l2", "-input_format", "mjpeg", "-video_size", "1280x720", "-framerate", "30",
        "-i", cam_device,
        "-c:v", "libx264", "-tune", "zerolatency", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
        "-b:v", "4M", "-minrate", "3M", "-maxrate", "5M", "-bufsize", "10M",
        "-vf", "drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:text='%{localtime\:%Y-%m-%d %a %X}':x=20:y=20:fontsize=30:fontcolor=black:borderw=1:bordercolor=white",
        "-r", "30", "-g", "30", "-keyint_min", "30",
        "-f", "flv",
        push_rtmp_url
    ]
    return camera_cmd


# ========================================================================
# 命令渲染
# ========================================================================
def quote(tok):
    """需要时给 token 加双引号，保证可直接粘贴执行。"""
    if tok and any(c in tok for c in " ;[]"):
        return f'"{tok}"'
    return tok

def render(groups):
    return " \\\n  ".join(" ".join(quote(t) for t in g) for g in groups)


def is_numeric_arg(arg):
    """
    判断一个字符串是否是数字（包括负数、整数、浮点数）
    例如: '-1', '123', '-3.14', '0' -> True
         '-a', 'abc', '-' -> False
    """
    if not arg:
        return False
    # 尝试转换为浮点数，如果能成功，说明是数字
    try:
        float(arg)
        return True
    except ValueError:
        return False

def print_ffmpeg_cmd_advanced(cmd_list):
    """
    高级格式化打印 FFmpeg 命令：
    1. 遍历参数列表。
    2. 如果当前参数以 '-' 开头：
       - 检查下一个参数是否存在。
       - 如果下一个参数是“值”（即：不以 '-' 开头 OR 是以 '-' 开头的纯数字），则合并当前和下一个参数。
       - 否则，当前参数单独一行。
    3. 如果当前参数不以 '-' 开头：
       - 说明它已经被上一个参数“认领”并合并了，跳过（除非逻辑有误，这里假设输入列表合法）。
       - *注意*：为了鲁棒性，如果遇到不以 '-' 开头且未被认领的元素，单独打印。
    4. 最后一行去掉反斜杠。
    5. 使用 shlex.quote 确保特殊字符安全。
    """
    if not cmd_list:
        return

    lines = []
    i = 0
    n = len(cmd_list)

    while i < n:
        arg = cmd_list[i]
        safe_arg = shlex.quote(arg)
        
        # 标记当前参数是否已经被处理（作为值被合并到前一行）
        # 在这个循环结构中，我们只处理“键”或“独立参数”。
        # 如果 arg 不以 '-' 开头，且不是第一个元素，它通常是上一个元素的值。
        # 但为了简单起见，我们主要关注以 '-' 开头的元素作为“锚点”。
        
        if arg.startswith('-'):
            # 当前是一个潜在的“键”
            # 检查是否可以与下一个参数合并
            merged = False
            if i + 1 < n:
                next_arg = cmd_list[i+1]
                # 判断下一个参数是否是“值”：
                # 1. 不以 '-' 开头 (标准值，如 'input.mp4')
                # 2. 以 '-' 开头但是纯数字 (如 '-1', '-2')
                if not next_arg.startswith('-') or is_numeric_arg(next_arg):
                    safe_next = shlex.quote(next_arg)
                    lines.append(f"  {safe_arg} {safe_next} \\")
                    i += 2  # 跳过下一个参数
                    merged = True
            
            if not merged:
                # 不能合并，单独一行
                lines.append(f"  {safe_arg} \\")
                i += 1
        else:
            # 当前参数不以 '-' 开头
            # 这种情况通常发生在：
            # 1. 第一个参数不是 ffmpeg（少见）
            # 2. 逻辑遗漏：上一个参数没有认领它（比如上一个也是非横杠，或者上一个横杠参数没合并它）
            # 为了安全，单独打印
            lines.append(f"  {safe_arg} \\")
            i += 1

    # 处理最后一行：去掉末尾的 " \"
    if lines:
        lines[-1] = lines[-1].rstrip(" \\")
    
    print("\n".join(lines))


# ========================================================================
# 入口
# ========================================================================
def main():
    
    # ================= 使用示例 =================
    # 修改这里的 recursive 值来切换模式：
    # recursive=1 -> 开启递归，查找所有子目录
    # recursive=0 -> 关闭递归，只查找 --input 直接包含的文件
    
    ap = argparse.ArgumentParser(
        description="推流命令",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        
    )
    
    ap.add_argument("-i", "--input", default=None, help="输入源，目录或摄像头设备地址")
    ap.add_argument("-s", "--stream", default=None, help="直播地址")
    ap.add_argument("--run", action="store_true", help="直接执行")
    
    args = ap.parse_args()
    
    source     = args.input
    stream_url = args.stream
    
    # 如果输入源以 /dev/ 开头，则说明是摄像头设备
    if source.startswith("/dev/"):
        print("你可以启动 FFmpeg 进行摄像头推流了。")
        cmd = push_camera(source, stream_url)
        
    else:
        playlist_file = os.path.join(source, "playlist.txt")
        success = generate_playlist(source, playlist_file, ALLOWED_EXTS, recursive=1)
        
        if success:
            print("视频文件列表生成成功！你可以启动 FFmpeg 进行视频文件推流了。")
            cmd = push_video(playlist_file, stream_url)
    
    # ---------- 打印 ----------
    print("=" * 72)
    print("📋 生成的 FFmpeg 命令：")
    print("-" * 72)
    print_ffmpeg_cmd_advanced(cmd) #展示命令行
    print("-" * 72)
    print()
    
    if not args.run:
        print("💡 只打印不执行。加 --run 直接跑，上面格式化后的命令行只是为了方便观看。")
        return 0
    
    subprocess.run(cmd)
    
if __name__ == "__main__":
    sys.exit(main())
