import boto3
import os
from bedrock_agentcore_starter_toolkit.operations.gateway.client import GatewayClient
from dotenv import load_dotenv, set_key

def create_gateway_with_lambda(cognito_config, gateway_role_arn, lambda_arn):
    """
    Cognito認証付きGatewayを作成し、Lambda関数をMCPツール化
    """
    
    # Gateway clientの初期化
    gateway_client = GatewayClient(region_name="us-west-2")
    
    # 1. Gatewayの作成（Cognito認証設定）
    print("🚀 Gatewayを作成中...")
    authorizer_config = {
        "customJWTAuthorizer": {
            "discoveryUrl": cognito_config["discovery_url"],
            "allowedClients": [cognito_config["client_id"]]
        }
    }
    
    gateway_response = gateway_client.create_mcp_gateway(
        name="order-management-gateway-sample",
        role_arn=gateway_role_arn,
        authorizer_config=authorizer_config,
        enable_semantic_search=True 
    )
    
    # gateway_responseは辞書なので、標準キーでアクセス
    gateway_id = gateway_response.get('gatewayId')
    gateway_url = gateway_response.get('gatewayUrl')
    if not gateway_id or not gateway_url:
        raise RuntimeError(f"Unexpected create_mcp_gateway response keys: {list(gateway_response.keys())}")
    print(f"✅ Gateway作成完了！")
    print(f"   Gateway ID: {gateway_id}")
    
    # 2. Lambda関数をターゲットとして登録
    print("\n🔧 Lambda関数をMCPツールとして登録中...")
    
    # ツールスキーマの定義
    tool_schemas = [
        {
            "name": "get_order_tool",
            "description": "注文情報を取得します",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "orderId": {
                        "type": "string",
                        "description": "注文ID"
                    }
                },
                "required": ["orderId"]
            }
        },
        {
            "name": "update_order_tool",
            "description": "注文情報を更新します",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "orderId": {
                        "type": "string",
                        "description": "注文ID"
                    }
                },
                "required": ["orderId"]
            }
        }
    ]
    
    # ターゲット設定
    target_config = {
        "mcp": {
            "lambda": {
                "lambdaArn": lambda_arn,
                "toolSchema": {
                    "inlinePayload": tool_schemas
                }
            }
        }
    }
    
    # 認証情報プロバイダー（Lambda呼び出しにはGatewayのIAMロールを使用）
    credential_config = [
        {
            "credentialProviderType": "GATEWAY_IAM_ROLE"
        }
    ]
    
    # 低レベルAPIでターゲットを作成
    bedrock_client = boto3.client('bedrock-agentcore-control', region_name='us-west-2')
    target_response = bedrock_client.create_gateway_target(
        gatewayIdentifier=gateway_id,
        name="order-lambda-target",
        description="注文管理Lambda関数",
        targetConfiguration=target_config,
        credentialProviderConfigurations=credential_config
    )
    
    print(f"✅ Lambda MCPツール登録完了！")
    print(f"   Target ID: {target_response['targetId']}")
    
    # .envファイルに結果を保存
    set_key(".env", "GATEWAY_ID", gateway_id)
    set_key(".env", "GATEWAY_URL", gateway_url)
    print(f"\n✅ Gateway情報を.envファイルに保存しました！")
    
    return {
        "gateway_id": gateway_id,
        "gateway_url": gateway_url,
        "target_id": target_response['targetId']
    }

if __name__ == "__main__":
    # .envファイルから設定を読み込み
    load_dotenv()
    
    # Cognito設定を.envから取得
    cognito_config = {
        "discovery_url": os.environ.get("COGNITO_DISCOVERY_URL"),
        "client_id": os.environ.get("M2M_CLIENT_ID"),
        "client_secret": os.environ.get("M2M_CLIENT_SECRET")
    }
    
    # IAMロールとLambda ARNも.envから取得
    gateway_role_arn = os.environ.get("GATEWAY_ROLE_ARN")
    lambda_arn = os.environ.get("LAMBDA_ARN")
    
    # 必須項目のチェック
    if not all([cognito_config["discovery_url"], cognito_config["client_id"], 
                cognito_config["client_secret"], gateway_role_arn, lambda_arn]):
        print("❌ .envファイルに必要な設定が不足しています")
        print("   以下の項目を確認してください:")
        print("   - COGNITO_DISCOVERY_URL, M2M_CLIENT_ID, M2M_CLIENT_SECRET")
        print("   - GATEWAY_ROLE_ARN, LAMBDA_ARN")
        exit(1)
    
    gateway_info = create_gateway_with_lambda(cognito_config, gateway_role_arn, lambda_arn)