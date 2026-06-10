# -*- coding: utf-8 -*-
"""
时光上色 - 数据库模块（生产级）
使用 PostgreSQL（推荐）或 MySQL
支持 SQLite 作为开发环境
"""

import os
import time
import uuid
import hashlib
from typing import Optional, Dict, List
from contextlib import contextmanager

# 数据库配置
DB_TYPE = os.getenv("DB_TYPE", "sqlite")  # sqlite, postgresql, mysql

if DB_TYPE == "sqlite":
    import sqlite3
    DB_PATH = os.getenv("DB_PATH", "colorize.db")
elif DB_TYPE == "postgresql":
    import psycopg2
    from psycopg2.extras import RealDictCursor
    DB_URL = os.getenv("DATABASE_URL", "postgresql://localhost:5432/colorize")
elif DB_TYPE == "mysql":
    import mysql.connector
    DB_URL = os.getenv("DATABASE_URL", "mysql://localhost:3306/colorize")


@contextmanager
def get_db():
    """获取数据库连接"""
    if DB_TYPE == "sqlite":
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    elif DB_TYPE == "postgresql":
        conn = psycopg2.connect(DB_URL, cursor_factory=RealDictCursor)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    elif DB_TYPE == "mysql":
        conn = mysql.connector.connect(DB_URL)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


