from typing import Optional, List
import os
import json
import httpx
from fastapi import FastAPI, Request, HTTPException, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from src.auth import authenticate_workers_jwt
from fastapi_mcp import FastApiMCP

INTERNAL_SERVICES = {
    "sequentialthinking": {
        "url": os.getenv("SEQUENTIALTHINKING_SERVICE_URL", "http://sequentialthinking.railway.internal:8080"),
        "method": "tools/list"
    },
    "server-memory": {
        "url": os.getenv("SERVER_MEMORY_SERVICE_URL", "http://server-memory.railway.internal:8080"),
        "method": "tools/list"
    }
}

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
    thoughtNumber: int
    totalThoughts: int
    nextThoughtNeeded: bool
    isRevision: Optional[bool] = False
    revisesThought: Optional[int] = None
    branchFromThought: Optional[int] = None
    branchId: Optional[str] = None
    needsMoreThoughts: bool = False

class SequentialThinkingResponse(BaseModel):
    """Sequential Thinking レスポンス"""
    result: str

class ServermemoryRequest(BaseModel):
    """server-memory リクエスト - 柔軟な構造"""
    operation: str  # 操作名（例: search_nodes, open_nodes, create_entities等）
    
    class Config:
        extra = "allow"  # 追加フィールドを許可（各操作固有のパラメータ用）

class ServermemoryResponse(BaseModel):
    """server-memory レスポンス"""
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

class ToolInfo(BaseModel):
    """ツール情報"""
    name: str
    description: Optional[str] = None
    inputSchema: dict

class ListToolsResponse(BaseModel):
    """ツールリストレスポンス"""
    tools: List[dict]

@app.exception_handler(RequestValidationError)
async def handler(request:Request, exc:RequestValidationError):
    print(exc)
    return JSONResponse(content={}, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)

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
async def authenticate_middleware(request: Request, call_next):
    """全リクエストでWorkers JWT認証"""
    
    # ヘルスチェックとドキュメントのみ除外（MCPエンドポイントは認証対象）
    if request.url.path in ["/health", "/", "/docs", "/redoc", "/openapi.json"]:
        return await call_next(request)
    
    # 開発環境では認証をスキップ（オプション）
    #if os.getenv("SKIP_AUTH") == "true":
    #    print("[AUTH] 認証スキップ（SKIP_AUTH=true）")
    #    return await call_next(request)
    
    # Authorization ヘッダーから JWT を取得
    auth_header = request.headers.get("Authorization")
    
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Authorization header with Bearer token required"
        )
    
    # JWT検証（verify_workers_jwt を直接呼び出し）
    from src.auth import verify_workers_jwt
    
    token = auth_header.replace("Bearer ", "")
    try:
        await verify_workers_jwt(token)
    except HTTPException:
        raise
    except Exception as e:
        print(f"[AUTH] 認証エラー: {e}")
        raise HTTPException(
            status_code=403,
            detail="Authentication failed"
        )
    # print(f"[DEBUG] Request: {request}")
    response = await call_next(request)
    return response

@app.get("/", response_model=RootResponse, tags=["Health"])
async def root():
    """
    ルートエンドポイント
    
    サーバーの基本的な状態を確認するためのエンドポイントです。
    """
    print(f"/")
    return {"message": "Sequential Thinking MCP Server is running", "status": "healthy"}

@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """
    ヘルスチェックエンドポイント
    
    サーバーの健康状態を確認します。
    ロードバランサーやモニタリングシステムで使用されます。
    """
    print(f"/health")
    return {"status": "healthy", "server": "Sequential Thinking MCP Server"}

@app.get("/list", response_model=ListToolsResponse, tags=["MCP Tools"])
async def list_tools():
    """
    利用可能なMCPツールのリストを取得
    
    全てのMCPサーバーで使用可能なツールとその引数の情報を取得します。
    """
    print(f"[DEBUG] /list called")
    
    all_tools = []
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        for service_name, service_config in INTERNAL_SERVICES.items():
            service_url = service_config["url"]
            
            try:
                print(f"[DEBUG] Sending GET request to {service_name} at {service_url}/api/tools")
                
                response = await client.get(f"{service_url}/api/tools")
                response.raise_for_status()
                
                print(f"[DEBUG] Response status: {response.status_code}")
                # print(f"[DEBUG] Response body: {response.text[:1000]}")
                
                # レスポンスをパース
                response_data = response.json()
                
                # レスポンス形式: { tools: [...] }
                if "tools" in response_data:
                    tools = response_data["tools"]
                    service = {service_name: tools}
                    all_tools.append(service)
                    print(f"[DEBUG] Added {len(tools)} tools from {service_name}")
                else:
                    print(f"[WARNING] Invalid response format from {service_name}")
                    
            except httpx.RequestError as e:
                print(f"[ERROR] Request error for {service_name}: {str(e)}")
                # 他のサービスの取得を続行
                continue
            except httpx.HTTPStatusError as e:
                print(f"[ERROR] HTTP error for {service_name}: {e.response.status_code} - {e.response.text}")
                # 他のサービスの取得を続行
                continue
            except Exception as e:
                print(f"[ERROR] Unexpected error for {service_name}: {str(e)}")
                # 他のサービスの取得を続行
                continue
    
    print(f"[DEBUG] Total tools collected: {len(all_tools)}")
    # print(f"[DEBUG] all tools: {all_tools}")
    return {"tools": all_tools}

