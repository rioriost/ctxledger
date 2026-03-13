このプロジェクトでは、Docker コンテナで動作する remote MCP サーバを HTTP 専用で提供しています。

直近の進捗:
- 以前の session までに、HTTP `/mcp` に対する最小 MCP 経路として `initialize` / `tools/list` / `tools/call` を実装済みでした。
- 追加で HTTP 側の `resources/list` / `resources/read` も実装済みで、workflow 系 resources も live Docker 上で確認済みです。
- 認証有効 (`CTXLEDGER_REQUIRE_AUTH=true`) の remote MCP path でも workflow 系 + resource 系 E2E が通る状態は維持されています。
- 以前の整理で stdio MCP サーバの残骸は削除済みで、HTTP 専用 shape に寄せています。

前回までの cleanup 完了事項:
- `server.py` 依存の縮小を継続し、tests と runtime modules の import を canonical location へ寄せる整理を進めました。
- `tests/test_server.py` で `create_runtime` と `print_runtime_summary` の import を `ctxledger.runtime.orchestration` から読む形へ変更しました。
- `tests/test_server.py` から `build_runtime_dispatch_result` への依存を外し、dispatch helper の代わりに `HttpRuntimeAdapter.dispatch()` の public surface を直接検証する形へ変更しました。
- `runtime.orchestration.create_runtime()` は `server` と `http_runtime_builder` を要求するシグネチャなので、対応する test は `HttpRuntimeAdapter(settings)` を返す builder を渡す形に修正しました。
- `HttpRuntimeAdapter.dispatch()` は module-level `build_runtime_dispatch_result()` helper を経由せず、自身で handler lookup と route-not-found 応答を返すように変更しました。
- これにより `build_runtime_dispatch_result()` は不要になり、`src/ctxledger/server.py` から関数定義を削除しました。
- あわせて `src/ctxledger/server.py` の `__all__` から `build_runtime_dispatch_result` と `RuntimeDispatchResult` の再公開を削除しました。
- `HttpRuntimeAdapter` 本体を `src/ctxledger/server.py` から `src/ctxledger/runtime/http_runtime.py` へ移動しました。
- `src/ctxledger/runtime/http_runtime.py` は、HTTP handler registration だけでなく、HTTP runtime adapter の concrete implementation も持つ canonical module になりました。
- `src/ctxledger/runtime/http_runtime.py` の `build_http_runtime_adapter()` から `..server` への runtime import 依存を削除しました。
- `src/ctxledger/server.py` は `HttpRuntimeAdapter` を `ctxledger.runtime.http_runtime` から import する側へ回り、server module から concrete adapter 実装を取り除きました。
- `tests/test_server.py` の `HttpRuntimeAdapter` import も `ctxledger.server` ではなく `ctxledger.runtime.http_runtime` から読む形へ変更しました。
- `tests/test_server.py` における `ctxledger.server` 依存は `CtxLedgerServer` と `create_server` のみに縮小しました。
- `src/ctxledger/server.py` の export surface を棚卸しし、`__all__` を意図的な public API のみに絞りました。
- `src/ctxledger/server.py` の `__all__` は `CtxLedgerServer` / `create_server` / `run_server` のみを公開する shape に変更しました。
- あわせて `server.py` から、もはや public surface として残す必要がない大量の import と再公開前提コードを削減しました。
- `src/ctxledger/mcp/tool_handlers.py` に残っていた `from ..server import McpToolResponse` を修正し、`McpToolResponse` の canonical import 先を `ctxledger.runtime.types` に変更しました。
- これにより、MCP tool response の生成は `server.py` を経由しない形に整理され、slimmed server exports と整合するようになりました。
- `src/ctxledger/server.py` に残っていた internal bridge helper も整理しました。
- `server.py` から `build_http_runtime_adapter()` / `build_workflow_service_factory()` / `create_runtime()` / `_print_runtime_summary()` を削除しました。
- `create_server()` は `runtime.server_factory.create_server()` への委譲をやめ、`CtxLedgerServer(...)` の構築、workflow service factory の選択、`build_http_runtime_adapter(server)` による runtime 装着を `server.py` 内で直接行う形に変更しました。
- `src/ctxledger/runtime/server_factory.py` を整理し、現在の `server.py` から使われなくなっていた `create_server()` helper を削除しました。
- `src/ctxledger/runtime/server_factory.py` は `build_workflow_service_factory()` のみを持つ小さな factory module に縮小されました。
- `runtime.server_factory` から不要になった type-only import と protocol import を削除し、module の責務に合わせて import surface を簡素化しました。
- `src/ctxledger/runtime/server_responses.py` に残っていた `server.py` への response type backref を整理しました。
- `build_workspace_resume_resource_response()` と `build_workflow_detail_resource_response()` が `from ..server import McpResourceResponse` を使っていたため、これを canonical な `ctxledger.runtime.types.McpResourceResponse` 参照へ変更しました。
- これにより、server response builder 群は response DTO 型について `server.py` を経由しない構成になり、response type の dependency direction もより自然になりました。
- debug/introspection response の組み立てを serializer 側の表現へ寄せました。
- `src/ctxledger/runtime/server_responses.py` の `build_runtime_routes_response()` と `build_runtime_tools_response()` は、生の introspection object から直接 dict を組み立てるのではなく、`serialize_runtime_introspection()` の出力を使って `transport` / `routes` / `tools` を切り出す形に変更しました。
- `build_runtime_introspection_response()` はもともと `serialize_runtime_introspection_collection()` を通していたため、debug introspection family 全体の表現がより一貫しました。
- route registry の naming を introspection responsibility に寄せました。
- `src/ctxledger/runtime/http_runtime.py` の `registered_routes()` を `introspection_endpoints()` に改名しました。
- `HttpRuntimeAdapter.introspect()` は `routes=self.introspection_endpoints()` を返す形へ更新され、route registry が「HTTP dispatch 全般の公開 API」ではなく「runtime introspection に載せる endpoint 集合」であることがメソッド名から明確になりました。
- `HttpRuntimeAdapter.start()` / `stop()` の logging extras も `registered_routes` ではなく `introspection_endpoints` キーで出す形に変更しました。
- `src/ctxledger/runtime/protocols.py` の `HttpRuntimeAdapterProtocol` も `registered_routes()` ではなく `introspection_endpoints()` を要求する shape に更新しました。
- `tests/test_server.py` で route registry を直接確認していた箇所も `registered_routes()` から `introspection_endpoints()` へ追従しました。
- `test_http_runtime_adapter_introspect_returns_registered_routes()` では、固定 tuple 直書きではなく `runtime.introspection_endpoints()` と `introspection.routes` が一致することを確認する形に変更しました。
- live Docker validation も実施しました。
- `docker compose -f docker/docker-compose.yml up -d --build` で PostgreSQL と `ctxledger` サービスを起動しました。
- `docker compose -f docker/docker-compose.yml ps` で `ctxledger-postgres` / `ctxledger-server` の両方が healthy になっていることを確認しました。
- `python scripts/mcp_http_smoke.py --base-url http://127.0.0.1:8080 --scenario workflow --workflow-resource-read` を実行し、live Docker 上で以下が通ることを確認しました。
  - `initialize`
  - `tools/list`
  - `tools/call`
  - `resources/list`
  - `workspace_register`
  - `workflow_start`
  - `workflow_checkpoint`
  - `workflow_resume`
  - `resources/read` for workspace resume
  - `resources/read` for workflow detail
  - `workflow_complete`
