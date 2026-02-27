import json
import os
from typing import Dict, List, Set


class AuthSystem:
    def __init__(self, admin_id: int, allowed_group: int):
        self.admin_id = admin_id
        self.allowed_group = allowed_group
        self.authorized_users: Dict[int, str] = {}
        self.banned_users: Set[int] = set()
        self.admin_users: Set[int] = set()
        self.gratis_mode = False
        self.load_data()

    def load_data(self):
        try:
            if os.path.exists('auth_data.json'):
                with open('auth_data.json', 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if 'authorized_users' in data and isinstance(data['authorized_users'], list):
                        self.authorized_users = {int(uid): f"Usuario_{uid}" for uid in data['authorized_users']}
                    elif 'authorized_users' in data and isinstance(data['authorized_users'], dict):
                        self.authorized_users = {int(k): v for k, v in data['authorized_users'].items()}
                    else:
                        self.authorized_users = {}
                    self.banned_users = set(int(uid) for uid in data.get('banned_users', []))
                    self.admin_users = set(int(uid) for uid in data.get('admin_users', []))
                    self.gratis_mode = data.get('gratis_mode', False)
        except Exception as e:
            print(f"[AUTH] Error cargando datos: {e}")
            self.authorized_users = {}
            self.banned_users = set()
            self.admin_users = set()
            self.gratis_mode = False

    def save_data(self):
        try:
            data = {
                'authorized_users': {str(k): v for k, v in self.authorized_users.items()},
                'banned_users': list(self.banned_users),
                'admin_users': list(self.admin_users),
                'gratis_mode': self.gratis_mode
            }
            with open('auth_data.json', 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[AUTH] Error guardando datos: {e}")

    def is_admin(self, user_id: int) -> bool:
        return user_id == self.admin_id or user_id in self.admin_users

    def is_main_admin(self, user_id: int) -> bool:
        return user_id == self.admin_id

    def add_admin(self, user_id: int) -> bool:
        if user_id == self.admin_id:
            return False
        self.admin_users.add(user_id)
        self.save_data()
        return True

    def remove_admin(self, user_id: int) -> bool:
        if user_id == self.admin_id:
            return False
        if user_id in self.admin_users:
            self.admin_users.remove(user_id)
            self.save_data()
            return True
        return False

    def get_admin_users(self) -> List[int]:
        return list(self.admin_users)

    def is_authorized(self, user_id: int) -> bool:
        return user_id in self.authorized_users

    def is_banned(self, user_id: int) -> bool:
        return user_id in self.banned_users

    def can_use_bot(self, user_id: int, chat_id: int, is_private=None) -> bool:
        user_id = int(user_id)
        chat_id = int(chat_id)
        if self.is_banned(user_id):
            return False
        if is_private is None:
            try:
                is_private = chat_id > 0
            except Exception:
                is_private = False
        if self.gratis_mode:
            return True
        return self.is_authorized(user_id) or self.is_admin(user_id)

    def auto_register_user(self, user_id: int, username: str = None, first_name: str = None) -> bool:
        if self.is_banned(user_id):
            return False
        if not self.is_authorized(user_id):
            if first_name:
                nombre = f"{first_name}_{user_id}"
            elif username:
                nombre = f"@{username}_{user_id}"
            else:
                nombre = f"Usuario_Auto_{user_id}"
            self.add_user(user_id, nombre)
            return True
        return False

    def add_user(self, user_id: int, nombre: str = None) -> bool:
        if nombre is None:
            nombre = f"Usuario_{user_id}"
        self.authorized_users[user_id] = nombre
        self.save_data()
        return True

    def remove_user(self, user_id: int) -> bool:
        if user_id in self.authorized_users:
            del self.authorized_users[user_id]
            self.save_data()
            return True
        return False

    def ban_user(self, user_id: int) -> bool:
        self.banned_users.add(user_id)
        self.save_data()
        return True

    def unban_user(self, user_id: int) -> bool:
        if user_id in self.banned_users:
            self.banned_users.remove(user_id)
            self.save_data()
            return True
        return False

    def set_gratis_mode(self, enabled: bool):
        self.gratis_mode = enabled
        self.save_data()

    def get_authorized_users(self) -> Dict[int, str]:
        return self.authorized_users.copy()

    def get_banned_users(self) -> List[int]:
        return list(self.banned_users)

    def get_stats(self) -> Dict:
        return {
            'total_authorized': len(self.authorized_users),
            'total_banned': len(self.banned_users),
            'total_admins': len(self.admin_users) + 1,
            'gratis_mode': self.gratis_mode,
            'allowed_group': self.allowed_group
        }
