from app.db.init_db import init_db


def update_db() -> None:
    init_db()


if __name__ == "__main__":
    update_db()