- これにより、HTTP-only cleanup 後の remote MCP server 実装が Docker Compose 経由でも end-to-end に動作することを確認しました。
- 最後に `pytest -q` を全体実行し、cleanup 一連の変更後も全体回帰がないことを確認しました。

今回の作業:
- `docs/plans/auth_proxy_scaling_plan.md` の方針に沿って、small pattern の実装に着手しました。
- 目的は `ctxledger` 自身に auth logic を増やすのではなく、`Traefik -> auth-small -> ctxledger(private)` の proxy-centered な front door を Compose に追加することです。
- repository の現状確認として、`docker/docker-compose.yml`、`docker/docker-compose.auth.yml`、`src/ctxledger/config.py`、`src/ctxledger/http_app.py`、`src/ctxledger/runtime/http_handlers.py`、`scripts/mcp_http_smoke.py`、`tests/test_config.py`、README の local startup/authenticated smoke 周辺を見直しました。
- 既存の app-layer auth は `CTXLEDGER_REQUIRE_AUTH` + `CTXLEDGER_AUTH_BEARER_TOKEN` による bearer validation で、small pattern ではこれを backend private network 化で置き換える想定が自然だと判断しました。
- `docker/auth_small/` と `docker/traefik/` の配置を作成しました。
- `docker/auth_small/src/auth_small_app.py` を新規作成し、FastAPI ベースの lightweight auth service のたたき台を追加しました。
- この auth service は:
  - `AUTH_SMALL_BEARER_TOKEN` を必須設定として読む
  - `AUTH_SMALL_USER` / `AUTH_SMALL_MODE` を optional identity metadata として返す
  - `GET /healthz` を持つ
  - `GET /auth/verify` で `Authorization: Bearer <token>` を検証する
  - missing/invalid token で `401` + `WWW-Authenticate`
  - valid token で `200` + `X-Auth-User` / `X-Auth-Mode`
  という small pattern plan どおりの最小 shape を持っています。
