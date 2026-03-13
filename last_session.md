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
- さらに `scripts/mcp_http_smoke.py` で、実際に以下のE2E確認を行いました:
  1. `initialize`
  2. `tools/list`
  3. `tools/call` (`memory_get_context`)
  4. `resources/list`
- `tools/call(memory_get_context)` は `ok: true` で応答し、`implemented: false` の stub として返ることを確認しました。
- 現在のテスト結果は `169 passed` です。

確認済みのE2E結果の要点:
- FastAPI + uvicorn + Docker 構成で `http://127.0.0.1:8080/mcp` が remote MCP endpoint として到達可能
- `initialize` は `protocolVersion: 2024-11-05` を返す
- `tools/list` は 10 個の tool を返す
- `resources/list` は 2 個の resource URI を返す
- `memory_get_context` は v0.1.0 では未実装stubだが、HTTP MCP経由での呼び出し自体は成功している

まだ残っていること:
1. README / docs に FastAPI ベースの実起動手順と smoke test 手順を反映する
2. 必要なら `resources/read` のE2Eも、実在する workflow/workspace データを使って確認する
3. 可能なら `workspace_register` など workflow 系 tool のE2Eも、Docker上の実DBに対して追加で確認する
4. 作業がまとまったら `git commit` する

次セッションで優先してやること:
- README の local / Docker startup 手順を FastAPI + uvicorn ベースに更新
- `scripts/mcp_http_smoke.py` の使い方を docs に追記
- 必要なら workflow 系の実データを投入して `workspace_register` / `workflow_*` のE2Eを追加
- `last_session.md` を最新化したうえでコミット