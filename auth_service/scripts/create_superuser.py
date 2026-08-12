"""
One-off script to create an admin user, e.g. for initial environment setup.

Usage:
    python -m scripts.create_superuser --email admin@example.com --password 'Str0ng!Pass1' --name "Admin"

Or set FIRST_SUPERUSER_EMAIL / FIRST_SUPERUSER_PASSWORD in the environment
and run with no arguments.
"""
import argparse
import asyncio
import sys

from app.core.config import settings
from app.core.constants import UserRole
from app.core.security import hash_password
from app.db.database import AsyncSessionLocal
from app.repositories.user_repository import UserRepository
from app.models.user import User


async def create_superuser(email: str, password: str, full_name: str | None) -> None:
    async with AsyncSessionLocal() as session:
        repo = UserRepository(session)
        if await repo.email_exists(email):
            print(f"A user with email '{email}' already exists. Aborting.")
            sys.exit(1)

        user = User(
            email=email.lower(),
            hashed_password=hash_password(password),
            full_name=full_name,
            role=UserRole.ADMIN,
            is_active=True,
            is_verified=True,
        )
        await repo.add(user)
        await repo.commit()
        print(f"Superuser created: {email}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create an admin/superuser account.")
    parser.add_argument("--email", default=settings.FIRST_SUPERUSER_EMAIL)
    parser.add_argument("--password", default=settings.FIRST_SUPERUSER_PASSWORD)
    parser.add_argument("--name", dest="full_name", default="Superuser")
    args = parser.parse_args()

    if not args.email or not args.password:
        parser.error(
            "Provide --email/--password, or set FIRST_SUPERUSER_EMAIL/"
            "FIRST_SUPERUSER_PASSWORD in the environment."
        )

    asyncio.run(create_superuser(args.email, args.password, args.full_name))


if __name__ == "__main__":
    main()
