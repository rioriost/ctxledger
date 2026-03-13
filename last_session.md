このプロジェクトでは、Docker コンテナで動作する remote MCP サーバを HTTP 専用で提供しています。

直近の進捗:
- 以前の session までに、HTTP `/mcp` に対する最小 MCP 経路として `initialize` / `tools/list` / `tools/call` を実装済みでした。
- 追加で HTTP 側の `resources/list` / `resources/read` も実装済みで、workflow 系 resources も live Docker 上で確認済みです。
- 以前の整理で stdio MCP サーバの残骸は削除済みで、HTTP 専用 shape に寄せています。
- `server.py` 依存の縮小、HTTP runtime adapter の canonical module への移動、debug/runtime introspection の serializer 整理など、HTTP-only cleanup の大きな pruning は完了済みです。
- 直近の session では、small pattern / proxy-only auth 周辺の docs・compose・runbook 整理、その live Docker re-validation、さらに large-pattern design-prep の decision-template / scoring-rubric / navigation 補強を継続しました。

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

small pattern 実装・検証完了事項:
- `docs/plans/auth_proxy_scaling_plan.md` の方針に沿って、small pattern の実装と live validation を完了しました。
- small pattern の中心は、`ctxledger` 自身に auth logic を増やすのではなく、`Traefik -> auth-small -> private MCP backend` の proxy-centered topology を Docker Compose へ追加することでした。
- `docker/auth_small/` と `docker/traefik/` の配置を作成しました。
- `docker/auth_small/src/auth_small_app.py` を追加し、FastAPI ベースの lightweight auth service を実装しました。
- この auth service は:
  - `AUTH_SMALL_BEARER_TOKEN` を必須設定として読む
  - `AUTH_SMALL_USER` / `AUTH_SMALL_MODE` を optional identity metadata として返す
  - `GET /healthz` を持つ
  - `GET /auth/verify` で `Authorization: Bearer <token>` を検証する
  - missing/invalid token で `401` + `WWW-Authenticate`
  - valid token で `200` + `X-Auth-User` / `X-Auth-Mode`
  という small pattern plan どおりの最小 shape を持っています。
- `docker/docker-compose.small-auth.yml` を追加しました。
- initial overlay では base compose の `ctxledger` 公開 port が merge 後も残り、private backend にならない問題があったため、small pattern 用には base `ctxledger` service を `profiles: [disabled]` で無効化し、代わりに `ctxledger-private` service を定義する構成へ変更しました。
- `ctxledger-private` は:
  - `python:3.14-slim`
  - `uvicorn ctxledger.http_app:app`
  - host port 非公開
  - `expose: 8080`
  という proxy backend 専用 shape にしました。
- Traefik の Docker provider は今回の環境で Docker daemon metadata の取得に失敗し、router/service が組み上がらず `404 page not found` になる問題が出たため、Traefik は Docker labels ベースをやめ、`providers.file` を使う形へ切り替えました。
- `docker/traefik/dynamic.yml` を追加し、以下を file provider で定義しました:
  - router `ctxledger-mcp`
  - middleware `ctxledger-forward-auth`
  - service `ctxledger-backend -> http://ctxledger-private:8080`
- 途中で `docker/traefik/dynamic.yml` の root `http:` key が欠けた状態になっていたため修正しました。
- 途中で `docker/auth_small/src/auth_small_app.py` に stray `}` が残っており、container 起動時に `SyntaxError: unmatched '}'` で落ちる問題もありました。
- これも修正し、auth-small は healthy で起動する状態にしました。
- `scripts/mcp_http_smoke.py` を small pattern validation 向けに拡張しました。
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
- Traefik healthcheck は `/ping` / `/ping/` が `404` になっていたため、最終的に process-level probe へ変更しました。
- その結果、small pattern stack 全体が healthy になりました。
- 未使用だった `docker/auth_small/Dockerfile` は削除済みです。
- current small pattern は source mount + `python:3.14-slim` + runtime install で一貫させています。
- これにより、repo 上の auth-small artifact は actual compose runtime shape と一致するようになりました。

今回の作業:
- small pattern をさらに進め、**proxy-only auth cleanup** を実施しました。
- 目的は、small pattern を「proxy layer が唯一の認証境界」で完結させ、`ctxledger` 本体から app-layer auth 実装を完全に外すことです。
- `src/ctxledger/config.py` から app-layer auth 設定を削除しました。
  - `AuthSettings` dataclass を削除
  - `AppSettings.auth` を削除
  - `CTXLEDGER_REQUIRE_AUTH`
  - `CTXLEDGER_AUTH_BEARER_TOKEN`
  に関する validation を削除
  - `load_settings()` での auth 設定読み込みを削除
