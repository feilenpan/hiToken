// 资源减重说明（开发者须知）
// 1. 所有静态图片优先使用 WebP（比 JPG/PNG 小 30%~70%）
// 2. static/images/demo/** 不打包（见 project.config.json packOptions.ignore）
// 3. 大图一律通过 CDN/对象存储按需加载；把域名加入 downloadFile 合法域名
// 4. 禁用未使用页面（如 enhance），避免进入主包
// 5. 分包：pkg-user（历史/我的）、pkg-legal（隐私/协议，independent）
