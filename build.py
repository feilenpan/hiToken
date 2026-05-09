#!/usr/bin/env python3
"""
hiToken 静态站生成器。

零依赖，仅使用 Python 3.8+ 标准库。
读取 data/ 下的 JSON，渲染 dist/ 下的 HTML。
"""
from __future__ import annotations

import html
import json
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
PUBLIC_DIR = ROOT / "public"
DIST_DIR = ROOT / "dist"

CATEGORY_ORDER = ["国产旗舰", "海外旗舰", "开源明星"]
DIFFICULTY_ORDER = {"easy": 0, "medium": 1, "hard": 2}
DIFFICULTY_LABEL = {"easy": "简单", "medium": "中等", "hard": "较难"}


# ---------- data loading ----------

@dataclass
class FreeSource:
    platform_id: str
    platform_name: str
    offer: str
    threshold: str
    difficulty: str
    expires: str
    verified_at: str
    source_url: str
    eligible_models: list[str] = field(default_factory=list)
    notes: str = ""


@dataclass
class Model:
    id: str
    display_name: str
    category: str
    tags: list[str]
    summary: str
    official: dict[str, str]
    free_sources: list[FreeSource]


@dataclass
class Platform:
    id: str
    name: str
    url: str
    type: str
    region: str
    direct_access: Any
    openai_compatible: Any
    payment: Any
    invoice: Any
    kyc: str
    summary: str


def _load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def load_models() -> list[Model]:
    models = []
    for f in sorted((DATA_DIR / "models").glob("*.json")):
        raw = _load_json(f)
        sources = [FreeSource(**s) for s in raw.pop("free_sources", [])]
        models.append(Model(**raw, free_sources=sources))
    models.sort(
        key=lambda m: (
            CATEGORY_ORDER.index(m.category) if m.category in CATEGORY_ORDER else 99,
            m.display_name,
        )
    )
    return models


def load_platforms() -> list[Platform]:
    platforms = []
    for f in sorted((DATA_DIR / "platforms").glob("*.json")):
        platforms.append(Platform(**_load_json(f)))
    platforms.sort(key=lambda p: p.name)
    return platforms


# ---------- rendering helpers ----------

def esc(s: Any) -> str:
    return html.escape(str(s), quote=True)


def yn(v: Any) -> str:
    if v is True:
        return "是"
    if v is False:
        return "否"
    return esc(v)


def payment_text(p: Any) -> str:
    if isinstance(p, list):
        return esc(" / ".join(p))
    return esc(p)


def diff_badge(d: str) -> str:
    label = DIFFICULTY_LABEL.get(d, d)
    return f'<span class="diff diff-{esc(d)}">{esc(label)}</span>'


def tag(s: str, cls: str = "tag") -> str:
    return f'<span class="{cls}">{esc(s)}</span>'


def sort_sources(sources: list[FreeSource]) -> list[FreeSource]:
    return sorted(sources, key=lambda s: DIFFICULTY_ORDER.get(s.difficulty, 99))


# ---------- layout ----------

