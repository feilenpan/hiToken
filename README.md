# hiToken

**Top 模型 × 薅羊毛聚合站** — 面向中文开发者的轻量 AI API 免费额度信息站。

> 聚焦 Top 10 大模型的"今天能免费用多少"。
> 每周更新一次，覆盖主流国内外渠道。
> 首页一屏看完，3 分钟领到手。

> 完整的产品与技术需求请看 [`SPEC.md`](./SPEC.md)。

## 设计原则

- **内容克制**：只做 ~10 个 Top 模型，覆盖 90% 真实需求
- **可信透明**：每条活动都带来源链接和核实日期
- **极致轻量**：纯静态 HTML + CSS，零运行时 JS 框架，无需 npm
- **零依赖构建**：Python 标准库即可生成整站（无需安装任何包）
- **数据驱动**：所有内容是 JSON，改数据即改仓库，欢迎社区 PR

## 目录结构

```
data/
  models/              # 每个模型一个 JSON，含该模型所有免费渠道
  platforms/           # 每个平台一个 JSON，含基础信息
public/                # 静态资源（favicon 等），构建时会复制到 dist/
build.py               # 生成器（标准库，零依赖）
dist/                  # 生成产物（HTML + CSS，可直接部署到任意 CDN）
```

## 构建与预览

```bash
python3 build.py                    # 一键构建到 dist/
python3 -m http.server -d dist 8080 # 本地预览
```

需要 Python 3.8+。**不需要 pip install 任何包。**

## 部署

`dist/` 是纯静态文件，可直接上传到：
- Cloudflare Pages（推荐，免费且快）
- GitHub Pages
- Vercel / Netlify
- 任意对象存储 + CDN

## 贡献数据

发现活动过期、信息错误，或想补充新的免费渠道？

1. 打开 `data/models/<model>.json`，在 `free_sources` 数组追加一项
2. 必填字段：`platform_id` / `platform_name` / `offer` / `threshold` / `difficulty` / `expires` / `verified_at` / `source_url`
3. `source_url` 必须是**官方公告页**，便于读者核实
4. 如果引入了新平台，在 `data/platforms/` 下新建一个 JSON
5. 本地 `python3 build.py` 验证无报错后提 PR

`difficulty` 枚举：`easy` / `medium` / `hard`

## 免责声明

所有信息整理自各平台官方公告，以官方最新政策为准。本站不承担因活动变化造成的任何损失。
