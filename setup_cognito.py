import boto3
import json
import os
import time
from botocore.exceptions import ClientError
from dotenv import load_dotenv, set_key

REGION = "us-west-2"
USER_POOL_NAME = "agentcore-gateway-pool"
RESOURCE_SERVER_ID = "agentcore-gateway"
RESOURCE_SERVER_NAME = "AgentCore Gateway Resource Server"
CLIENT_NAME = "agentcore-m2m-client"

# Scopeの定義
SCOPES = [
    {"ScopeName": "read", "ScopeDescription": "Read access to Gateway"},
    {"ScopeName": "write", "ScopeDescription": "Write access to Gateway"}
]

def create_cognito_m2m_setup():
    cognito = boto3.client("cognito-idp", region_name=REGION)
    
    try:
        # User Poolの作成
        pool_response = cognito.create_user_pool(
            PoolName=USER_POOL_NAME,
            Policies={
                'PasswordPolicy': {
                    'MinimumLength': 8,
                    'RequireUppercase': True,
                    'RequireLowercase': True,
                    'RequireNumbers': True,
                    'RequireSymbols': True
                }
            }
        )
        pool_id = pool_response['UserPool']['Id']
        print(f"✅ User Pool作成完了: {pool_id}")
        
        # Resource Serverの作成
        resource_response = cognito.create_resource_server(
            UserPoolId=pool_id,
            Identifier=RESOURCE_SERVER_ID,
            Name=RESOURCE_SERVER_NAME,
            Scopes=SCOPES
        )
        print(f"✅ Resource Server作成完了: {RESOURCE_SERVER_ID}")
        
        # User Pool Domain作成（OAuth2 token endpointに必須）
        domain_name = f"agentcore-gateway-auth-{int(time.time())}"
        try:
            domain_response = cognito.create_user_pool_domain(
                Domain=domain_name,
                UserPoolId=pool_id
            )
            print(f"✅ User Pool Domain作成完了: {domain_name}")
        except ClientError as e:
            if e.response['Error']['Code'] == 'InvalidParameterException' and 'already exists' in str(e):
                # ドメイン名重複時は別の名前で再試行
                domain_name = f"agentcore-gateway-auth-{int(time.time())}-retry"
                domain_response = cognito.create_user_pool_domain(
                    Domain=domain_name,
                    UserPoolId=pool_id
                )
                print(f"✅ User Pool Domain作成完了（リトライ）: {domain_name}")
            else:
                raise
        
        # App Client作成（M2M用）
        client_response = cognito.create_user_pool_client(
            UserPoolId=pool_id,
            ClientName=CLIENT_NAME,
            GenerateSecret=True,  # M2M認証には必須
            AllowedOAuthFlows=['client_credentials'],  # M2M認証フロー
            AllowedOAuthScopes=[
                f"{RESOURCE_SERVER_ID}/read",
                f"{RESOURCE_SERVER_ID}/write"
            ],
            AllowedOAuthFlowsUserPoolClient=True
        )
        client_id = client_response['UserPoolClient']['ClientId']
        client_secret = client_response['UserPoolClient']['ClientSecret']
        
        # Discovery URLの生成
        discovery_url = f"https://cognito-idp.{REGION}.amazonaws.com/{pool_id}/.well-known/openid-configuration"
        
        print("\n🎉 Cognito M2M設定完了！")
        print(f"Pool ID: {pool_id}")
        print(f"Client ID: {client_id}")
        print(f"Client Secret: {client_secret}")
        print(f"Discovery URL: {discovery_url}")
        
        # .envファイルに設定を自動保存
        env_file = ".env"
        
        # .env.exampleからコピー（初回のみ）
        if not os.path.exists(env_file) and os.path.exists(".env.example"):
            with open(".env.example", "r") as src, open(env_file, "w") as dst:
                dst.write(src.read())
        
        # 環境変数を更新
        set_key(env_file, "COGNITO_POOL_ID", pool_id)
        set_key(env_file, "M2M_CLIENT_ID", client_id)
        set_key(env_file, "M2M_CLIENT_SECRET", client_secret)
        set_key(env_file, "COGNITO_DISCOVERY_URL", discovery_url)
        set_key(env_file, "RESOURCE_SERVER_ID", RESOURCE_SERVER_ID)
        
        print(f"\n✅ 設定を.envファイルに保存しました！")
        
        return {
            "pool_id": pool_id,
            "client_id": client_id,
            "client_secret": client_secret,
            "discovery_url": discovery_url
        }
        
    except ClientError as e:
        print(f"❌ エラーが発生しました: {e}")
        raise

if __name__ == "__main__":
    cognito_config = create_cognito_m2m_setup()