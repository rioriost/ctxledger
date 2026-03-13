このプロジェクトでは、Docker コンテナで動作する remote MCP サーバを HTTP 専用で提供しています。

現在の repository posture:
- HTTP `/mcp` に対する最小 MCP 経路として `initialize` / `tools/list` / `tools/call` を実装済みです。
- 追加で HTTP 側の `resources/list` / `resources/read` も実装済みで、workflow 系 resources も live Docker 上で確認済みです。
- stdio MCP サーバの残骸は削除済みで、HTTP 専用 shape に寄せています。
- `server.py` 依存の縮小、HTTP runtime adapter の canonical module への移動、debug/runtime introspection の serializer 整理など、HTTP-only cleanup の大きな pruning は完了済みです。

HTTP/runtime cleanup の current state:
- `HttpRuntimeAdapter` は `src/ctxledger/runtime/http_runtime.py` に移動済みです。
- `src/ctxledger/server.py` の public surface は `CtxLedgerServer` / `create_server` / `run_server` のみに縮小済みです。
- response DTO や introspection serializer の canonical import path への整理も完了しています。
- route registry naming は `registered_routes()` ではなく `introspection_endpoints()` に統一済みです。

proxy-only auth cleanup の current state:
- `src/ctxledger/config.py` から app-layer auth 設定を削除済みです。
  - `AuthSettings`
  - `AppSettings.auth`
  - `CTXLEDGER_REQUIRE_AUTH`
  - `CTXLEDGER_AUTH_BEARER_TOKEN`
- `src/ctxledger/runtime/http_handlers.py` から app-layer bearer auth helper を削除済みです。
- その結果、`ctxledger` 本体は documented deployment path 上では app-layer bearer auth を持たず、認証境界は proxy layer のみです。
- `docker/docker-compose.auth.yml` は deprecated compatibility stub のみになっています。
- `docker/docker-compose.yml` と `docker/docker-compose.small-auth.yml` から deprecated direct-backend auth env の残骸も除去済みです。

small pattern の current state:
- `Traefik -> auth-small -> private ctxledger backend -> PostgreSQL` の small pattern は実装済みです。
- 主要 artifact:
  - `docker/docker-compose.small-auth.yml`
  - `docker/traefik/dynamic.yml`
  - `docker/auth_small/src/auth_small_app.py`
  - `scripts/mcp_http_smoke.py`
- `docs/small_auth_operator_runbook.md` を追加済みで、startup / reject-allow smoke / shutdown / common failure modes をまとめています。
- documented proxy port は `8091` です。
- `ctxledger-private` は host port 非公開、`traefik` が唯一の公開 entrypoint です。

small pattern の latest live validation:
- overlay stack 起動後、以下を確認済みです。
  - `ctxledger-postgres` healthy
  - `ctxledger-auth-small` healthy
  - `ctxledger-server-private` healthy
  - `ctxledger-traefik` healthy
- missing token path:
  - `401`
  - `error: missing_bearer_token`
- invalid token path:
  - `401`
  - `error: invalid_bearer_token`
- valid token path:
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
  を live Docker 上で再確認済みです。

large pattern documentation prep の current state:
- `docs/plans/auth_proxy_scaling_plan.md` で、large pattern は **after roadmap `0.4`** の deferred phase という整理です。
- `docs/plans/auth_large_gateway_evaluation_memo.md` を追加済みです。
  - `Pomerium`
  - `oauth2-proxy`
  - other OIDC-aware gateway
  - organization-standard gateway
  の比較観点を整理しています。
- 同 memo に weighted scoring rubric を追加済みです。
  - MCP IDE compatibility = `5`
  - identity quality = `4`
  - operational fit = `4`
  - identity propagation readiness = `3`
  - authorization extensibility = `3`
  - architecture alignment = `4`
  - organization-standard alignment = `2`
- `docs/plans/auth_large_gateway_decision_record_template.md` を追加済みです。
- `docs/plans/auth_large_gateway_shortlist_example.md` を追加済みで、provisional な example scorecard / mock shortlist を記録しています。
  - example ranking:
    - `Pomerium`
    - organization-standard gateway
    - `oauth2-proxy`
    - other OIDC-aware gateway
- ただし large pattern はまだ実装開始ではなく、design-prep material の段階です。

docs/navigation の current state:
- `README.md` の Documentation Index に auth/deployment guidance への導線を追加済みです。
- `docs/plans/auth_planning_index.md` を追加済みです。
- `docs/CONTRIBUTING.md` を実質的な contributor guide に拡張済みです。
- `docs/plans/mcp_planning_index.md` から `docs/plans/auth_planning_index.md` への参照も追加済みです。

テストの current state:
- 通常状態では `pytest -q` は `246 passed` です。
- `tests/test_config.py` / `tests/test_mcp_modules.py` / `tests/test_cli.py` / `tests/test_server.py` は `178 passed` を確認済みです。
- 注意点:
  - small-pattern live Docker validation の直後に full `pytest -q` を流すと、`tests/test_postgres_integration.py` の integration fixture と live Docker state が干渉して失敗することがあります。
  - recovery 手順は:
    - `docker compose -f docker/docker-compose.yml -f docker/docker-compose.small-auth.yml down --remove-orphans`
    - その後に `pytest -q`
  です。

現在の直近コミット群:
- `420a057` — `Add large auth gateway evaluation memo`
- `66f4b7b` — `Align docs with proxy-only auth model`
- `b7fc5aa` — `Refine proxy auth wording in API docs`
- `dd64ba9` — `Align specification with proxy auth model`
- `b967a7f` — `Add small auth operator runbook`
- `1a3fa92` — `Remove deprecated auth envs from compose`
- `76bfe6f` — `Record small auth revalidation results`
- `8cf8cbe` — `Add large auth gateway decision template`
- `4b1b261` — `Add auth planning index and contributing guide`
- `b8bd514` — `Document auth planning navigation and test recovery`
- `33d5db1` — `Add large auth gateway shortlist example`
- `9381a1e` — `Link large auth shortlist example in docs`

次 session で自然な候補:
1. large-pattern design prep をさらに進める
   - shortlist example を actual decision record へ橋渡しする運用整理
2. 別 stream に戻る
   - MCP transport / compliance
   - workflow / memory
   - remaining code cleanup
3. small-pattern live validation を再実行する場合は、終了後に overlay stack を落としてから full test suite を回す