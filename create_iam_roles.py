#!/usr/bin/env python3
"""
IAMロール作成スクリプト
Gateway用とRuntime用のIAMロールを作成し、.envファイルに自動保存します。
"""

import boto3
import json
import os
import time
from botocore.exceptions import ClientError
from dotenv import  set_key

# AWSクライアント
iam = boto3.client('iam')
sts = boto3.client('sts')

def get_account_id():
    """AWSアカウントIDを取得"""
    return sts.get_caller_identity()["Account"]

def create_trust_policy(account_id):
    """信頼ポリシーを生成（Gateway/Runtime共通）"""
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "AssumeRolePolicy",
                "Effect": "Allow",
                "Principal": {
                    "Service": "bedrock-agentcore.amazonaws.com"
                },
                "Action": "sts:AssumeRole",
                "Condition": {
                    "StringEquals": {
                        "aws:SourceAccount": account_id
                    },
                    "ArnLike": {
                        "aws:SourceArn": f"arn:aws:bedrock-agentcore:us-west-2:{account_id}:*"
                    }
                }
            }
        ]
    }

def create_lambda_trust_policy():
    """Lambda用信頼ポリシーを生成"""
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {
                    "Service": "lambda.amazonaws.com"
                },
                "Action": "sts:AssumeRole"
            }
        ]
    }

def create_runtime_policy(account_id):
    """Runtime用の詳細な実行ポリシーを生成"""
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "ECRImageAccess",
                "Effect": "Allow",
                "Action": [
                    "ecr:BatchGetImage",
                    "ecr:GetDownloadUrlForLayer"
                ],
                "Resource": [
                    f"arn:aws:ecr:us-west-2:{account_id}:repository/*"
                ]
            },
            {
                "Sid": "ECRTokenAccess",
                "Effect": "Allow",
                "Action": [
                    "ecr:GetAuthorizationToken"
                ],
                "Resource": "*"
            },
            {
                "Sid": "LogsAccess",
                "Effect": "Allow",
                "Action": [
                    "logs:DescribeLogStreams",
                    "logs:CreateLogGroup",
                    "logs:DescribeLogGroups",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents"
                ],
                "Resource": [
                    f"arn:aws:logs:us-west-2:{account_id}:log-group:/aws/bedrock-agentcore/runtimes/*"
                ]
            },
            {
                "Sid": "XRayAccess",
                "Effect": "Allow",
                "Action": [
                    "xray:PutTraceSegments",
                    "xray:PutTelemetryRecords",
                    "xray:GetSamplingRules",
                    "xray:GetSamplingTargets"
                ],
                "Resource": ["*"]
            },
            {
                "Sid": "CloudWatchMetrics",
                "Effect": "Allow",
                "Resource": "*",
                "Action": "cloudwatch:PutMetricData",
                "Condition": {
                    "StringEquals": {
                        "cloudwatch:namespace": "bedrock-agentcore"
                    }
                }
            },
            {
                "Sid": "BedrockModelInvocation",
                "Effect": "Allow",
                "Action": [
                    "bedrock:InvokeModel",
                    "bedrock:InvokeModelWithResponseStream"
                ],
                "Resource": [
                    "arn:aws:bedrock:*::foundation-model/*",
                    f"arn:aws:bedrock:us-west-2:{account_id}:*"
                ]
            },
            {
                "Sid": "AgentCoreIdentityAccess",
                "Effect": "Allow",
                "Action": [
                    "bedrock-agentcore:GetResourceOauth2Token",
                    "bedrock-agentcore:GetWorkloadAccessToken",
                    "bedrock-agentcore:GetWorkloadAccessTokenForUserId"
                ],
                "Resource": ["*"]
            },
            {
                "Sid": "SecretsManagerAccess",
                "Effect": "Allow",
                "Action": [
                    "secretsmanager:GetSecretValue"
                ],
                "Resource": ["*"]
            }
        ]
    }

def create_gateway_policy(account_id):
    """Gateway用の実行ポリシーを生成"""
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "LambdaInvocation",
                "Effect": "Allow",
                "Action": [
                    "lambda:InvokeFunction"
                ],
                "Resource": f"arn:aws:lambda:us-west-2:{account_id}:function:*"
            },
            {
                "Sid": "LogsAccess",
                "Effect": "Allow",
                "Action": [
                    "logs:DescribeLogStreams",
                    "logs:CreateLogGroup",
                    "logs:DescribeLogGroups",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents"
                ],
                "Resource": [
                    f"arn:aws:logs:us-west-2:{account_id}:log-group:/aws/bedrock-agentcore/gateway/*"
                ]
            },
            {
                "Sid": "XRayAccess",
                "Effect": "Allow",
                "Action": [
                    "xray:PutTraceSegments",
                    "xray:PutTelemetryRecords"
                ],
                "Resource": ["*"]
            }
        ]
    }

