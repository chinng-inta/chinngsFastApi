---
title: FastAPI MCP Gateway
description: A FastAPI MCP Gateway Server
tags:
  - fastapi
  - mcp
  - python
---

# FastAPI MCP Gateway

Railway上で動作するMCP（Model Context Protocol）ゲートウェイサーバーです。複数のMCPサービスを統合し、単一のエンドポイントから利用できるようにします。

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/template/-NvLj4?referralCode=CRJ8FE)

## ✨ Features

- FastAPI
- MCP Protocol Support
- Cloudflare Workers JWT Authentication
- Multiple Internal MCP Services Integration
  - Sequential Thinking
  - Server Memory (Knowledge Graph)
- Python 3

## 🚀 統合されているMCPサービス

### 1. Sequential Thinking
段階的思考をサポートするMCPサーバー

### 2. Server Memory
ナレッジグラフベースのメモリ管理MCPサーバー
- エンティティとリレーションの管理
- 観察データの保存と検索
- グラフベースのナレッジ管理

## 💁‍♀️ How to use

### ローカル開発

1. パッケージのインストール:
```bash
pip install -r requirements.txt
```

2. 環境変数の設定:
```bash
cp .env.example .env
# .envファイルを編集して必要な環境変数を設定
```

3. ローカルで実行:
```bash
uvicorn src.server:app --reload --port 8000
```

### Railway デプロイ

1. Railwayプロジェクトを作成
2. 以下のサービスをデプロイ:
   - このゲートウェイサーバー
   - Sequential Thinking サーバー
   - Server Memory サーバー
3. 環境変数を設定:
   - `WORKERS_MCP_URL`: Cloudflare Workers MCP ServerのURL
   - `SEQUENTIALTHINKING_SERVICE_URL`: Sequential ThinkingサービスのURL
   - `SERVER_MEMORY_SERVICE_URL`: Server MemoryサービスのURL

## 📝 API Endpoints

### Health Check
- `GET /` - ルートエンドポイント
- `GET /health` - ヘルスチェック

### MCP Tools
- `GET /list` - 利用可能なツールのリスト取得
- `POST /sequentialthinking` - Sequential Thinking実行
- `POST /server-memory` - Server Memory (Knowledge Graph) 操作
- `GET /server_info` - サーバー情報取得

### Debug
- `GET /debug/auth` - 認証接続テスト
- `GET /debug/sequentialthinking` - Sequential Thinking接続テスト
- `GET /debug/server-memory` - Server Memory接続テスト

## 🔐 認証

本番環境ではCloudflare Access JWTによる認証が必要です。
開発環境では`SKIP_AUTH=true`を設定することで認証をスキップできます。

## 📚 Documentation

- FastAPI自動生成ドキュメント: `/docs`
- ReDoc: `/redoc`
