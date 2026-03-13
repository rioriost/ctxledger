final HTTP-only sweep の続きとして、今回は **session handoff 用に最終状態を簡潔に記録するメモ** を残します。patch 1A の config/orchestration HTTP-only 化、patch 1B の server/module/CLI cleanup、patch 1C の legacy stdio module 削除、patch 1D の protocol/introspection/docs cleanup、patch 1E の planning/review docs 整理を土台にして、現時点では **stdio removal は実質完了、残りは final acceptance framing と必要なら broader MCP proof の整理** という段階です。

このセッション終端で引き継ぐべき要点:

- active runtime / transport semantics は HTTP-only
- stdio concrete implementation は source tree から削除済み
- main source / tests / primary docs は HTTP-only wording と behavior にほぼ整合
- review / implementation-plan docs もかなり HTTP-only 現状へ寄せた
- 直近の確認済み baseline は:
  - `tests/test_config.py`
  - `tests/test_server.py`
  - `tests/test_mcp_modules.py`
  - `tests/test_cli.py`
  - `tests/test_postgres_integration.py`
  - **204 passed**
- 現在の open question は stdio removal そのものではなく、
  - minimal HTTP MCP path で `v0.1.0` acceptance として十分か
  - `resources/list` / `resources/read` など broader HTTP MCP surface proof が必要か
  の整理

## 1. patch progression の最終整理

### patch 1A
- `src/ctxledger/config.py` を HTTP-only semantics に変更
- `src/ctxledger/runtime/orchestration.py` を HTTP-only semantics に変更
- `tests/test_config.py` を追従
- `tests/test_config.py` は **21 passed**

### patch 1B
- `server.py` から stdio-related import/export surface を除去
- `runtime/status.py` の `settings.stdio` 参照を除去
- `runtime/http_runtime.py` の stdio builder 依存を除去
- CLI transport choices を HTTP-only に更新
- `tests/test_server.py`
- `tests/test_mcp_modules.py`
- `tests/test_cli.py`
  を HTTP-only semantics に追従
- これらは **167 passed**

### patch 1C
- `src/ctxledger/mcp/stdio.py` を削除
- `tests/test_postgres_integration.py` から `CTXLEDGER_ENABLE_STDIO` を削除
- `tests/test_server.py` に残っていた stdio introspection example を削除
- 追加確認で **183 passed**
- `tests/test_config.py` を合わせて **204 passed**

### patch 1D
- `runtime/protocols.py` から stdio-only protocol type を削除
- `runtime/introspection.py` から stdio-like fallback path を削除
- `server.py` docstring を HTTP-only wording に更新
- `README.md`
- `docs/CHANGELOG.md`
- `docs/architecture.md`
- `docs/deployment.md`
- `docs/SECURITY.md`
  を HTTP-only wording に寄せた
- baseline は **204 passed** を維持

### patch 1E
- `docs/imple_plan_0.1.0.md` を HTTP-only runtime direction に寄せた
- `docs/imple_plan_review_0.1.0.md` の review narrative を HTTP-only 現状に合わせて整理
- `docs/mcp-api.md` の stdio-centric explanation をかなり除去
- baseline は引き続き **204 passed**

## 2. confirmed baseline

現時点で handoff 向けに明示してよい baseline:

- `tests/test_config.py`
- `tests/test_server.py`
- `tests/test_mcp_modules.py`
- `tests/test_cli.py`
- `tests/test_postgres_integration.py`
- **204 passed**

この baseline は少なくとも次を示す基準として扱ってよいです:

- config semantics が HTTP-only で成立
- server/runtime façade が HTTP-only に寄っている
- MCP module behavior が HTTP-only runtime shape と整合
- CLI surface が HTTP-only
- PostgreSQL integration でも stale stdio env 前提が除去済み

## 3. 現在の architecture / transport interpretation

### active transport
- `http` のみ

### active MCP entry surface
- `/mcp`

### active runtime ownership
- HTTP runtime adapter が MCP tool listing / tool dispatch / runtime introspection を担う
- stdio transport は active implementation surface ではない
- stdio concrete module は source tree から削除済み

### current canonical ownership
- bootstrap error: `runtime/errors.py`
- response/status dataclasses: `runtime/types.py`
- serializers: `runtime/serializers.py`
- shared helper protocols: `runtime/protocols.py`
- health/readiness helper: `runtime/status.py`
- HTTP handler implementation: `runtime/http_handlers.py`
- HTTP runtime registration wiring: `runtime/http_runtime.py`
- response/resource response implementation: `runtime/server_responses.py`
- server construction wiring: `runtime/server_factory.py`
- DB health helper: `runtime/database_health.py`
- runtime introspection normalization: `runtime/introspection.py`
- transport/runtime selection orchestration: `runtime/orchestration.py`

