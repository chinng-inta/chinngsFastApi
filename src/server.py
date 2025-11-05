from fastmcp import FastMCP
from typing import Optional
import os
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

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
app = FastAPI(title="Sequential Thinking MCP Server", version="1.0.0")

@app.get("/")
async def root():
    """Root endpoint for health check."""
    return {"message": "Sequential Thinking MCP Server is running", "status": "healthy"}

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "server": "Sequential Thinking MCP Server"}

@app.get("/tools")
async def list_tools():
    """List available MCP tools."""
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

@app.post("/mcp")
async def handle_mcp_request(request: Request):
    """Handle MCP protocol requests."""
    try:
        body = await request.json()
        # MCPリクエストを処理
        response = await mcp.handle_request(body)
        return response
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": f"MCP request failed: {str(e)}"}
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))