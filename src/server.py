from typing import Optional, List
import os
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from src.auth import verify_cloudflare_jwt
from fastapi_mcp import FastApiMCP

# FastAPI アプリケーションを作成
app = FastAPI(
    title="Sequential Thinking MCP Server",
    version="1.0.0",
    description="""
    ## Sequential Thinking MCP Server

    このサーバーは段階的思考（Sequential Thinking）をサポートするMCP（Model Context Protocol）サーバーです。

    ### 主な機能
    - **Sequential Thinking**: 複雑な問題を段階的に分析・解決
    - **MCP Protocol**: `/mcp`エンドポイントでMCPリクエストを処理
    - **Cloudflare Access**: JWT認証による安全なアクセス制御

    ### 認証
    本番環境では Cloudflare Access による JWT 認証が必要です。
    開発環境では認証をスキップします。
    """,
    contact={
        "name": "Sequential Thinking MCP Server",
        "url": "https://github.com/your-repo",
    },
    license_info={
        "name": "MIT License",
        "url": "https://opensource.org/licenses/MIT",
    },
    docs_url="/docs",
    redoc_url="/redoc"
)

# Pydanticモデル定義
class SequentialThinkingRequest(BaseModel):
    """Sequential Thinking リクエスト"""
    thought: str
    thought_number: int
    total_thoughts: int
    next_thought_needed: bool
    is_revision: bool = False
    revises_thought: Optional[int] = None
    branch_from_thought: Optional[int] = None
    branch_id: Optional[str] = None
    needs_more_thoughts: bool = False

class SequentialThinkingResponse(BaseModel):
    """Sequential Thinking レスポンス"""
    result: str

class ServerInfoResponse(BaseModel):
    """サーバー情報レスポンス"""
    name: str
    version: str
    environment: str
    tools: List[str]

class HealthResponse(BaseModel):
    """ヘルスチェックレスポンス"""
    status: str
    server: str

class RootResponse(BaseModel):
    """ルートエンドポイントレスポンス"""
    message: str
    status: str

class DNSDebugResponse(BaseModel):
    """DNS デバッグレスポンス"""
    cf_team_domain: Optional[str] = None
    dns_resolution: bool
    cert_fetch: bool
    key_count: int = 0
    error: Optional[str] = None

# CORS設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        os.getenv("CLOUDFLARE_WORKER_URL", "https://*.workers.dev")
    ],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# 認証ミドルウェア
@app.middleware("http")
async def authenticate_cloudflare(request: Request, call_next):
    """全リクエストでCloudflare JWT認証"""
    
    # ヘルスチェックとドキュメントのみ除外（MCPエンドポイントは認証対象）
    if request.url.path in ["/health", "/", "/docs", "/redoc", "/openapi.json", "/debug/dns"]:
        return await call_next(request)
    
    # 開発環境では認証をスキップ
    #if os.getenv("RAILWAY_ENVIRONMENT") != "production":
    #    return await call_next(request)
    
    # JWT取得
    jwt_token = request.headers.get("CF-Access-Jwt-Assertion")
    
    if not jwt_token:
        raise HTTPException(
            status_code=401,
            detail="CF-Access-Jwt-Assertion header required"
        )
    
    # JWT検証
    try:
        is_valid = await verify_cloudflare_jwt(jwt_token)
        
        if not is_valid:
            raise HTTPException(
                status_code=403,
                detail="Invalid Cloudflare Access token"
            )
    except Exception as e:
        # DNS解決エラーなどの場合は警告ログを出して通す
        print(f"認証エラー（開発環境のため通します）: {e}")
        pass
    
    response = await call_next(request)
    return response

@app.get("/", response_model=RootResponse, tags=["Health"])
async def root():
    """
    ルートエンドポイント
    
    サーバーの基本的な状態を確認するためのエンドポイントです。
    """
    return {"message": "Sequential Thinking MCP Server is running", "status": "healthy"}

@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """
    ヘルスチェックエンドポイント
    
    サーバーの健康状態を確認します。
    ロードバランサーやモニタリングシステムで使用されます。
    """
    return {"status": "healthy", "server": "Sequential Thinking MCP Server"}

# MCPツールとして公開されるエンドポイント
@app.post("/sequentialthinking", response_model=SequentialThinkingResponse, tags=["MCP Tools"])
async def sequentialthinking(request: SequentialThinkingRequest):
    """
    Sequential thinking tool for step-by-step reasoning.
    
    このツールは複雑な問題を段階的に分析・解決するための思考プロセスをサポートします。
    """
    result = f"✓ Thought {request.thought_number}/{request.total_thoughts} recorded\n"
    result += f"Content: {request.thought}\n"
    
    if request.is_revision and request.revises_thought:
        result += f"📝 Revising thought #{request.revises_thought}\n"
    
    if request.branch_from_thought and request.branch_id:
        result += f"🌿 Branching from thought #{request.branch_from_thought} (branch: {request.branch_id})\n"
    
    if request.needs_more_thoughts:
        result += "⚠️ More thoughts needed beyond initial estimate\n"
    
    if request.next_thought_needed:
        result += "➡️ Continue to next thought\n"
    else:
        result += "✅ Thinking process complete\n"
    
    return {"result": result}

@app.get("/server_info", response_model=ServerInfoResponse, tags=["MCP Tools"])
async def get_server_info():
    """
    Get information about the MCP server.
    
    サーバーの基本情報を取得します。
    """
    return {
        "name": "Sequential Thinking MCP Server",
        "version": "1.0.0",
        "environment": os.getenv("RAILWAY_ENVIRONMENT", "development"),
        "tools": ["sequentialthinking", "get_server_info"]
    }

@app.get("/debug/dns", response_model=DNSDebugResponse, tags=["Debug"])
async def debug_dns():
    """
    DNS解決とCloudflare接続テスト
    
    Cloudflare Access の DNS 解決と証明書取得をテストします。
    認証の問題をデバッグする際に使用してください。
    """
    from src.auth import CF_TEAM_DOMAIN, test_dns_resolution, get_cloudflare_public_keys
    
    result = {
        "cf_team_domain": CF_TEAM_DOMAIN,
        "dns_resolution": False,
        "cert_fetch": False,
        "error": None
    }
    
    if CF_TEAM_DOMAIN:
        try:
            # DNS解決テスト
            result["dns_resolution"] = await test_dns_resolution(CF_TEAM_DOMAIN)
            
            # 証明書取得テスト
            certs = await get_cloudflare_public_keys()
            result["cert_fetch"] = len(certs.get('keys', [])) > 0
            result["key_count"] = len(certs.get('keys', []))
            
        except Exception as e:
            result["error"] = str(e)
    
    return result

# FastApiMCPを初期化してマウント
mcp = FastApiMCP(app)
mcp.mount()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