## 4. すでに整合しているもの

### source
- `src/ctxledger/config.py`
- `src/ctxledger/runtime/orchestration.py`
- `src/ctxledger/runtime/status.py`
- `src/ctxledger/runtime/http_runtime.py`
- `src/ctxledger/runtime/introspection.py`
- `src/ctxledger/runtime/protocols.py`
- `src/ctxledger/server.py`
- `src/ctxledger/__init__.py`

### tests
- `tests/test_config.py`
- `tests/test_server.py`
- `tests/test_mcp_modules.py`
- `tests/test_cli.py`
- `tests/test_postgres_integration.py`

### docs already substantially updated
- `README.md`
- `docs/CHANGELOG.md`
- `docs/architecture.md`
- `docs/deployment.md`
- `docs/SECURITY.md`
- `docs/imple_plan_0.1.0.md`
- `docs/imple_plan_review_0.1.0.md`
- `docs/mcp-api.md`

## 5. まだ見てよい final sweep 対象

source / main tests の stdio removal はかなり終わっています。ここから見る価値があるのは主に residual docs と final acceptance framing です。

### likely residual historical docs
- `docs/workflow-model.md`
- `docs/memory-model.md`
- `docs/design-principles.md`
- `docs/roadmap.md`

### config/example artifacts
- `.env.example`
- `.env.production.example`

### possible residual wording categories
- historical “stdio support”
- old config vars such as `CTXLEDGER_ENABLE_STDIO`
- transport enum references such as `TransportMode.STDIO` / `TransportMode.BOTH`
- wording that implies “dual transport is current state”
- startup summary references like `stdio_transport=enabled`

## 6. practical interpretation of remaining work

ここから先はもう大きな transport refactor ではなく、主に:

1. residual wording sweep
2. example/config alignment check
3. final project-wide verification
4. completion memo synthesis

が中心です。

つまり整理としては:

- source-level removal はほぼ完了
- behavior-level migration も主要面は完了
- 残タスクは mostly documentation / evidence / verification
- 「stdio removal ができるか」ではなく「どこまで final closeout evidence を整えるか」の段階

## 7. current open question

現時点の中心的な open question はもう stdio ではありません。

いまの中心は:

**already-proven minimal HTTP MCP path at `/mcp` が `v0.1.0` acceptance として十分か、それとも broader HTTP MCP surface proof が必要か**

という点です。

現時点で強く言えること:

- `/mcp` の minimal HTTP MCP path は repository evidence 上かなり強い
  - `initialize`
  - `tools/list`
  - `tools/call`
- workflow tool surface と tool schema publication は HTTP 側で成立している
- release evidence はもう stdio-side maturity ではなく HTTP-side acceptance を中心に組み立てるべき
- もし追加で詰めるなら、焦点は:
  - `resources/list`
  - `resources/read`
  - broader MCP coverage
  - acceptance matrix
  のどこまでを `v0.1.0` closeout に含めるか

## 8. next natural work items

### patch 1F / final acceptance & verification sweep
1. project-wide で residual
   - `stdio`
   - `CTXLEDGER_ENABLE_STDIO`
   - `TransportMode.STDIO`
   - `TransportMode.BOTH`
   を最終探索
2. `docs/workflow-model.md`, `docs/memory-model.md`, `docs/design-principles.md`, `docs/roadmap.md` の residual wording を必要なら更新
3. `.env.example` / `.env.production.example` の実内容が README examples と一致しているか最終確認
4. 可能なら project-wide test run で final baseline を確定
5. `v0.1.0` acceptance boundary を短く整理
   - minimal HTTP MCP path confirmed
   - broader HTTP MCP coverage status
   - resource coverage status
6. stdio removal 完了判定メモを `last_session.md` に残す

## 9. conclusions for handoff

今回の handoff 向け結論:

- stdio removal は **final closeout / verification phase** に入っている
- active runtime / transport semantics は HTTP-only
- stdio concrete implementation は source tree から削除済み
- public façade / helper layers / main docs もかなり HTTP-only に整理済み
- major verified baseline は **204 passed**
- remaining work is primarily:
  - historical/residual docs cleanup
  - example/env alignment
  - final release-evidence framing
  - optional broader HTTP MCP proof
- `docs/specification.md` は引き続き触らない
- まだ compliance claim はしない

## 10. suggested commit message candidates for the next loop

次ループで final sweep や closeout note まで進んだ場合の commit 候補例:

- `Finish final stdio residual sweep`
- `Complete HTTP-only stdio removal cleanup`
- `Finalize stdio removal documentation and verification`
- `Clarify final HTTP MCP acceptance boundary`