- `src/ctxledger/runtime/http_handlers.py` から app-layer bearer auth 実装を削除しました。
  - `extract_bearer_token()`
  - `build_http_auth_error_response()`
  - `require_http_bearer_auth()`
  を削除
- これにあわせて各 HTTP handler から auth gate 呼び出しを削除しました。
  - `build_workflow_resume_http_handler()`
  - `build_closed_projection_failures_http_handler()`
  - `build_projection_failures_ignore_http_handler()`
  - `build_projection_failures_resolve_http_handler()`
  - `build_runtime_introspection_http_handler()`
  - `build_runtime_routes_http_handler()`
  - `build_runtime_tools_http_handler()`
  - `build_mcp_http_handler()`
- その結果、`ctxledger` application runtime は `/mcp` も debug routes も operator routes も、**app-layer bearer auth なし**で動く shape になりました。
- `build_mcp_http_handler()` では `StreamableHttpEndpoint` の `auth_validator` を渡さない形へ変更しました。
- `runtime/http_handlers.py` の `__all__` も auth helper の export を外し、canonical HTTP handler surface のみを残しました。
- auth cleanup の途中で circular import が顕在化しました。
  - `runtime.introspection` が serializer を re-export していた旧前提と
  - `runtime.orchestration` / `runtime.server_responses` の import path
  が噛み合わず、`serialize_runtime_introspection_collection` import で循環が起きました。
- そのため:
  - `src/ctxledger/runtime/introspection.py` から serializer re-export を削除
  - `runtime.orchestration` は `serialize_runtime_introspection_collection` を canonical `runtime.serializers` から import
  - `runtime.server_responses.build_runtime_introspection_response()` も serializer を canonical module から import
  する形へ修正しました。
- これにより、auth cleanup で表面化した introspection/serializer import cycle は解消しました。
- `docker/docker-compose.auth.yml` は direct app-layer auth override としては廃止扱いにしました。
- 現在の内容は compatibility stub コメントのみで、deprecated であること、認証は `docker/docker-compose.small-auth.yml` 側の proxy layer でやるべきことを明記しています。
- `tests/test_config.py` から auth 設定前提のケースを削除・更新しました。
  - `minimum_valid_env()` から `CTXLEDGER_REQUIRE_AUTH` を削除
  - `settings.auth.is_enabled` assertion を削除
  - auth-required validation test 群を削除
- `tests/test_cli.py` から `AuthSettings` import と `AppSettings.auth` 生成を削除しました。
- `tests/test_mcp_modules.py` から `AuthSettings` import と `make_settings()` の auth args を削除しました。
- `tests/test_postgres_integration.py` の loaded settings fixture env から `CTXLEDGER_REQUIRE_AUTH` を削除しました。
- `tests/test_server.py` も追従しました。
  - top-level `AuthSettings` import を削除
  - `make_settings()` から `auth_bearer_token` / `require_auth` args を削除
  - `AppSettings.auth` 生成を削除
  - HTTP route の bearer auth 必須を確認していた test 群を削除
- これにより、server-side test suite から direct app auth 前提の coverage は除去されました。
- なお、generic streamable HTTP unit test にある `auth_validator` 使用テストは、`build_streamable_http_endpoint()` 自体の generic capability test として残っているだけで、`ctxledger` app-layer auth の存在を意味しません。
- README を proxy-only 前提へ更新しました。
  - config list から `CTXLEDGER_REQUIRE_AUTH` / `CTXLEDGER_AUTH_BEARER_TOKEN` を削除
  - direct app-layer authenticated smoke step を削除し、proxy-authenticated smoke step に置換
  - production guidance を proxy-layer authentication 前提に書き換え
  - security notes も proxy-layer bearer auth 前提へ修正
- `docs/SECURITY.md` を proxy-only auth model 前提へ書き換えました。
  - app-layer bearer auth 記述を削除
  - proxy-only authentication model を明示
  - config expectation を proxy/gateway secret 前提へ変更
  - local/shared/prod deployment recommendations を proxy-first shape へ更新
  - action routes / debug routes の保護境界も proxy-layer前提へ統一
- `docs/deployment.md` も proxy-only auth 前提へ更新しました。
  - recommended env vars から `CTXLEDGER_REQUIRE_AUTH` / `CTXLEDGER_AUTH_BEARER_TOKEN` を削除
  - environment guidance table を proxy-layer auth 前提へ変更
  - malformed authentication configuration 記述を削除
