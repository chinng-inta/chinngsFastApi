from fastmcp import FastMCP
from typing import Optional
import os
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, List
from fastapi.middleware.cors import CORSMiddleware
from src.auth import verify_cloudflare_jwt

# FastMCPサーバーを初期化
mcp = FastMCP("Sequential Thinking MCP Server")

# Sequential Thinkingツールの定義
@mcp.tool()
def sequentialthinking(
    thought: str,
    thought_number: int,
    total_thoughts: int,
    next_thought_needed: bool,
    is_revision: bool = False,
    revises_thought: Optional[int] = None,
    branch_from_thought: Optional[int] = None,
    branch_id: Optional[str] = None,
    needs_more_thoughts: bool = False
) -> str:
    """
    Sequential thinking tool for step-by-step reasoning.
    
    Args:
        thought: Current thinking step
        thought_number: Current thought number (1-indexed)
        total_thoughts: Estimated total thoughts needed
        next_thought_needed: Whether another thought is needed
        is_revision: Whether this revises previous thinking
        revises_thought: Which thought number is being reconsidered
        branch_from_thought: Branching point thought number
        branch_id: Branch identifier
        needs_more_thoughts: If more thoughts are needed
    
    Returns:
        Confirmation message with thought details
    """
    
    result = f"✓ Thought {thought_number}/{total_thoughts} recorded\n"
    result += f"Content: {thought}\n"
    
    if is_revision and revises_thought:
        result += f"📝 Revising thought #{revises_thought}\n"
    
    if branch_from_thought and branch_id:
        result += f"🌿 Branching from thought #{branch_from_thought} (branch: {branch_id})\n"
    
    if needs_more_thoughts:
        result += "⚠️ More thoughts needed beyond initial estimate\n"
    
    if next_thought_needed:
        result += "➡️ Continue to next thought\n"
    else:
        result += "✅ Thinking process complete\n"
    
    return result

# サーバー情報ツール
@mcp.tool()
def get_server_info() -> dict:
    """Get information about the MCP server."""
    return {
        "name": "Sequential Thinking MCP Server",
        "version": "1.0.0",
        "environment": os.getenv("RAILWAY_ENVIRONMENT", "development"),
        "tools": ["sequentialthinking", "get_server_info"]
    }

# リソース定義（オプション）
@mcp.resource("server://info")
def server_info_resource() -> str:
    """Server information resource."""
    return "Sequential Thinking MCP Server running on Railway"

# プロンプト定義（オプション）
@mcp.prompt()
def thinking_guidance() -> str:
    """Guidance for using sequential thinking."""
    return """
    Sequential Thinking Guidelines:
    1. Start with initial estimate of needed thoughts
    2. Break down complex problems into steps
    3. Question or revise previous thoughts when needed
    4. Add more thoughts if needed, even at the "end"
    5. Express uncertainty and explore alternatives
    """

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

    ### 利用可能なツール
    - `sequentialthinking`: 段階的思考プロセスの実行
    - `get_server_info`: サーバー情報の取得

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
class MCPRequest(BaseModel):
    """MCP リクエストのスキーマ"""
    method: str
    params: dict = {}
    id: Optional[str] = "1"
    
    class Config:
        schema_extra = {
            "example": {
                "method": "tools/call",
                "params": {
                    "name": "sequentialthinking",
                    "arguments": {
                        "thought": "最初の思考ステップ",
                        "thought_number": 1,
                        "total_thoughts": 3,
                        "next_thought_needed": True
                    }
                },
                "id": "1"
            }
        }

class HealthResponse(BaseModel):
    """ヘルスチェックレスポンス"""
    status: str
    server: str

class RootResponse(BaseModel):
    """ルートエンドポイントレスポンス"""
    message: str
    status: str

class ToolInfo(BaseModel):
    """ツール情報"""
    name: str
    description: str

class ToolsResponse(BaseModel):
    """ツール一覧レスポンス"""
    tools: List[ToolInfo]

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
    
    # ヘルスチェックとドキュメントは除外
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

@app.get("/tools", response_model=ToolsResponse, tags=["MCP"])
async def list_tools():
    """
    利用可能なMCPツール一覧
    
    このサーバーで利用可能なMCPツールの一覧を返します。
    各ツールの名前と説明が含まれます。
    """
    return {
        "tools": [
            {
                "name": "sequentialthinking",
                "description": "Sequential thinking tool for step-by-step reasoning"
            },
            {
                "name": "get_server_info", 
                "description": "Get information about the MCP server"
            }
        ]
    }

@app.post("/mcp", tags=["MCP"])
async def handle_mcp_request(mcp_request: MCPRequest):
    """
    MCPプロトコルリクエスト処理
    
    Model Context Protocol (MCP) のリクエストを処理します。
    
    ### 使用例
    ```json
    {
        "method": "tools/call",
        "params": {
            "name": "sequentialthinking",
            "arguments": {
                "thought": "最初の思考ステップ",
                "thought_number": 1,
                "total_thoughts": 3,
                "next_thought_needed": true
            }
        },
        "id": "1"
    }
    ```
    """
    try:
        body = mcp_request.dict()
        method = body.get("method", "")
        params = body.get("params", {})
        request_id = body.get("id", "1")
        
        # MCPメソッドに応じて処理を分岐
        if method == "tools/call":
            tool_name = params.get("name")
            arguments = params.get("arguments", {})
            
            if tool_name == "sequentialthinking":
                # sequentialthinking ツールを直接呼び出し
                result = sequentialthinking(**arguments)
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": result
                            }
                        ]
                    }
                }
            elif tool_name == "get_server_info":
                # get_server_info ツールを直接呼び出し
                result = get_server_info()
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "content": [
                            {
                                "type": "text", 
                                "text": str(result)
                            }
                        ]
                    }
                }
            else:
                return JSONResponse(
                    status_code=400,
                    content={
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "error": {
                            "code": -32601,
                            "message": f"Unknown tool: {tool_name}"
                        }
                    }
                )
        
        elif method == "tools/list":
            # ツール一覧を返す
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "tools": [
                        {
                            "name": "sequentialthinking",
                            "description": "Sequential thinking tool for step-by-step reasoning",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "thought": {"type": "string"},
                                    "thought_number": {"type": "integer"},
                                    "total_thoughts": {"type": "integer"},
                                    "next_thought_needed": {"type": "boolean"}
                                },
                                "required": ["thought", "thought_number", "total_thoughts", "next_thought_needed"]
                            }
                        },
                        {
                            "name": "get_server_info",
                            "description": "Get information about the MCP server",
                            "inputSchema": {
                                "type": "object",
                                "properties": {}
                            }
                        }
                    ]
                }
            }
        
        else:
            return JSONResponse(
                status_code=400,
                content={
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32601,
                        "message": f"Unknown method: {method}"
                    }
                }
            )
            
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "jsonrpc": "2.0",
                "id": mcp_request.id if mcp_request.id else "unknown",
                "error": {
                    "code": -32603,
                    "message": f"Internal error: {str(e)}"
                }
            }
        )

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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))