import aiohttp
import hashlib
import hmac
import base64
import logging
from abc import ABC, abstractmethod
from typing import Optional
from config import SETTINGS

logger = logging.getLogger(__name__)

class BaseClient(ABC):
    """Abstract base class for API clients."""
    @abstractmethod
    async def get_balance(self) -> float:
        """Retrieves current balance as float."""
        pass

class ZadarmaClient(BaseClient):
    """
    Client for Zadarma API interactions using HMAC-SHA1 signature.
    """
    def __init__(self):
        self.key = SETTINGS.ZADARMA_KEY
        self.secret = SETTINGS.ZADARMA_SECRET
        self.api_url = "https://api.zadarma.com"

    def _get_auth_header(self, method: str, params: dict) -> str:
        """Generates Authorization header based on Zadarma API requirements."""
        # 1. Sort parameters and build query string
        params_str = '&'.join(f"{k}={v}" for k, v in sorted(params.items()))
        
        # 2. MD5 hash of the query string
        md5_hex = hashlib.md5(params_str.encode('utf-8')).hexdigest()
        
        # 3. Create signature string
        string_to_sign = method + params_str + md5_hex
        
        # 4. Generate HMAC-SHA1
        hmac_obj = hmac.new(self.secret.encode('utf-8'), string_to_sign.encode('utf-8'), hashlib.sha1)
        hmac_hex = hmac_obj.hexdigest()
        
        # 5. Base64 encode the hex digest
        hmac_base64 = base64.b64encode(hmac_hex.encode('utf-8')).decode('utf-8')
        
        return f"{self.key}:{hmac_base64}"

    async def get_balance(self) -> float:
        method = "/v1/info/balance/"
        params = {'format': 'json'}
        
        try:
            auth_header = self._get_auth_header(method, params)
            headers = {
                'Authorization': auth_header,
                'User-Agent': 'PythonScript'
            }
            full_url = f"{self.api_url}{method}"
            
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(full_url, params=params) as response:
                    data = await response.json()
                    
                    if response.status == 200 and data.get('status') == 'success':
                        # API response structure check
                        if 'balance' in data:
                             return float(data['balance'])
                        if 'info' in data and 'balance' in data['info']:
                             return float(data['info']['balance'])
                        return 0.0
                    else:
                        logger.error(f"Zadarma API Error: {response.status}. Data: {data}")
                        return 0.0
        except Exception as e:
            logger.error(f"Zadarma Connection Error: {e}")
            return 0.0

class DIDWWClient(BaseClient):
    """
    Client for DIDWW API v3.
    """
    def __init__(self):
        self.token = SETTINGS.DIDWW_KEY
        self.api_url = "https://api.didww.com/v3/"

    async def get_balance(self) -> Optional[float]:
        headers = {
            "Api-Key": self.token,
            "Accept": "application/vnd.api+json"
        }
        full_url = f"{self.api_url}balance"
        
        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(full_url) as response:
                    if response.status == 404:
                        logger.error("DIDWW API Error: Endpoint not found.")
                        return None
                    
                    # Parse JSON safely
                    try:
                        data = await response.json()
                    except Exception:
                        logger.error(f"DIDWW API Error: Invalid JSON response.")
                        return None

                    # Extract balance from JSON:API structure
                    data_block = data.get('data', {})
                    if isinstance(data_block, list) and data_block:
                        attributes = data_block[0].get('attributes', {})
                    elif isinstance(data_block, dict):
                        attributes = data_block.get('attributes', {})
                    else:
                        attributes = {}

                    if attributes:
                        # Prefer total_balance, fallback to balance
                        return float(attributes.get('total_balance', attributes.get('balance', 0.0)))

                    logger.error(f"DIDWW API Error: Unexpected structure. {data}")
                    return None

        except Exception as e:
            logger.error(f"DIDWW Connection Error: {e}")
            return None

# Service Registry
API_CLIENTS = {
    'Zadarma': ZadarmaClient(),
    'DIDWW': DIDWWClient(),
}