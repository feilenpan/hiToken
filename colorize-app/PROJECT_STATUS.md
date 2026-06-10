
# 时光修复 — 后端 FastAPI 状态

根目录：/Users/fiona/colorize-app

## 当前接口
- GET /api/health (app.py)
- GET /api/features (app.py)
- POST /api/wechat/login (app.py)
- GET /api/user/info (app.py)
- POST /api/process (app.py)
- POST /api/colorize (app.py)
- GET /api/results/{year}/{month}/{day}/{filename} (app.py)
- GET /api/wechat/records (app.py)
- POST /api/user/agree-privacy (app.py)
- POST /api/user/agree-agreement (app.py)
- POST /api/user/request-deletion (app.py)
- GET /api/privacy (app.py)
- GET /api/agreement (app.py)

## 现存 TODO/FIXME
- app.py: 135|    # TODO: 生产环境调用 jscode2session

## 必做清单（最小内测闸门）
- [ ] Implement /healthz health check
- [ ] Add unified error codes and map to front-end messages
- [ ] Add request id / job_id idempotency for /api/process
- [ ] Timeouts + retry + rate limit protection (queue) for external Palette API
- [ ] Background job: 30-day results cleanup + logs

## 备注
photo_ai_engine.py: palette api usage present
palette_api.py: palette api usage present
database.py: palette api usage present
