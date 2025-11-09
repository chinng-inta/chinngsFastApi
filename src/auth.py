import os
import httpx
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

# Workers MCP ServerのURL
WORKERS_MCP_URL = os.getenv("WORKERS_MCP_URL")

# HTTPBearerスキーム
security = HTTPBearer()

async def verify_workers_jwt(token: str) -> dict:
    """
    Workers MCP Serverが発行したJWTを検証する
    
    Args:
        token: Bearer トークン（"Bearer "プレフィックスなし）
    
    Returns:
        dict: 検証結果 {"valid": True, "userId": "...", "email": "..."}
    
    Raises:
        HTTPException: JWT検証失敗時
    """
    if not WORKERS_MCP_URL:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="WORKERS_MCP_URL environment variable is not set"
        )
    
    verify_url = f"{WORKERS_MCP_URL}/verify-jwt"
    
    try:
        print(f"[AUTH] JWT検証開始: {verify_url}")
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                verify_url,
                headers={"Authorization": f"Bearer {token}"}
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("valid"):
                    print(f"[AUTH] JWT検証成功: userId={result.get('userId')}, email={result.get('email')}")
                    return result
                else:
                    error_msg = result.get('error', 'Unknown error')
                    print(f"[AUTH] JWT無効: {error_msg}")
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Invalid JWT: {error_msg}"
                    )
            elif response.status_code == 401:
                print(f"[AUTH] 認証ヘッダーが無効または欠落")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authorization header missing or invalid"
                )
            elif response.status_code == 403:
                print(f"[AUTH] JWT検証失敗")
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="JWT verification failed"
                )
            else:
                print(f"[AUTH] JWT検証サービスエラー: status={response.status_code}")
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"JWT verification service returned status {response.status_code}"
                )
    
    except httpx.TimeoutException:
        print(f"[AUTH] JWT検証タイムアウト")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="JWT verification service timeout"
        )
    except httpx.RequestError as e:
        print(f"[AUTH] JWT検証サービス接続失敗: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to connect to JWT verification service: {str(e)}"
        )

async def authenticate_workers_jwt(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """
    FastAPIの依存性注入で使用する認証関数
    
    Args:
        credentials: HTTPBearerスキームから抽出された認証情報
    
    Returns:
        dict: ユーザー情報 {"userId": "...", "email": "..."}
    
    Raises:
        HTTPException: 認証失敗時
    """
    token = credentials.credentials
    result = await verify_workers_jwt(token)
    
    return {
        "userId": result.get("userId"),
        "email": result.get("email")
    }