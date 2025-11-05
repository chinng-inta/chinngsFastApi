import jwt
import httpx
from typing import Optional
from fastapi import Request, HTTPException
from functools import wraps
import os
import socket

CF_TEAM_DOMAIN = os.getenv("CF_TEAM_DOMAIN")
CF_AUD_TAG = os.getenv("CF_AUD_TAG")

# Cloudflareの公開鍵キャッシュ
_cf_public_keys = None

async def test_dns_resolution(domain: str) -> bool:
    """DNS解決をテスト"""
    try:
        # ドメインからホスト名を抽出
        hostname = domain.replace("https://", "").replace("http://", "")
        socket.gethostbyname(hostname)
        print(f"DNS解決成功: {hostname}")
        return True
    except socket.gaierror as e:
        print(f"DNS解決失敗: {hostname} - {e}")
        return False

async def get_cloudflare_public_keys():
    """Cloudflare Accessの公開鍵を取得（キャッシュ付き）"""
    global _cf_public_keys
    
    if not CF_TEAM_DOMAIN:
        print("警告: CF_TEAM_DOMAIN環境変数が設定されていません")
        return {"keys": []}
    
    if _cf_public_keys is None:
        certs_url = f"https://{CF_TEAM_DOMAIN}/cdn-cgi/access/certs"
        
        # DNS解決をテスト
        dns_ok = await test_dns_resolution(CF_TEAM_DOMAIN)
        if not dns_ok:
            print(f"警告: {CF_TEAM_DOMAIN}のDNS解決に失敗しました")
            return {"keys": []}  # 空のキーを返して処理を継続
        
        try:
            print(f"証明書取得を試行: {certs_url}")
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(certs_url)
                response.raise_for_status()
                _cf_public_keys = response.json()
                print(f"証明書取得成功: {len(_cf_public_keys.get('keys', []))}個のキー")
        except (httpx.RequestError, httpx.HTTPStatusError) as e:
            print(f"Cloudflare証明書取得エラー: {e}")
            print(f"URL: {certs_url}")
            # エラーの場合も空のキーを返して処理を継続
            _cf_public_keys = {"keys": []}
    
    return _cf_public_keys

async def verify_cloudflare_jwt(jwt_token: str) -> bool:
    """Cloudflare Access JWTを検証"""
    # 環境変数が設定されていない場合はスキップ
    if not CF_TEAM_DOMAIN or not CF_AUD_TAG:
        print("警告: CF_TEAM_DOMAIN または CF_AUD_TAG が設定されていません。認証をスキップします。")
        return False
    
    try:
        print(f"JWT検証開始 - Domain: {CF_TEAM_DOMAIN}, AUD: {CF_AUD_TAG}")
        certs = await get_cloudflare_public_keys()
        
        if not certs.get('keys'):
            print("警告: 証明書キーが取得できませんでした。認証をスキップします。")
            return False
        
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
                
                print("JWT検証成功")
                return True
                
            except jwt.InvalidTokenError as e:
                print(f"JWT検証失敗（次のキーを試行）: {e}")
                continue
        
        print("すべてのキーでJWT検証に失敗")
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