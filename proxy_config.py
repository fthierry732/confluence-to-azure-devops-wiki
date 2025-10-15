#!/usr/bin/env python3
"""
Proxy Configuration Module for Confluence to Azure DevOps Wiki Migration
Supports PAC proxies, normal proxies, and no proxies
"""

import os
import requests
from typing import Optional

# Load environment variables from .env file if it exists
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

class ProxyConfig:
    """Handles different types of proxy configurations"""
    
    def __init__(self):
        self.session = None
        self.proxy_type = None
        self.proxy_config = None
        
    def configure_proxy(self, proxy_type: Optional[str] = None, 
                       proxy_url: Optional[str] = None,
                       pac_url: Optional[str] = None) -> requests.Session:
        """
        Configure and return a requests session with appropriate proxy settings
        
        Args:
            proxy_type: Type of proxy ('pac', 'http', 'https', 'socks', 'none', or None for auto-detect)
            proxy_url: URL for normal proxy (e.g., 'http://proxy.company.com:8080')
            pac_url: URL for PAC file (e.g., 'http://proxy.company.com:8080/proxy.pac')
        
        Returns:
            requests.Session configured with appropriate proxy settings
        """
        
        # Auto-detect proxy type from environment variables if not specified
        if proxy_type is None:
            proxy_type = self._detect_proxy_type()
        
        self.proxy_type = proxy_type
        
        if proxy_type == 'pac':
            return self._configure_pac_proxy(pac_url)
        elif proxy_type in ['http', 'https', 'socks']:
            return self._configure_normal_proxy(proxy_type, proxy_url)
        elif proxy_type == 'none':
            return self._configure_no_proxy()
        else:
            # Default to no proxy if type is not recognized
            print(f"⚠️ Unknown proxy type '{proxy_type}', using no proxy")
            return self._configure_no_proxy()
    
    def _detect_proxy_type(self) -> str:
        """Auto-detect proxy type from environment variables"""
        
        # Check for PAC proxy configuration
        pac_url = os.getenv('PROXY_PAC_URL')
        if pac_url:
            print(f"🔍 Detected PAC proxy configuration: {pac_url}")
            return 'pac'
        
        # Check for normal proxy configuration
        http_proxy = os.getenv('HTTP_PROXY') or os.getenv('http_proxy')
        https_proxy = os.getenv('HTTPS_PROXY') or os.getenv('https_proxy')
        
        if http_proxy or https_proxy:
            print("🔍 Detected normal proxy configuration")
            if http_proxy:
                print(f"   HTTP Proxy: {http_proxy}")
            if https_proxy:
                print(f"   HTTPS Proxy: {https_proxy}")
            return 'http'  # Default to http for normal proxies
        
        # Check for explicit no-proxy setting
        no_proxy = os.getenv('NO_PROXY', '').lower()
        if no_proxy in ['true', '1', 'yes']:
            print("🔍 Detected explicit no-proxy configuration")
            return 'none'
        
        # Default to no proxy
        print("🔍 No proxy configuration detected, using direct connection")
        return 'none'
    
    def _configure_pac_proxy(self, pac_url: Optional[str] = None) -> requests.Session:
        """Configure session with PAC proxy"""
        try:
            from pypac import PACSession, get_pac
            
            # Get PAC URL from parameter or environment
            if not pac_url:
                pac_url = os.getenv('PROXY_PAC_URL')
            
            if not pac_url:
                raise ValueError("PAC URL not provided and PROXY_PAC_URL environment variable not set")
            
            print(f"🌐 Configuring PAC proxy: {pac_url}")
            
            # Load PAC file
            pac = get_pac(url=pac_url)
            
            # Create session with PAC
            session = PACSession(pac)
            
            print("✅ PAC proxy configured successfully")
            return session
            
        except ImportError:
            print("❌ pypac library not installed. Install with: pip install pypac")
            print("   Falling back to no proxy")
            return self._configure_no_proxy()
        except Exception as e:
            print(f"❌ Failed to configure PAC proxy: {str(e)}")
            print("   Falling back to no proxy")
            return self._configure_no_proxy()
    
    def _configure_normal_proxy(self, proxy_type: str, proxy_url: Optional[str] = None) -> requests.Session:
        """Configure session with normal HTTP/HTTPS/SOCKS proxy"""
        
        # Get proxy URL from parameter or environment variables
        if not proxy_url:
            if proxy_type == 'http':
                proxy_url = os.getenv('HTTP_PROXY') or os.getenv('http_proxy')
            elif proxy_type == 'https':
                proxy_url = os.getenv('HTTPS_PROXY') or os.getenv('https_proxy')
            elif proxy_type == 'socks':
                proxy_url = os.getenv('SOCKS_PROXY') or os.getenv('socks_proxy')
        
        if not proxy_url:
            raise ValueError(f"{proxy_type.upper()} proxy URL not provided and environment variable not set")
        
        print(f"🌐 Configuring {proxy_type.upper()} proxy: {proxy_url}")
        
        # Create session
        session = requests.Session()
        
        # Configure proxy
        if proxy_type == 'http':
            session.proxies = {
                'http': proxy_url,
                'https': proxy_url  # Use same proxy for HTTPS unless specifically configured
            }
        elif proxy_type == 'https':
            session.proxies = {
                'https': proxy_url
            }
        elif proxy_type == 'socks':
            session.proxies = {
                'http': proxy_url,
                'https': proxy_url
            }
        
        # Override with HTTPS-specific proxy if available
        https_proxy = os.getenv('HTTPS_PROXY') or os.getenv('https_proxy')
        if https_proxy and proxy_type == 'http':
            session.proxies['https'] = https_proxy
            print(f"   HTTPS Proxy: {https_proxy}")
        
        print("✅ Normal proxy configured successfully")
        return session
    
    def _configure_no_proxy(self) -> requests.Session:
        """Configure session with no proxy (direct connection)"""
        print("🌐 Configuring direct connection (no proxy)")
        
        session = requests.Session()
        
        # Explicitly set no proxy
        session.proxies = {
            'http': None,
            'https': None
        }
        
        print("✅ Direct connection configured successfully")
        return session
    
    def get_session(self) -> requests.Session:
        """Get the configured session"""
        if self.session is None:
            raise RuntimeError("Session not configured. Call configure_proxy() first.")
        return self.session
    
    def test_connection(self, test_url: str = "https://httpbin.org/ip") -> bool:
        """Test the proxy connection"""
        try:
            print(f"🧪 Testing connection to {test_url}")
            response = self.get_session().get(test_url, timeout=10)
            
            if response.status_code == 200:
                print("✅ Connection test successful")
                try:
                    ip_info = response.json()
                    print(f"   Your IP: {ip_info.get('origin', 'Unknown')}")
                except Exception:
                    pass
                return True
            else:
                print(f"❌ Connection test failed: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Connection test failed: {str(e)}")
            return False

def create_proxy_session(proxy_type: Optional[str] = None,
                        proxy_url: Optional[str] = None,
                        pac_url: Optional[str] = None,
                        test_connection: bool = True) -> requests.Session:
    """
    Convenience function to create a proxy-configured session
    
    Args:
        proxy_type: Type of proxy ('pac', 'http', 'https', 'socks', 'none', or None for auto-detect)
        proxy_url: URL for normal proxy
        pac_url: URL for PAC file
        test_connection: Whether to test the connection after configuration
    
    Returns:
        requests.Session configured with appropriate proxy settings
    """
    config = ProxyConfig()
    session = config.configure_proxy(proxy_type, proxy_url, pac_url)
    
    if test_connection:
        config.session = session
        config.test_connection()
    
    return session

# Global session instance for backward compatibility
_global_session = None

def get_global_session() -> requests.Session:
    """Get or create the global session"""
    global _global_session
    if _global_session is None:
        _global_session = create_proxy_session()
    return _global_session

def set_global_session(session: requests.Session):
    """Set the global session"""
    global _global_session
    _global_session = session
