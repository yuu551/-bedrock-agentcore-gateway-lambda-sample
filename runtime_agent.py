import os
from strands import Agent
from strands.models import BedrockModel
from strands.tools.mcp import MCPClient
from mcp.client.streamable_http import streamablehttp_client
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from bedrock_agentcore.identity.auth import requires_access_token
from typing import Dict, Any

# エージェントアプリケーションの初期化
app = BedrockAgentCoreApp()

@app.entrypoint
async def order_management_agent(payload: Dict[str, Any]):
    """
    注文管理エージェント（AgentCore Identity使用）
    """
    print("📋 エージェント起動")
    print(f"受信したペイロード: {payload}")
    
    # AgentCore Identityを使用してGatewayにアクセス
    gateway_url = os.environ.get("GATEWAY_URL")
    provider_name = os.environ.get("IDENTITY_PROVIDER_NAME", "agentcore-identity-for-gateway")
    gateway_scope = os.environ.get("GATEWAY_SCOPE")  # 例: "agentcore-gateway/read agentcore-gateway/write"
    
    @requires_access_token(
        provider_name=provider_name,
        scopes=gateway_scope.split() if gateway_scope else [],
        auth_flow="M2M",
        force_authentication=False,
    )
    async def process_with_gateway(*, access_token: str) -> str:
        """
        Gatewayへのアクセストークンを取得し、MCPクライアントで処理
        """
        print(f"✅ アクセストークン取得成功")
        
        # MCPクライアントの作成（AgentCore Identity認証トークン付き）
        def create_streamable_http_transport():
            return streamablehttp_client(
                gateway_url, 
                headers={"Authorization": f"Bearer {access_token}"}
            )
        
        client = MCPClient(create_streamable_http_transport)
        print(f"✅ MCP Client初期化完了（AgentCore Identity認証）")
        
        try:
            with client:
                # ツールリストを取得
                tools = client.list_tools_sync()
                print(f"🛠️ 利用可能なツール: {[tool.tool_name for tool in tools]}")
                
                # Bedrockモデルとエージェントの初期化
                model = BedrockModel(
                    model_id="anthropic.claude-3-5-haiku-20241022-v1:0",
                    params={"max_tokens": 4096, "temperature": 0.7},
                    region="us-west-2"
                )
                
                agent = Agent(
                    model=model,
                    tools=tools,
                    system_prompt="あなたは注文管理システムのアシスタントです。注文の照会や更新を手伝います。"
                )
                print("✅ エージェント初期化完了！")
                
                # ユーザー入力を処理
                user_input = payload.get("prompt", "注文IDの123の情報を教えて")
                print(f"💬 ユーザー入力: {user_input}")
                
                # エージェントで処理（内部でGatewayのツールを呼び出す）
                response = agent(user_input)
                result = response.message['content'][0]['text']
                print(f"🤖 エージェント応答: {result}")
                return result
                
        except Exception as e:
            print(f"❌ エージェント処理エラー: {e}")
            return f"エラーが発生しました: {str(e)}"
    
    try:
        # AgentCore Identityを使用してアクセストークンを取得し、処理を実行
        return await process_with_gateway()
    except Exception as e:
        print(f"❌ 認証エラー: {e}")
        return f"認証に失敗しました: {str(e)}"

if __name__ == "__main__":
    app.run()