CSS = """\
:root{--bg:#fafafa;--surface:#fff;--border:#e6e6e6;--text:#1a1a1a;--muted:#707070;--accent:#d63384;--tag-bg:#f2f2f2;--easy:#2b8a3e;--medium:#d9770f;--hard:#c92a2a}
*{box-sizing:border-box}
html,body{margin:0;padding:0;background:var(--bg);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei","Segoe UI",Roboto,sans-serif;font-size:15px;line-height:1.6}
a{color:var(--accent);text-decoration:none}
a:hover{text-decoration:underline}
.container{max-width:960px;margin:0 auto;padding:0 20px}
.site-header{background:var(--surface);border-bottom:1px solid var(--border);padding:14px 0;position:sticky;top:0;z-index:10}
.site-header .container{display:flex;align-items:center;justify-content:space-between}
.brand{font-weight:700;font-size:18px;color:var(--text)}
.brand:hover{text-decoration:none}
.brand-mark{color:var(--accent)}
.site-header nav a{color:var(--text);margin-left:18px;font-size:14px}
main{padding:28px 20px 48px}
.site-footer{border-top:1px solid var(--border);padding:24px 0;font-size:13px;color:var(--muted);background:var(--surface)}
.site-footer p{margin:2px 0}
.muted{color:var(--muted)}
.hero{margin-bottom:32px}
.hero h1{font-size:28px;margin:0 0 8px 0}
.lead{font-size:16px;margin:4px 0}
.hint{font-size:13px;margin-top:6px}
.group{margin-top:28px}
.group h2{font-size:18px;margin:0 0 14px 0;padding-bottom:6px;border-bottom:2px solid var(--border)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:16px}
.model-card{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:18px 20px;display:flex;flex-direction:column;gap:10px}
.model-card>header{display:flex;align-items:baseline;justify-content:space-between;gap:12px;flex-wrap:wrap}
.model-card h3{margin:0;font-size:17px}
.model-card h3 a{color:var(--text)}
.tags{display:flex;gap:6px;flex-wrap:wrap}
.tag{background:var(--tag-bg);color:var(--muted);font-size:12px;padding:1px 8px;border-radius:10px}
.cat{background:var(--accent);color:#fff;padding:2px 10px;border-radius:10px;font-size:12px}
.summary{margin:0;color:var(--muted);font-size:14px}
.sources-list{list-style:none;padding:0;margin:0;display:flex;flex-direction:column;gap:6px}
.sources-list li{font-size:14px;display:flex;align-items:baseline;gap:8px;flex-wrap:wrap}
.diff{font-size:11px;padding:1px 6px;border-radius:4px;color:#fff;flex-shrink:0}
.diff-easy{background:var(--easy)}
.diff-medium{background:var(--medium)}
.diff-hard{background:var(--hard)}
.pname{font-weight:600}
.more{font-size:13px}
.crumb{margin-bottom:12px;font-size:13px}
.detail-head h1{margin:0 0 8px 0;font-size:26px}
.info-grid{display:grid;grid-template-columns:120px 1fr;gap:6px 12px;font-size:14px;margin:0}
.info-grid dt{color:var(--muted)}
.info-grid dd{margin:0}
section h2{font-size:18px;margin:28px 0 12px 0;padding-bottom:6px;border-bottom:2px solid var(--border)}
.sources{list-style:none;padding:0;margin:0;display:flex;flex-direction:column;gap:14px}
.source{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:16px 18px}
.row{display:flex;justify-content:space-between;align-items:baseline;gap:10px;margin-bottom:4px}
.source h3{margin:0;font-size:16px}
.source h3 a{color:var(--text)}
.offer{margin:4px 0 10px 0;font-weight:500}
.source dl{margin:0;display:grid;grid-template-columns:84px 1fr;gap:4px 12px;font-size:13px}
.source dt{color:var(--muted)}
.source dd{margin:0}
.notes{margin:10px 0 0 0;font-size:13px;color:var(--muted)}
.cta{margin:12px 0 0 0}
.btn{display:inline-block;background:var(--accent);color:#fff;padding:6px 14px;border-radius:6px;font-size:13px}
.btn:hover{text-decoration:none;opacity:.9}
.plist{list-style:none;padding:0;margin:18px 0 0 0;display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:12px}
.plist a{display:block;background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:14px 16px;color:var(--text)}
.plist a:hover{text-decoration:none;border-color:var(--accent)}
.plist .top{display:flex;justify-content:space-between;align-items:baseline;gap:8px}
.plist .region{font-size:12px;color:var(--muted)}
.plist p{margin:4px 0 0 0;font-size:13px;color:var(--muted)}
.items{list-style:none;padding:0;margin:0;display:flex;flex-direction:column;gap:12px}
.items li{background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:12px 14px}
.items .mname{font-weight:600;color:var(--text)}
.items .meta{margin:0;font-size:12px}
"""


def layout(title: str, description: str, body: str, prefix: str = "") -> str:
    """prefix: 相对于生成页面到站点根的路径前缀，例如 '../'。"""
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="{esc(description)}">
<title>{esc(title)}</title>
<link rel="icon" type="image/svg+xml" href="{prefix}favicon.svg">
<link rel="stylesheet" href="{prefix}assets/style.css">
</head>
<body>
<header class="site-header">
  <div class="container">
    <a href="{prefix or '/'}" class="brand"><span class="brand-mark">hi</span>Token</a>
    <nav>
      <a href="{prefix or '/'}">首页</a>
      <a href="{prefix}platforms/">平台</a>
      <a href="{prefix}about/">关于</a>
    </nav>
  </div>
</header>
<main class="container">
{body}
</main>
<footer class="site-footer">
  <div class="container">
    <p>hiToken · 聚焦 Top 模型 · 信息整理自各平台官方公告，以官方最新政策为准。</p>
    <p class="muted">发现活动过期或错误？欢迎提 Issue / PR 更正。</p>
  </div>
</footer>
</body>
</html>
"""


# ---------- page renderers ----------

def render_model_card(model: Model, prefix: str) -> str:
    sources = sort_sources(model.free_sources)
    top = sources[:3]
    lines = []
    for s in top:
        lines.append(
            f'<li>{diff_badge(s.difficulty)}'
            f'<a href="{prefix}platforms/{esc(s.platform_id)}/" class="pname">{esc(s.platform_name)}</a>'
            f'<span>{esc(s.offer)}</span></li>'
        )
    tags_html = "".join(tag(t) for t in model.tags)
    return f"""<article class="model-card">
