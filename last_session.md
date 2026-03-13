このプロジェクトでは、Docker コンテナで動作する remote MCP サーバを HTTP 専用で提供しています。

直近の進捗:
- 以前の session までに、HTTP `/mcp` に対する最小 MCP 経路として `initialize` / `tools/list` / `tools/call` を実装済みでした。
- 追加で HTTP 側の `resources/list` / `resources/read` も実装済みで、workflow 系 resources も live Docker 上で確認済みです。
- FastAPI ベースの `src/ctxledger/http_app.py` と Docker 起動導線は維持されています。
- 認証有効 (`CTXLEDGER_REQUIRE_AUTH=true`) の remote MCP path でも workflow 系 + resource 系 E2E が通る状態は維持されています。
- 以前の整理で stdio MCP サーバの残骸は削除済みで、HTTP 専用 shape に寄せています。

今回の作業:
- `docs/plans/http_fastapi_cleanup_plan.md` を新規作成し、HTTP MCP + FastAPI 導入後に残っている不要レイヤーの整理方針を文書化しました。
- cleanup の第一段として、`src/ctxledger/http_app.py` を変更し、FastAPI route から `runtime.dispatch(route_name, ...)` に再委譲せず、`runtime.http_handlers` の具体ハンドラを直接束縛する形に変更しました。
- これにより、FastAPI が HTTP route ownership を持ち、アプリ層の request flow が追いやすくなりました。
- `src/ctxledger/http_app.py` から `server.runtime._server = server` の後付け代入を削除しました。
- `src/ctxledger/runtime/http_runtime.py` を変更し、`HttpRuntimeAdapter` を `HttpRuntimeAdapter(server.settings, server=server)` で構築するようにして、runtime/server の依存関係を生成時に明示しました。
- `src/ctxledger/server.py` の `HttpRuntimeAdapter.__init__` に `server` 引数を追加し、private field の後付け patch を不要にしました。
- `src/ctxledger/server.py` の `build_http_runtime_adapter()` から `_server` の後付け代入を削除しました。
- まだ `server.py` には compatibility wrapper や route registry ベースの仕組みが多く残っていますが、今回の変更で「FastAPI の上にもう一段 route dispatch がある」状態は app entrypoint 側では解消できています。
- 今回は挙動互換を優先し、`HttpRuntimeAdapter.register_handler()` / `registered_routes()` / `dispatch_http_request()` などのテスト対象はまだ残しています。次段で `server.py` の薄い委譲関数や route registry の縮小を進める想定です。

今回確認したテスト結果:
- `pytest -q tests/test_server.py tests/test_mcp_modules.py`
- 結果: `157 passed`

今回の未コミット変更:
- `docs/plans/http_fastapi_cleanup_plan.md` を新規追加
- `src/ctxledger/http_app.py`
- `src/ctxledger/runtime/http_runtime.py`
- `src/ctxledger/server.py`

現時点での設計メモ:
- `http_app.py` はかなり自然になった一方、`server.py` は依然として wrapper / re-export / thin delegation が多く、次の cleanup の主対象です。
- `dispatch_http_request()` は現時点で主に既存テストと route registry ベースの runtime path を支えるために残しています。
- `registered_routes()` は debug/introspection と既存テストで参照されているため、削除前に introspection の責務整理が必要です。
- 設定面では `TransportMode` と `http.enabled` の二重性がまだ残っており、HTTP 専用化に合わせた簡素化余地があります。
- FastAPI app は依然として import 時に `create_default_fastapi_app()` が走る shape なので、必要なら次段で lifespan 管理へ寄せる余地があります。

次セッションで優先してやること:
1. `server.py` の thin wrapper / re-export の棚卸し
2. テスト import を canonical module (`runtime.http_handlers`, `runtime.server_responses`) に寄せられる箇所から移行
3. 使われなくなった `server.py` の wrapper を削除
4. 必要なら `dispatch_http_request()` と route registry の責務を縮小
5. 変更が一段落したら `pytest -q` で全体確認
6. 問題なければ cleanup 用の descriptive commit を作成