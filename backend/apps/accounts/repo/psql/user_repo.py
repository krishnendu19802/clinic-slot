from apps.accounts.models import User


class UserRepo:
    def get_by_phone(self, phone: str) -> User | None:
        return User.objects.filter(phone=phone).first()

    def create(self, phone: str, role: str) -> User:
        return User.objects.create_user(phone, role)

    def set_email(self, user: User, email: str | None) -> None:
        user.email = email
        user.save(update_fields=["email"])