- `docs/CHANGELOG.md` の production guidance note も proxy-only auth 前提へ更新しました。
- この一連の変更により、**small pattern = proxy-only auth** が repo 全体でより一貫した形になっています。

large pattern documentation prep:
- `docs/plans/auth_proxy_scaling_plan.md` の large pattern section を改めて見直し、現時点では「実装」ではなく「比較観点と着手条件の整理」に留める方針が自然だと確認しました。
- roadmap 上、large pattern は **after roadmap `0.4`** の別フェーズであり、今すぐ compose や runtime に手を入れる対象ではありません。
- 現時点で large pattern に入る前提条件として重要なのは:
  - `docs/roadmap.md` 上の `0.4` 以後であること
  - proxy-layer auth だけで十分か、app-layer authorization / ownership / audit attribution が必要かを再評価すること
  - MCP-capable IDE client と non-browser auth flow の両立性を first-class に扱うこと
- candidate comparison の観点として、plan に既に書かれている以下が重要です:
  - `Pomerium`
  - `oauth2-proxy`
  - another OIDC-aware gateway
  - organization-standard identity gateway
- 現時点の整理としては:
  - `oauth2-proxy` は browser/cookie/redirect-heavy になりやすく、IDE UX との相性評価が必要
  - `Pomerium` は policy-friendly で multi-user internal tool には合いそう
  - ただし large pattern の最終選定は、client compatibility / operational fit / org standard の3軸で比較するのが自然
- 次に large pattern documentation prep を進めるなら、`docs/plans/` 配下に「candidate evaluation memo」や「decision matrix」を 1 枚追加し、
  - auth flow shape
  - IDE compatibility
  - identity propagation
  - operator complexity
  - future authorization extensibility
  の観点で比較整理するのがよさそうです。
- ただしこれは implementation 開始ではなく、phase gate を越える前の design prep として扱うべきです。

今回確認したテスト結果:
- `pytest -q tests/test_config.py tests/test_mcp_modules.py tests/test_cli.py`
- session 開始時点で project-wide diagnostics は 0 errors / 0 warnings でした。
- full test suite として `pytest -q` も実行し、`246 passed in 11.31s` でした。
- この時点で auth cleanup 後の repo は diagnostics / tests ともに green です。

今回追加した documentation prep:
- `docs/plans/auth_large_gateway_evaluation_memo.md` を新規追加しました。
- この memo は large pattern の implementation plan ではなく、**post-0.4 の design-prep comparison memo** として位置づけています。
- memo では主に以下を整理しました:
  - MCP IDE compatibility を最優先評価軸にすること
  - identity quality / operational fit / authorization extensibility / architecture alignment を比較軸にすること
  - `Pomerium` / `oauth2-proxy` / other OIDC-aware gateway / organization-standard gateway の4カテゴリ比較
  - downstream identity propagation を将来の optional capability として意識すること
  - final gateway 選定前に answer すべき readiness questions
- `docs/plans/auth_proxy_scaling_plan.md` にも追記し、
  - large pattern の early comparison criteria はこの新 memo にあること
  - current comparison frame の参照先
  - implementation sequence における design-prep baseline
  を明記しました。

docs consistency cleanup:
- large-pattern memo 追加後の wording 整合性を追加確認しました。
- `docs/SECURITY.md` を再調整し、
  - current security boundary を app-layer bearer auth ではなく proxy-layer auth と明記
  - projection failure action routes の保護・観測の説明を proxy-layer wording に統一
  - security review guidance も proxy-first 前提へ寄せる方向を確認しました。
- `docs/deployment.md` を再調整し、
  - recommended production topology の auth 表現を proxy-layer authentication handling strategy に更新
  - projection failure action routes の保護説明を bearer-auth boundary ではなく proxy-layer authentication boundary に更新
  - deployment/security セクション全体が proxy-only auth model と矛盾しないよう整合性を取りました。
- `docs/CHANGELOG.md` の unreleased note も追従し、
  - `/debug/*` route protection の説明を proxy-layer authentication boundary に更新しました。
- `docs/imple_plan_0.1.0.md` に残っていた旧 auth wording も軽く整理し、
  - `config.py` responsibilities の auth token configuration を proxy/auth-gateway integration expectations に更新
  - recommended env vars の bearer token 固定記述を proxy-layer auth secret / gateway credential 方向へ更新
  - security plan の minimum security を reverse-proxy or auth-gateway enforcement 前提に更新
  - task breakdown の `auth hook` を `proxy/auth boundary integration` に更新しました。