def create_lambda_policy(account_id):
    """Lambda関数用の実行ポリシーを生成"""
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "LogsAccess",
                "Effect": "Allow",
                "Action": [
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents"
                ],
                "Resource": [
                    f"arn:aws:logs:us-west-2:{account_id}:log-group:/aws/lambda/agentcore-order-tools:*"
                ]
            },
            {
                "Sid": "XRayAccess",
                "Effect": "Allow",
                "Action": [
                    "xray:PutTraceSegments",
                    "xray:PutTelemetryRecords"
                ],
                "Resource": ["*"]
            }
        ]
    }

def create_iam_role(role_name, trust_policy, execution_policy, description):
    """IAMロールを作成し、ポリシーをアタッチ"""
    try:
        # ロール作成
        role_response = iam.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(trust_policy),
            Description=description
        )
        
        role_arn = role_response['Role']['Arn']
        print(f"✅ IAMロール作成成功: {role_name}")
        
        # インラインポリシーをアタッチ
        iam.put_role_policy(
            RoleName=role_name,
            PolicyName=f"{role_name}Policy",
            PolicyDocument=json.dumps(execution_policy)
        )
        print(f"   ポリシーをアタッチしました")
        
        return role_arn
        
    except ClientError as e:
        if e.response['Error']['Code'] == 'EntityAlreadyExists':
            print(f"ℹ️  IAMロール '{role_name}' は既に存在します")
            role_response = iam.get_role(RoleName=role_name)
            return role_response['Role']['Arn']
        else:
            print(f"❌ IAMロール作成エラー: {e}")
            raise

def main():
    """メイン関数"""
    print("🚀 IAMロール作成スクリプトを開始します...")
    
    # アカウントIDを取得
    account_id = get_account_id()
    print(f"   アカウントID: {account_id}")
    
    # タイムスタンプを追加してロール名の重複を避ける
    timestamp = str(int(time.time()))
    
    # 信頼ポリシーを生成
    agentcore_trust_policy = create_trust_policy(account_id)
    lambda_trust_policy = create_lambda_trust_policy()
    
    # Gateway用IAMロール
    print(f"\n📦 Gateway用IAMロールを作成中...")
    gateway_role_name = f"AgentCoreGatewayRole-{timestamp}"
    gateway_policy = create_gateway_policy(account_id)
    gateway_role_arn = create_iam_role(
        gateway_role_name,
        agentcore_trust_policy,
        gateway_policy,
        "AgentCore Gateway execution role"
    )
    
    # Runtime用IAMロール
    print(f"\n📦 Runtime用IAMロールを作成中...")
    runtime_role_name = f"AgentCoreRuntimeRole-{timestamp}"
    runtime_policy = create_runtime_policy(account_id)
    runtime_role_arn = create_iam_role(
        runtime_role_name,
        agentcore_trust_policy,
        runtime_policy,
        "AgentCore Runtime execution role"
    )
    
    # Lambda関数用IAMロール
    print(f"\n📦 Lambda関数用IAMロールを作成中...")
    lambda_role_name = f"AgentCoreLambdaRole-{timestamp}"
    lambda_policy = create_lambda_policy(account_id)
    lambda_role_arn = create_iam_role(
        lambda_role_name,
        lambda_trust_policy,
        lambda_policy,
        "Lambda function execution role for AgentCore"
    )
    
    print(f"\n🎉 IAMロール作成完了！")
    print(f"   Gateway Role ARN: {gateway_role_arn}")
    print(f"   Runtime Role ARN: {runtime_role_arn}")
    print(f"   Lambda Role ARN: {lambda_role_arn}")
    
    # .envファイルに保存
    env_file = ".env"
    
    # .env.exampleからコピー（初回のみ）
    if not os.path.exists(env_file) and os.path.exists(".env.example"):
        with open(".env.example", "r") as src, open(env_file, "w") as dst:
            dst.write(src.read())
    
    # 環境変数を更新
    set_key(env_file, "GATEWAY_ROLE_ARN", gateway_role_arn)
    set_key(env_file, "RUNTIME_ROLE_ARN", runtime_role_arn)
    set_key(env_file, "LAMBDA_ROLE_ARN", lambda_role_arn)
    
    print(f"\n✅ .envファイルに保存しました")
    
    return {
        "gateway_role_arn": gateway_role_arn,
        "runtime_role_arn": runtime_role_arn,
        "lambda_role_arn": lambda_role_arn
    }

if __name__ == "__main__":
    main()