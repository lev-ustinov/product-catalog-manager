"""
Seed demo data: application users (app_user) and a realistic change-history
(audit_log), so the "Пользователи" and "История изменений" panels are not
empty on a freshly-cloned demo.

Usage
-----
    cd app
    python seed_demo_data.py

This script is idempotent: if app_user (or audit_log) already has rows,
that table is left untouched and a message is printed instead.

It assumes the catalog schema from init.sql has already been applied
(categories 1-19, products 1-9, xo_instances 1-5 — see init.sql for the
exact seed values referenced in the generated audit trail below).
"""

from datetime import datetime, timedelta, timezone

from database import engine, SessionLocal, Base
from models import User, AuditLog, XOInstance, XOClass
from auth import hash_password


DEMO_USERS = [
    {"username": "admin",   "password": "admin123",   "role": "admin"},
    {"username": "manager", "password": "manager123", "role": "user"},
    {"username": "analyst", "password": "analyst123", "role": "user"},
]


def seed_users(db) -> dict:
    """Create demo accounts. Returns {username: {"id":.., "username":..}}."""
    if db.query(User).count() > 0:
        print("  app_user already has data — skipping user seeding.")
        return {u.username: {"id": u.id, "username": u.username} for u in db.query(User).all()}

    created = {}
    for spec in DEMO_USERS:
        user = User(
            username=spec["username"],
            password_hash=hash_password(spec["password"]),
            role=spec["role"],
            is_active=True,
        )
        db.add(user)
        db.flush()
        created[spec["username"]] = {"id": user.id, "username": user.username}
        print(f"  + user '{spec['username']}' (role={spec['role']}, password='{spec['password']}')")

    db.commit()
    return created


def seed_xo_instances(db) -> None:
    """
    Add recent XO instances (last 6 months) so the analytics chart shows
    live data. Skipped if any XO instance has op_date in the last 6 months.
    The init.sql data is from 2024 and would look like a flat dead chart.
    """
    from datetime import date, timedelta

    recent_cutoff = date.today() - timedelta(days=180)
    has_recent = db.execute(
        __import__('sqlalchemy').text(
            "SELECT 1 FROM xo_instance WHERE op_date >= :cutoff LIMIT 1"
        ),
        {"cutoff": recent_cutoff},
    ).first()

    if has_recent:
        print("  xo_instance already has recent data — skipping.")
        return

    # Use the XO classes created by init.sql.
    # ids: 1=root, 2=Отгрузка, 3=Поступление, 4=Перемещение, 5=Инвентаризация
    xo_classes = {r.name: r.id for r in db.query(XOClass).all()}
    if not xo_classes:
        print("  xo_class table is empty — skipping XO instance seed.")
        return

    def cls(name: str, fallback_id: int = 3) -> int:
        return xo_classes.get(name, fallback_id)

    today = date.today()

    def ago(months: int) -> date:
        y, m = divmod(today.month - 1 - months, 12)
        return today.replace(year=today.year + y, month=m + 1, day=1)

    entries = [
        # (op_date, xo_class_name, number, status, created_by, notes)
        (ago(5), "Поступление товара",     "ПН-2026-001", "posted",    "manager", "Плановое пополнение склада"),
        (ago(5), "Отгрузка товара",        "ТН-2026-001", "posted",    "manager", None),
        (ago(4), "Поступление товара",     "ПН-2026-002", "posted",    "manager", "Сезонная закупка"),
        (ago(4), "Внутреннее перемещение", "ВП-2026-001", "posted",    "admin",   "Перемещение на склад №2"),
        (ago(3), "Отгрузка товара",        "ТН-2026-002", "posted",    "manager", None),
        (ago(3), "Инвентаризация",         "ИНВ-2026-001","posted",    "admin",   "Плановая ежеквартальная"),
        (ago(2), "Поступление товара",     "ПН-2026-003", "posted",    "manager", "Закупка у нового поставщика"),
        (ago(2), "Отгрузка товара",        "ТН-2026-003", "posted",    "manager", None),
        (ago(1), "Поступление товара",     "ПН-2026-004", "posted",    "manager", None),
        (ago(1), "Отгрузка товара",        "ТН-2026-004", "posted",    "manager", None),
        (ago(1), "Внутреннее перемещение", "ВП-2026-002", "cancelled", "admin",   "Отменено, ошибка адреса"),
        (today,  "Поступление товара",     "ПН-2026-005", "draft",     "manager", "В обработке"),
        (today,  "Отгрузка товара",        "ТН-2026-005", "draft",     "manager", None),
    ]

    for op_date, cls_name, number, status, created_by, notes in entries:
        db.add(XOInstance(
            xo_class_id=cls(cls_name),
            number=number,
            op_date=op_date,
            status=status,
            created_by=created_by,
            notes=notes,
        ))
    db.commit()
    print(f"  + {len(entries)} XO instances (last 6 months)")