- この cleanup により、large-pattern memo 追加後の docs 群はより一貫して **proxy-only auth / proxy-first security boundary** を前提に読める状態になっています。
- なお `docs/imple_plan_0.1.0.md` は historical planning document 的な性格もあるため、今後さらに厳密に current-state aligned wording へ寄せるかどうかは別途判断余地があります。

docs consistency cleanup:
- large-pattern memo 追加後の wording 整合性を追加確認しました。
- `docs/SECURITY.md` を再調整し、
  - current security boundary を app-layer bearer auth ではなく proxy-layer auth と明記
  - projection failure action routes の保護・観測の説明を proxy-layer wording に統一
  - security review guidance を `bearer auth` / `bearer token` ではなく `proxy-layer authentication` / `proxy-layer secrets or gateway credentials` に更新しました。
- `docs/deployment.md` を再調整し、
  - recommended production topology の auth 表現を proxy-layer authentication handling strategy に更新
  - projection failure action routes の保護説明を bearer-auth boundary ではなく proxy-layer authentication boundary に更新
  - deployment/security セクション全体が proxy-only auth model と矛盾しないよう整合性を取りました。
- `docs/CHANGELOG.md` の unreleased note も追従し、
  - `/debug/*` route protection の説明を proxy-layer authentication boundary に更新しました。
- `docs/imple_plan_0.1.0.md` に残っていた旧 auth wording も軽く整理し、
  - `config.py` responsibilities の auth token configuration を proxy/auth-gateway integration expectations に更新
  - recommended env vars の bearer token 固定記述を proxy-layer auth secret / gateway credential 方向へ更新
  - security plan の minimum security を reverse-proxy or auth-gateway enforcement 前提に更新
  - task breakdown の `auth hook` を `proxy/auth boundary integration` に更新しました。
- `docs/mcp-api.md` も追従し、
  - HTTP operator action route examples を app-layer HTTP auth wording ではなく proxy-protected deployment / trusted direct local path という説明に更新
  - `401` の説明を HTTP bearer-auth contract ではなく proxy-auth rejection shape に更新
  - authentication error examples を `missing/invalid bearer token` ではなく `missing/invalid proxy-layer bearer token` と `unsupported proxy/auth-gateway mode` に更新しました。
- `docs/specification.md` も最終横断チェックの一環で追従し、
  - Security section の `Bearer token authentication` を `Proxy-layer authentication` に更新しました。
- `README.md` / `docs/workflow-model.md` は今回の確認範囲では proxy-only auth model と矛盾する明確な修正点は見当たりませんでした。
- large pattern の次段 documentation prep として、`docs/plans/auth_large_gateway_decision_record_template.md` を新規追加しました。
  - decision status
  - phase gate confirmation
  - candidate comparison matrix
  - MCP client compatibility notes
  - identity propagation decision
  - app-layer authorization decision
  - trust boundary
  - validation requirements
  - migration notes
  - final decision statement
  を埋めるための template です。
- `docs/plans/auth_large_gateway_evaluation_memo.md` にも追記し、design-prep memo から actual gateway selection 時にはこの decision-record template を使う流れを明記しました。
- `README.md` の documentation index も軽く改善し、auth/deployment guidance として
  - `docs/small_auth_operator_runbook.md`
  - `docs/plans/auth_proxy_scaling_plan.md`
  - `docs/plans/auth_large_gateway_evaluation_memo.md`
    への導線を追加しました。
  - `docs/plans/auth_large_gateway_evaluation_memo.md` に、large-pattern gateway 候補を narrowing するときの **weighted scoring rubric** も追記しました。
    - scoring scale `1-5`
    - default weights
      - MCP IDE compatibility = `5`
      - identity quality = `4`
      - operational fit = `4`
      - identity propagation readiness = `3`
      - authorization extensibility = `3`
      - architecture alignment = `4`
      - organization-standard alignment = `2`
    - weighted score の式
    - worksheet template
    - scoring guardrails
  - これにより、small pattern の operator guidance、large pattern の evaluation memo、future decision record template、そして candidate scoring の4層が docs navigation 上でも辿りやすくなっています。
- `docs/specification.md` も最終横断チェックの一環で追従し、
  - Security section の `Bearer token authentication` を `Proxy-layer authentication` に更新しました。
- `README.md` / `docs/workflow-model.md` は今回の確認範囲では proxy-only auth model と矛盾する明確な修正点は見当たりませんでした。
- large pattern の次段 documentation prep として、`docs/plans/auth_large_gateway_decision_record_template.md` を新規追加しました。
  - decision status
  - phase gate confirmation
  - candidate comparison matrix
  - MCP client compatibility notes
  - identity propagation decision
  - app-layer authorization decision
  - trust boundary
  - validation requirements
  - migration notes
  - final decision statement
  を埋めるための template です。
