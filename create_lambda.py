#!/usr/bin/env python3
"""
Lambda関数作成スクリプト
注文管理Lambda関数を作成し、.envファイルに自動保存します。
"""

import boto3
import zipfile
import os
import tempfile
from botocore.exceptions import ClientError
from dotenv import load_dotenv, set_key

# AWSクライアント
lambda_client = boto3.client('lambda', region_name='us-west-2')

LAMBDA_FUNCTION_NAME = "agentcore-order-tools"
LAMBDA_RUNTIME = "python3.12"
LAMBDA_HANDLER = "lambda_function.lambda_handler"

def create_lambda_code():
    """Lambda関数のコードを生成"""
    lambda_code = '''import json

def lambda_handler(event, context):
    """
    AgentCore Gateway経由で呼び出されるLambda関数
    context.client_contextからツール名を判別して処理を分岐
    """
    
    # Gateway経由の場合、context.client_contextが設定される
    tool_name = None
    try:
        if hasattr(context, 'client_context') and context.client_context:
            # client_contextから直接ツール名を取得
            tool_name = context.client_context.custom['bedrockAgentCoreToolName']
            print(f"Original tool name from Gateway: {tool_name}")
            
            # Gateway Target プレフィックスを除去
            delimiter = "___"
            if delimiter in tool_name:
                tool_name = tool_name[tool_name.index(delimiter) + len(delimiter):]
            print(f"Processed tool name: {tool_name}")
            print(f"Client context structure: {str(context.client_context)}")
        else:
            print("No client_context available - direct Lambda invocation")
    except (AttributeError, KeyError, TypeError) as e:
        print(f"Error accessing client_context: {e}")
        tool_name = None
    
    # ツール名に基づいて処理を分岐
    if tool_name == 'get_order_tool':
        order_id = event.get('orderId', 'unknown')
        # 実際のビジネスロジックをここに実装
        result = {
            "orderId": order_id,
            "status": "processing",
            "items": [
                {"name": "商品A", "quantity": 2},
                {"name": "商品B", "quantity": 1}
            ],
            "total": 5000
        }
        return {
            "statusCode": 200,
            "body": json.dumps(result)
        }
    
    elif tool_name == 'update_order_tool':
        order_id = event.get('orderId', 'unknown')
        # 実際の更新処理をここに実装
        result = {
            "orderId": order_id,
            "status": "updated",
            "message": f"Order {order_id} has been updated successfully"
        }
        return {
            "statusCode": 200,
            "body": json.dumps(result)
        }
    
    else:
        # ツール名が不明な場合
        return {
            "statusCode": 400,
            "body": json.dumps({
                "error": f"Unknown tool: {tool_name}"
            })
        }
'''
    return lambda_code

def create_deployment_package():
    """デプロイメントパッケージを作成"""
    lambda_code = create_lambda_code()
    
    # 一時ディレクトリでZIPファイルを作成
    with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as temp_zip:
        with zipfile.ZipFile(temp_zip.name, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # Lambda関数コードを追加
            zip_file.writestr('lambda_function.py', lambda_code)
        
        return temp_zip.name

def create_lambda_function(role_arn):
    """Lambda関数を作成"""
    try:
        # デプロイメントパッケージを作成
        zip_file_path = create_deployment_package()
        print("✅ デプロイメントパッケージを作成しました: lambda_function_code.zip")
        
        # デプロイメントパッケージを読み込み
        with open(zip_file_path, "rb") as f:
            zip_content = f.read()
        
        # Lambda関数を作成
        response = lambda_client.create_function(
            FunctionName=LAMBDA_FUNCTION_NAME,
            Runtime=LAMBDA_RUNTIME,
            Role=role_arn,
            Handler=LAMBDA_HANDLER,
            Code={'ZipFile': zip_content},
            Description='Order management tools for AgentCore Gateway'
        )
        
        function_arn = response['FunctionArn']
        print(f"✅ Lambda関数作成成功: {LAMBDA_FUNCTION_NAME}")
        
        # 一時ファイルを削除
        os.unlink(zip_file_path)
        
        return function_arn
        
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceConflictException':
            print(f"ℹ️  Lambda関数 '{LAMBDA_FUNCTION_NAME}' は既に存在します")
            response = lambda_client.get_function(FunctionName=LAMBDA_FUNCTION_NAME)
            return response['Configuration']['FunctionArn']
        else:
            print(f"❌ Lambda関数作成エラー: {e}")
            raise

def main():
    """メイン関数"""
    print("🚀 Lambda関数作成スクリプトを開始します...")
    
    # .envファイルを読み込み
    load_dotenv()
    
    # Lambda実行ロールARNを取得
    lambda_role_arn = os.environ.get("LAMBDA_ROLE_ARN")
    
    if not lambda_role_arn:
        print("❌ LAMBDA_ROLE_ARNが.envファイルに設定されていません")
        print("   create_iam_roles.pyを先に実行してください")
        return
    
    print("✅ Lambda関数のコードを作成しました")
    
    # Lambda関数を作成
    function_arn = create_lambda_function(lambda_role_arn)
    
    print(f"\n🎉 Lambda関数作成完了！")
    print(f"   Function ARN: {function_arn}")
    
    # .envファイルに保存
    set_key(".env", "LAMBDA_ARN", function_arn)
    print(f"\n✅ .envファイルに保存しました")
    print("🧹 作業ファイルを削除しました")
    
    return function_arn

if __name__ == "__main__":
    main()