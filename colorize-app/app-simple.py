# -*- coding: utf-8 -*-
"""
時光修復 - AI老照片修復工具 免費版（簡化版）
功能：上色 / 照片修復 / 人臉增強 / 超分辨率
"""

import os
import uuid
import time
import hashlib
import logging
import base64
from pathlib import Path
from typing import Optional
from datetime import datetime
from fastapi import FastAPI, File, UploadFile, HTTPException, Header, Depends, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="時光修復", description="AI老照片修復工具 - 免費版")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).parent
RESULTS_DIR = BASE_DIR / "results"
RESULTS_DIR.mkdir(exist_ok=True)

# 簡易內存數據庫（生產環境應使用 SQLite/PostgreSQL）
users_db = {}
records_db = {}

def get_result_dir() -> Path:
    today = datetime.now().strftime("%Y/%m/%d")
    d = RESULTS_DIR / today
    d.mkdir(parents=True, exist_ok=True)
    return d

# ===== 工具函數 =====

def get_current_user(authorization: Optional[str] = Header(None)) -> Optional[dict]:
    if not authorization:
        return None
    token = authorization.replace("Bearer ", "")
    return users_db.get(token)

def require_user(authorization: Optional[str] = Header(None)) -> dict:
    user = get_current_user(authorization)
    if not user:
        raise HTTPException(401, "請先登錄")
    return user

# ===== API =====

@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "service": "時光修復 免費版",
        "timestamp": int(time.time())
    }

@app.post("/api/wechat/login")
async def wechat_login(request: Request):
    data = await request.json()
    code = data.get("code", "")
    if not code:
        raise HTTPException(400, "code is required")
    
    # 簡化登錄（生產環境應調用微信 jscode2session）
    openid = hashlib.md5(code.encode()).hexdigest()[:16]
    
    if openid not in users_db:
        users_db[openid] = {
            "id": len(users_db) + 1,
            "openid": openid,
            "nickname": "用戶" + openid[:4],
            "total_used": 0,
            "privacy_agreed": False,
            "agreement_agreed": False
        }
    
    user = users_db[openid]
    return {
        "success": True,
        "token": openid,
        "user": {
            "id": user["id"],
            "nickname": user["nickname"],
            "total_used": user["total_used"],
            "privacy_agreed": user["privacy_agreed"],
            "agreement_agreed": user["agreement_agreed"]
        }
    }

@app.get("/api/user/info")
async def get_user_info(user: dict = Depends(require_user)):
    return {
        "success": True,
        "user": {
            "id": user["id"],
            "nickname": user["nickname"],
            "total_used": user["total_used"],
            "privacy_agreed": user["privacy_agreed"],
            "agreement_agreed": user["agreement_agreed"]
        }
    }

@app.post("/api/process")
async def process_photo(
    file: UploadFile = File(...),
    process_type: str = "colorize",
    user: Optional[dict] = Depends(get_current_user)
):
    """統一處理端點"""
    
    # 驗證文件
    if not file.content_type.startswith("image/"):
        raise HTTPException(400, "請上傳圖片文件")
    
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(400, "圖片大小不能超過10MB")
    
    task_id = str(uuid.uuid4())
    
    # 模擬處理（生產環境應調用真實 AI 引擎）
    # 這裡直接返回原圖作為演示
    result_base64 = base64.b64encode(content).decode()
    
    # 保存結果圖
    result_url = ""
    try:
        result_dir = get_result_dir()
        filename = f"{task_id}.jpg"
        filepath = result_dir / filename
        filepath.write_bytes(content)
        
        date_path = datetime.now().strftime("%Y/%m/%d")
        result_url = f"/api/results/{date_path}/{filename}"
        logger.info(f"結果圖已保存: {filepath}")
    except Exception as e:
        logger.error(f"保存結果圖失敗: {e}")
    
    # 更新用戶統計
    if user:
        user["total_used"] += 1
    
    return {
        "success": True,
        "task_id": task_id,
        "process_type": process_type,
        "result": f"data:image/jpeg;base64,{result_base64}",
        "result_url": result_url,
        "engine": "demo"
    }

