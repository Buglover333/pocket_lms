"""Product allowlist of Russian email providers; exact domain matching only."""

RUSSIAN_EMAIL_DOMAINS = frozenset(
    {
        "yandex.ru",
        "ya.ru",
        "yandex.com",
        "mail.ru",
        "inbox.ru",
        "list.ru",
        "bk.ru",
        "internet.ru",
        "vk.com",
        "vk.ru",
        "rambler.ru",
        "lenta.ru",
        "autorambler.ru",
        "myrambler.ru",
        "ro.ru",
    }
)


def russian_registration_email(value: str) -> str:
    value = str(value).lower()
    if value.rsplit("@", 1)[-1] not in RUSSIAN_EMAIL_DOMAINS:
        raise ValueError(
            "Используйте почту российского сервиса: Яндекс, Mail, VK или Рамблер"
        )
    return value
