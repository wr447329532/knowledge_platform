"""一次性脚本：创建或重置管理员账号。请在项目根目录执行：PYTHONPATH=. python scripts/create_admin.py"""
import sys
from pathlib import Path

# 保证从项目根目录运行时可导入 backend
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy.orm import Session

from backend.app.core.security import get_password_hash, verify_password
from backend.app.db.session import SessionLocal
from backend.app.models.user import User


def main():
    username = "admin"
    password = "admin123"
    db: Session = SessionLocal()
    try:
        existing = db.query(User).filter(User.username == username).first()
        new_hash = get_password_hash(password)
        if existing:
            # 强制重置密码，避免之前 bcrypt 版本不一致导致无法登录
            existing.hashed_password = new_hash
            existing.is_superuser = True
            existing.is_active = True
            db.commit()
            db.refresh(existing)
            print("已重置管理员密码。")
        else:
            user = User(
                username=username,
                email="admin@example.com",
                hashed_password=new_hash,
                is_active=True,
                is_superuser=True,
            )
            db.add(user)
            db.commit()
            print("已创建初始管理员账号。")
        # 验证：用当前环境校验一次，确保后端用同样环境能登录
        if verify_password(password, new_hash):
            print(f"  用户名: {username}\n  密码: {password}\n可直接用以上账号登录。")
        else:
            print("  警告：密码校验未通过，请确认本环境与运行后端的 Python 环境一致（含 bcrypt<4.1）。")
    finally:
        db.close()


if __name__ == "__main__":
    main()
