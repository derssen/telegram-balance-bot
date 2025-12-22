import aiohttp
import hashlib
import hmac
import base64 # Добавили
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
    Клиент для Zadarma API (Обновленная авторизация).
    """
    def __init__(self):
        self.key = SETTINGS.ZADARMA_KEY
        self.secret = SETTINGS.ZADARMA_SECRET
        self.api_url = "https://api.zadarma.com" # Убрал /v1/ отсюда

    def _get_auth_header(self, method: str, params: dict) -> str:
        """Генерирует заголовок Authorization по новой схеме."""
        # Шаг 1. Сортировка и строка запроса
        params_str = '&'.join(f"{k}={v}" for k, v in sorted(params.items()))
        
        # Шаг 2. MD5 от строки запроса
        md5_hex = hashlib.md5(params_str.encode('utf-8')).hexdigest()
        
        # Шаг 3. Строка для подписи
        string_to_sign = method + params_str + md5_hex
        
        # Шаг 4. HMAC-SHA1
        hmac_obj = hmac.new(self.secret.encode('utf-8'), string_to_sign.encode('utf-8'), hashlib.sha1)
        # Важно: поддержка делает .digest(), потом переводит в hex вручную. 
        # .hexdigest() делает то же самое.
        hmac_hex = hmac_obj.hexdigest()
        
        # Шаг 5. base64 от HEX-строки (очень странно, но так в инструкции)
        hmac_base64 = base64.b64encode(hmac_hex.encode('utf-8')).decode('utf-8')
        
        # Шаг 6. Authorization header
        return f"{self.key}:{hmac_base64}"

    async def get_balance(self) -> float:
        method = "/v1/info/balance/"
        params = {'format': 'json'} # Параметры API
        
        try:
            auth_header = self._get_auth_header(method, params)
            
            headers = {
                'Authorization': auth_header,
                'User-Agent': 'PythonScript' # Поддержка рекомендовала добавить
            }
            
            full_url = f"{self.api_url}{method}"
            
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(full_url, params=params) as response:
                    data = await response.json()
                    
                    if response.status == 200 and data.get('status') == 'success':
                        balance = float(data['balance']) # В новом API поле называется 'balance', а не 'info'['balance']?
                        # На всякий случай проверим оба варианта, так как документация может отличаться
                        if 'info' in data and 'balance' in data['info']:
                             balance = float(data['info']['balance'])
                        
                        return balance
                    else:
                        logger.error(f"Zadarma API error: Status {response.status}. Data: {data}")
                        return 0.0
        except Exception as e:
            logger.error(f"Failed to connect Zadarma API: {e}")
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