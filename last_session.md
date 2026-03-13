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
- `docs/plans/auth_proxy_scaling_plan.md` の方針に沿って、small pattern の実装と live validation を進めました。
- small pattern の中心は、`ctxledger` 自身に auth logic を増やすのではなく、`Traefik -> auth-small -> private MCP backend` の proxy-centered topology を Docker Compose へ追加することです。
- repository の現状確認として、`docker/docker-compose.yml`、`docker/docker-compose.auth.yml`、`src/ctxledger/config.py`、`src/ctxledger/http_app.py`、`src/ctxledger/runtime/http_handlers.py`、`scripts/mcp_http_smoke.py`、README 周辺を見直しました。
- `docker/auth_small/` と `docker/traefik/` の配置を作成しました。
- `docker/auth_small/src/auth_small_app.py` を新規作成し、FastAPI ベースの lightweight auth service を追加しました。
- この auth service は:
  - `AUTH_SMALL_BEARER_TOKEN` を必須設定として読む
  - `AUTH_SMALL_USER` / `AUTH_SMALL_MODE` を optional identity metadata として返す
  - `GET /healthz` を持つ
  - `GET /auth/verify` で `Authorization: Bearer <token>` を検証する
  - missing/invalid token で `401` + `WWW-Authenticate`
  - valid token で `200` + `X-Auth-User` / `X-Auth-Mode`
  という small pattern plan どおりの最小 shape を持っています。
- `docker/docker-compose.small-auth.yml` を新規作成しました。
- initial overlay では base compose の `ctxledger` 公開 port が merge 後も残り、private backend にならない問題が見つかりました。
- そのため small pattern 用には base `ctxledger` service を `profiles: [disabled]` で無効化し、代わりに `ctxledger-private` service を定義する構成へ変更しました。
- `ctxledger-private` は:
  - `python:3.14-slim`
  - `uvicorn ctxledger.http_app:app`
  - host port 非公開
  - `expose: 8080`
  - `CTXLEDGER_REQUIRE_AUTH=false`
  という proxy backend 専用 shape にしました。
- Traefik も small pattern 用には専用 entrypoint port を使うように変更しました。
- host 既存 `8080` と競合したため、small pattern の proxy 公開 port は `8091` に変更しました。
- Traefik の Docker provider は今回の環境で Docker daemon metadata の取得に失敗し、router/service が組み上がらず `404 page not found` になる問題が出ました。
- そのため Traefik は Docker labels ベースをやめ、`providers.file` を使う形へ切り替えました。
- `docker/traefik/dynamic.yml` を追加し、以下を file provider で定義しました:
  - router `ctxledger-mcp`
  - middleware `ctxledger-forward-auth`
  - service `ctxledger-backend -> http://ctxledger-private:8080`
- 途中で `docker/traefik/dynamic.yml` の root `http:` key が欠けた状態になっていたため修正しました。
- 途中で `docker/auth_small/src/auth_small_app.py` に stray `}` が残っており、container 起動時に `SyntaxError: unmatched '}'` で落ちる問題もありました。
- これも修正し、auth-small は healthy で起動する状態にしました。
- `scripts/mcp_http_smoke.py` も small pattern validation 向けに拡張しました。
- 追加した内容:
  - `--expect-http-status`
  - `--expect-auth-failure`
  - initialize probe を先に流して expected HTTP status を検証する flow
- 最初は proxy rejection 時に payload 内 `error` object を必須扱いしていましたが、ForwardAuth rejection body は JSON-RPC ではなく plain JSON/transport body でもよいので、この制約を外しました。
- その結果、proxy rejection path と allow path の両方を同じ smoke script で確認できるようになりました。
- README も更新しました。
- small pattern section を追加・更新し、
  - `docker/docker-compose.small-auth.yml`
  - `CTXLEDGER_SMALL_AUTH_TOKEN`
  - proxy port `8091`
  - missing token `401`
  - invalid token `401`
  - valid token で workflow/resource smoke 通過
  を明記しました。
- `docs/plans/auth_proxy_scaling_plan.md` に small pattern 実装済み/検証済みの注記を追記しました。
  - deliverables A-D の status
  - exit criteria の current assessment
  - current repository shape と validated shape
- `docker compose -f docker/docker-compose.yml -f docker/docker-compose.small-auth.yml ps` で service state を確認しました。
- `ctxledger-auth-small`、`ctxledger-server-private` は healthy、`ctxledger-traefik` は起動している一方で healthcheck 上は `starting` / `unhealthy` になるケースがありました。
- Traefik log を見ると、`GET /ping` と `GET /ping/` が `404` を返しており、現在の healthcheck が実態に合っていないことを確認しました。
- 実トラフィック自体は通っており、small pattern の smoke validation は成功しています。
- よって現時点の remaining issue は、Traefik healthcheck の調整です。
- さらに整理として、未使用だった `docker/auth_small/Dockerfile` は削除済みです。
- current small pattern は source mount + `python:3.14-slim` + runtime install で一貫させています。
- この削除により、repo 上の auth-small artifact は actual compose runtime shape と一致するようになりました。

