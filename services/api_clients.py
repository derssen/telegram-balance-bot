import aiohttp
import hashlib
import hmac
import base64
import logging
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from config import SETTINGS

logger = logging.getLogger(__name__)

class BaseClient(ABC):
    """Abstract base class for API clients."""
    @abstractmethod
    async def get_balance(self) -> Optional[float]:
        """Retrieves current balance as float."""
        pass

class ZadarmaClient(BaseClient):
    """Client for Zadarma API interactions using HMAC-SHA1."""
    def __init__(self):
        self.key = SETTINGS.ZADARMA_KEY
        self.secret = SETTINGS.ZADARMA_SECRET
        self.api_url = "https://api.zadarma.com"

    def _get_auth_header(self, method: str, params: dict) -> str:
        params_str = '&'.join(f"{k}={v}" for k, v in sorted(params.items()))
        md5_hex = hashlib.md5(params_str.encode('utf-8')).hexdigest()
        string_to_sign = method + params_str + md5_hex
        hmac_obj = hmac.new(self.secret.encode('utf-8'), string_to_sign.encode('utf-8'), hashlib.sha1)
        hmac_base64 = base64.b64encode(hmac_obj.hexdigest().encode('utf-8')).decode('utf-8')
        return f"{self.key}:{hmac_base64}"

    async def get_balance(self) -> Optional[float]:
        method = "/v1/info/balance/"
        params = {'format': 'json'}
        try:
            auth_header = self._get_auth_header(method, params)
            headers = {'Authorization': auth_header, 'User-Agent': 'PythonScript'}
            full_url = f"{self.api_url}{method}"
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(full_url, params=params) as response:
                    data = await response.json()
                    if response.status == 200 and data.get('status') == 'success':
                        if 'balance' in data: return float(data['balance'])
                        if 'info' in data and 'balance' in data['info']: return float(data['info']['balance'])
                    return None
        except Exception as e:
            logger.error(f"Zadarma Connection Error: {e}")
            return None

class DIDWWClient(BaseClient):
    """Client for DIDWW API v3."""
    def __init__(self):
        self.token = SETTINGS.DIDWW_KEY
        self.api_url = "https://api.didww.com/v3/"

    async def get_balance(self) -> Optional[float]:
        headers = {"Api-Key": self.token, "Accept": "application/vnd.api+json"}
        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(f"{self.api_url}balance") as response:
                    if response.status != 200: return None
                    data = await response.json()
                    attrs = {}
                    if 'data' in data:
                        d = data['data']
                        attrs = d[0]['attributes'] if isinstance(d, list) and d else (d.get('attributes', {}) if isinstance(d, dict) else {})
                    return float(attrs.get('total_balance', attrs.get('balance', 0.0))) if attrs else None
        except Exception as e:
            logger.error(f"DIDWW Connection Error: {e}")
            return None

class MakeClient(BaseClient):
    """
    Client for Make (Integromat) API.
    """
    def __init__(self):
        self.token = SETTINGS.MAKE_API_KEY
        self.org_id = SETTINGS.MAKE_ORG_ID
        self.zone = SETTINGS.MAKE_ZONE # eu1 or us1
        self.api_url = f"https://{self.zone}.make.com/api/v2/organizations/{self.org_id}"
        self.cached_details = {}

    async def get_details(self) -> Optional[Dict[str, Any]]:
        """Fetches full license details including usage and reset dates."""
        headers = {"Authorization": f"Token {self.token}"}
        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(self.api_url) as response:
                    if response.status != 200:
                        logger.error(f"Make API Error: Status {response.status}")
                        return None
                    
                    data = await response.json()
                    
                    # Log removed to reduce noise after fix, but structure is:
                    # { 'organization': { 'operations': '14851', 'nextReset': '...', 'license': { 'operations': 20000 } } }
                    
                    org = data.get('organization', {})
                    license_info = org.get('license', {})

                    # Parsing logic based on provided logs
                    usage = float(org.get('operations', 0)) # Value is string in JSON
                    limit = float(license_info.get('operations', 0)) # Value is int/float
                    reset_at = org.get('nextReset')

                    return {
                        'usage': usage,
                        'limit': limit,
                        'reset_at': reset_at 
                    }
        except Exception as e:
            logger.error(f"Make API Connection Error: {e}")
            return None

    async def get_balance(self) -> Optional[float]:
        """Returns REMAINING operations."""
        details = await self.get_details()
        if details:
            self.cached_details = details
            
            limit = details.get('limit', 0)
            usage = details.get('usage', 0)
            remaining = limit - usage
            
            logger.info(f"Make Calc: Limit {limit} - Usage {usage} = {remaining}")
            return float(remaining)
        return None

API_CLIENTS = {
    'Zadarma': ZadarmaClient(),
    'DIDWW': DIDWWClient(),
    'Make': MakeClient(),
}