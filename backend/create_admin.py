# -*- coding: utf-8 -*-
"""Bootstrap the first admin account.

Usage:
    python -m backend.create_admin

Reads ADMIN_USERNAME / ADMIN_EMAIL / ADMIN_PASSWORD / ADMIN_FULL_NAME from
the environment (handy for scripted/CI bootstrap); any that are missing are
prompted for interactively, with the password read via `getpass` (never
echoed, never logged, never hardcoded in source).

Refuses to overwrite an existing user — promote/demote existing accounts
through `PATCH /admin/users/{id}` instead, once at least one admin exists.
"""

from __future__ import annotations

import os
import sys
from getpass import getpass

from backend import crud
from backend.db import SessionLocal, init_db

_USERNAME_MIN, _PASSWORD_MIN = 3, 8


def _prompt_username() -> str:
    while True:
        value = input("Nom d'utilisateur administrateur: ").strip()
        if len(value) >= _USERNAME_MIN:
            return value
        print(f"  Au moins {_USERNAME_MIN} caractères.")


def _prompt_email() -> str:
    while True:
        value = input("E-mail: ").strip()
        if "@" in value and "." in value.split("@")[-1]:
            return value
        print("  Adresse e-mail invalide.")


def _prompt_password() -> str:
    while True:
        value = getpass("Mot de passe (saisie masquée): ")
        if len(value) < _PASSWORD_MIN:
            print(f"  Au moins {_PASSWORD_MIN} caractères.")
            continue
        confirm = getpass("Confirmer le mot de passe: ")
        if value != confirm:
            print("  Les mots de passe ne correspondent pas.")
            continue
        return value


def main() -> int:
    username = os.environ.get("ADMIN_USERNAME") or _prompt_username()
    email = os.environ.get("ADMIN_EMAIL") or _prompt_email()
    full_name = os.environ.get("ADMIN_FULL_NAME") or username
    password = os.environ.get("ADMIN_PASSWORD")

    if password is None:
        password = _prompt_password()
    elif len(password) < _PASSWORD_MIN:
        print(f"ADMIN_PASSWORD doit contenir au moins {_PASSWORD_MIN} caractères.", file=sys.stderr)
        return 1

    if len(username) < _USERNAME_MIN:
        print(f"ADMIN_USERNAME doit contenir au moins {_USERNAME_MIN} caractères.", file=sys.stderr)
        return 1

    init_db()
    db = SessionLocal()
    try:
        if crud.get_user_by_username(db, username) is not None:
            print(f"Le nom d'utilisateur « {username} » existe déjà — abandon.", file=sys.stderr)
            print("Utilisez PATCH /admin/users/{id} pour promouvoir un compte existant.", file=sys.stderr)
            return 1
        if crud.get_user_by_email(db, email) is not None:
            print(f"L'adresse « {email} » est déjà utilisée — abandon.", file=sys.stderr)
            return 1

        user = crud.create_user(
            db, username=username, email=email, password=password,
            full_name=full_name, role="admin",
        )
        print(f"Compte administrateur créé : {user.username} (id={user.id}).")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