<header>
<h3><a href="{prefix}models/{esc(model.id)}/">{esc(model.display_name)}</a></h3>
<div class="tags">{tags_html}</div>
</header>
<p class="summary">{esc(model.summary)}</p>
<ul class="sources-list">{''.join(lines)}</ul>
<footer><a class="more" href="{prefix}models/{esc(model.id)}/">查看全部 {len(sources)} 个薅法 →</a></footer>
</article>"""


def render_index(models: list[Model]) -> str:
    total_sources = sum(len(m.free_sources) for m in models)
    groups: dict[str, list[Model]] = {}
    for m in models:
        groups.setdefault(m.category, []).append(m)
    sections = []
    for cat in CATEGORY_ORDER:
        if cat not in groups:
            continue
        cards = "\n".join(render_model_card(m, prefix="") for m in groups[cat])
        sections.append(f'<section class="group"><h2>{esc(cat)}</h2><div class="grid">{cards}</div></section>')
    body = f"""<section class="hero">
<h1>今天，Top AI 模型在哪里能免费用？</h1>
<p class="lead">聚焦 {len(models)} 个主流大模型，收录 {total_sources} 个官方免费渠道 · 专为中文开发者整理。</p>
<p class="hint muted">所有信息整理自各平台官方公告；以官方最新政策为准。</p>
</section>
{''.join(sections)}"""
    return layout(
        "hiToken — Top 模型薅羊毛聚合",
        '专注 Top 大模型的"今天能免费用多少"聚合站 · 面向中文开发者',
        body,
        prefix="",
    )


def render_model_page(model: Model) -> str:
    sources = sort_sources(model.free_sources)
    prefix = "../../"  # from dist/models/<id>/index.html to dist/
    items = []
    for s in sources:
        eligible = (
            f'<dt>可用模型</dt><dd>{esc(" / ".join(s.eligible_models))}</dd>'
            if s.eligible_models
            else ""
        )
        notes = f'<p class="notes">备注：{esc(s.notes)}</p>' if s.notes else ""
        items.append(f"""<li class="source">
<div class="row">
<h3><a href="{prefix}platforms/{esc(s.platform_id)}/">{esc(s.platform_name)}</a></h3>
{diff_badge(s.difficulty)}
</div>
<p class="offer">{esc(s.offer)}</p>
<dl>
<dt>门槛</dt><dd>{esc(s.threshold)}</dd>
<dt>有效期</dt><dd>{esc(s.expires)}</dd>
{eligible}
<dt>最近核实</dt><dd>{esc(s.verified_at)}</dd>
</dl>
{notes}
<p class="cta"><a class="btn" href="{esc(s.source_url)}" rel="noopener nofollow">前往官网领取 →</a></p>
</li>""")

    tags_html = "".join(tag(t) for t in model.tags)
    official_note = f' · {esc(model.official.get("note", ""))}' if model.official.get("note") else ""
    body = f"""<nav class="crumb"><a href="{prefix}">← 返回首页</a></nav>
<header class="detail-head">
<h1>{esc(model.display_name)}</h1>
<div class="tags"><span class="cat">{esc(model.category)}</span>{tags_html}</div>
<p>{esc(model.summary)}</p>
<p class="muted">官方出口：<a href="{esc(model.official["url"])}" rel="noopener">{esc(model.official["name"])}</a>{official_note}</p>
</header>
<section>
<h2>免费渠道（{len(sources)}）</h2>
<ol class="sources">{''.join(items)}</ol>
</section>"""
    return layout(
        f"{model.display_name} 免费渠道汇总 — hiToken",
        f"{model.display_name}：{model.summary}",
        body,
        prefix=prefix,
    )


def render_platform_page(platform: Platform, sources_for_platform: list[tuple[Model, FreeSource]]) -> str:
    prefix = "../../"
    items = []
    for model, s in sources_for_platform:
        items.append(f"""<li>
<div class="row">
<a class="mname" href="{prefix}models/{esc(model.id)}/">{esc(model.display_name)}</a>
{diff_badge(s.difficulty)}
</div>
<p class="offer">{esc(s.offer)}</p>
<p class="meta muted">门槛：{esc(s.threshold)} · 有效期：{esc(s.expires)} · 核实于 {esc(s.verified_at)}</p>
</li>""")
    items_html = (
        f'<section><h2>本站收录的免费活动（{len(sources_for_platform)}）</h2><ul class="items">{"".join(items)}</ul></section>'
        if sources_for_platform
        else ""
    )
    body = f"""<nav class="crumb"><a href="{prefix}platforms/">← 平台一览</a></nav>