def init_db():
    """初始化数据库表"""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # 用户表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                openid TEXT UNIQUE NOT NULL,
                nickname TEXT DEFAULT '色友',
                avatar_url TEXT DEFAULT '',
                phone TEXT DEFAULT '',
                free_credits INTEGER DEFAULT 3,
                paid_credits INTEGER DEFAULT 0,
                total_used INTEGER DEFAULT 0,
                is_vip INTEGER DEFAULT 0,
                vip_expire_at INTEGER DEFAULT 0,
                privacy_agreed INTEGER DEFAULT 0,
                privacy_agreed_at INTEGER DEFAULT 0,
                agreement_agreed INTEGER DEFAULT 0,
                agreement_agreed_at INTEGER DEFAULT 0,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            )
        """)
        
        # 上色记录表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS colorize_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT UNIQUE NOT NULL,
                user_id INTEGER NOT NULL,
                original_filename TEXT DEFAULT '',
                file_size INTEGER DEFAULT 0,
                width INTEGER DEFAULT 0,
                height INTEGER DEFAULT 0,
                engine TEXT DEFAULT 'palette',
                status TEXT DEFAULT 'processing',
                result_url TEXT DEFAULT '',
                created_at INTEGER NOT NULL,
                completed_at INTEGER DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        
        # 订单表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id TEXT UNIQUE NOT NULL,
                user_id INTEGER NOT NULL,
                package_id TEXT NOT NULL,
                package_name TEXT NOT NULL,
                price REAL NOT NULL,
                credits INTEGER NOT NULL,
                status TEXT DEFAULT 'pending',
                payment_id TEXT DEFAULT '',
                payment_method TEXT DEFAULT '',
                created_at INTEGER NOT NULL,
                paid_at INTEGER DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        
        # 分享记录表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS share_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                share_type TEXT NOT NULL,
                credits_earned INTEGER DEFAULT 0,
                created_at INTEGER NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        
        # 隐私协议版本表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS privacy_versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                version TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                published_at INTEGER NOT NULL,
                is_current INTEGER DEFAULT 1
            )
        """)
        
        # 数据删除请求表（合规性要求）
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS deletion_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                openid TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                requested_at INTEGER NOT NULL,
                processed_at INTEGER DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        
        # 创建索引
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_openid ON users(openid)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_records_user_id ON colorize_records(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_records_created_at ON colorize_records(created_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status)")
        
        print("✅ 数据库初始化完成")


def create_user(openid: str, nickname: str = '色友', avatar_url: str = '') -> dict:
    """创建新用户"""
    with get_db() as conn:
        cursor = conn.cursor()
        now = int(time.time())
        
        cursor.execute("""
            INSERT INTO users (openid, nickname, avatar_url, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
        """, (openid, nickname, avatar_url, now, now))
        
        user_id = cursor.lastrowid
        
        return {
            "id": user_id,
            "openid": openid,
            "nickname": nickname,
            "avatar_url": avatar_url,
            "free_credits": 3,
            "paid_credits": 0,
            "total_used": 0,
            "is_vip": False
        }


def get_user_by_openid(openid: str) -> Optional[dict]:
    """根据openid获取用户"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE openid = ?", (openid,))
        row = cursor.fetchone()
        
        if row:
            return dict(row)
        return None


def update_user_privacy_agreement(openid: str, agreed: bool = True) -> bool:
    """更新用户隐私协议同意状态"""
    with get_db() as conn:
        cursor = conn.cursor()
        now = int(time.time())
        
        cursor.execute("""
            UPDATE users 
            SET privacy_agreed = ?, privacy_agreed_at = ?, updated_at = ?
            WHERE openid = ?
        """, (1 if agreed else 0, now, now, openid))
        
        return cursor.rowcount > 0


def update_user_agreement(openid: str, agreed: bool = True) -> bool:
    """更新用户服务协议同意状态"""
    with get_db() as conn:
        cursor = conn.cursor()
        now = int(time.time())
        
        cursor.execute("""
            UPDATE users 
            SET agreement_agreed = ?, agreement_agreed_at = ?, updated_at = ?
            WHERE openid = ?
        """, (1 if agreed else 0, now, now, openid))
        
        return cursor.rowcount > 0


def deduct_credits(openid: str, credits: int = 1) -> bool:
    """扣除用户额度"""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # 优先扣除免费额度
        cursor.execute("""
            UPDATE users 
            SET free_credits = free_credits - ?, updated_at = ?
            WHERE openid = ? AND free_credits >= ?
        """, (credits, int(time.time()), openid, credits))
        
        if cursor.rowcount > 0:
            return True
        
        # 免费额度不足，扣除付费额度
        cursor.execute("""
            UPDATE users 
            SET paid_credits = paid_credits - ?, updated_at = ?
            WHERE openid = ? AND paid_credits >= ?
        """, (credits, int(time.time()), openid, credits))
        
        return cursor.rowcount > 0


def add_credits(openid: str, credits: int, credit_type: str = 'paid') -> bool:
    """增加用户额度"""
    with get_db() as conn:
        cursor = conn.cursor()
        
        field = 'free_credits' if credit_type == 'free' else 'paid_credits'
        
        cursor.execute(f"""
            UPDATE users 
            SET {field} = {field} + ?, updated_at = ?
            WHERE openid = ?
        """, (credits, int(time.time()), openid))
        
        return cursor.rowcount > 0


def create_colorize_record(task_id: str, user_id: int, filename: str, 
                           file_size: int, width: int, height: int) -> dict:
    """创建上色记录"""
    with get_db() as conn:
        cursor = conn.cursor()
        now = int(time.time())
        
        cursor.execute("""
            INSERT INTO colorize_records 
            (task_id, user_id, original_filename, file_size, width, height, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (task_id, user_id, filename, file_size, width, height, now))
        
        return {
            "id": cursor.lastrowid,
            "task_id": task_id,
            "user_id": user_id,
            "status": "processing"
        }


def update_colorize_record(task_id: str, status: str, result_url: str = '') -> bool:
    """更新上色记录"""
    with get_db() as conn:
        cursor = conn.cursor()
        now = int(time.time())
        
        cursor.execute("""
            UPDATE colorize_records 
            SET status = ?, result_url = ?, completed_at = ?
            WHERE task_id = ?
        """, (status, result_url, now, task_id))
        
        return cursor.rowcount > 0


def get_user_records(user_id: int, limit: int = 50, offset: int = 0) -> List[dict]:
    """获取用户上色记录"""
    with get_db() as conn:
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM colorize_records 
            WHERE user_id = ? 
            ORDER BY created_at DESC 
            LIMIT ? OFFSET ?
        """, (user_id, limit, offset))
        
        return [dict(row) for row in cursor.fetchall()]


def create_order(user_id: int, package_id: str, package_name: str, 
                 price: float, credits: int) -> dict:
    """创建订单"""
    with get_db() as conn:
        cursor = conn.cursor()
        now = int(time.time())
        order_id = f"ORD{uuid.uuid4().hex[:16].upper()}"
        
        cursor.execute("""
            INSERT INTO orders 
            (order_id, user_id, package_id, package_name, price, credits, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (order_id, user_id, package_id, package_name, price, credits, now))
        
        return {
            "id": cursor.lastrowid,
            "order_id": order_id,
            "status": "pending"
        }


def update_order_status(order_id: str, status: str, payment_id: str = '') -> bool:
    """更新订单状态"""
    with get_db() as conn:
        cursor = conn.cursor()
        now = int(time.time())
        
        cursor.execute("""
            UPDATE orders 
            SET status = ?, payment_id = ?, paid_at = ?
            WHERE order_id = ?
        """, (status, payment_id, now, order_id))
        
        return cursor.rowcount > 0


def get_user_orders(user_id: int, limit: int = 50) -> List[dict]:
    """获取用户订单"""
    with get_db() as conn:
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM orders 
            WHERE user_id = ? 
            ORDER BY created_at DESC 
            LIMIT ?
        """, (user_id, limit))
        
        return [dict(row) for row in cursor.fetchall()]


def create_deletion_request(openid: str) -> dict:
    """创建数据删除请求"""
    with get_db() as conn:
        cursor = conn.cursor()
        now = int(time.time())
        
        # 获取用户ID
        cursor.execute("SELECT id FROM users WHERE openid = ?", (openid,))
        user = cursor.fetchone()
        
        if not user:
            raise ValueError("用户不存在")
        
        cursor.execute("""
            INSERT INTO deletion_requests (user_id, openid, requested_at)
            VALUES (?, ?, ?)
        """, (user['id'], openid, now))
        
        return {
            "id": cursor.lastrowid,
            "status": "pending"
        }


def process_deletion_request(request_id: int, approved: bool = True) -> bool:
    """处理数据删除请求"""
    with get_db() as conn:
        cursor = conn.cursor()
        now = int(time.time())
        status = 'approved' if approved else 'rejected'
        
        cursor.execute("""
            UPDATE deletion_requests 
            SET status = ?, processed_at = ?
            WHERE id = ?
        """, (status, now, request_id))
        
        if approved and cursor.rowcount > 0:
            # 获取用户信息
            cursor.execute("SELECT user_id, openid FROM deletion_requests WHERE id = ?", (request_id,))
            request = cursor.fetchone()
            
            if request:
                # 删除用户数据
                user_id = request['user_id']
                cursor.execute("DELETE FROM colorize_records WHERE user_id = ?", (user_id,))
                cursor.execute("DELETE FROM share_records WHERE user_id = ?", (user_id,))
                cursor.execute("DELETE FROM orders WHERE user_id = ?", (user_id,))
                cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
                
                return True
        
        return cursor.rowcount > 0


def get_record_by_task_id(task_id: str) -> Optional[dict]:
    """根据task_id获取记录"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM colorize_records WHERE task_id = ?", (task_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def delete_user_records(openid: str) -> bool:
    """删除用户的所有上色记录（配合数据删除申请）"""
    user = get_user_by_openid(openid)
    if not user:
        return False
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM colorize_records WHERE user_id = ?", (user["id"],))
        return True


# 初始化数据库
if __name__ == "__main__":
    init_db()
