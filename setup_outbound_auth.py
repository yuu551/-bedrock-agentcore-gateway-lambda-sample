#!/usr/bin/env python3
"""
AgentCore Identity OutboundAuth自動セットアップスクリプト
Gateway用のCredential Providerを自動作成します。
"""

import boto3
import os
import re
from typing import Dict, Any, Optional
from botocore.exceptions import ClientError
from dotenv import load_dotenv, set_key


class OutboundAuthSetup:
    def __init__(self, region: str = "us-west-2"):
        self.region = region
        self.cognito_client = boto3.client("cognito-idp", region_name=region)
        self.gateway_client = boto3.client("bedrock-agentcore-control", region_name=region)
        self.identity_client = boto3.client("bedrock-agentcore-control", region_name=region)
        
    def get_gateway_info(self, gateway_id: str) -> Dict[str, Any]:
        """
        Gateway IDから必要な情報を取得
        """
        try:
            # 詳細情報を取得
            gateway_detail = self.gateway_client.get_gateway(
                gatewayIdentifier=gateway_id
            )
            
            print(f"✅ Gateway情報取得成功: {gateway_detail.get('name', gateway_id)}")
            print(f"   Gateway ID: {gateway_detail['gatewayId']}")
            print(f"   Gateway URL: {gateway_detail['gatewayUrl']}")
            
            return gateway_detail
            
        except ClientError as e:
            print(f"❌ Gateway情報取得エラー: {e}")
            raise

    def get_cognito_discovery_url(self, gateway_detail: Dict[str, Any]) -> str:
        """
        GatewayのCognito設定からDiscovery URLを取得
        """
        try:
            auth_config = gateway_detail.get("authorizerConfiguration", {})
            custom_jwt = auth_config.get("customJWTAuthorizer", {})
            discovery_url = custom_jwt.get("discoveryUrl")
            
            if not discovery_url:
                raise Exception("Gateway authorizerConfiguration にdiscoveryUrlが見つかりません")
            
            print(f"✅ Discovery URL取得成功: {discovery_url}")
            return discovery_url
            
        except Exception as e:
            print(f"❌ Discovery URL取得エラー: {e}")
            raise

    def get_cognito_client_info(self, discovery_url: str) -> Dict[str, str]:
        """
        Discovery URLからUser Pool IDを抽出し、クライアント情報を取得
        """
        try:
            # Discovery URLからUser Pool IDを抽出
            # 例: https://cognito-idp.us-west-2.amazonaws.com/us-west-2_XXXXXXX/.well-known/openid-configuration
            match = re.search(r'/([^/]+)/.well-known', discovery_url)
            if not match:
                raise Exception("Discovery URLからUser Pool IDを抽出できません")
            
            user_pool_id = match.group(1)
            print(f"✅ User Pool ID抽出成功: {user_pool_id}")
            
            # User Pool Clientsを取得
            clients_response = self.cognito_client.list_user_pool_clients(
                UserPoolId=user_pool_id
            )
            
            if not clients_response.get("UserPoolClients"):
                raise Exception("User Pool Clientが見つかりません")
            
            # 最初のクライアント（通常M2M用）を使用
            client_info = clients_response["UserPoolClients"][0]
            client_id = client_info["ClientId"]
            
            # クライアント詳細を取得
            client_detail = self.cognito_client.describe_user_pool_client(
                UserPoolId=user_pool_id,
                ClientId=client_id
            )
            
            client_secret = client_detail["UserPoolClient"].get("ClientSecret")
            
            print(f"✅ Cognito Client情報取得成功:")
            print(f"   Client ID: {client_id}")
            print(f"   Client Secret: {'*' * 8}...{client_secret[-4:] if client_secret else 'なし'}")
            
            return {
                "client_id": client_id,
                "client_secret": client_secret,
                "user_pool_id": user_pool_id,
                "discovery_url": discovery_url
            }
            
        except ClientError as e:
            print(f"❌ Cognito Client情報取得エラー: {e}")
            raise

    def create_oauth2_credential_provider(self, 
                                        provider_name: str,
                                        cognito_info: Dict[str, str]) -> Dict[str, Any]:
        """
        OAuth2 Credential Providerを作成
        """
        try:
            create_request = {
                "name": provider_name,
                "credentialProviderVendor": "CustomOauth2",
                "oauth2ProviderConfigInput": {
                    "customOauth2ProviderConfig": {
                        "oauthDiscovery": {
                            "discoveryUrl": cognito_info["discovery_url"]
                        },
                        "clientId": cognito_info["client_id"],
                        "clientSecret": cognito_info["client_secret"]
                    }
                }
            }
            
            print(f"🔐 OAuth2 Credential Provider作成中: {provider_name}")
            
            response = self.identity_client.create_oauth2_credential_provider(**create_request)
            
            print(f"✅ OAuth2 Credential Provider作成成功!")
            print(f"   Provider Name: {response['name']}")
            print(f"   Provider ID: {response.get('credentialProviderId', 'N/A')}")
            
            return response
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'ConflictException':
                print(f"⚠️ Credential Provider '{provider_name}' は既に存在します")
                # 既存のプロバイダ情報を取得
                try:
                    list_response = self.identity_client.list_oauth2_credential_providers()
                    for provider in list_response.get("oauth2CredentialProviders", []):
                        if provider["name"] == provider_name:
                            print(f"✅ 既存のCredential Provider使用: {provider_name}")
                            return provider
                except Exception as list_error:
                    print(f"❌ 既存プロバイダ情報取得エラー: {list_error}")
                    raise
            else:
                print(f"❌ OAuth2 Credential Provider作成エラー: {e}")
                raise

    def setup_outbound_auth(self, gateway_id: str, provider_name: str = "agentcore-identity-for-gateway") -> Dict[str, Any]:
        """
        OutboundAuth設定のメイン処理
        """
        print(f"🚀 OutboundAuth自動設定開始")
        print(f"   Gateway ID: {gateway_id}")
        print(f"   Provider Name: {provider_name}")
        print(f"   Region: {self.region}")
        print("--" * 25)
        
        # 1. Gatewayの情報を取得
        gateway_detail = self.get_gateway_info(gateway_id)
        
        # 2. CognitoのDiscovery URLを取得
        discovery_url = self.get_cognito_discovery_url(gateway_detail)
        
        # 3. Cognitoクライアント情報を取得
        cognito_info = self.get_cognito_client_info(discovery_url)
        
        # 4. OAuth2 Credential Providerを作成
        provider_response = self.create_oauth2_credential_provider(provider_name, cognito_info)
        
        print("--" * 25)
        print("🎉 OutboundAuth設定完了!")
        
        # 5. .envファイルに結果を保存
        env_vars = {
            "IDENTITY_PROVIDER_NAME": provider_name,
            "GATEWAY_SCOPE": "agentcore-gateway/read agentcore-gateway/write"
        }
        
        for key, value in env_vars.items():
            set_key(".env", key, value)
        
        print(f"\n✅ 以下の環境変数を.envファイルに自動保存しました:")
        for key, value in env_vars.items():
            print(f"   {key}={value}")
        
        return {
            "provider_name": provider_name,
            "gateway_scope": env_vars["GATEWAY_SCOPE"],
            "provider_response": provider_response
        }


def main():
    """メイン関数"""
    # .envファイルを読み込み
    load_dotenv()
    
    print("🚀 OutboundAuth自動設定開始")
    print("   .envファイルから設定を読み込み中...")
    
    # .envファイルからGateway IDを取得
    gateway_id = os.environ.get("GATEWAY_ID")
    provider_name = "agentcore-identity-for-gateway"
    region = "us-west-2"
    
    if not gateway_id:
        print("❌ GATEWAY_IDが.envファイルに設定されていません")
        print("   create_gateway.pyを先に実行してください")
        return
    
    print(f"   Gateway ID: {gateway_id}")
    print(f"   Provider Name: {provider_name}")
    print(f"   Region: {region}")
    print("--" * 25)
    
    # OutboundAuthSetupクラスのインスタンス作成
    setup = OutboundAuthSetup(region=region)
    
    try:
        # OutboundAuth設定を実行
        result = setup.setup_outbound_auth(gateway_id, provider_name)
        print(f"\n🎉 設定が完了しました！")
        return result
    except Exception as e:
        print(f"❌ エラーが発生しました: {e}")
        raise


if __name__ == "__main__":
    main()