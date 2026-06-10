# 时光上色 - AI老照片上色工具

## 📋 项目概述

「时光上色」是一款基于AI技术的微信小程序，能够将黑白老照片智能转换为彩色照片。

### 核心功能

- ✅ AI智能上色（支持多种引擎）
- ✅ 微信登录
- ✅ 额度管理（免费+付费）
- ✅ 上色记录
- ✅ 分享得额度
- ✅ 隐私协议合规
- ✅ 数据删除请求

---

## 🏗️ 技术架构

### 后端 (Python)

```
colorize-app/
├── app.py              # 主应用（FastAPI）
├── database.py         # 数据库模块
├── colorize_engine.py  # AI上色引擎
├── palette_api.py      # Palette API封装
├── deploy.sh           # 部署脚本
├── requirements.txt    # Python依赖
├── .env                # 环境变量
├── uploads/            # 上传文件目录
├── output/             # 输出文件目录
└── static/             # 静态资源
```

### 前端 (微信小程序)

```
colorize-miniapp/
├── app.js              # 全局逻辑
├── app.json            # 全局配置
├── app.wxss            # 全局样式
├── project.config.json # 项目配置
├── pages/
│   ├── index/          # 首页
│   ├── preview/        # 预览页
│   ├── result/         # 结果页
│   ├── history/        # 历史记录
│   ├── profile/        # 我的
│   ├── privacy/        # 隐私协议
│   └── agreement/      # 服务协议
└── static/
    └── images/         # 图片资源
```

---

## 🚀 快速开始

### 1. 环境要求

- Python 3.9+
- Node.js 16+
- 微信开发者工具

### 2. 后端启动

```bash
cd colorize-app

# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 初始化数据库
python3 database.py

# 启动服务
python3 app.py
```

后端服务将在 `http://localhost:8888` 启动。

### 3. 小程序开发

1. 打开微信开发者工具
2. 导入 `colorize-miniapp` 目录
3. 配置 AppID（或使用测试号）
4. 修改 `app.js` 中的 `API_BASE` 为后端地址
5. 编译预览

---

## 🔌 API 接口

### 公开接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/health` | GET | 健康检查 |
| `/api/privacy` | GET | 获取隐私政策 |
| `/api/agreement` | GET | 获取服务协议 |

### 用户接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/wechat/login` | POST | 微信登录 |
| `/api/user/info` | GET | 获取用户信息 |
| `/api/user/agree-privacy` | POST | 同意隐私协议 |
| `/api/user/agree-agreement` | POST | 同意服务协议 |
| `/api/user/request-deletion` | POST | 申请数据删除 |

### 功能接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/colorize` | POST | Web端上色（免费） |
| `/api/wechat/colorize` | POST | 小程序上色（扣额度） |
| `/api/records` | GET | 获取上色记录 |
| `/api/orders` | GET | 获取订单记录 |
| `/api/order/create` | POST | 创建订单 |

---

## 📱 小程序页面

### 首页 (index)

- 品牌展示
- 效果轮播
- 选择照片入口
- 隐私协议确认弹窗

### 预览页 (preview)

- 图片预览
- 文件信息
- 确认上色

### 结果页 (result)

- 上色进度
- 对比展示（滑块）
- 保存/分享

### 历史页 (history)

- 上色记录列表
- 保存到相册

### 我的 (profile)

- 用户信息
- 额度显示
- 套餐购买
- 分享得额度
- 联系客服

### 隐私协议 (privacy)

- 完整隐私政策

### 服务协议 (agreement)

- 完整服务协议

---

## 🔒 合规性

### 已实现

- ✅ 隐私保护政策
- ✅ 用户服务协议
- ✅ 协议确认流程
- ✅ 数据删除请求
- ✅ 未成年人保护说明
- ✅ 客服联系方式

### 待完善

- ⏳ ICP备案（大陆服务器）
- ⏳ 小程序审核提交
- ⏳ SSL证书配置
- ⏳ 微信支付接入

---

## 🛡️ 安全措施

### 已实现

- ✅ HTTPS加密传输
- ✅ 数据库加密存储
- ✅ 文件上传限制（10MB）
- ✅ 文件类型验证
- ✅ 用户鉴权
- ✅ SQL注入防护

### 待加强

- ⏳ JWT Token认证
- ⏳ 接口限流
- ⏳ 日志审计
- ⏳ 入侵检测

---

## 📦 部署

### 方式一：本地部署

```bash
# 运行部署脚本
chmod +x deploy.sh
./deploy.sh
```

### 方式二：云服务器部署

1. 购买云服务器（推荐阿里云/腾讯云香港节点）
2. 上传代码
3. 运行部署脚本
4. 配置域名和SSL

### 方式三：容器化部署

```bash
# 构建Docker镜像
docker build -t colorize-app .

# 运行容器
docker run -d -p 8888:8888 colorize-app
```

---

## 📊 数据库

### 表结构

- `users` - 用户表
- `colorize_records` - 上色记录表
- `orders` - 订单表
- `share_records` - 分享记录表
- `deletion_requests` - 数据删除请求表

### 生产环境建议

- SQLite → PostgreSQL
- 添加数据库备份
- 配置读写分离

---

## 🔧 配置说明

### 环境变量

```bash
# 数据库
DB_TYPE=sqlite  # sqlite, postgresql, mysql
DB_PATH=colorize.db
DATABASE_URL=postgresql://user:pass@localhost/db

# 服务器
HOST=0.0.0.0
PORT=8888
DEBUG=false

# 安全
SECRET_KEY=your-secret-key
```

---

## 📈 性能优化

### 已实现

- ✅ 数据库索引
- ✅ 静态文件缓存
- ✅ Gzip压缩
- ✅ 图片压缩

### 待优化

- ⏳ CDN加速
- ⏳ Redis缓存
- ⏳ 异步处理
- ⏳ 负载均衡

---

## 🐛 常见问题

### Q: 小程序无法连接后端？

A: 检查以下配置：
1. 后端服务是否启动
2. `app.js` 中的 `API_BASE` 是否正确
3. 小程序是否配置了合法域名

### Q: 上色失败？

A: 检查以下原因：
1. 图片格式是否支持（JPG/PNG）
2. 图片大小是否超过10MB
3. AI引擎是否正常

### Q: 如何申请数据删除？

A: 在小程序内「我的」→「联系客服」提交申请，或发送邮件至 privacy@colorize-hk.com

---

## 📞 联系我们

- **客服微信：** colorize_hk
- **邮箱：** support@colorize-hk.com
- **地址：** 中国香港

---

## 📄 许可证

本项目为私有项目，未经授权禁止使用。

---

**最后更新：2026年5月16日**
