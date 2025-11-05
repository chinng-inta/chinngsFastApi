import jwt
import httpx
from typing import Optional
from fastapi import Request, HTTPException
from functools import wraps
import os

CF_TEAM_DOMAIN = os.getenv("CF_TEAM_DOMAIN", "your-team.cloudflareaccess.com")
CF_AUD_TAG = os.getenv("CF_AUD_TAG", "")

# Cloudflareの公開鍵キャッシュ
_cf_public_keys = None

async def get_cloudflare_public_keys():
    """Cloudflare Accessの公開鍵を取得（キャッシュ付き）"""
    global _cf_public_keys
    
    if _cf_public_keys is None:
        certs_url = f"https://{CF_TEAM_DOMAIN}/cdn-cgi/access/certs"
        async with httpx.AsyncClient() as client:
            response = await client.get(certs_url)
            response.raise_for_status()
            _cf_public_keys = response.json()
    
    return _cf_public_keys

async def verify_cloudflare_jwt(jwt_token: str) -> bool:
    """Cloudflare Access JWTを検証"""
    try:
        certs = await get_cloudflare_public_keys()
        
        for cert_dict in certs.get('keys', []):
            try:
                # JWTデコード＆検証
                decoded = jwt.decode(
                    jwt_token,
                    key=jwt.algorithms.RSAAlgorithm.from_jwk(cert_dict),
                    algorithms=['RS256'],
                    audience=CF_AUD_TAG,
                    options={
                        "verify_signature": True,
                        "verify_exp": True,
                        "verify_aud": True
                    }
                )
                
                # issuerの検証
                expected_iss = f"https://{CF_TEAM_DOMAIN}"
                if decoded.get('iss') != expected_iss:
                    continue
                
                return True
                
            except jwt.InvalidTokenError:
                continue
        
        return False
        
    except Exception as e:
        print(f"JWT検証エラー: {e}")
        return False

def require_cloudflare_auth(func):
    """Cloudflare認証が必要なエンドポイントのデコレーター"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        # Requestオブジェクトを取得
        request = None
        for arg in args:
            if isinstance(arg, Request):
                request = arg
                break
        
        if not request:
            raise HTTPException(status_code=500, detail="Request object not found")
        
        # JWT取得
        jwt_token = request.headers.get("CF-Access-Jwt-Assertion")
        
        if not jwt_token:
            raise HTTPException(
                status_code=401, 
                detail="CF-Access-Jwt-Assertion header required"
            )
        
        # JWT検証
        is_valid = await verify_cloudflare_jwt(jwt_token)
        
        if not is_valid:
            raise HTTPException(
                status_code=403, 
                detail="Invalid Cloudflare Access token"
            )
        
        return await func(*args, **kwargs)
    
    return wrapper