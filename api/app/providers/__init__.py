from app.config import get_settings
from app.providers.base import Provider


def get_provider() -> Provider:
    s = get_settings()
    if s.dd_provider == "mistral":
        from app.providers.mistral import MistralProvider

        return MistralProvider()
    from app.providers.local import LocalProvider

    return LocalProvider()
