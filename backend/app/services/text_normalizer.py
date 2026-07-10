import re
import unicodedata


def normalize(value: str | None) -> str:
    text = (value or '').strip().lower()
    text = unicodedata.normalize('NFKD', text)
    text = ''.join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r'[^a-z0-9 ]+', ' ', text)
    text = re.sub(r'\b(fc|cf|club|de|the|team|esports|e sports|gaming)\b', ' ', text)
    return ' '.join(text.split())
