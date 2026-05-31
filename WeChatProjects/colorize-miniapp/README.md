# 时光上色 - 微信小程序

## 📁 项目结构

```
colorize-miniapp/
├── app.js                    # 全局逻辑
├── app.json                  # 全局配置（页面路由、tabBar）
├── app.wxss                  # 全局样式
├── project.config.json       # 项目配置
├── sitemap.json              # 站点地图
├── pages/
│   ├── index/                # 首页（上传、上色、结果）
│   │   ├── index.wxml
│   │   ├── index.wxss
│   │   ├── index.js
│   │   └── index.json
│   ├── history/              # 历史记录
│   │   ├── history.wxml
│   │   ├── history.wxss
│   │   ├── history.js
│   │   └── history.json
│   └── profile/              # 我的（额度、购买）
│       ├── profile.wxml
│       ├── profile.wxss
│       ├── profile.js
│       └── profile.json
└── static/
    └── images/               # 图片资源
        ├── tab-*.png         # tabBar 图标
        ├── demo-*.jpg        # 示例图片
        └── demo/             # 效果对比图
```

## 🚀 使用方法

### 1. 下载微信开发者工具

https://developers.weixin.qq.com/miniprogram/dev/devtools/download.html

### 2. 导入项目

打开微信开发者工具 → 导入项目 → 选择 `~/WeChatProjects/colorize-miniapp` 目录

### 3. 配置 AppID

在 `project.config.json` 中修改 `appid`：
- 测试：使用 `touristappid`
- 正式：使用你的小程序 AppID

### 4. 配置后端地址

在 `app.js` 中修改 `API_BASE`：
```javascript
// 本地测试
API_BASE: 'http://localhost:8888'

// 正式环境
API_BASE: 'https://your-domain.com'
```

### 5. 预览/编译

点击「预览」或「真机调试」即可在手机上测试

## 📱 页面说明

### 首页 (index)
- 选择照片（相册/拍照）
- 预览确认
- AI 上色处理
- 结果对比（滑块对比）
- 保存/分享

### 历史记录 (history)
- 查看上色记录
- 保存到相册

### 我的 (profile)
- 查看额度
- 购买额度包
- 分享得额度
- 联系客服

## ⚙️ 后端接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/wechat/login` | POST | 微信登录 |
| `/api/wechat/user` | GET | 用户信息 |
| `/api/colorize` | POST | 图片上色 |
| `/api/wechat/order` | POST | 创建订单 |
