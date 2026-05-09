# hiToken — 产品与技术需求文档（PRD + Tech Spec）

**版本**：v1.0（MVP）
**最后更新**：2026-05-09

---

## 1. 一句话定位

> **聚焦 Top 10 大模型的"今天能免费用多少"聚合站。面向中文开发者。轻量、克制、可信。**

---

## 2. 产品目标

解决一个真实痛点：中文 AI 开发者想用 Claude / GPT / Gemini / DeepSeek / Qwen 等主流模型时，不知道**哪里能免费用、送多少、怎么领**。信息散落在公众号、V2EX、小红书、知乎、各家官网，找起来累。

**hiToken 要成为这件事的"第一站"** —— 进来 3 秒看到有货，30 秒找到心动的，3 分钟领到手。

## 3. 核心约束（非常重要，决定一切设计）

| 约束 | 说明 |
|---|---|
| **轻量** | 纯静态站，无 JS 框架，无数据库，无登录系统。首屏加载 < 100KB。 |
| **低维护** | 单人每周 ≤ 4 小时可持续运营一年以上。 |
| **可信** | 每条数据带来源链接 + 核实日期；不做软广；明确 affiliate 标注。 |
| **克制** | 只做 10 个 Top 模型；不追求全量覆盖。 |
| **数据驱动** | 所有内容以 JSON 文件形式放在仓库里，改数据即提 PR。 |

## 4. 目标用户

以**中文开发者**为主，三类画像（流程会收敛成一类）：

1. **薅羊毛党**（个人开发者、学生）：想白嫖 token 做 side project
2. **选型者**（小团队技术负责人）：对比平台合规/支付/直连
3. **搜索引擎路过者**：搜"XX 平台怎么样"落到二级页

**不服务**：追求全量模型百科的研究者（他们有 HuggingFace）；要求 SLA 的大企业采购（他们直接找厂商）。

## 5. 核心内容范围

### 5.1 收录的 Top 10 模型

| # | 模型 | 分类 | 关键卖点 |
|---|---|---|---|
| 1 | **DeepSeek V3 / R1** | 国产旗舰 | 性价比之王，R1 对标 o1 |
| 2 | **Qwen3（通义千问）** | 国产旗舰 | 阿里开源旗舰 |
| 3 | **Kimi（Moonshot）** | 国产旗舰 | 超长上下文 |
| 4 | **豆包 Doubao** | 国产旗舰 | 字节中文优化 |
| 5 | **GLM（智谱 AI）** | 国产旗舰 | 代码 + 多模态 |
| 6 | **Claude**（Sonnet/Opus） | 海外旗舰 | 代码和写作强 |
| 7 | **GPT-4o / GPT-4.1** | 海外旗舰 | OpenAI 旗舰 |
| 8 | **Gemini 2.5 Pro/Flash** | 海外旗舰 | 百万上下文 + 慷慨免费层 |
| 9 | **Llama**（Meta 最新版） | 开源明星 | 开源标杆 |
| 10 | **Mistral** | 开源明星 | 欧洲开源 |

### 5.2 收录的平台（约 13 家，按需增减）

**国内直连**：硅基流动、阿里云百炼、火山方舟、智谱开放平台、Moonshot 开放平台、PPIO 派欧云、魔搭 ModelScope

**海外**：OpenRouter、Google AI Studio、GitHub Models、Groq、Poe API、Mistral 官方

### 5.3 不做的内容（明确划界）

- ❌ 实时速度 / 可用性监控（推荐外链到 artificialanalysis.ai、openrouter.ai/rankings）
- ❌ 模型能力榜（外链到 lmarena、livebench）
- ❌ 全量模型百科
- ❌ 账号系统、评论系统、收藏系统
- ❌ 中转类灰色平台（合规风险）

## 6. 页面结构

### 6.1 URL 规划

```
/                          # 首页 — Top 模型 × 免费渠道
/models/<id>/              # 模型详情页（如 /models/deepseek/）
/platforms/                # 平台一览
/platforms/<id>/           # 平台详情页
/about/                    # 关于
```

所有 URL 必须 SEO 友好（目录形式而非 `.html`）。

### 6.2 页面说明

#### 首页 `/`

**目标**：3 秒内让用户看到"现在能薅什么"。

