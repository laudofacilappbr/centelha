import re
import unicodedata

# O mesmo formato dos slugs de tema, post e campanha.
SLUG = r"^[a-z0-9]+(-[a-z0-9]+)*$"


def slugificar(texto: str, maximo: int = 120) -> str:
    """ "L'Évangile selon le Spiritisme" → "l-evangile-selon-le-spiritisme"."""
    sem_acento = unicodedata.normalize("NFKD", texto)
    sem_acento = "".join(c for c in sem_acento if not unicodedata.combining(c))
    slug = re.sub(r"[^a-z0-9]+", "-", sem_acento.lower()).strip("-")
    return slug[:maximo].rstrip("-")