- `docker/auth_small/Dockerfile` も追加しました。
- `docker/docker-compose.small-auth.yml` を新規作成し、small pattern 用の compose overlay のたたき台を追加しました。
- その overlay には以下を入れています:
  - `traefik`
  - `auth-small`
  - `ctxledger` override
- `traefik` は Docker provider を使い、`/mcp`・`/debug/*`・`/workflow-resume/*`・projection failure endpoints を forward auth 付きで backend に流す方針です。
- `auth-small` は `python:3.14-slim` 上で source mount して `uvicorn auth_small_app:app` を起動する shape にしています。
- `ctxledger` 側は small pattern overlay では `CTXLEDGER_REQUIRE_AUTH=false` にし、host port を公開せず `expose` のみへ寄せる方針にしました。
- 途中で compose overlay と auth service の間に naming mismatch が見つかりました。
  - 初期版では env 名が `AUTH_SMALL_EXPECTED_BEARER_TOKEN` / `AUTH_SMALL_IDENTITY_USER` / `AUTH_SMALL_IDENTITY_MODE`
  - auth service 実装側は `AUTH_SMALL_BEARER_TOKEN` / `AUTH_SMALL_USER` / `AUTH_SMALL_MODE`
  になっていたため、overlay を auth service 実装に揃える修正を入れました。
- 同様に module 名も初期 compose では `auth_small:app` を起動していましたが、実ファイルは `auth_small_app.py` に寄せたため、compose command は `uvicorn auth_small_app:app --app-dir /app/src ...` に修正しました。
- 途中で `docker/traefik/dynamic.yml` も一度追加しましたが、この段階では Traefik labels ベースで十分と判断し、dynamic file は削除しました。
- ここまでの変更は small pattern の骨格追加までで、まだ validation までは到達していません。

現時点で未完了 / 次にやること:
1. `docker/docker-compose.small-auth.yml` を最終確認する
   - auth service env 名
   - `uvicorn` module path
   - healthcheck quoting
   - Traefik healthcheck
   - `ctxledger` host port unpublish の挙動
2. 必要なら `scripts/mcp_http_smoke.py` を拡張する
   - missing token で proxy が `401`
   - wrong token で proxy が `401`
   - valid token で MCP workflow smoke が通る
   を 1 コマンドまたは再現しやすい手順で確認できるようにする
3. README に small pattern の compose 手順を追記する
   - `docker compose -f docker/docker-compose.yml -f docker/docker-compose.small-auth.yml up -d --build`
   - `CTXLEDGER_SMALL_AUTH_TOKEN=...`
   - IDE は Traefik の `http://127.0.0.1:8080/mcp` に bearer header 付きで接続