# MCPツールとして公開されるエンドポイント
@app.post("/sequentialthinking", response_model=SequentialThinkingResponse, tags=["MCP Tools"])
async def sequentialthinking(request: SequentialThinkingRequest):
    """
    Sequential thinking tool for step-by-step reasoning.
    
    このツールは複雑な問題を段階的に分析・解決するための思考プロセスをサポートします。
    内部的にHTTPトランスポートでsequentialthinkingサービスを呼び出します。
    """
    service_config = INTERNAL_SERVICES["sequentialthinking"]
    service_url = service_config["url"]
    print(f"[DEBUG] /sequentialthinking called")
    # print(f"[DEBUG] Service URL: {service_url}")
    # print(f"[DEBUG] Request: {request}")
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # HTTPトランスポートでMCPリクエストを送信
            mcp_request = {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": "sequentialthinking",
                    "arguments": {
                        "thought": request.thought,
                        "thoughtNumber": request.thoughtNumber,
                        "totalThoughts": request.totalThoughts,
                        "nextThoughtNeeded": request.nextThoughtNeeded,
                        "isRevision": request.isRevision,
                        "revisesThought": request.revisesThought,
                        "branchFromThought": request.branchFromThought,
                        "branchId": request.branchId,
                        "needsMoreThoughts": request.needsMoreThoughts
                    }
                },
                "id": 1
            }
            
            #  print(f"[DEBUG] Sending MCP request: {json.dumps(mcp_request, indent=2)}")
            
            response = await client.post(
                f"{service_url}/api/tools/sequentialthinking",
                json=mcp_request["params"]["arguments"],
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            
            print(f"[DEBUG] Response status: {response.status_code}")
            # print(f"[DEBUG] Response body: {response.text[:500]}")
            
            # レスポンスから結果を抽出
            api_response = response.json()
            
            # SequentialThinkingサービスのレスポンス形式: { content: [{ type: "text", text: "..." }] }
            if "content" in api_response:
                content = api_response["content"]
                if content and len(content) > 0:
                    # print(f"[DEBUG] Content: {content}")
                    result_text = content[0].get("text", "")
                    return {"result": result_text}
            
            # フォールバック: レスポンス全体を返す
            return {"result": json.dumps(api_response, indent=2)}
            
    except httpx.RequestError as e:
        print(f"[ERROR] Request error: {str(e)}")
        raise HTTPException(
            status_code=503,
            detail=f"Failed to connect to sequentialthinking service: {str(e)}"
        )
    except httpx.HTTPStatusError as e:
        print(f"[ERROR] HTTP error: {e.response.status_code} - {e.response.text}")
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"Sequentialthinking service error: {str(e)}"
        )
    except Exception as e:
        print(f"[ERROR] Unexpected error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal error: {str(e)}"
        )

# MCPツールとして公開されるエンドポイント
@app.post("/server-memory", response_model=ServermemoryResponse, tags=["MCP Tools"])
async def server_memory_tool(request: ServermemoryRequest):
    """
    Server Memory MCP Server - Knowledge Graph operations
    
    内部的にHTTPトランスポートでserver-memoryサービスを呼び出します。
    """
    service_config = INTERNAL_SERVICES["server-memory"]
    service_url = service_config["url"]
    print(f"[DEBUG] /server-memory called")
    # print(f"[DEBUG] Service URL: {service_url}")
    # print(f"[DEBUG] Request: {request}")
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # リクエストをそのまま辞書に変換
            request_data = request.model_dump(exclude_unset=True)
            
            # server-memoryが期待する形式に変換
            # 形式: {"method": "tools/call", "arguments": {"operation": "...", ...}}
            mcp_request = {
                "method": "tools/call",
                "arguments": request_data
            }
            
            # print(f"[DEBUG] Sending MCP request: {json.dumps(mcp_request, indent=2)}")
            
            response = await client.post(
                f"{service_url}/api/tools/server-memory",
                json=mcp_request,
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            
            print(f"[DEBUG] Response status: {response.status_code}")
            # print(f"[DEBUG] Response body: {response.text[:500]}")
            
            # レスポンスから結果を抽出
            api_response = response.json()
            
            # server-memoryサービスのレスポンス形式: { content: [{ type: "text", text: "..." }] }
            if "content" in api_response:
                content = api_response["content"]
                if content and len(content) > 0:
                    # print(f"[DEBUG] Content: {content}")
                    result_text = content[0].get("text", "")
                    return {"result": result_text}
            
            # フォールバック: レスポンス全体を返す
            return {"result": json.dumps(api_response, indent=2)}
            
    except httpx.RequestError as e:
        print(f"[ERROR] Request error: {str(e)}")
        raise HTTPException(
            status_code=503,
            detail=f"Failed to connect to server-memory service: {str(e)}"
        )
    except httpx.HTTPStatusError as e:
        print(f"[ERROR] HTTP error: {e.response.status_code} - {e.response.text}")
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"server-memory service error: {str(e)}"
        )
    except Exception as e:
        print(f"[ERROR] Unexpected error: {str(e)}")
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
    print(f"/server_info")
    return {
        "name": "Sequential Thinking MCP Server",
        "version": "1.0.0",
        "environment": os.getenv("RAILWAY_ENVIRONMENT", "development"),
        "tools": ["sequentialthinking", "server-memory", "get_server_info"]
    }

# FastApiMCPを初期化してマウント
mcp = FastApiMCP(app)
mcp.mount()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