**结构**：
```
[Header] hiToken | 首页 | 平台 | 关于

[Hero]
  H1: 今天，Top AI 模型在哪里能免费用？
  副标题: 聚焦 N 个主流大模型，收录 M 个官方免费渠道
  提示: 所有信息整理自各平台官方公告；以官方最新政策为准。

[分组 1：国产旗舰]
  [模型卡片网格 — 响应式 auto-fill]
    每张卡：
      · 模型名（链接到详情页）
      · 标签（中文/代码/推理 等）
      · 一句话简介
      · 前 3 个免费渠道（按难度升序）
        每条渠道：难度 badge + 平台名 + 一句话福利
      · "查看全部 N 个薅法 →" 链接

[分组 2：海外旗舰]
  （同上）

[分组 3：开源明星]
  （同上）

[Footer] 声明 + 贡献入口
```

#### 模型详情页 `/models/<id>/`

**目标**：把一个模型的所有薅法呈现清楚，并引导用户点击"前往官网领取"。

**结构**：
```
[面包屑] ← 返回首页

[Header]
  H1: 模型显示名
  Tags: 分类 + 标签
  一句话简介
  官方出口: 链接到官方平台

[免费渠道（按难度升序排列）]
  每个渠道卡片：
    · 平台名（链接到平台详情）+ 难度 badge（简单/中等/较难）
    · 福利描述（offer）
    · 结构化字段：
        - 门槛（threshold）
        - 有效期（expires）
        - 可用模型（eligible_models）
        - 最近核实（verified_at）
    · 备注（notes，可选）
    · CTA 大按钮："前往官网领取 →"（带 rel="noopener nofollow"）
```

#### 平台一览 `/platforms/`

**结构**：卡片网格，每张卡显示平台名 + 地区 + 一句话简介。

#### 平台详情页 `/platforms/<id>/`

**结构**：
```
[面包屑] ← 平台一览

[Header]
  平台名
  一句话简介
  CTA: 前往官网

[基础信息] — 表格（dl/dt/dd）
  · 类型（大厂官方 / 聚合平台）
  · 地区（中国大陆 / 海外）
  · 国内直连（是 / 否 / 部分网络可）
  · OpenAI 兼容（是 / 否 / 部分）
  · 支付方式（支付宝 / 微信 / 对公 / 信用卡 / 加密货币）
  · 开发票（是 / 否）
  · 实名/KYC 要求

[本站收录的免费活动]
  反查所有在该平台的活动，按模型分组展示
```

#### 关于页 `/about/`

说明网站做什么、不做什么、数据可信度原则、轻量化原则。

## 7. 数据模型（JSON Schema）

数据文件位置：`data/models/<id>.json`、`data/platforms/<id>.json`

### 7.1 Model Schema

```json
{
  "id": "deepseek",
  "display_name": "DeepSeek V3 / R1",
  "category": "国产旗舰",
  "tags": ["代码", "推理", "中文", "高性价比"],
  "summary": "深度求索出品，V3 通用对话强，R1 推理能力对标 o1。",
  "official": {
    "name": "DeepSeek 开放平台",
    "url": "https://platform.deepseek.com",
    "note": "（可选）官方出口说明。"
  },
  "free_sources": [
    {
      "platform_id": "siliconflow",
      "platform_name": "硅基流动",
      "offer": "注册送 ¥14 体验金（约 2000 万 tokens）",
      "threshold": "手机号注册",
      "difficulty": "easy",
      "expires": "永久",
      "eligible_models": ["DeepSeek-V3", "DeepSeek-R1"],
      "verified_at": "2026-05-07",
      "source_url": "https://siliconflow.cn",
      "notes": "（可选）额外说明。"
    }
  ]
}
```

