from getpass import getpass

from app.db import SessionLocal
from app.models import User
from app.core.migrations import initialize_database
from app.core.security import hash_password


def main():
    initialize_database()
    db = SessionLocal()
    try:
        username = input("请输入用户名: ").strip()
        if not username:
            print("用户名不能为空")
            return

        existing = db.query(User).filter(User.username == username).first()
        if existing:
            print("该用户名已存在")
            return

        password = getpass("请输入密码: ")
        confirm = getpass("请再次输入密码: ")

        if password != confirm:
            print("两次密码不一致")
            return

        is_admin_input = input("是否管理员？(y/n): ").strip().lower()
        is_admin = is_admin_input == "y"

        user = User(
            username=username,
            password_hash=hash_password(password),
            is_active=True,
            is_admin=is_admin
        )
        db.add(user)
        db.commit()

        print(f"用户 {username} 创建成功，管理员状态：{is_admin}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
