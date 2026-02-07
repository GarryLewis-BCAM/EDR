"""
Threat Intelligence Integration
- AbuseIPDB IP reputation checking
- Cached results to minimize API calls
- Rate limiting and error handling
"""
import os
import time
import requests
import logging
from typing import Dict, Optional
from functools import lru_cache
import json

logger = logging.getLogger(__name__)


class ThreatIntelligence:
    """Threat intelligence API integration"""
    
    def __init__(self, config: Dict):
        """Initialize threat intelligence client"""
        self.config = config
        self.abuseipdb_key = os.environ.get('ABUSEIPDB_API_KEY') or config.get('threat_intel', {}).get('abuseipdb_key')
        
        # Rate limiting (free tier: 1000 requests/day)
        self.last_request_time = 0
        self.min_request_interval = 1.0  # 1 second between requests
        
        # Cache results for 24 hours
        self.cache = {}
        self.cache_ttl = 86400  # 24 hours
        
        if not self.abuseipdb_key:
            logger.warning("AbuseIPDB API key not configured - threat intel disabled")
    
    def check_ip(self, ip_address: str, max_age_days: int = 90) -> Dict:
        """
        Check IP reputation against AbuseIPDB
        
        Args:
            ip_address: IP to check
            max_age_days: Max age of reports to consider
            
        Returns:
            Dictionary with:
            - abuse_confidence_score: 0-100 score
            - is_malicious: Boolean
            - total_reports: Number of reports
            - last_reported_at: Last report timestamp
            - country_code: Country code
            - usage_type: Type of IP (ISP, datacenter, etc)
        """
        if not self.abuseipdb_key:
            return self._default_result(ip_address)
        
        # Check cache
        cache_key = f"{ip_address}:{max_age_days}"
        if cache_key in self.cache:
            cached_data, cached_time = self.cache[cache_key]
            if time.time() - cached_time < self.cache_ttl:
                logger.debug(f"Using cached result for {ip_address}")
                return cached_data
        
        # Rate limiting
        self._rate_limit()
        
        try:
            url = 'https://api.abuseipdb.com/api/v2/check'
            headers = {
                'Accept': 'application/json',
                'Key': self.abuseipdb_key
            }
            params = {
                'ipAddress': ip_address,
                'maxAgeInDays': max_age_days,
                'verbose': True
            }
            
            response = requests.get(url, headers=headers, params=params, timeout=5)
            response.raise_for_status()
            
            data = response.json()['data']
            
            result = {
                'ip_address': ip_address,
                'abuse_confidence_score': data.get('abuseConfidenceScore', 0),
                'is_malicious': data.get('abuseConfidenceScore', 0) > 50,
                'total_reports': data.get('totalReports', 0),
                'last_reported_at': data.get('lastReportedAt'),
                'country_code': data.get('countryCode', 'Unknown'),
                'usage_type': data.get('usageType', 'Unknown'),
                'isp': data.get('isp', 'Unknown'),
                'domain': data.get('domain', 'Unknown'),
                'is_whitelisted': data.get('isWhitelisted', False),
                'checked_at': time.time()
            }
            
            # Cache the result
            self.cache[cache_key] = (result, time.time())
            
            logger.info(f"IP {ip_address} checked: score={result['abuse_confidence_score']}, "
                       f"reports={result['total_reports']}, country={result['country_code']}")
            
            return result
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                logger.warning(f"AbuseIPDB rate limit exceeded")
                return self._default_result(ip_address, error="Rate limit exceeded")
            elif e.response.status_code == 401:
                logger.error(f"AbuseIPDB authentication failed - check API key")
                return self._default_result(ip_address, error="Authentication failed")
            else:
                logger.error(f"AbuseIPDB HTTP error: {e}")
                return self._default_result(ip_address, error=str(e))
                
        except Exception as e:
            logger.error(f"Error checking IP {ip_address}: {e}")
            return self._default_result(ip_address, error=str(e))
    
    def _rate_limit(self):
        """Enforce rate limiting"""
        now = time.time()
        time_since_last = now - self.last_request_time
        
        if time_since_last < self.min_request_interval:
            sleep_time = self.min_request_interval - time_since_last
            logger.debug(f"Rate limiting: sleeping {sleep_time:.2f}s")
            time.sleep(sleep_time)
        
        self.last_request_time = time.time()
    
    def _default_result(self, ip_address: str, error: Optional[str] = None) -> Dict:
        """Return default result when API unavailable"""
        return {
            'ip_address': ip_address,
            'abuse_confidence_score': 0,
            'is_malicious': False,
            'total_reports': 0,
            'last_reported_at': None,
            'country_code': 'Unknown',
            'usage_type': 'Unknown',
            'isp': 'Unknown',
            'domain': 'Unknown',
            'is_whitelisted': False,
            'checked_at': time.time(),
            'error': error or 'API not configured'
        }
    
    def bulk_check(self, ip_addresses: list, max_age_days: int = 90) -> Dict[str, Dict]:
        """
        Check multiple IPs (respects rate limits)
        
        Args:
            ip_addresses: List of IPs to check
            max_age_days: Max age of reports
            
        Returns:
            Dictionary mapping IP -> result
        """
        results = {}
        for ip in ip_addresses:
            results[ip] = self.check_ip(ip, max_age_days)
        return results
    
    def get_cache_stats(self) -> Dict:
        """Get cache statistics"""
        return {
            'cached_ips': len(self.cache),
            'cache_ttl_hours': self.cache_ttl / 3600,
            'api_configured': bool(self.abuseipdb_key)
        }


# Global instance (lazy initialized)
_threat_intel_instance = None


def get_threat_intel(config: Dict) -> ThreatIntelligence:
    """Get or create threat intelligence instance"""
    global _threat_intel_instance
    if _threat_intel_instance is None:
        _threat_intel_instance = ThreatIntelligence(config)
    return _threat_intel_instance


if __name__ == '__main__':
    """Test threat intelligence"""
    import yaml
    
    # Load config
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'edr_config.yaml')
    with open(config_path) as f:
        config = yaml.safe_load(f)
    
    # Test with known malicious IPs
    ti = ThreatIntelligence(config)
    
    test_ips = [
        '8.8.8.8',  # Google DNS - should be clean
        '185.220.101.1',  # Known Tor exit node
    ]
    
    for ip in test_ips:
        print(f"\nChecking {ip}...")
        result = ti.check_ip(ip)
        print(json.dumps(result, indent=2))