- `docs/plans/auth_large_gateway_evaluation_memo.md` にも追記し、design-prep memo から actual gateway selection 時にはこの decision-record template を使う流れを明記しました。
- `README.md` の documentation index も軽く改善し、auth/deployment guidance として
  - `docs/small_auth_operator_runbook.md`
  - `docs/plans/auth_proxy_scaling_plan.md`
  - `docs/plans/auth_large_gateway_evaluation_memo.md`
  への導線を追加しました。
- これにより、small pattern の operator guidance、large pattern の evaluation memo、そして future decision record template の3層が docs navigation 上でも辿りやすくなっています。
- small pattern の operator-facing 手順を整理するため、`docs/small_auth_operator_runbook.md` を新規追加しました。
  - startup
  - health verification
  - missing/invalid/valid token smoke verification
  - client target `http://127.0.0.1:8091/mcp`
  - shutdown with layered compose files
  - common failure modes
  を 1 枚にまとめています。
- `README.md` の small Traefik auth pattern 節から、この runbook への参照も追加しました。
- compose 側の軽い棚卸しも行い、deprecated app-layer auth env の残骸を整理しました。
  - `docker/docker-compose.yml` から
    - `CTXLEDGER_REQUIRE_AUTH`
    - `CTXLEDGER_AUTH_BEARER_TOKEN`
    に関する旧コメントと env 定義を削除しました。
  - `docker/docker-compose.small-auth.yml` の `ctxledger-private` から `CTXLEDGER_REQUIRE_AUTH: "false"` を削除しました。
- これにより、compose 設定も current proxy-only auth model とより自然に一致する shape になりました。
- small-pattern live Docker re-validation も compose cleanup 後に再実施しました。
  - `docker compose -f docker/docker-compose.yml -f docker/docker-compose.small-auth.yml down --remove-orphans`
  - `CTXLEDGER_SMALL_AUTH_TOKEN=smoke-small-secret docker compose -f docker/docker-compose.yml -f docker/docker-compose.small-auth.yml up -d --build --force-recreate`
  - `docker compose -f docker/docker-compose.yml -f docker/docker-compose.small-auth.yml ps`
  - 結果:
    - `ctxledger-postgres` healthy
    - `ctxledger-auth-small` healthy
    - `ctxledger-server-private` healthy
    - `ctxledger-traefik` healthy
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
    - proxy 背後の small pattern 経由で以下が再確認できました
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
- この再確認により、runbook と compose cleanup 後の実運用手順は引き続き有効であることを確認しました。
- この cleanup により、large-pattern memo 追加後の docs 群はより一貫して **proxy-only auth / proxy-first security boundary** を前提に読める状態になっています。
- なお `docs/imple_plan_0.1.0.md` は historical planning document 的な性格もあるため、今後さらに厳密に current-state aligned wording へ寄せるかどうかは別途判断余地があります。
- code / test / script 側には `CTXLEDGER_REQUIRE_AUTH` / `CTXLEDGER_AUTH_BEARER_TOKEN` / `AuthSettings` などの旧 app-layer auth 参照は今回の確認範囲では残っていませんでした。
- auth/deployment planning materials の導線をさらに整理するため、`docs/plans/auth_planning_index.md` を新規追加しました。
  - current auth model
  - small vs large pattern
  - operator runbook
  - evaluation memo
  - future decision-record template
  の reading order と quick reference を 1 枚にまとめています。
- `docs/CONTRIBUTING.md` も実質的な guide に拡張し、
  - core docs
  - MCP planning docs
  - auth/deployment docs
  の recommended reading order
  - proxy-first auth model を壊さないための caution
  - small auth / proxy work で期待される validation flow
  - auth/deployment docs map
  を追記しました。
- live Docker validation 後に `pytest -q` をそのまま実行すると、`tests/test_postgres_integration.py` の integration fixture 前提と live stack state が干渉して 6 件の error が出ることを確認しました。
- 原因は docs 変更や code regression ではなく、small-pattern live validation 後に `ctxledger-postgres` / related Docker state が integration test setup と噛み合わなかったことです。
- その後、`docker compose -f docker/docker-compose.yml -f docker/docker-compose.small-auth.yml down --remove-orphans` で small-pattern stack を明示的に落としてから `pytest -q` を再実行し、`246 passed` に復帰することを確認しました。
- これにより、integration-test recovery 手順としては「live small-pattern validation 後に overlay stack を落としてから full pytest を流す」が有効だと確認できました。
- code / test / script 側には `CTXLEDGER_REQUIRE_AUTH` / `CTXLEDGER_AUTH_BEARER_TOKEN` / `AuthSettings` などの旧 app-layer auth 参照は今回の確認範囲では残っていませんでした。
- auth/deployment planning materials の導線をさらに整理するため、`docs/plans/auth_planning_index.md` を新規追加しました。
  - current auth model
  - small vs large pattern
  - operator runbook
  - evaluation memo
  - future decision-record template
  の reading order と quick reference を 1 枚にまとめています。