def seed_audit_log(db, users: dict) -> None:
    """
    Insert a believable ~3-week change history covering all four entity
    types shown in the audit filter (category, product, xo_instance, user)
    and the create / update / delete / post actions.

    Entity ids reference the catalog seeded by init.sql:
      categories: 1=Товар(root) .. 4=Огурцы, 5=Томаты, 17=Инструменты, 19=Для полива
      products:    1=Огурец засолочный .. 5=Секатор садовый .. 9=Распылитель флакон
      xo_instances: 1=ТН-2024-0001, 3=ПН-2024-0101, 4=ВП-2024-0003(draft), 5=ИНВ-2024-0001
    """
    if db.query(AuditLog).count() > 0:
        print("  audit_log already has data — skipping audit seeding.")
        return

    def uid(username: str) -> int | None:
        u = users.get(username)
        return u["id"] if u else None

    now = datetime.now(timezone.utc).replace(tzinfo=None)  # naive UTC, matches DateTime columns

    # (days_ago, hours_ago, username, action, entity_type, entity_id, details)
    entries = [
        (14, 9,  "admin",   "create", "category",    1,
            "Создана корневая категория «Товар» (id=1)"),
        (14, 11, "admin",   "create", "category",    4,
            "Создана категория «Огурцы» (id=4), родитель id=3"),

        (13, 10, "admin",   "create", "product",     1,
            "Создан товар «Огурец засолочный» (категория id=4, цена=45.50)"),
        (13, 14, "admin",   "create", "product",     5,
            "Создан товар «Секатор садовый» (категория id=17, цена=1250.00)"),

        (12, 10, "admin",   "create", "user",        uid("manager"),
            "Создан пользователь «manager» (роль=user)"),
        (12, 10, "admin",   "create", "user",        uid("analyst"),
            "Создан пользователь «analyst» (роль=user)"),

        (11, 9,  "manager", "create", "xo_instance", 1,
            "Создан экземпляр ХО «Отгрузка товара», № ТН-2024-0001 от 2024-03-15"),
        (11, 15, "manager", "post",   "xo_instance", 1,
            "Проведена ХО «Отгрузка товара», № ТН-2024-0001 от 2024-03-15"),

        (10, 13, "manager", "create", "xo_instance", 3,
            "Создан экземпляр ХО «Поступление товара», № ПН-2024-0101 от 2024-03-10"),
        (9,  10, "admin",   "post",   "xo_instance", 3,
            "Проведена ХО «Поступление товара», № ПН-2024-0101 от 2024-03-10"),

        (8,  12, "analyst", "update", "product",     2,
            "Товар «Томат сибирский» (id=2): цена 35.00 → 38.00"),
        (7,  9,  "analyst", "update", "category",    5,
            "Категория «Томаты» (id=5): единица упаковки → «грамм»"),

        (6,  11, "manager", "create", "xo_instance", 4,
            "Создан экземпляр ХО «Внутреннее перемещение», № ВП-2024-0003 от 2024-04-01"),
        (6,  16, "manager", "update", "xo_instance", 4,
            "ХО id=4: примечания изменены"),

        (5,  10, "admin",   "create", "xo_instance", 5,
            "Создан экземпляр ХО «Инвентаризация», № ИНВ-2024-0001 от 2024-03-31"),
        (4,  13, "admin",   "post",   "xo_instance", 5,
            "Проведена ХО «Инвентаризация», № ИНВ-2024-0001 от 2024-03-31"),

        (3,  10, "manager", "create", "product",     10,
            "Создан товар «Распылитель (пробная партия)» (категория id=19, цена=99.00)"),
        (2,  14, "admin",   "delete", "product",     10,
            "Удалён товар «Распылитель (пробная партия)» (id=10, цена=99.00)"),

        (1,  9,  "admin",   "update", "user",        uid("analyst"),
            "Пользователь «analyst»: роль → user"),
    ]

    for days_ago, hours_ago, username, action, entity_type, entity_id, details in entries:
        db.add(AuditLog(
            timestamp=now - timedelta(days=days_ago, hours=hours_ago),
            user_login=username,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details,
        ))

    db.commit()
    print(f"  + {len(entries)} audit log entries (last {entries[0][0]} days)")


def main() -> None:
    print("Ensuring tables exist...")
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        print("\nSeeding recent XO instances:")
        seed_xo_instances(db)

        print("\nSeeding users:")
        users = seed_users(db)

        print("\nSeeding audit log:")
        seed_audit_log(db, users)
    finally:
        db.close()

    print("\nDone. Demo accounts:")
    for spec in DEMO_USERS:
        print(f"  {spec['username']:8} / {spec['password']:12} (role={spec['role']})")


if __name__ == "__main__":
    main()