**字段约束**：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `id` | string | ✓ | URL 使用，小写字母和连字符 |
| `display_name` | string | ✓ | 页面展示名 |
| `category` | enum | ✓ | `国产旗舰` / `海外旗舰` / `开源明星` |
| `tags` | string[] | ✓ | 标签数组，2-5 个 |
| `summary` | string | ✓ | 一句话简介（≤ 50 字） |
| `official.name` | string | ✓ | 官方平台名 |
| `official.url` | string | ✓ | 官方平台 URL |
| `official.note` | string | | 可选说明 |
| `free_sources` | array | ✓ | 免费渠道数组，至少 1 条 |
| `free_sources[].platform_id` | string | ✓ | 对应 platforms 目录下的某个 JSON 的 id |
| `free_sources[].difficulty` | enum | ✓ | `easy` / `medium` / `hard` |
| `free_sources[].verified_at` | string | ✓ | ISO 日期，`YYYY-MM-DD` |
| `free_sources[].source_url` | string | ✓ | 官方公告页 URL |
| `free_sources[].eligible_models` | string[] | | 该福利覆盖的具体模型 |
| `free_sources[].notes` | string | | 备注 |

### 7.2 Platform Schema

```json
{
  "id": "siliconflow",
  "name": "硅基流动 SiliconFlow",
  "url": "https://siliconflow.cn",
  "type": "聚合平台",
  "region": "中国大陆",
  "direct_access": true,
  "openai_compatible": true,
  "payment": ["支付宝", "微信", "对公"],
  "invoice": true,
  "kyc": "手机号（基础使用）",
  "summary": "国内直连的开源模型聚合平台，OpenAI 兼容，新人 ¥14 体验金。"
}
```

**字段约束**：

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `id` | string | ✓ | 必须与文件名一致 |
| `name` | string | ✓ | 展示名 |
| `url` | string | ✓ | 官网链接 |
| `type` | enum | ✓ | `大厂官方` / `聚合平台` |
| `region` | enum | ✓ | `中国大陆` / `海外` |
| `direct_access` | bool \| string | ✓ | `true` / `false` / `"部分网络可"` |
| `openai_compatible` | bool \| string | ✓ | `true` / `false` / `"部分"` |
| `payment` | string[] \| string | ✓ | 支付方式 |
| `invoice` | bool | ✓ | 是否可开票 |
| `kyc` | string | ✓ | 实名要求描述 |
| `summary` | string | ✓ | 一句话简介 |

### 7.3 引用完整性

- `model.free_sources[].platform_id` 必须在 `data/platforms/` 下存在同名 JSON。
- 构建器应在编译时报警（warning）不匹配的 platform_id。

## 8. 视觉 / UX 规范

### 8.1 设计风格

- **信息密度高、装饰少**，类似 artificialanalysis.ai、simonwillison.net 的冷静工具站风格
- **无插画、无渐变、无动画**（除了标准的 hover）
- 首屏不放 Hero 大图，直接上数据

### 8.2 配色（CSS 变量）

```css
--bg: #fafafa;          /* 页面底色 */
--surface: #ffffff;     /* 卡片底 */
--border: #e6e6e6;
--text: #1a1a1a;
--muted: #707070;
--accent: #d63384;      /* 品牌色（洋红），用于链接和 CTA */
--tag-bg: #f2f2f2;

--easy: #2b8a3e;        /* 绿 */
--medium: #d9770f;      /* 橙 */
--hard: #c92a2a;        /* 红 */
```

### 8.3 字体栈

```
-apple-system, BlinkMacSystemFont, "PingFang SC",
"Microsoft YaHei", "Segoe UI", Roboto, sans-serif
```

不引入任何 web 字体（性能考虑）。

### 8.4 布局

- 容器最大宽度：960px
- 移动优先（响应式），卡片网格用 CSS Grid：
  ```css
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  ```
- 顶栏 sticky

### 8.5 难度 badge

```
简单：绿底白字
中等：橙底白字
较难：红底白字
```
显示在渠道名旁边，11-12px。

### 8.6 响应式断点

不刻意断点，靠 CSS Grid 的 `auto-fill` + `minmax` 自适应。

## 9. 技术栈

### 9.1 选定方案：Python 标准库静态生成

**选它的理由**：
- **零依赖**（不需要 `pip install` 任何包），构建只需 Python 3.8+
- 生成产物是纯 HTML + CSS，可部署到任意 CDN
- 比 Astro/VitePress 更轻，适合这种数据量不大的站
- 数据用 JSON（而不是 YAML）避免对 `pyyaml` 的依赖

**要求**：
- 源文件：Python 3.8+ 标准库 `json` / `html` / `pathlib` / `shutil`
- 一个入口脚本 `build.py`，跑一次输出 `dist/`
- 本地预览：`python3 -m http.server -d dist`

