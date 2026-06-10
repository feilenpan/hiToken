#!/bin/bash
# 时光上色 - 服务器部署脚本
# 使用方法: ./deploy.sh

set -e  # 遇到错误立即退出

echo "🚀 开始部署时光上色..."

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 检查是否为root用户
if [ "$EUID" -eq 0 ]; then
    echo -e "${RED}请不要使用root用户运行此脚本${NC}"
    exit 1
fi

# 配置变量
APP_NAME="colorize-app"
APP_DIR="$HOME/$APP_NAME"
PYTHON_VERSION="3.11"
DOMAIN="${DOMAIN:-localhost}"

echo -e "${YELLOW}📦 安装系统依赖...${NC}"

# 检测操作系统
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    echo "检测到 macOS"
    brew update
    brew install python@$PYTHON_VERSION nginx
elif [[ -f /etc/debian_version ]]; then
    # Debian/Ubuntu
    sudo apt update
    sudo apt install -y python3 python3-pip python3-venv nginx
elif [[ -f /etc/redhat-release ]]; then
    # CentOS/RHEL
    sudo yum update
    sudo yum install -y python3 python3-pip nginx
fi

echo -e "${GREEN}✅ 系统依赖安装完成${NC}"

# 创建应用目录
echo -e "${YELLOW}📁 创建应用目录...${NC}"
mkdir -p $APP_DIR
cd $APP_DIR

# 创建Python虚拟环境
echo -e "${YELLOW}🐍 创建Python虚拟环境...${NC}"
python3 -m venv venv
source venv/bin/activate

# 安装Python依赖
echo -e "${YELLOW}📦 安装Python依赖...${NC}"
pip install --upgrade pip
pip install -r requirements.txt

echo -e "${GREEN}✅ Python依赖安装完成${NC}"

# 创建.env文件
echo -e "${YELLOW}⚙️  配置环境变量...${NC}"
if [ ! -f .env ]; then
    cat > .env << EOF
# 数据库配置
DB_TYPE=sqlite
DB_PATH=colorize.db

# 生产环境建议使用PostgreSQL
# DB_TYPE=postgresql
# DATABASE_URL=postgresql://user:password@localhost:5432/colorize

# 服务器配置
HOST=0.0.0.0
PORT=8888
DEBUG=false

# 安全配置
SECRET_KEY=$(openssl rand -hex 32)
EOF
    echo -e "${GREEN}✅ .env 文件已创建${NC}"
else
    echo -e "${YELLOW}⚠️  .env 文件已存在，跳过创建${NC}"
fi

# 初始化数据库
echo -e "${YELLOW}💾 初始化数据库...${NC}"
python3 database.py
echo -e "${GREEN}✅ 数据库初始化完成${NC}"

# 创建systemd服务
echo -e "${YELLOW}🔧 创建系统服务...${NC}"
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    sudo tee /etc/systemd/system/colorize.service > /dev/null << EOF
[Unit]
Description=时光上色 API 服务
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$APP_DIR
Environment="PATH=$APP_DIR/venv/bin"
ExecStart=$APP_DIR/venv/bin/python3 app.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

    sudo systemctl daemon-reload
    sudo systemctl enable colorize
    sudo systemctl start colorize
    
    echo -e "${GREEN}✅ 系统服务已创建并启动${NC}"
fi

# 配置Nginx
echo -e "${YELLOW}🌐 配置Nginx...${NC}"
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    sudo tee /etc/nginx/sites-available/colorize > /dev/null << EOF
server {
    listen 80;
    server_name $DOMAIN;

    # 安全头
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;

    # 静态文件
    location /static/ {
        alias $APP_DIR/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # API代理
    location / {
        proxy_pass http://127.0.0.1:8888;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        
        # 上传限制
        client_max_body_size 10M;
    }

    # Gzip压缩
    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml application/xml+rss text/javascript;
}
EOF

    # 启用站点
    sudo ln -sf /etc/nginx/sites-available/colorize /etc/nginx/sites-enabled/
    sudo nginx -t
    sudo systemctl restart nginx
    
    echo -e "${GREEN}✅ Nginx配置完成${NC}"
fi

# 创建上传和输出目录
mkdir -p uploads output results

echo -e "${GREEN}✅ 部署完成！${NC}"
echo ""
echo -e "${YELLOW}📋 后续步骤：${NC}"
echo "1. 配置域名解析: $DOMAIN -> 服务器IP"
echo "2. 申请SSL证书: sudo certbot --nginx -d $DOMAIN"
echo "3. 配置防火墙: 允许80和443端口"
echo "4. 测试API: curl http://$DOMAIN/api/health"
echo ""
echo -e "${YELLOW}🔧 常用命令：${NC}"
echo "查看服务状态: sudo systemctl status colorize"
echo "查看日志: sudo journalctl -u colorize -f"
echo "重启服务: sudo systemctl restart colorize"
echo ""
echo -e "${GREEN}🎉 时光上色已成功部署！${NC}"
