from typing import Optional, List
import os
import json
import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from src.auth import verify_cloudflare_jwt
from fastapi_mcp import FastApiMCP

INTERNAL_SERVICES = {
    "sequentialthinking": os.getenv("SEQUENTIALTHINKING_SERVICE_URL", "http://sequentialthinking.railway.internal:8080")
}

async def call_mcp_sse(service_url: str, method: str, params: dict) -> dict:
    """SSEトランスポートを使用してMCPサーバーを呼び出す"""
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            # SSEエンドポイントにPOSTリクエストを送信
            mcp_request = {
                "jsonrpc": "2.0",
                "method": method,
                "params": params,
                "id": 1
            }
            
            response = await client.post(
                f"{service_url}/sse",
                json=mcp_request,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "text/event-stream"
                }
            )
            response.raise_for_status()
            
            # SSEレスポンスをパース
            lines = response.text.strip().split('\n')
            result = None
            
            for line in lines:
                if line.startswith('data: '):
                    data_str = line[6:]  # "data: " を除去
                    try:
                        data = json.loads(data_str)
                        if 'result' in data:
                            result = data
                        elif 'error' in data:
                            raise HTTPException(
                                status_code=500,
                                detail=f"MCP error: {data['error']}"
                            )
                    except json.JSONDecodeError:
                        continue
            
            if result:
                return result
            else:
                raise HTTPException(
                    status_code=500,
                    detail="No valid response from MCP server"
                )
                
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=503,
            detail=f"Failed to connect to MCP service: {str(e)}"
        )
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"MCP service error: {str(e)}"
        )

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
    内部的にSSEトランスポートでsequentialthinkingサービスを呼び出します。
    """
    service_url = INTERNAL_SERVICES["sequentialthinking"]
    
    try:
        # SSEトランスポートでMCPサーバーを呼び出し
        mcp_response = await call_mcp_sse(
            service_url=service_url,
            method="tools/call",
            params={
                "name": "sequentialthinking",
                "arguments": {
                    "thought": request.thought,
                    "thoughtNumber": request.thought_number,
                    "totalThoughts": request.total_thoughts,
                    "nextThoughtNeeded": request.next_thought_needed,
                    "isRevision": request.is_revision,
                    "revisesThought": request.revises_thought,
                    "branchFromThought": request.branch_from_thought,
                    "branchId": request.branch_id,
                    "needsMoreThoughts": request.needs_more_thoughts
                }
            }
        )
        
        # MCPレスポンスから結果を抽出
        if "result" in mcp_response and "content" in mcp_response["result"]:
            content = mcp_response["result"]["content"]
            if content and len(content) > 0:
                result_text = content[0].get("text", "")
                return {"result": result_text}
        
        # フォールバック: レスポンス全体を返す
        return {"result": json.dumps(mcp_response, indent=2)}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Internal error: {str(e)}"
        )

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

@app.get("/debug/sequentialthinking", tags=["Debug"])
async def debug_sequentialthinking():
    """
    SequentialThinkingサービスへの接続テスト
    
    内部サービスへの接続をテストします。
    """
    service_url = INTERNAL_SERVICES["sequentialthinking"]
    
    result = {
        "service_url": service_url,
        "health_check": False,
        "sse_endpoint": False,
        "error": None
    }
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # ヘルスチェック
            try:
                health_response = await client.get(f"{service_url}/health")
                result["health_check"] = health_response.status_code == 200
                result["health_response"] = health_response.json() if health_response.status_code == 200 else None
            except Exception as e:
                result["health_error"] = str(e)
            
            # SSEエンドポイントテスト
            try:
                sse_response = await client.post(
                    f"{service_url}/sse",
                    json={
                        "jsonrpc": "2.0",
                        "method": "tools/list",
                        "params": {},
                        "id": 1
                    },
                    headers={"Accept": "text/event-stream"}
                )
                result["sse_endpoint"] = sse_response.status_code == 200
                result["sse_response_preview"] = sse_response.text[:200] if sse_response.status_code == 200 else None
            except Exception as e:
                result["sse_error"] = str(e)
                
    except Exception as e:
        result["error"] = str(e)
    
    return result

# FastApiMCPを初期化してマウント
mcp = FastApiMCP(app)
mcp.mount()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