<header class="detail-head">
<h1>{esc(platform.name)}</h1>
<p>{esc(platform.summary)}</p>
<p><a class="btn" href="{esc(platform.url)}" rel="noopener">前往官网 →</a></p>
</header>
<section>
<h2>基础信息</h2>
<dl class="info-grid">
<dt>类型</dt><dd>{esc(platform.type)}</dd>
<dt>地区</dt><dd>{esc(platform.region)}</dd>
<dt>国内直连</dt><dd>{yn(platform.direct_access)}</dd>
<dt>OpenAI 兼容</dt><dd>{yn(platform.openai_compatible)}</dd>
<dt>支付方式</dt><dd>{payment_text(platform.payment)}</dd>
<dt>开发票</dt><dd>{yn(platform.invoice)}</dd>
<dt>实名/KYC</dt><dd>{esc(platform.kyc)}</dd>
</dl>
</section>
{items_html}"""
    return layout(
        f"{platform.name} — hiToken",
        platform.summary,
        body,
        prefix=prefix,
    )


def render_platforms_index(platforms: list[Platform]) -> str:
    prefix = "../"
    items = "\n".join(
        f'<li><a href="{prefix}platforms/{esc(p.id)}/"><div class="top"><strong>{esc(p.name)}</strong><span class="region">{esc(p.region)}</span></div><p>{esc(p.summary)}</p></a></li>'
        for p in platforms
    )
    body = f"""<h1>平台一览</h1>
<p class="muted">收录本站涉及的所有模型聚合/官方平台。</p>
<ul class="plist">{items}</ul>"""
    return layout("平台一览 — hiToken", "hiToken 收录的所有模型平台", body, prefix=prefix)


def render_about() -> str:
    prefix = "../"
    body = """<h1>关于 hiToken</h1>
<p>hiToken 是一个聚焦 <strong>Top 大模型薅羊毛信息</strong>的轻量站点，专为中文开发者整理。</p>
<h2>我们做什么</h2>
<ul>
<li>只收录主流的 10 个左右 <strong>Top 模型</strong>，覆盖 90% 真实需求</li>
<li>每个模型下汇总官方/聚合平台的<strong>免费渠道</strong>（新人额度、长期免费层、体验金等）</li>
<li>每条活动标注<strong>来源链接、核实日期、领取难度</strong></li>
</ul>
<h2>我们不做什么</h2>
<ul>
<li>不做全量模型百科（用 HuggingFace 足矣）</li>
<li>不做速度/可用性实时监控（推荐参考 artificialanalysis.ai）</li>
<li>不做账号系统，浏览无需注册</li>
<li>不教"多开小号"类灰色薅法，仅收录正规活动</li>
</ul>
<h2>数据可信度</h2>
<p>所有信息整理自各平台<strong>官方公告</strong>，并在站内标注来源链接与核实日期。由于活动政策可能随时变化，最终以官方实时政策为准。发现信息过期或错误，欢迎提 Issue / PR 更正。</p>
<h2>轻量化原则</h2>
<ul>
<li>纯静态站点，零客户端 JS 框架</li>
<li>数据以 JSON 管理，改数据即提 PR</li>
<li>生成器零依赖（Python 标准库）；产出纯 HTML + CSS，任意 CDN 可部署</li>
</ul>"""
    return layout("关于 — hiToken", "关于 hiToken 项目", body, prefix=prefix)


# ---------- build ----------

def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def build() -> int:
    models = load_models()
    platforms = load_platforms()

    # 反查：每个平台有哪些模型活动
    platform_sources: dict[str, list[tuple[Model, FreeSource]]] = {}
    known_platform_ids = {p.id for p in platforms}
    dangling: list[tuple[str, str]] = []
    for m in models:
        for s in m.free_sources:
            platform_sources.setdefault(s.platform_id, []).append((m, s))
            if s.platform_id not in known_platform_ids:
                dangling.append((m.id, s.platform_id))
    if dangling:
        print("WARN: free_sources referencing unknown platforms:", dangling, file=sys.stderr)

    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)
    DIST_DIR.mkdir()

    # assets
    (DIST_DIR / "assets").mkdir()
    (DIST_DIR / "assets" / "style.css").write_text(CSS, encoding="utf-8")

    # copy public/
    if PUBLIC_DIR.exists():
        for item in PUBLIC_DIR.iterdir():
            target = DIST_DIR / item.name
            if item.is_dir():
                shutil.copytree(item, target)
            else:
                shutil.copy2(item, target)

    # pages
    write(DIST_DIR / "index.html", render_index(models))
    write(DIST_DIR / "about" / "index.html", render_about())
    write(DIST_DIR / "platforms" / "index.html", render_platforms_index(platforms))

    for m in models:
        write(DIST_DIR / "models" / m.id / "index.html", render_model_page(m))

    for p in platforms:
        write(
            DIST_DIR / "platforms" / p.id / "index.html",
            render_platform_page(p, platform_sources.get(p.id, [])),
        )

    print(f"OK: {len(models)} models, {len(platforms)} platforms → dist/")
    return 0


if __name__ == "__main__":
    sys.exit(build())
