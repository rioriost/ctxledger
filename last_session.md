Final HTTP acceptance and stdio removal closeout note.

このセッションでは、これまで進めてきた stdio removal と HTTP-only migration の流れを、**closeout 前提の最終整理**としてまとめます。  
結論から言うと、**stdio removal 自体は実質完了**であり、現時点の主要論点は実装ではなく **`v0.1.0` acceptance boundary の表現整理** にあります。

## 1. 現在の状態の要約

現時点の project state は次のように整理してよいです。

- active transport semantics は **HTTP-only**
- active MCP entry surface は **`/mcp`**
- stdio concrete implementation は **source tree から削除済み**
- public façade / runtime helper / config / CLI / main tests は **HTTP-only semantics に整合**
- primary docs / env examples も **概ね HTTP-only wording に整合**
- project-wide baseline は **green**

言い換えると:

- **stdio removal itself is effectively complete**
- **HTTP-only semantics are the active project state**
- remaining work is mainly
  - acceptance wording
  - release-evidence framing
  - optional broader HTTP MCP proof

## 2. patch progression の最終整理

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
- `.env.example`
- `.env.production.example`
  から `CTXLEDGER_ENABLE_STDIO=false` を削除
- baseline は引き続き **204 passed**

### final verification
- focused baseline:
  - `tests/test_config.py`
  - `tests/test_server.py`
  - `tests/test_mcp_modules.py`
  - `tests/test_cli.py`
  - `tests/test_postgres_integration.py`
  - **204 passed**
- project-wide baseline:
  - `pytest -q`
  - **256 passed**

## 3. confirmed baseline

### focused verification baseline
- `tests/test_config.py`
- `tests/test_server.py`
- `tests/test_mcp_modules.py`
- `tests/test_cli.py`
- `tests/test_postgres_integration.py`
- **204 passed**

この baseline は少なくとも次を示す基準として扱ってよいです。

- config semantics が HTTP-only で成立
- server/runtime façade が HTTP-only に寄っている
- MCP module behavior が HTTP-only runtime shape と整合
- CLI surface が HTTP-only
- PostgreSQL integration でも stale stdio env 前提が除去済み

### final project-wide verification baseline
- `pytest -q`
- **256 passed**

この project-wide baseline により、現時点では:

- stdio removal に伴う主要な regression は見えていない
- focused migration area だけでなく repository 全体でも green を確認済み
- handoff / closeout 時点の confidence は高い

## 4. 現在の architecture / transport interpretation

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

## 5. すでに整合しているもの

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

### config/example artifacts updated
- `.env.example`
- `.env.production.example`

## 6. stdio removal closeout judgement

現時点では次のように表現してよいです。

- **stdio removal itself is effectively complete**
- **HTTP-only semantics are the active project state**
- **major verification baselines are green**

より具体的には:

1. stdio concrete implementation は削除済み
2. stdio public/runtime surface は除去済み
3. config / orchestration / façade / helper layers は HTTP-only
4. tests は focused baseline / project-wide baseline ともに green
5. docs / env examples も主要面は HTTP-only に追従済み

したがって、今後の残作業は「stdio を消せるか」ではなく、「closeout をどう記述するか」の問題です。

## 7. current open question

現時点の中心的な open question は stdio ではありません。

いまの中心は:

**already-proven minimal HTTP MCP path at `/mcp` が `v0.1.0` acceptance として十分か、それとも broader HTTP MCP surface proof が必要か**

という点です。

現時点で強く言えること:

- `/mcp` の minimal HTTP MCP path は repository evidence 上かなり強い
  - `initialize`
  - `tools/list`
  - `tools/call`
- workflow tool surface と tool schema publication は HTTP 側で成立している
- release evidence は stdio-side maturity ではなく HTTP-side acceptance を中心に組み立てるべき

もし追加で詰めるなら、焦点は次です。

- `resources/list`
- `resources/read`
- broader MCP coverage
- acceptance matrix

## 8. recommended final framing

現時点の closeout wording としては、次の表現が自然です。

### implementation conclusion
- stdio removal is effectively complete
- the repository now operates with HTTP-only transport semantics
- the active MCP surface is `/mcp`

### verification conclusion
- focused migration baseline: **204 passed**
- project-wide baseline: **256 passed**

### release evidence conclusion
- the minimal HTTP MCP path is proven:
  - `initialize`
  - `tools/list`
  - `tools/call`
- broader HTTP MCP surface proof remains a release-framing question, not a stdio-removal blocker

## 9. remaining optional follow-up

もし最後にさらにやるなら、実装変更というより次の整理です。

1. historical docs の residual wording sweep
   - `docs/workflow-model.md`
   - `docs/memory-model.md`
   - `docs/design-principles.md`
   - `docs/roadmap.md`

2. acceptance boundary memo の明文化
   - minimal HTTP MCP path confirmed
   - broader HTTP MCP coverage status
   - resource coverage status

3. release note / closeout note の最終整理

## 10. handoff conclusion

次に入る人は、次を前提にしてよいです。

- stdio concrete implementation は削除済み
- active transport semantics は HTTP-only
- primary source / tests / docs / env examples は概ね HTTP-only に整合
- focused baseline は **204 passed**
- project-wide baseline は **256 passed**
- stdio removal itself is **effectively complete**
- remaining work is mostly
  - residual historical docs cleanup
  - final release-evidence framing
  - optional broader HTTP MCP proof
- `docs/specification.md` は引き続き触らない
- まだ compliance claim はしない

## 11. suggested final commit message candidates

もし最後の acceptance framing / historical docs sweep を進める場合の commit 候補例:

- `Finish final stdio residual sweep`
- `Complete HTTP-only stdio removal cleanup`
- `Finalize stdio removal documentation and verification`
- `Clarify final HTTP MCP acceptance boundary`
