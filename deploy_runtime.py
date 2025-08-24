from bedrock_agentcore_starter_toolkit import Runtime
import os
from dotenv import load_dotenv, set_key

def deploy_runtime():
    """
    認証なしのRuntimeをデプロイ（M2M認証はGateway呼び出し時に実行）
    """
    # .envファイルを読み込み
    load_dotenv()
    
    print("🚀 AgentCore Runtimeのデプロイを開始...")
    
    # .envファイルから環境変数を取得
    env_vars = {
        # Gateway接続情報
        "GATEWAY_URL": os.environ.get("GATEWAY_URL"),
        
        # Cognito M2M認証情報
        "COGNITO_DISCOVERY_URL": os.environ.get("COGNITO_DISCOVERY_URL"),
        "M2M_CLIENT_ID": os.environ.get("M2M_CLIENT_ID"),
        "M2M_CLIENT_SECRET": os.environ.get("M2M_CLIENT_SECRET"),
        "RESOURCE_SERVER_ID": os.environ.get("RESOURCE_SERVER_ID", "agentcore-gateway"),
        
        # AgentCore Identity設定
        "IDENTITY_PROVIDER_NAME": os.environ.get("IDENTITY_PROVIDER_NAME"),
        "GATEWAY_SCOPE": os.environ.get("GATEWAY_SCOPE")
    }
    
    # 必要な環境変数のチェック
    required_vars = ["GATEWAY_URL", "RUNTIME_ROLE_ARN", "IDENTITY_PROVIDER_NAME"]
    missing_vars = [var for var in required_vars if not os.environ.get(var)]
    
    if missing_vars:
        print(f"❌ 以下の環境変数が.envファイルに設定されていません:")
        for var in missing_vars:
            print(f"   - {var}")
        print("\n必要なスクリプトを先に実行してください:")
        if "GATEWAY_URL" in missing_vars:
            print("   - create_gateway.py")
        if "RUNTIME_ROLE_ARN" in missing_vars:
            print("   - create_iam_roles.py")
        if "IDENTITY_PROVIDER_NAME" in missing_vars:
            print("   - setup_outbound_auth.py")
        return
    
    print("✅ 環境変数チェック完了")
    
    # Runtimeの設定（認証なし）
    runtime = Runtime()
    
    response = runtime.configure(
        entrypoint="runtime_agent.py",
        execution_role=os.environ.get("RUNTIME_ROLE_ARN"),
        auto_create_ecr=True,
        requirements_file="requirements.txt",
        region="us-west-2",
        agent_name="order_management_runtime_test",
        # 認証設定なし！（Inbound Authなし）
    )
    
    print("✅ Runtime設定完了！デプロイ中...")
    
    # デプロイ実行
    launch_result = runtime.launch(env_vars=env_vars)
    
    print(f"✅ Runtimeデプロイ完了！")
    print(f"   Agent ARN: {launch_result.agent_arn}")
    print(f"   注意: このRuntimeは認証なしで動作します（開発環境用）")
    
    # Runtime ARNを.envファイルに保存
    set_key(".env", "RUNTIME_ARN", launch_result.agent_arn)
    print(f"✅ Runtime ARNを.envファイルに保存しました！")
    
    return launch_result

if __name__ == "__main__":
    deploy_runtime()