- `docs/CONTRIBUTING.md` も実質的な guide に拡張し、
  - core docs
  - MCP planning docs
  - auth/deployment docs
  の recommended reading order
  - proxy-first auth model を壊さないための caution
  - small auth / proxy work で期待される validation flow
  - auth/deployment docs map
  を追記しました。
- `docs/plans/mcp_planning_index.md` からも `docs/plans/auth_planning_index.md` への参照を追加し、MCP planning set と auth/deployment planning set の相互導線を強化しました。
- live Docker validation 後に `pytest -q` をそのまま実行すると、`tests/test_postgres_integration.py` の integration fixture 前提と live stack state が干渉して 6 件の error が出ることを確認しました。
- 原因は docs 変更や code regression ではなく、small-pattern live validation 後に `ctxledger-postgres` / related Docker state が integration test setup と噛み合わなかったことです。
- その後、`docker compose -f docker/docker-compose.yml -f docker/docker-compose.small-auth.yml down --remove-orphans` で small-pattern stack を明示的に落としてから `pytest -q` を再実行し、`246 passed` に復帰することを確認しました。
- これにより、integration-test recovery 手順としては「live small-pattern validation 後に overlay stack を落としてから full pytest を流す」が有効だと確認できました。
- `docs/plans/auth_large_gateway_evaluation_memo.md` の scoring-rubric 追記後も、code-adjacent scope として
  - `tests/test_config.py`
  - `tests/test_mcp_modules.py`
  - `tests/test_cli.py`
  - `tests/test_server.py`
  を実行し、`178 passed` を確認しました。

次 session への引き継ぎ候補:
- `git status` を見て今回の docs/navigation 変更を確認する
- repo ルールに従って、work loop の区切りで descriptive message 付きの `git commit` を行う
  - 例: `Document auth planning navigation and test recovery`
- live Docker validation を再度流す場合は、終了後に
  - `docker compose -f docker/docker-compose.yml -f docker/docker-compose.small-auth.yml down --remove-orphans`
  を実行してから full `pytest -q` を流す
- large-pattern design prep をさらに進めるなら、`docs/plans/auth_large_gateway_decision_record_template.md` を起点に、candidate evaluation memo から actual selection record へ移るときの ADR/decision-record 運用を整える
- `docs/plans/auth_large_gateway_evaluation_memo.md` の scoring rubric を使って、candidate shortlisting の example scorecard や filled example を 1 枚追加するのも自然
- `README.md` の documentation index と `docs/plans/auth_planning_index.md` / `docs/CONTRIBUTING.md` / `docs/plans/mcp_planning_index.md` の導線は追加済みなので、必要なら次は plans 間の相互リンクや auth index から具体 plans への cross-reference をもう一段強化する
- integration-test recovery の観点では、small-pattern live validation 後に full test suite が失敗した場合、まず overlay stack を落としてから `pytest -q` を再実行する

今回の作業:
- small pattern をさらに進め、**proxy-only auth cleanup** を実施しました。
- 目的は、small pattern を「proxy layer が唯一の認証境界」で完結させ、`ctxledger` 本体から app-layer auth 実装を完全に外すことです。
- `src/ctxledger/config.py` から app-layer auth 設定を削除しました。
  - `AuthSettings` dataclass を削除
  - `AppSettings.auth` を削除
  - `CTXLEDGER_REQUIRE_AUTH`
  - `CTXLEDGER_AUTH_BEARER_TOKEN`
  に関する validation を削除
  - `load_settings()` での auth 設定読み込みを削除
- `src/ctxledger/runtime/http_handlers.py` から app-layer bearer auth 実装を削除しました。
  - `extract_bearer_token()`
  - `build_http_auth_error_response()`
  - `require_http_bearer_auth()`
  を削除
- これにあわせて各 HTTP handler から auth gate 呼び出しを削除しました。
  - `build_workflow_resume_http_handler()`
  - `build_closed_projection_failures_http_handler()`
  - `build_projection_failures_ignore_http_handler()`
  - `build_projection_failures_resolve_http_handler()`
  - `build_runtime_introspection_http_handler()`
  - `build_runtime_routes_http_handler()`
  - `build_runtime_tools_http_handler()`
  - `build_mcp_http_handler()`