@app.get("/api/results/{year}/{month}/{day}/{filename}")
async def get_result_image(year: str, month: str, day: str, filename: str):
    filepath = RESULTS_DIR / year / month / day / filename
    if not filepath.exists():
        raise HTTPException(404, "圖片不存在")
    return FileResponse(str(filepath), media_type="image/jpeg")

@app.post("/api/user/agree-privacy")
async def agree_privacy(user: dict = Depends(require_user)):
    user["privacy_agreed"] = True
    return {"success": True}

@app.post("/api/user/agree-agreement")
async def agree_agreement(user: dict = Depends(require_user)):
    user["agreement_agreed"] = True
    return {"success": True}

@app.get("/api/privacy")
async def get_privacy_policy():
    content = """# 時光修復 - 隱私保護政策

最後更新日期：2026年5月30日

## 一、引言

「時光修復」小程序（以下簡稱"我們"或"本小程序"）由時光修復團隊開發運營。我們深知個人信息對您的重要性，將嚴格遵守《中華人民共和國個人信息保護法》《中華人民共和國數據安全法》《中華人民共和國網絡安全法》等法律法規，盡全力保護您的個人信息安全和隱私。

請您在使用本小程序前仔細閱讀本隱私保護政策，確保您已充分理解所有條款。一旦您使用本小程序，即表示您已同意本政策所述的個人信息處理方式。

## 二、我們收集的信息

### 2.1 必要信息（為提供服務所必需）

- 微信賬號信息（OpenID、暱稱、頭像）：用於用戶身份識別與登錄，賬戶存續期間保存
- 您上傳的照片（原始照片文件）：用於AI評分分析和修復處理，處理完成後立即刪除
- 修復結果圖片（AI生成的修復結果）：供您查看和保存，30天後自動刪除
- 評分記錄（評分、點評、建議內容）：歷史記錄展示，30天後自動刪除

### 2.2 自動收集的信息

- 設備型號與操作系統版本：用於適配優化，保存30天
- 服務使用日誌：用於服務改進和故障排查，保存30天
- 功能使用統計：用於了解使用情況和優化產品，保存90天（匿名化處理）

### 2.3 我們絕不收集的信息

- 您的微信密碼
- 您的支付密碼或銀行卡信息
- 您的地理位置精確信息
- 您的通訊錄或聊天記錄
- 您設備的其他照片（僅處理您主動上傳的照片）

## 三、我們如何使用信息

我們收集的所有信息僅用於以下目的：

- 照片打分與點評 — 將您上傳的照片發送至AI模型進行智能分析和評分
- 照片修復處理 — 將您上傳的照片發送至AI修復模型進行修復處理
- 修復建議生成 — 基於AI分析為您提供個性化修復建議
- 服務優化 — 分析功能使用情況以改進產品體驗
- 安全保障 — 檢測和防止濫用行為

## 四、信息存儲與保護

### 4.1 存儲地點

您的所有數據均存儲在位於中華人民共和國境內（不含港澳台）的服務器上。我們承諾您的個人信息不會出境。

### 4.2 安全措施

- 數據傳輸全程加密（HTTPS/TLS 1.3）
- 數據庫加密存儲
- 嚴格的訪問控制和權限管理
- 最小權限原則
- 定期安全自查和漏洞掃描
- 操作日誌審計

## 五、信息共享與委托處理

我們不會出售、交換或轉讓您的個人信息給任何第三方。

為實現照片評分和修復功能，我們會將您上傳的照片臨時發送至以下國內AI服務商進行處理：

- 北京火山引擎科技有限公司（seededit AI修復模型）
- 字節跳動旗下豆包大模型（AI智能評分與點評）

所有數據處理均在中華人民共和國境內完成，數據不出境。處理完成後服務商不保留您的照片數據。

## 六、您的權利

根據《中華人民共和國個人信息保護法》，您享有以下權利：

- 知情權、查閱權、更正權、刪除權、撤回同意權、註銷賬戶權、投訴舉報權

行使方式：
- 小程序內：「我的」→「聯繫客服」
- 郵箱：privacy@time-restore.com
- 我們將在收到申請後的15個工作日內處理並回復

## 七、未成年人保護

- 未滿14周歲的兒童需在監護人陪同和同意下使用
- 未滿18周歲的未成年人請在監護人指導下使用

## 八、隱私政策的更新

我們可能會根據產品功能調整或法律法規變化，不時更新本隱私政策。重大變更時將通過小程序內彈窗通知或首頁公告告知。

## 九、聯繫我們

- 小程序內客服：「我的」→「聯繫客服」
- 個人信息保護負責人郵箱：privacy@time-restore.com

本隱私保護政策自2026年5月30日起生效。"""
    return {"success": True, "content": content}

