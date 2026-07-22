"""
Utility script: generate a bcrypt hash for the admin password.

Usage:
    python scripts/hash_password.py "your-plain-text-password"

Copy the printed hash into ADMIN_PASSWORD_HASH in your .env file.
"""

import sys

import bcrypt


def main() -> None:
    if len(sys.argv) != 2:
        print('Usage: python scripts/hash_password.py "your-password"')
        sys.exit(1)

    plain_password = sys.argv[1].encode("utf-8")
    hashed = bcrypt.hashpw(plain_password, bcrypt.gensalt())
    print(hashed.decode("utf-8"))


if __name__ == "__main__":
    main()