4. 必要なら tests を追加する
   - ただし auth-small は現時点では docker 専用 artifact なので、まずは smoke と compose validation を優先してよい
5. Docker live validation を行う
   - compose up
   - compose ps
   - missing token request
   - invalid token request
   - valid token 付き `scripts/mcp_http_smoke.py --scenario workflow --workflow-resource-read`
6. 問題なければ `pytest -q` を再実行して回帰確認する
7. `last_session.md` をこの進捗で更新した状態を維持する
8. 最後に descriptive commit を作る

今回確認したテスト結果:
- この session ではまだ新規テスト / 全体テストの再実行までは未着手
- 前回 session の確認済み結果は維持:
  - `pytest -q tests/test_server.py` → `140 passed`
  - `pytest -q tests/test_server.py tests/test_cli.py` → `152 passed`
  - `pytest -q tests/test_server.py tests/test_cli.py tests/test_postgres_integration.py` → `168 passed`
  - `pytest -q` → `254 passed`

今回確認した live Docker validation:
- この session では small pattern 用 compose/Traefik/auth-small の live validation はまだ未実施
- 前回 session までの authenticated direct-backend validation は確認済み:
  - `docker compose -f docker/docker-compose.yml up -d --build`
  - `docker compose -f docker/docker-compose.yml ps`
  - `python scripts/mcp_http_smoke.py --base-url http://127.0.0.1:8080 --scenario workflow --workflow-resource-read`

今回の直近コミット:
- 前回 session まで:
  - `d316d74` — `Reduce server test imports to runtime modules`
  - `968499e` — `Trim remaining server test helper imports`
  - `b3a5b95` — `Inline HTTP adapter dispatch helper`
  - `0224852` — `Move HTTP runtime adapter into runtime module`
  - `93b472b` — `Import HTTP runtime adapter from canonical module in tests`
  - `3181d7a` — `Slim server exports to public entrypoints`
  - `d7d2284` — `Inline server bootstrap helper flow`
  - `28de53a` — `Prune unused runtime server factory helper`
  - `0ad5419` — `Use runtime response types directly in server responses`
  - `1bfc34d` — `Align debug runtime responses with serializers`
  - `089bc2e` — `Clarify runtime route registry introspection role`
  - `c9e4a77` — `Record full cleanup verification status`
  - `5d8500b` — `Record cleanup plan completion status`
- この session ではまだ commit 未作成

現時点での設計メモ:
- small pattern の中心は app-layer auth の追加ではなく、proxy-layer auth への移行です。
- 既存 `CTXLEDGER_REQUIRE_AUTH` は direct exposure 時の safety net として残しつつ、small pattern documented topology では `ctxledger` backend を private にするのが自然です。
- `auth-small` は repo 内の tiny service として十分成立しそうで、small pattern deliverable A にかなり素直に沿っています。
- `Traefik` は Docker labels だけでも今回の構成には十分そうで、dynamic config file は必須ではなさそうです。
- proxy で守る endpoint 範囲としては、`/mcp` だけでなく debug/workflow resume/projection failure endpoints も揃えて保護する方が運用上自然です。
- `scripts/mcp_http_smoke.py` はすでに bearer header を送れるので、proxy allow path の validation にはそのまま使えます。
- ただし proxy reject path を再現しやすくするため、unauthorized expectation を扱うオプションを足すと small pattern smoke deliverable に合います。
- small pattern が通ったら、README と `docs/plans/auth_proxy_scaling_plan.md` の deliverables/exit criteria と照らして完了度を整理するとよいです。

次セッションで優先してやること:
1. `docker/docker-compose.small-auth.yml` の整合性を仕上げる
2. 必要に応じて smoke script を proxy rejection/allow validation 向けに拡張する
3. README に small pattern の startup / token / validation 手順を書く
4. `docker compose -f docker/docker-compose.yml -f docker/docker-compose.small-auth.yml up -d --build` で live validation
5. missing / invalid / valid token の 3 系統を検証する
6. `pytest -q` を回して回帰確認する
7. 問題なければ descriptive commit を作る