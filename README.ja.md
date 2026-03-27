# ctxledger 日本語README

`ctxledger` は、AIエージェント向けの durable workflow runtime / memory system です。

主な特徴:

- セッションをまたいだ resumable な workflow
- PostgreSQL を canonical state とする durable persistence
- MCP サーバとしての remote access
- memory / search / resume の bounded な運用
- ローカル HTTPS + 認証つき Docker Compose 起動
- CLI / Grafana による operator 向け observability

---

## 1. できること

`ctxledger` を使うと、MCP クライアントや AI エージェントは次の操作を行えます。

- workspace を登録する
- workflow を開始する
- checkpoint を記録する
- durable state から resume する
- verify status つきで workflow を完了する
- 高シグナルな episode を明示記録する
- bounded canonical retrieval として memory を検索する
- hierarchy-aware client 向けの grouped context を読む
- workflow / memory / failure state を確認する

---

## 2. ローカル起動で得られるもの

標準のローカル構成では次を使えます。

- MCP endpoint
  - `https://localhost:8443/mcp`
- Grafana
  - `http://localhost:3000`
- proxy-layer bearer token 認証
- PostgreSQL 17
- Docker Compose による一式起動

---

## 3. 起動手順

### 3.1 TLS 証明書を用意する

`localhost` 用の証明書を作成します。`mkcert` を使う例:

```/dev/null/sh#L1-3
mkdir -p docker/traefik/certs
mkcert -install
mkcert -cert-file docker/traefik/certs/localhost.crt -key-file docker/traefik/certs/localhost.key localhost 127.0.0.1 ::1
```

### 3.2 `.env` を用意する

`.env` は **MCP サーバを起動するための設定ファイル** です。  
典型的には `ctxledger` リポジトリを clone してから、リポジトリ root で次を行います。

```/dev/null/sh#L1-2
cp .env.example .env
# その後 .env を編集
```

最低限の例:

```/dev/null/dotenv#L1-5
CTXLEDGER_SMALL_AUTH_TOKEN=replace-me-with-a-strong-secret
CTXLEDGER_GRAFANA_ADMIN_USER=admin
CTXLEDGER_GRAFANA_ADMIN_PASSWORD=replace-with-a-strong-admin-password
CTXLEDGER_GRAFANA_POSTGRES_USER=ctxledger_grafana
CTXLEDGER_GRAFANA_POSTGRES_PASSWORD=replace-with-a-strong-secret
```

### 3.3 `envrcctl` を使う場合

`envrcctl` があるなら、secret を設定してから `docker compose` を実行します。

```/dev/null/sh#L1-1
envrcctl exec -- docker compose -f docker/docker-compose.yml -f docker/docker-compose.small-auth.yml up -d --build
```

### 3.4 通常の Docker Compose 起動

```/dev/null/sh#L1-1
docker compose -f docker/docker-compose.yml -f docker/docker-compose.small-auth.yml up -d --build
```

---

## 4. `.rules` の役割

`.rules` は `.env` と用途が違います。

- `.env`
  - `ctxledger` サーバを起動するための設定
- `.rules`
  - ユーザーが AI エージェントで開発する **対象プロジェクト側** に置く運用ルール

使い方:

- `ctxledger` リポジトリ内の `.rules` を参照する
- 開発対象プロジェクトのディレクトリへコピーする
- そのまま AI エージェントに読ませて使う

つまり、`.rules` は `ctxledger` コンテナ起動用ファイルではありません。  
AI エージェントが作業する **各プロジェクトのディレクトリ** に置いて使います。

---

## 5. 動作確認

### 5.1 認証なしアクセスは拒否されること

```/dev/null/sh#L1-1
python scripts/mcp_http_smoke.py --base-url https://localhost:8443 --expect-http-status 401 --expect-auth-failure --insecure
```

### 5.2 認証ありで workflow シナリオが通ること

```/dev/null/sh#L1-1
python scripts/mcp_http_smoke.py --base-url https://localhost:8443 --bearer-token YOUR_TOKEN_HERE --scenario workflow --workflow-resource-read --insecure
```

`YOUR_TOKEN_HERE` は `CTXLEDGER_SMALL_AUTH_TOKEN` の値に置き換えます。

### 5.3 稼働状態の確認

```/dev/null/sh#L1-1
docker compose -f docker/docker-compose.yml -f docker/docker-compose.small-auth.yml ps
```

---

## 6. MCP クライアント設定例

```/dev/null/json#L1-7
{
  "ctxledger": {
    "url": "https://localhost:8443/mcp",
    "headers": {
      "Authorization": "Bearer YOUR_TOKEN_HERE"
    }
  }
}
```

---

## 7. 便利な CLI

よく使うコマンド:

- `ctxledger stats`
- `ctxledger workflows`
- `ctxledger memory-stats`
- `ctxledger failures`

### episode summary を明示 build する

```/dev/null/sh#L1-4
python -m ctxledger.__init__ build-episode-summary \
  --episode-id <episode-uuid> \
  --summary-kind episode_summary \
  --format json
```

### AGE graph の状態確認

```/dev/null/sh#L1-1
ctxledger age-graph-readiness
```

### derived summary graph を refresh

```/dev/null/sh#L1-1
ctxledger refresh-age-summary-graph
```

### constrained graph を bootstrap

```/dev/null/sh#L1-1
ctxledger bootstrap-age-graph
```

---

## 8. Grafana

Grafana:

```/dev/null/txt#L1-1
http://localhost:3000
```

ログイン情報:

- username
  - `CTXLEDGER_GRAFANA_ADMIN_USER`
- password
  - `CTXLEDGER_GRAFANA_ADMIN_PASSWORD`

---

## 9. 補足

現在のローカル標準 deployment mode は `small` です。

含まれるもの:

- HTTPS
- proxy-layer authentication
- Grafana
- Apache AGE
- repository-owned PostgreSQL image path

より詳しい実装・仕様は次を参照してください。

- `README.md`
- `docs/project/product/specification.md`
- `docs/project/product/architecture.md`
- `docs/project/product/mcp-api.md`
- `docs/project/product/memory-model.md`
- `docs/project/releases/0.9.0_acceptance_review.md`
- `docs/project/releases/0.9.0_closeout.md`