### 9.2 产物要求

- 纯 HTML + 一个 `assets/style.css`
- CSS 内联或单独文件均可（建议单独，利于缓存）
- 首屏 HTML ≤ 50KB（gzip 前）
- 零 JavaScript
- favicon 用 SVG

### 9.3 部署

首选 **Cloudflare Pages**（免费、CDN 快、全球可达，大陆访问速度也还行）。
备选 GitHub Pages、Vercel、Netlify。

## 10. 项目结构（交付期望）

```
hiToken/
├── README.md
├── SPEC.md                           # 本文档
├── .gitignore
├── build.py                          # 生成器
├── data/
│   ├── models/
│   │   ├── deepseek.json
│   │   ├── qwen.json
│   │   └── ...                       # 共 10 个
│   └── platforms/
│       ├── siliconflow.json
│       ├── openrouter.json
│       └── ...                       # 约 13 个
├── public/
│   └── favicon.svg
└── dist/                             # 构建产物（git 忽略）
    ├── index.html
    ├── about/index.html
    ├── platforms/index.html
    ├── platforms/<id>/index.html
    ├── models/<id>/index.html
    ├── favicon.svg
    └── assets/style.css
```

## 11. 验收标准

实现完成后，需满足：

- [ ] `python3 build.py` 一键成功，无报错
- [ ] 共生成 1 个首页、1 个关于页、1 个平台列表页、10 个模型页、约 13 个平台页
- [ ] 每个模型页展示该模型下所有免费渠道，按难度升序
- [ ] 每个平台页反查出所有"使用了该平台"的模型活动
- [ ] 首页三个分组齐全（国产 / 海外 / 开源），分组内按首字母/模型名排
- [ ] 所有内链正常（无 404）
- [ ] 所有外链带 `rel="noopener"`，affiliate 链接额外带 `nofollow`
- [ ] 移动端宽度 375px 时布局不破
- [ ] 引用了不存在的 `platform_id` 时，构建脚本打印 warning
- [ ] 新增一个模型 JSON 后重新构建，首页和详情页自动出现
- [ ] HTML 中文无乱码，charset=UTF-8

## 12. 非功能性要求

| 项目 | 目标 |
|---|---|
| 首屏加载（gzip 后） | < 30 KB |
| Lighthouse Performance | > 95 |
| Lighthouse SEO | > 95 |
| 零客户端运行时依赖 | ✓ |
| 无 cookie、无追踪脚本 | ✓（MVP 阶段） |

## 13. 数据采集策略（重要，与产品定位直接相关）

实现方可跳过本节；本节用于后续运营者参考。

### 13.1 数据来源（按性价比分级）

**第一梯队 · 被动推送**（信息自动送到眼前）：
- 订阅各平台官方公众号（置顶）
- Twitter/微博官方 list
- 平台注册邮件列表
- QQ / 微信 / 飞书官方用户群
- 官方 Blog RSS

**第二梯队 · 社区聚合**：
- V2EX `/go/openai`、`/go/cloud`
- 小红书 #AI薅羊毛
- 知乎「大模型 API」话题
- GitHub: `awesome-free-ai`、`free-llm-api` 类 repo
- Reddit r/LocalLLaMA

**第三梯队 · 主动搜索（兜底）**：
- Google / 百度关键词：`"送 token"` / `"新人福利" 大模型` / `"free credit" LLM`
- Google Alerts 自动推送
- 每周 30-60 分钟主动扫

### 13.2 时间成本（单人运营）

| 阶段 | 耗时 |
|---|---|
| 一次性建信息管道（订阅 + 建群 + Alerts） | 4 小时 |
| 每日信息采集 | 20-30 分钟 |
| 每周兜底搜索 + 过期清洗 + 录入 | 2-3 小时 |
| **每周总计** | **~4-6 小时** |

### 13.3 准确性保障

- 每条数据必填 `source_url` —— 官方公告链接
- 每条数据必填 `verified_at` —— 最近核实日期
- 前端对超过 30 天未核实的数据视觉降级（灰色或加标签）
- 中立语气：始终强调"**信息整理自官方公告，以官方最新政策为准**"
- 开放 GitHub Issue / PR 让用户上报失效信息

