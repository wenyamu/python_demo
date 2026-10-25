## mediamtx 搭建(替换 nginx + rmtp 环境)
> 以我的香橙派为例，下载 arm64 版本，如果是服务器请下载 amd64 版本，配置都是一样的
> 
> 二进制文件下载 https://github.com/bluenviron/mediamtx/releases
>
> https://github.com/bluenviron/mediamtx/releases/download/v1.21.2/mediamtx_v1.21.2_linux_arm64.tar.gz

```
mkdir -p /usr/local/mediamtx && \
cd /usr/local/mediamtx && \
wget -c -t 0 -T 30 https://github.com/bluenviron/mediamtx/releases/download/v1.21.2/mediamtx_v1.21.2_linux_arm64.tar.gz && \
tar -xf mediamtx_v1.21.2_linux_arm64.tar.gz -C /usr/local/mediamtx


wget 命令详解
断点续传：-c ，靠本地已存在的同名文件判断进度，如果删了或改了文件名，就会当成新任务从头下载。
‌无限重试‌：-t 0，网络不稳定时自动重连，适合长时间挂机下载。
‌超时控制‌：-T 30，避免服务器无响应时无限等待。
‌后台下载‌：-b，不占用终端，日志默认写到 wget-log，用 tail -f wget-log 查看进度。
‌指定文件名‌：-O 下载文件重新命名，配合续传时注意文件名和路径要保持一致。‌‌

tar 命令详解
-C /usr/local/mediamtx 解压到指定目录中
```

```
# 先备份配置文件
cp mediamtx.yml mediamtx.yml.bak

#查看配置文件(过滤掉配置文件中的注释项)并写入另一文件
grep -v "#" mediamtx.yml.bak > mediamtx.yml
```

```
#配置文件中添加"网络实时通信附加主机ip",也就 mediamtx 运行的服务器ip，如果是局域网，可以不填
webrtcAdditionalHosts: ["192.168.1.121"]

#在配置文件底部的 paths: 下添加两个路径 rtmp-webrtc 和 rtsp-webrtc 
paths:
  rtmp-webrtc:
    # 来源设为 rtmp 外部推流
    source: rtmp://127.0.0.1:1935/show-rtc/abc123456
    sourceOnDemand: yes  # 有人观看才启动拉流，无人时自动停流省资源
  rtsp-webrtc:
    # 来源设为 rtsp 外部推流
    source: rtsp://127.0.0.1:8554/opi-cam
    sourceOnDemand: yes  # 有人观看才启动拉流，无人时自动停流省资源
```

### 开启服务器的tcp 和 udp 端口范围 8000-8999，用的端口比较多，大范围覆盖即可
```
#检测配置文件是否有问题
/usr/local/mediamtx/mediamtx --validate-conf /usr/local/mediamtx/mediamtx.yml

#运行，推荐指定配置文件，不指定时，有时会发生配置文件引用错误的情况
TZ=Asia/Shanghai /usr/local/mediamtx/mediamtx /usr/local/mediamtx/mediamtx.yml

#推流
# rtmp
TZ=Asia/Shanghai ffmpeg-diy -y \
   -f v4l2 -input_format mjpeg -video_size 1280x720 -framerate 30 -i /dev/video0 \
   -f lavfi -i anullsrc=channel_layout=stereo:sample_rate=48000 \
   -c:v libx264 -tune zerolatency -preset ultrafast -pix_fmt yuv420p \
   -b:v 4M -minrate 3M -maxrate 5M -bufsize 10M \
   -c:a aac -b:a 128k \
   -map 0:v -map 1:a \
   -vf "drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:text='%{localtime\:%Y-%m-%d %a %X}':x=120:y=350:fontsize=80:fontcolor=black:borderw=1:bordercolor=white" \
   -af "highpass=f=100,afftdn=nr=15:nf=-50:tn=1,acompressor=threshold=-20dB:ratio=4:attack=200:release=1000" \
   -r 30 -g 60 -keyint_min 60 \
   -f flv "rtmp://127.0.0.1:1935/show-rtc/abc123456"

# rtsp
TZ=Asia/Shanghai ffmpeg-diy -y \
   -f v4l2 -input_format mjpeg -video_size 1280x720 -framerate 30 -i /dev/video0 \
   -f alsa -ar 48000 -ac 2 -i plughw:3,0 \
   -c:v libx264 -tune zerolatency -preset ultrafast -pix_fmt yuv420p \
   -b:v 4M -minrate 3M -maxrate 5M -bufsize 10M \
   -c:a aac -b:a 128k \
   -map 0:v -map 1:a \
   -vf "drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:text='%{localtime\:%Y-%m-%d %a %X}':x=10:y=10:fontsize=22:fontcolor=black:borderw=1:bordercolor=white" \
   -af "highpass=f=100,afftdn=nr=15:nf=-50:tn=1,acompressor=threshold=-20dB:ratio=4:attack=200:release=1000" \
   -r 30 -g 60 -keyint_min 60 \
   -f rtsp "rtsp://127.0.0.1:8554/opi-cam"

```

```
# 浏览器访问 网络实时通信 webrtc 低延迟，局域网内延迟不明显
http://192.168.1.121:8889/rtmp-webrtc
http://192.168.1.121:8889/rtsp-webrtc

这里注意：
#"-c:a aac" 进行 webrtc 播放时没有声音，向 mediamtx 推流时改成 "-c:a libopus"，因为 webrtc 不支持 aac 音频编码；但是又会导致 rmtp 拉流时没有声音

如果想访问 hls，以下两种方式，延迟不一样
http://192.168.1.121:8888/rtmp-webrtc #延迟低
http://192.168.1.121:8888/rtmp-webrtc/index.m3u8 #延迟高
```
```
# 查看 ffmpeg 是否运行
ps aux | grep -i ffmpeg
ps aux | grep -i mediamtx
ps aux | grep -i supervisor
```