- その結果、`ctxledger` application runtime は `/mcp` も debug routes も operator routes も、**app-layer bearer auth なし**で動く shape になりました。
- `build_mcp_http_handler()` では `StreamableHttpEndpoint` の `auth_validator` を渡さない形へ変更しました。
- `runtime/http_handlers.py` の `__all__` も auth helper の export を外し、canonical HTTP handler surface のみを残しました。
- auth cleanup の途中で circular import が顕在化しました。
  - `runtime.introspection` が serializer を re-export していた旧前提と
  - `runtime.orchestration` / `runtime.server_responses` の import path
  が噛み合わず、`serialize_runtime_introspection_collection` import で循環が起きました。
- そのため:
  - `src/ctxledger/runtime/introspection.py` から serializer re-export を削除
  - `runtime.orchestration` は `serialize_runtime_introspection_collection` を canonical `runtime.serializers` から import
  - `runtime.server_responses.build_runtime_introspection_response()` も serializer を canonical module から import
  する形へ修正しました。
- これにより、auth cleanup で表面化した introspection/serializer import cycle は解消しました。
- `docker/docker-compose.auth.yml` は direct app-layer auth override としては廃止扱いにしました。
- 現在の内容は compatibility stub コメントのみで、deprecated であること、認証は `docker/docker-compose.small-auth.yml` 側の proxy layer でやるべきことを明記しています。
- `tests/test_config.py` から auth 設定前提のケースを削除・更新しました。
  - `minimum_valid_env()` から `CTXLEDGER_REQUIRE_AUTH` を削除
  - `settings.auth.is_enabled` assertion を削除
  - auth-required validation test 群を削除
- `tests/test_cli.py` から `AuthSettings` import と `AppSettings.auth` 生成を削除しました。
- `tests/test_mcp_modules.py` から `AuthSettings` import と `make_settings()` の auth args を削除しました。
- `tests/test_postgres_integration.py` の loaded settings fixture env から `CTXLEDGER_REQUIRE_AUTH` を削除しました。
- `tests/test_server.py` も追従しました。
  - top-level `AuthSettings` import を削除
  - `make_settings()` から `auth_bearer_token` / `require_auth` args を削除
  - `AppSettings.auth` 生成を削除
  - HTTP route の bearer auth 必須を確認していた test 群を削除
- これにより、server-side test suite から direct app auth 前提の coverage は除去されました。
- なお、generic streamable HTTP unit test にある `auth_validator` 使用テストは、`build_streamable_http_endpoint()` 自体の generic capability test として残っているだけで、`ctxledger` app-layer auth の存在を意味しません。
- README を proxy-only 前提へ更新しました。
  - config list から `CTXLEDGER_REQUIRE_AUTH` / `CTXLEDGER_AUTH_BEARER_TOKEN` を削除
  - direct app-layer authenticated smoke step を削除し、proxy-authenticated smoke step に置換
  - production guidance を proxy-layer authentication 前提に書き換え
  - security notes も proxy-layer bearer auth 前提へ修正
- `docs/SECURITY.md` を proxy-only auth model 前提へ書き換えました。
  - app-layer bearer auth 記述を削除
  - proxy-only authentication model を明示
  - config expectation を proxy/gateway secret 前提へ変更
  - local/shared/prod deployment recommendations を proxy-first shape へ更新
  - action routes / debug routes の保護境界も proxy-layer前提へ統一
- `docs/deployment.md` も proxy-only auth 前提へ更新しました。
  - recommended env vars から `CTXLEDGER_REQUIRE_AUTH` / `CTXLEDGER_AUTH_BEARER_TOKEN` を削除
  - environment guidance table を proxy-layer auth 前提へ変更
  - malformed authentication configuration 記述を削除
- `docs/CHANGELOG.md` の production guidance note も proxy-only auth 前提へ更新しました。
- この一連の変更により、**small pattern = proxy-only auth** が repo 全体でより一貫した形になっています。

large pattern documentation prep:
- `docs/plans/auth_proxy_scaling_plan.md` の large pattern section を改めて見直し、現時点では「実装」ではなく「比較観点と着手条件の整理」に留める方針が自然だと確認しました。
- roadmap 上、large pattern は **after roadmap `0.4`** の別フェーズであり、今すぐ compose や runtime に手を入れる対象ではありません。
- 現時点で large pattern に入る前提条件として重要なのは:
  - `docs/roadmap.md` 上の `0.4` 以後であること
  - proxy-layer auth だけで十分か、app-layer authorization / ownership / audit attribution が必要かを再評価すること
  - MCP-capable IDE client と non-browser auth flow の両立性を first-class に扱うこと
