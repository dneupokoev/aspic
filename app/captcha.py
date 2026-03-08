import random
import time
from dotenv import load_dotenv
import os

load_dotenv()

CAPTCHA_TTL = int(os.getenv("CAPTCHA_TTL_SECONDS", 300))


class CaptchaStore:
    def __init__(self):
        self.store = {}  # key: f"{token}:{ip}", value: {"answer": int, "expires": float}

    def generate(self, token: str, ip: str) -> dict:
        num1 = random.randint(1, 10)
        num2 = random.randint(1, 10)
        op = random.choice(['+', '-', '*'])
        answer = eval(f"{num1}{op}{num2}")

        key = f"{token}:{ip}"
        self.store[key] = {
            "answer": answer,
            "expires": time.time() + CAPTCHA_TTL
        }

        return {"question": f"{num1} {op} {num2} = ?", "key": key}

    def verify(self, token: str, ip: str, user_answer: str) -> bool:
        key = f"{token}:{ip}"
        data = self.store.get(key)

        if not data:
            return False

        if time.time() > data["expires"]:
            del self.store[key]
            return False

        try:
            is_valid = int(user_answer) == data["answer"]
            del self.store[key]  # одноразовая
            return is_valid
        except (ValueError, TypeError):
            return False


captcha_store = CaptchaStore()