今回確認したテスト結果:
- `pytest -q`
- 結果: `254 passed`

今回確認した live Docker validation:
- `docker compose -f docker/docker-compose.yml -f docker/docker-compose.small-auth.yml down --remove-orphans`
- `CTXLEDGER_SMALL_AUTH_TOKEN=smoke-small-secret docker compose -f docker/docker-compose.yml -f docker/docker-compose.small-auth.yml up -d --build --force-recreate`
- 結果:
  - `ctxledger-postgres` healthy
  - `ctxledger-auth-small` healthy
  - `ctxledger-server-private` healthy
  - `ctxledger-traefik` started
- `docker compose -f docker/docker-compose.yml -f docker/docker-compose.small-auth.yml ps`
- 結果:
  - `ctxledger-auth-small` healthy
  - `ctxledger-server-private` healthy
  - `ctxledger-traefik` healthcheck は `starting` / `unhealthy` だが、proxy routing 自体は動作
- `python scripts/mcp_http_smoke.py --base-url http://127.0.0.1:8091 --expect-http-status 401 --expect-auth-failure`
- 結果:
  - missing token path が `401`
  - payload:
    - `error: missing_bearer_token`
    - `message: Authorization header must contain a bearer token`
- `python scripts/mcp_http_smoke.py --base-url http://127.0.0.1:8091 --bearer-token wrong-token --expect-http-status 401 --expect-auth-failure`
- 結果:
  - invalid token path が `401`
  - payload:
    - `error: invalid_bearer_token`
    - `message: Bearer token is invalid`
- `python scripts/mcp_http_smoke.py --base-url http://127.0.0.1:8091 --bearer-token smoke-small-secret --scenario workflow --workflow-resource-read`
- 結果:
  - proxy 背後の small pattern 経由で以下が通過
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
- small pattern 関連:
  - `feac2dd` — `Add Traefik small auth deployment pattern`
  - `b23389a` — `Refine small auth deployment verification notes`

現時点での設計メモ:
- small pattern は app-layer auth の強化ではなく、proxy-layer auth への移行としてかなり自然に成立しています。
- `ctxledger-private` を別 service 名で定義したことで、base compose の published `ctxledger` と衝突せず、private backend topology を Compose 上で表現できました。
- Traefik はこの環境では Docker provider より file provider の方が安定でした。
- `docker/traefik/dynamic.yml` を使う方が、small pattern の route/middleware/service 関係を明示しやすく、debug もしやすいです。
- proxy で守る endpoint 範囲として `/mcp` だけでなく `/debug/*`、`/workflow-resume/*`、projection failure endpoints も揃えて保護する形にしています。
- smoke script の rejection mode は、JSON-RPC error object を前提にせず transport-level 401 を確認する方が proxy auth には適切です。
- small pattern deliverable D の smoke validation は、missing token / invalid token / valid token の 3 系統まで live Docker 上で確認済みです。
- small pattern の documented proxy port は `8091` です。default local direct app port `8080` とは分けて扱う前提です。
- README 上の small pattern section と actual compose/runtime shape は現在一致している状態です。
- `docs/plans/auth_proxy_scaling_plan.md` にも、small pattern が実装済み/検証済みであることを反映済みです。
- 残っている技術的な小タスクは Traefik healthcheck の調整です。
- いまの `ctxledger-traefik` health は `/ping` / `/ping/` が `404` になることだけが原因で、routing 本体の failure ではありません。
- 未使用 `docker/auth_small/Dockerfile` は削除したので、auth-small の repo shape と actual compose shape のズレは減っています。

次セッションで優先してやること:
1. `docker/docker-compose.small-auth.yml` の Traefik healthcheck を本当に通る probe に置き換える
   - `/ping` 系にこだわらず、Traefik process の liveness を確認できる方法へ寄せる
   - あるいは small pattern 向けに実 routing を使った lightweight probe へ変える
2. 修正後に `docker compose -f docker/docker-compose.yml -f docker/docker-compose.small-auth.yml up -d --build --force-recreate` と `ps` を再確認する
3. 必要なら README に Traefik healthcheck の運用 caveat を少し追記する
4. 問題なければ次の descriptive commit を作る
   - 例: `Fix small auth Traefik healthcheck`
5. large pattern はまだ着手しない
6. large pattern 着手時には、proxy-layer auth だけで十分か、app-layer authorization / ownership / audit attribution が必要かを再評価する