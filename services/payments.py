# services/payments.py
# Работа с ЮKassa: создание платежей и проверка статуса

from yookassa import Configuration, Payment
from config import YOOKASSA_SHOP_ID, YOOKASSA_SECRET_KEY


Configuration.account_id = YOOKASSA_SHOP_ID
Configuration.secret_key = YOOKASSA_SECRET_KEY


def create_payment(amount: float, description: str, user_id: int, payment_type: str) -> dict | None:
    """Создаёт платёж в ЮKassa."""
    try:
        payment = Payment.create({
            "amount": {
                "value": f"{amount:.2f}",
                "currency": "RUB"
            },
            "confirmation": {
                "type": "redirect",
                "return_url": "https://t.me/SubliminalGenBot"
            },
            "capture": True,
            "description": description,
            "metadata": {
                "user_id": user_id,
                "payment_type": payment_type
            }
        })

        return {
            "payment_id": payment.id,
            "confirmation_url": payment.confirmation.confirmation_url
        }

    except Exception as e:
        print(f"Ошибка создания платежа: {e}")
        return None


def check_payment(payment_id: str) -> str | None:
    """Проверяет статус платежа."""
    try:
        payment = Payment.find_one(payment_id)
        return payment.status
    except Exception as e:
        print(f"Ошибка проверки платежа: {e}")
        return None