import aiohttp
import hashlib
import hmac
import logging
from abc import ABC, abstractmethod
from config import SETTINGS

logger = logging.getLogger(__name__)

class BaseClient(ABC):
    """Базовый класс для API клиентов."""
    @abstractmethod
    async def get_balance(self) -> float:
        """Получает текущий баланс и возвращает его как float."""
        pass

class ZadarmaClient(BaseClient):
    """
    Клиент для Zadarma API (использует HMAC-SHA1 аутентификацию).
    """
    def __init__(self):
        self.key = SETTINGS.ZADARMA_KEY
        self.secret = SETTINGS.ZADARMA_SECRET
        self.api_url = "https://api.zadarma.com/v1/"

    def _generate_signature(self, path: str, params: dict) -> str:
        """Генерирует подпись HMAC-SHA1."""
        # 1. Формируем строку параметров
        params_str = '&'.join([f"{key}={params[key]}" for key in sorted(params.keys())])
        
        # 2. Формируем строку для подписи
        data = f"{path}{params_str}{hashlib.sha1(params_str.encode()).hexdigest()}"
        
        # 3. Подписываем
        h = hmac.new(self.secret.encode(), data.encode(), hashlib.sha1)
        return h.hexdigest()

    async def get_balance(self) -> float:
        path = "info/balance/"
        params = {'format': 'json'}
        signature = self._generate_signature(path, params)
        
        headers = {
            'Authorization': f'Bearer {self.key}',
            'Signature': signature
        }
        
        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                full_url = f"{self.api_url}{path}"
                async with session.get(full_url, params=params) as response:
                    content_type = (response.content_type or "").lower()
                    logger.info(f"Zadarma: Request to {full_url}. Status: {response.status}. Content-Type: {response.content_type}")

                    if response.status == 404:
                        logger.error("Zadarma API error: endpoint not found (404).")
                        return 0.0

                    if 'json' in content_type:
                        try:
                            data = await response.json()
                        except Exception as decode_err:
                            logger.error(f"Zadarma API error: failed to decode JSON: {decode_err}")
                            return 0.0

                        if response.status == 200 and data.get('status') == 'success':
                            balance = float(data['info']['balance'])
                            return balance

                        logger.error(f"Zadarma API error: {data.get('status')} - {data.get('error')}")
                        return 0.0

                    # Не JSON ответ
                    error_text = await response.text()
                    logger.error(f"Zadarma API error (Status {response.status}, Type {response.content_type}). Server message: {error_text[:200]}...")
                    return 0.0
        except Exception as e:
            logger.error(f"Failed to connect or process Zadarma API: {e}")
            return 0.0

class DIDWWClient(BaseClient):
    """
    Клиент для DIDWW API (использует API Key / Bearer Token).
    """
    def __init__(self):
        self.token = SETTINGS.DIDWW_KEY
        self.api_url = "https://api.didww.com/v3/"

    async def get_balance(self) -> float:
        # DIDWW использует заголовок Api-Key, а баланс доступен на /v3/balance
        headers = {
            "Api-Key": self.token,
            "Accept": "application/vnd.api+json"
        }
        path = "balance"
        full_url = f"{self.api_url}{path}"
        
        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(full_url) as response:
                    content_type = (response.content_type or "").lower()
                    logger.info(f"DIDWW: Request to {full_url}. Status: {response.status}. Content-Type: {response.content_type}")
                    
                    if response.status == 404:
                        logger.error("DIDWW API error: endpoint not found (404).")
                        return None

                    if 'json' in content_type:
                        try:
                            data = await response.json()
                        except Exception as decode_err:
                            logger.error(f"DIDWW API error: failed to decode JSON: {decode_err}")
                            return None

                        logger.debug(f"DIDWW: JSON response received: {data}")

                        data_block = data.get('data', {})
                        if isinstance(data_block, dict):
                            attributes = data_block.get('attributes', {})
                        elif isinstance(data_block, list) and data_block:
                            attributes = data_block[0].get('attributes', {})
                        else:
                            attributes = {}

                        if attributes:
                            # В ответе есть balance, credit, total_balance. Берем total_balance.
                            try:
                                balance = float(attributes.get('total_balance', attributes.get('balance', 0.0)))
                                return balance
                            except Exception:
                                logger.error(f"DIDWW API error: attributes not numeric. Raw: {attributes}")
                                return None

                        logger.error(f"DIDWW API error: Unexpected data structure. Raw Data: {data}")
                        return None

                    error_text = await response.text()
                    logger.error(f"DIDWW API error (Status {response.status}, Type {response.content_type}). Server message: {error_text[:200]}...")
                    return None
        except Exception as e:
            logger.error(f"Failed to connect or process DIDWW API (URL: {full_url}): {e}")
            return None

# Словарь для доступа к клиентам по имени сервиса
API_CLIENTS = {
    'Zadarma': ZadarmaClient(),
    'DIDWW': DIDWWClient(),
}