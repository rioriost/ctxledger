このプロジェクトでは、Dockerコンテナで動作するリモートMCPサーバを作成しています。

直近の進捗:
- HTTP `/mcp` に対する最小MCP経路として、`initialize` / `tools/list` / `tools/call` の実装とテスト確認は完了しています。
- 追加で、HTTP側の `resources/list` / `resources/read` も実装・テスト確認できる状態にしました。
- `HttpRuntimeAdapter` は `registered_resources()` / `dispatch_resource()` を持ち、runtime introspection でも `tools` / `resources` を返すようになっています。
- FastAPI を採用し、既存のHTTP dispatch ロジックを外側の実サーバとして公開する `src/ctxledger/http_app.py` を追加しました。
- Docker compose は `uvicorn ctxledger.http_app:app --host 0.0.0.0 --port 8080` で起動するよう変更しました。
- `pyproject.toml` に `fastapi` と `uvicorn[standard]` を追加しました。
- minimum MCP client として `scripts/mcp_http_smoke.py` を追加しました。
- Docker 上で `ctxledger` と `postgres` を起動し、`/debug/runtime` が応答することを確認しました。
- 現在のテスト結果は `169 passed` です。
- Git コミット:
  - `6df3f5f` — `Add FastAPI MCP runtime smoke validation`
  - `3525158` — `Document MCP smoke workflow validation`

確認済みのE2E結果:
1. basic smoke validation
   - `python scripts/mcp_http_smoke.py --base-url http://127.0.0.1:8080 --tool-name memory_get_context`
   - 成功確認:
     - `initialize`
     - `tools/list`
     - `tools/call(memory_get_context)`
     - `resources/list`
   - `memory_get_context` は `v0.1.0` では未実装stubだが、HTTP MCP経由の呼び出し自体は成功している

2. workflow smoke validation
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
   - `python scripts/mcp_http_smoke.py --base-url http://127.0.0.1:8080 --scenario workflow --workflow-resource-read`
   - 成功確認:
     - `resources/read` for `workspace://{workspace_id}/resume`
     - `resources/read` for `workspace://{workspace_id}/workflow/{workflow_instance_id}`
   - 実在する workflow/workspace データに対して、resource read が live Docker server 上で成功することを確認済み

README の更新内容:
- FastAPI + uvicorn ベースの Docker 起動手順を反映
- `/debug/runtime` による runtime wiring 確認手順を追加
- `scripts/mcp_http_smoke.py` の basic / workflow / workflow-resource-read シナリオの使い方を追記
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

到達点:
- Docker 上で remote MCP server として起動可能
- minimum MCP client で `initialize` / `tools/list` / `tools/call` / `resources/list` / `resources/read` を確認済み
- workflow 系 (`workspace_register`, `workflow_start`, `workflow_checkpoint`, `workflow_resume`, `workflow_complete`) も Docker + 実DB で確認済み
- これにより、`v0.1.0` の remote MCP closeout に必要な最小確認ラインはかなり満たせている

まだ残っていること:
1. `docs/deployment.md` と `docs/v0.1.0_acceptance_evidence.md` の変更をコミットに含める
2. 必要なら `docs/mcp-api.md` にも FastAPI / smoke validation の実運用手順を反映する
3. 必要なら auth 有効時 (`CTXLEDGER_REQUIRE_AUTH=true`) の smoke validation も追加で確認する
4. 作業区切りとして追加コミットする

次セッションで優先してやること:
- deployment / acceptance docs の変更を最終確認
- auth 有効パスの E2E を必要に応じて追加
- `last_session.md` を再確認してコミット