@app.get("/api/agreement")
async def get_user_agreement():
    content = """# 時光修復 - 用戶服務協議

最後更新日期：2026年5月30日

## 一、服務條款的接受

歡迎使用「時光修復」小程序（以下簡稱"本服務"）。本協議是您與時光修復團隊（以下簡稱"我們"）之間關於您使用本服務所訂立的協議。

使用本服務即表示您已閱讀、理解並接受本協議的全部內容。

## 二、服務內容

本服務利用人工智能技術，為您提供以下功能：

- AI照片打分與點評 — 對上傳的照片進行智能評分和個性化點評
- AI照片修復 — 利用先進AI模型對老照片、受損照片進行智能修復
- 修復建議生成 — 基於AI分析生成個性化的修復建議和編輯效果預覽
- 歷史記錄 — 查看您的修復歷史記錄

特別說明：以上所有功能均為AI自動處理，結果僅供娛樂和參考，不具有任何專業鑑定或法律效力。

## 三、用戶註冊與賬戶

- 您需要使用微信賬號授權登錄本服務
- 您應確保微信賬號為本人使用

## 四、使用規範

### 4.1 您同意

- 遵守《中華人民共和國網絡安全法》《中華人民共和國數據安全法》《中華人民共和國個人信息保護法》及所有適用的法律法規
- 不利用本服務從事任何違法違規活動
- 不侵犯他人合法權益（包括但不限於肖像權、隱私權、知識產權等）

### 4.2 您不得上傳以下內容的照片

- 違反中華人民共和國法律法規的內容
- 涉及國家安全、國家秘密的內容
- 侵犯他人肖像權、隱私權的未經授權的他人照片
- 涉及色情、暴力、恐怖主義等違法違規內容
- 含有病毒、木馬等惡意程序的文件

### 4.3 禁止行為

- 反向工程、反編譯、反彙編本服務的任何部分
- 利用技術手段干擾、破壞本服務的正常運行
- 批量調用、自動化腳本等濫用API的行為
- 惡意攻擊、入侵服務器或網絡系統

## 五、知識產權

- 本服務的所有內容（包括但不限於軟件代碼、算法模型、用戶界面設計、商標、Logo等）的知識產權歸我們或技術合作方所有
- 您上傳的照片，其知識產權歸您或原權利人所有
- 我們不會將您的照片用於服務之外的任何用途
- 照片處理完成後，原始照片和中間結果將立即從服務器刪除
- 修復後的照片，知識產權歸您所有，您可自由使用

## 六、收費與免費

- 本服務目前完全免費，不收取任何費用
- 我們保留未來調整收費模式的權利
- 如引入收費功能，將至少提前30天通知並在小程序內顯著公示

## 七、免責聲明

### 7.1 AI處理結果

- AI評分、點評和修復結果均由人工智能模型自動生成，僅供參考和娛樂
- 我們不保證AI處理結果的準確性、真實性、完整性和適用性
- AI修復效果因照片質量、損傷程度等因素而異

### 7.2 服務可用性

因系統維護、不可抗力（自然災害、政策變化等）、第三方服務故障（微信平台、AI模型服務商等）導致的服務中斷，我們不承擔責任。

### 7.3 用戶內容責任

您應對上傳的照片內容承擔全部法律責任。

## 八、爭議解決

本協議的解釋、效力及糾紛的解決，適用中華人民共和國法律。雙方因本協議發生爭議的，應首先協商解決；協商不成的，向有管轄權的人民法院提起訴訟。

## 九、聯繫方式

- 小程序內：「我的」→「聯繫客服」
- 電子郵箱：support@time-restore.com

本協議自2026年5月30日起生效。"""
    return {"success": True, "content": content}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8888)