## 14. 后续迭代（MVP 之外）

按优先级列出，实现者不用做，但设计时要**预留扩展空间**：

1. **筛选器**：首页按难度、按地区、按是否直连筛选（可以纯客户端 JS 实现）
2. **搜索框**：顶部搜索模型名/平台名（纯客户端，用 lunr 之类的轻量库）
3. **已过期活动档案**：独立页面归档，利于 SEO
4. **RSS / 订阅**：新活动上线自动生成 RSS
5. **Telegram / 微信群** 入口（留存）
6. **数据自动抓取**：对 OpenRouter 等有 API 的平台做 GitHub Actions 定时更新
7. **贡献者榜单**：GitHub 贡献者自动展示

## 15. 风险与规避

| 风险 | 规避 |
|---|---|
| 数据过期被用户吐槽 | 每条数据带 `verified_at`，超过 30 天前端灰色标记；开放社区 PR |
| 被平台举报（尤其中转类） | 只收录官方/持牌平台；明确"信息整理自官方公告"立场 |
| 合规敏感词 | 文案避免"翻墙""破解"类措辞 |
| 维护者烧尽 | 严控收录范围（10 个模型），每周 ≤ 4 小时 |
| 被当成拉人头分销站 | 推广链接明确标注 `Affiliate`；保持中立编辑口吻 |

## 16. 交付清单（给实现方）

请交付：

1. ✅ `build.py` 生成器源码（Python 标准库，零依赖）
2. ✅ `data/` 目录下 10 个模型 JSON + 约 13 个平台 JSON（样板数据，允许 2026-05 时点的信息）
3. ✅ `public/favicon.svg`
4. ✅ `README.md`：说明如何 build、如何贡献数据
5. ✅ `.gitignore`：至少忽略 `dist/` 和 `__pycache__/`
6. ✅ 运行 `python3 build.py` 后，`dist/` 下的完整站点

---

## 附录 A：一个完整 Model JSON 示例（可直接照抄结构）

```json
{
  "id": "deepseek",
  "display_name": "DeepSeek V3 / R1",
  "category": "国产旗舰",
  "tags": ["代码", "推理", "中文", "高性价比"],
  "summary": "深度求索出品，V3 通用对话强，R1 推理能力对标 o1，性价比之王。",
  "official": {
    "name": "DeepSeek 开放平台",
    "url": "https://platform.deepseek.com",
    "note": "官方 API 价格极低，本身就是\"平价\"。"
  },
  "free_sources": [
    {
      "platform_id": "siliconflow",
      "platform_name": "硅基流动",
      "offer": "注册送 ¥14 体验金（约 2000 万 DeepSeek tokens）",
      "threshold": "手机号注册",
      "difficulty": "easy",
      "expires": "永久（不含使用时效）",
      "eligible_models": ["DeepSeek-V3", "DeepSeek-R1", "Qwen", "GLM 等"],
      "verified_at": "2026-05-07",
      "source_url": "https://siliconflow.cn",
      "notes": "国内直连，OpenAI 兼容，开箱即用。"
    },
    {
      "platform_id": "volcengine",
      "platform_name": "火山方舟",
      "offer": "每个模型 50 万 tokens 免费额度",
      "threshold": "实名认证",
      "difficulty": "medium",
      "expires": "6 个月",
      "eligible_models": ["DeepSeek-V3", "DeepSeek-R1", "豆包系列"],
      "verified_at": "2026-05-05",
      "source_url": "https://www.volcengine.com/product/ark"
    }
  ]
}
```

## 附录 B：一个完整 Platform JSON 示例

```json
{
  "id": "siliconflow",
  "name": "硅基流动 SiliconFlow",
  "url": "https://siliconflow.cn",
  "type": "聚合平台",
  "region": "中国大陆",
  "direct_access": true,
  "openai_compatible": true,
  "payment": ["支付宝", "微信", "对公"],
  "invoice": true,
  "kyc": "手机号（基础使用）",
  "summary": "国内直连的开源模型聚合平台，OpenAI 兼容，新人 ¥14 体验金。"
}
```

---

**文档结束**。对方拿到这份，配合 JSON 示例，应该可以直接独立实现出 MVP。
