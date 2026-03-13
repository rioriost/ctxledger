このプロジェクトでは、Dockerコンテナで動作するリモートMCPサーバを作成しています。

直近の進捗:
- HTTP `/mcp` に対する最小MCP経路として、`initialize` / `tools/list` / `tools/call` の実装とテスト確認は完了しています。
- 追加で、HTTP側の `resources/list` / `resources/read` も実装・テスト確認できる状態にしました。
- `HttpRuntimeAdapter` は `registered_resources()` / `dispatch_resource()` を持ち、runtime introspection でも `tools` / `resources` を返すようになっています。
- FastAPI を採用し、既存のHTTP dispatch ロジックを外側の実サーバとして公開する `src/ctxledger/http_app.py` を追加しました。
- Docker compose は `uvicorn ctxledger.http_app:app --host 0.0.0.0 --port 8080` で起動するよう変更しました。
- `pyproject.toml` に `fastapi` と `uvicorn[standard]` を追加しました。
- minimum MCP client として `scripts/mcp_http_smoke.py` を追加しました。
- 認証有効の Docker override として `docker/docker-compose.auth.yml` を追加しました。
- FastAPI wrapper 側で `Authorization: Bearer ...` ヘッダを既存認証ロジックが扱えるよう橋渡しする調整を入れました。
- `scripts/mcp_http_smoke.py` は workflow シナリオ時に毎回ユニークな `repo_url` / `canonical_path` を使うため、繰り返し実行可能です。
- 現在のテスト結果は `169 passed` です。

Git コミット:
- `6df3f5f` — `Add FastAPI MCP runtime smoke validation`
- `3525158` — `Document MCP smoke workflow validation`
- `0af6a4b` — `Add MCP resource read acceptance evidence`
- `b8a4cb8` — `Document MCP HTTP runtime operations`
- `0079407` — `Add authenticated MCP smoke validation`

確認済みのE2E結果:
1. basic smoke validation
   - 実行:
     - `python scripts/mcp_http_smoke.py --base-url http://127.0.0.1:8080 --tool-name memory_get_context`
   - 成功確認:
     - `initialize`
     - `tools/list`
     - `tools/call(memory_get_context)`
     - `resources/list`
   - `memory_get_context` は `v0.1.0` では未実装stubだが、HTTP MCP経由の呼び出し自体は成功している

2. workflow smoke validation
   - 実行:
     - `python scripts/mcp_http_smoke.py --base-url http://127.0.0.1:8080 --scenario workflow`
   - 成功確認:
     - `workspace_register`
     - `workflow_start`
     - `workflow_checkpoint`
     - `workflow_resume`
     - `workflow_complete`
   - 実Docker上の PostgreSQL に対して、workflow 系の最小E2Eが通ることを確認済み
   - `workflow_complete` まで成功し、attempt は `succeeded`、workflow は `completed` になった

3. workflow resource-read validation
   - 実行:
     - `python scripts/mcp_http_smoke.py --base-url http://127.0.0.1:8080 --scenario workflow --workflow-resource-read`
   - 成功確認:
     - `resources/read` for `workspace://{workspace_id}/resume`
     - `resources/read` for `workspace://{workspace_id}/workflow/{workflow_instance_id}`
   - 実在する workflow/workspace データに対して、resource read が live Docker server 上で成功することを確認済み

4. authenticated MCP smoke validation
   - 実行:
     - `docker compose -f docker/docker-compose.yml -f docker/docker-compose.auth.yml down`
     - `docker compose -f docker/docker-compose.yml -f docker/docker-compose.auth.yml up -d --build --force-recreate`
     - `python scripts/mcp_http_smoke.py --base-url http://127.0.0.1:8080 --bearer-token smoke-test-secret-token --scenario workflow --workflow-resource-read`
   - 認証有効状態で成功確認:
     - `initialize`
     - `tools/list`
     - `tools/call(memory_get_context)`
     - `resources/list`
     - `workspace_register`
     - `workflow_start`
     - `workflow_checkpoint`
     - `workflow_resume`
     - `resources/read workspace resume`
     - `resources/read workflow detail`
     - `workflow_complete`
   - これにより、認証有効 (`CTXLEDGER_REQUIRE_AUTH=true`) の remote MCP path でも、workflow 系 + resource 系を含む live Docker E2E が通ることを確認済み

README の更新内容:
- FastAPI + uvicorn ベースの Docker 起動手順を反映
- `/debug/runtime` による runtime wiring 確認手順を追加
- `scripts/mcp_http_smoke.py` の basic / workflow / workflow-resource-read シナリオの使い方を追記
- auth 有効時の smoke validation 手順を追記
- Python 直接起動の推奨手順を `uvicorn ctxledger.http_app:app --host 0.0.0.0 --port 8080` に更新

docs の更新内容:
- `docs/deployment.md`
  - FastAPI/uvicorn ベースの実HTTP serving 形態を反映
  - Docker local deployment evidence を追記
  - smoke validation コマンド例を追記
  - `resources/read` を含む remote validation の説明を追記
- `docs/v0.1.0_acceptance_evidence.md`
  - Docker + FastAPI + minimum client による live remote MCP evidence を反映
  - workflow tools と workflow resources の HTTP MCP E2E確認を反映
  - `resources/list` / `resources/read` の confirmed 扱いを反映
  - Docker local deployment works を Confirmed に寄せる更新を反映
- `docs/mcp-api.md`
  - `/mcp` で現在確認済みの HTTP MCP operations を更新
  - FastAPI / uvicorn / Docker による remote runtime shape を反映
  - smoke validation 手順を追記
  - workflow tool / workflow resource の live validation evidence を反映
- `docs/specification.md`
  - FastAPI + uvicorn ベースのHTTP runtime を反映
  - Docker 上の remote MCP serving 形態を明記
  - auth 有効 path を含む確認済み surface の土台を反映

到達点:
- Docker 上で remote MCP server として起動可能
- minimum MCP client で `initialize` / `tools/list` / `tools/call` / `resources/list` / `resources/read` を確認済み
- workflow 系 (`workspace_register`, `workflow_start`, `workflow_checkpoint`, `workflow_resume`, `workflow_complete`) も Docker + 実DB で確認済み
- auth 有効 (`CTXLEDGER_REQUIRE_AUTH=true`) の状態でも、workflow 系 + resource 系を含む remote MCP E2E が確認済み
- これにより、`v0.1.0` の remote MCP closeout に必要な最小確認ラインはかなり満たせている

まだ残っていること:
1. `README.md` / `docs/deployment.md` / `docs/mcp-api.md` / `docs/specification.md` の auth 有効時説明を最終目視確認する
2. `.gitignore` 以外の作業中変更を整理して、必要なら最後の仕上げコミットを切る
3. closeout 時点でどこまでを `v0.1.0` の confirmed surface と表現するかを最終確認する

次セッションで優先してやること:
- 作業ツリーの未整理変更確認
- auth 有効時説明の最終確認
- 必要なら最終コミット