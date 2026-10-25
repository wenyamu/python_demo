

cat > /etc/supervisor/my_config.ini <<EOF
#web管理界面
[inet_http_server]
port = 0.0.0.0:8000
username = admin
password = admin
EOF