- candidate comparison の観点として、plan に既に書かれている以下が重要です:
  - `Pomerium`
  - `oauth2-proxy`
  - another OIDC-aware gateway
  - organization-standard identity gateway
- 現時点の整理としては:
  - `oauth2-proxy` は browser/cookie/redirect-heavy になりやすく、IDE UX との相性評価が必要
  - `Pomerium` は policy-friendly で multi-user internal tool には合いそう
  - ただし large pattern の最終選定は、client compatibility / operational fit / org standard の3軸で比較するのが自然
- 次に large pattern documentation prep を進めるなら、`docs/plans/` 配下に「candidate evaluation memo」や「decision matrix」を 1 枚追加し、
  - auth flow shape
  - IDE compatibility
  - identity propagation
  - operator complexity
  - future authorization extensibility
  の観点で比較整理するのがよさそうです。
- ただしこれは implementation 開始ではなく、phase gate を越える前の design prep として扱うべきです。

今回確認したテスト結果:
- `pytest -q tests/test_config.py tests/test_mcp_modules.py tests/test_cli.py`
- 結果: `44 passed`
- `pytest -q tests/test_server.py`
- 結果: `134 passed`
- `pytest -q`
- 結果: `246 passed`

今回確認した live Docker validation:
- previous confirmed small pattern validation は引き続き有効:
  - `docker compose -f docker/docker-compose.yml -f docker/docker-compose.small-auth.yml down --remove-orphans`
  - `CTXLEDGER_SMALL_AUTH_TOKEN=smoke-small-secret docker compose -f docker/docker-compose.yml -f docker/docker-compose.small-auth.yml up -d --build --force-recreate`
  - 結果:
    - `ctxledger-postgres` healthy
    - `ctxledger-auth-small` healthy
    - `ctxledger-server-private` healthy
    - `ctxledger-traefik` healthy
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
  - `289d700` — `Fix small auth Traefik healthcheck`
- large pattern documentation prep:
  - `0c7eec6` — `Document large auth readiness criteria`

現時点での設計メモ:
- small pattern は app-layer auth の強化ではなく、proxy-layer auth への移行としてかなり自然に成立しています。
- `ctxledger-private` を別 service 名で定義したことで、base compose の published `ctxledger` と衝突せず、private backend topology を Compose 上で表現できました。
- Traefik はこの環境では Docker provider より file provider の方が安定でした。
- `docker/traefik/dynamic.yml` を使う方が、small pattern の route/middleware/service 関係を明示しやすく、debug もしやすいです。
- proxy で守る endpoint 範囲として `/mcp` だけでなく `/debug/*`、`/workflow-resume/*`、projection failure endpoints も揃えて保護する形にしています。
- smoke script の rejection mode は、JSON-RPC error object を前提にせず transport-level 401 を確認する方が proxy auth には適切です。
- small pattern deliverable D の smoke validation は、missing token / invalid token / valid token の 3 系統まで live Docker 上で確認済みです。
- small pattern の documented proxy port は `8091` です。default local direct app port `8080` とは分けて扱う前提です。
- README / SECURITY / deployment docs / small auth compose は、現在 proxy-only auth model にかなり揃ってきています。
- **server.py 側だけでなく、config/runtime HTTP handlers からも app-layer auth は削除済み**です。
- 現在の auth 境界は、documented deployment path 上では proxy layer のみです。
- `ctxledger` 本体には multi-user authorization / tenant isolation / per-user ownership は依然としてありません。
- large pattern を始める前には、identity-aware gateway 選定だけでなく downstream authorization semantics の要否判断もセットで扱うべきです。

次セッションで優先してやること:
1. proxy-only auth cleanup の最終確認
   - `README.md`
   - `docs/SECURITY.md`
   - `docs/deployment.md`
   - `docker/docker-compose.auth.yml`
   - `last_session.md`
2. 可能なら small-pattern smoke をもう一度回して、docs cleanup 後も operator path が変わっていないことを確認する
3. 問題なければ proxy-only auth cleanup を descriptive commit にまとめる
   - 例: `Remove app-layer HTTP auth in favor of proxy auth`
4. large pattern documentation prep はその次
   - candidate evaluation memo / decision matrix 追加
5. large pattern 実装そのものはまだ始めない
6. large pattern 着手時には、proxy-layer auth だけで十分か、app-layer authorization / ownership / audit attribution が必要かを再評価する