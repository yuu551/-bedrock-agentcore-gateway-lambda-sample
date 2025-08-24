# Amazon Bedrock AgentCore Gateway Sample

Lambda関数をMCPツール化してAIエージェントから呼び出すサンプルコード

## 概要

このプロジェクトは、Amazon Bedrock AgentCore RuntimeからM2M認証でGatewayを呼び出し、既存のLambda関数をMCP（Model Context Protocol）ツールとして利用可能にするサンプル実装です。

AgentCore Identityを活用してM2M認証を自動化し、Lambda関数をAIエージェントから簡単に呼び出せるようにします。

## 前提条件

- AWS CLI 2.28.8以上
- Python 3.12以上  
- AWSアカウント（us-west-2リージョンを使用）
- 適切なIAM権限（AgentCore、Lambda、Cognito、IAMの操作権限）
- Bedrock Claudeモデルの有効化（anthropic.claude-3-5-haiku-20241022-v1:0）

## プロジェクト構成

```
.
├── requirements.txt           # 依存関係
├── .env                       # 環境変数設定（自動生成）
├── .env.example              # 環境変数のテンプレート
├── setup_cognito.py          # Cognito設定スクリプト
├── create_iam_roles.py       # IAMロール作成スクリプト
├── create_lambda.py          # Lambda関数作成スクリプト
├── create_gateway.py         # Gateway作成スクリプト
├── setup_outbound_auth.py    # OutboundAuth設定スクリプト
├── runtime_agent.py          # Runtime実装
├── deploy_runtime.py         # Runtimeデプロイスクリプト
└── invoke_agentcore.py       # 動作確認用スクリプト
```

## セットアップ手順

### 1. 環境準備

```bash
# 仮想環境の作成と有効化
python3 -m venv agentcore-env
source agentcore-env/bin/activate

# 依存関係のインストール
pip install -r requirements.txt

# 環境変数ファイルの準備
cp .env.example .env
```

### 2. AWSリソースの作成

各スクリプトを順番に実行します。すべてのスクリプトは.envファイルを自動更新するため、手動での環境変数設定は不要です。

```bash
# 1. Cognito User Poolの作成（M2M認証用）
python setup_cognito.py

# 2. IAMロールの作成
python create_iam_roles.py

# 3. Lambda関数の作成
python create_lambda.py

# 4. Gatewayの作成
python create_gateway.py

# 5. AgentCore Identity OutboundAuthの設定（必須）
python setup_outbound_auth.py

# 6. Runtimeのデプロイ
python deploy_runtime.py
```

### 3. 動作確認

```bash
# エージェントを呼び出してテスト
python invoke_agentcore.py
```

## アーキテクチャ

本サンプルは以下の構成で動作します：

1. **AgentCore Runtime**: 認証なしで起動（開発環境用）
2. **AgentCore Gateway**: Cognito OAuth2によるInbound認証
3. **Lambda関数**: 注文管理ツール（get_order、update_order）
4. **AgentCore Identity**: M2M認証の自動化

### 認証フロー

1. RuntimeがAgentCore IdentityのOutboundAuth機能を使用してM2Mトークンを自動取得
2. 取得したトークンでGatewayにアクセス
3. GatewayがLambda関数を呼び出し、結果をMCP形式で返却

## 主要な機能

- **自動環境変数管理**: 各スクリプトが.envファイルを自動更新
- **M2M認証の自動化**: AgentCore Identityによるトークン管理
- **Lambda関数のMCP化**: 既存のLambda関数をそのままツール化

## トラブルシューティング

### Workload access tokenエラー

Runtime呼び出し時に「Workload access token has not been set」エラーが発生する場合は、invoke_agentcore.pyの`runtimeUserId`パラメータが設定されているか確認してください。

### Gateway認証エラー

M2M認証に失敗する場合は、以下を確認してください：
- Cognito User Pool Domainが作成されているか
- OutboundAuth設定が完了しているか
- .envファイルの認証情報が正しいか