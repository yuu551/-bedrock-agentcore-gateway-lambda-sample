#!/usr/bin/env python3
"""
Bedrock AgentCore Runtime を呼び出すサンプルスクリプト
"""

import boto3
import json
import os
from dotenv import load_dotenv

def invoke_agent_runtime(prompt, runtime_arn=None, qualifier="DEFAULT", region="us-west-2"):
    """
    Bedrock AgentCore Runtime を呼び出す
    
    Args:
        prompt: エージェントに送信するプロンプト
        runtime_arn: エージェントランタイムのARN（.envから自動読み取り）
        qualifier: エンドポイント名（デフォルトは "DEFAULT"）
        region: AWSリージョン（デフォルトは "us-west-2"）
    
    Returns:
        エージェントからのレスポンス
    """
    
    # .envファイルからランタイムARNを取得
    if runtime_arn is None:
        load_dotenv()
        runtime_arn = os.environ.get("RUNTIME_ARN")
        if not runtime_arn:
            raise ValueError("RUNTIME_ARN が.envファイルに設定されていません。deploy_runtime.pyを実行してください。")
    
    # Bedrock AgentCore クライアントを初期化
    client = boto3.client('bedrock-agentcore', region_name=region)
    
    # ペイロードを準備（JSON形式でエンコード）
    payload = json.dumps({
        "prompt": prompt
    }).encode('utf-8')
    
    try:
        # エージェントランタイムを呼び出し
        response = client.invoke_agent_runtime(
            agentRuntimeArn=runtime_arn,
            qualifier=qualifier,
            payload=payload,
            contentType='application/json',
            accept='application/json',
            runtimeUserId="test-user-123"
        )
        
        # レスポンスを処理
        if response.get('contentType') == 'text/event-stream':
            # ストリーミングレスポンスの処理
            content = []
            for line in response['response'].iter_lines(chunk_size=10):
                if line:
                    line = line.decode('utf-8')
                    if line.startswith('data: '):
                        line = line[6:]
                        print(f"ストリーミング: {line}")
                        content.append(line)
            return '\n'.join(content)
        
        elif response.get('contentType') == 'application/json':
            # JSON レスポンスの処理
            content = []
            for chunk in response.get('response', []):
                content.append(chunk.decode('utf-8'))
            return json.loads(''.join(content))
        
        else:
            # その他のレスポンス形式
            return response
            
    except Exception as e:
        print(f"エラーが発生しました: {type(e).__name__}: {str(e)}")
        
        # エラーの詳細情報を表示
        if hasattr(e, 'response'):
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            error_message = e.response.get('Error', {}).get('Message', 'No message')
            print(f"エラーコード: {error_code}")
            print(f"エラーメッセージ: {error_message}")
        
        return None


def main():
    """メイン関数"""
    
    
    # 呼び出し
    response = invoke_agent_runtime("注文ID 123の情報を教えてください エラーが起きた場合はエラーについても丁寧に教えてください。エラーメッセージの原文も添えてね。")
    if response:
        print(f"レスポンス: {response}\n")


if __name__ == "__main__":
    main()