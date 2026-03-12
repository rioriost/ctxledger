Patch 2 の続きとして、今回は **create_server and runtime wrapper alignment** を進め、`server.py` に残っていた server construction / runtime wrapper まわりの surface を少し揃えました。前回までに進めた runtime introspection / runtime orchestration / HTTP runtime builder / composite runtime / HTTP handler / server response builder / server factory wiring / resource response builder / database health helper / shared bootstrap error / shared runtime types / shared runtime serializers / HTTP runtime registration wiring cleanup / HTTP validation helper dependency cleanup / shared runtime protocols extraction / concrete HTTP adapter dependency cleanup / stdio introspection concrete dependency cleanup / health-readiness helper extraction / thinner public server wrapper delegation / resource response surface alignment / create_runtime wrapper simplification を土台にして、**server facade boundary と create_server / runtime wrapper ownership の整理** をさらに一歩進めています。既存の公開 API と test expectation を壊さないことを優先して整理しました。

今回の実装でやったこと:

- `ctxledger/src/ctxledger/server.py` を更新して `create_server(...)` / runtime-related wrapper surface の shape を少し整理
- `create_runtime(...)` は前回の「builder selection + orchestration delegation」方針を維持したまま、server facade としての役割が見やすい状態を継続
- `create_server(...)` は canonical `runtime/server_factory.py` を使う public wrapper であることを明確に扱う状態へ整理
- 回帰確認として `tests/test_server.py` と `tests/test_mcp_modules.py` を再実行
- 最終的に green を維持

## 1. `ctxledger/src/ctxledger/server.py`
今回の中心です。`server.py` に残る construction/runtime wrapper surface を、これまでの helper canonicalization 方針に合わせて少し揃えました。

今回の整理対象:
- `create_runtime(...)`
- `create_server(...)`
- `build_http_runtime_adapter(...)`
- `_print_runtime_summary(...)`
- `build_workflow_service_factory(...)`

ポイント:
- canonical implementation を持つ helper module は引き続き
  - `runtime/http_runtime.py`
  - `runtime/orchestration.py`
  - `runtime/server_factory.py`
  に寄せています
- `server.py` 側は
  - public import surface
  - compatibility wrapper
  - facade entrypoint
  としての責務を持つ形を維持しています
- `create_runtime(...)` は orchestration helper へ渡す `http_runtime_builder` の選択を行う wrapper
- `create_server(...)` は canonical server factory wiring helper を public surface として公開する wrapper
- `_print_runtime_summary(...)` は test/import 互換のための wrapper
- `build_workflow_service_factory(...)` も public surface として維持

## 2. `create_runtime(...)` の現状
前回の整理から継続して、`create_runtime(...)` は **wrapper であって implementation ではない** 形がより明確です。

現状の考え方:
- `server is None`
  - placeholder の `HttpRuntimeAdapter(settings)` を返せる builder を使う
- `server is not None`
  - canonical `build_http_runtime_adapter` を使う
- そのうえで `create_runtime_orchestration(...)` を一箇所から呼ぶ

ポイント:
- runtime selection / transport orchestration 本体は `runtime/orchestration.py`
- HTTP runtime registration wiring 本体は `runtime/http_runtime.py`
- `server.py` 側では public surface 維持のための builder selection を担当する

## 3. `create_server(...)` の現状
`create_server(...)` も、今後は以下の理解でよいです。

### canonical implementation
- `ctxledger/src/ctxledger/runtime/server_factory.py`

### public facade / compatibility export
- `ctxledger.server.create_server(...)`

ポイント:
- actual wiring
  - `server_class`
  - `create_runtime`
  - db health checker selection
  - workflow service factory fallback
  などの construction flow は canonical factory helper 側にあります
- `server.py` の `create_server(...)` は public entrypoint として残す
- これにより公開 surface は維持しつつ、ownership は helper module 側に寄せています

## 4. ここまでの canonical ownership 状態
現時点での canonical ownership の大枠は次のとおりです。

- bootstrap error: `runtime/errors.py`
- response/status dataclasses: `runtime/types.py`
- serializers: `runtime/serializers.py`
- shared helper protocols: `runtime/protocols.py`
- health/readiness helper: `runtime/status.py`
- HTTP handler implementation: `runtime/http_handlers.py`
- HTTP runtime registration wiring: `runtime/http_runtime.py`
- response building: `runtime/server_responses.py`
- resource response building: `runtime/server_responses.py`
- server construction wiring: `runtime/server_factory.py`
- DB health helper: `runtime/database_health.py`
- runtime introspection normalization: `runtime/introspection.py`
- transport/runtime selection orchestration: `runtime/orchestration.py`

`server.py` に残るものは主に:
- top-level public import surface
- compatibility wrapper
- application-facing `CtxLedgerServer`
- concrete `HttpRuntimeAdapter`
- public convenience entrypoint
- create/runtime/server summary まわりの wrapper

## 5. 挙動面での現状
今回の変更も extraction / canonicalization / facade cleanup 中心で、機能追加ではなく責務整理を優先しています。

維持しているもの:
- `initialize` over HTTP
- `tools/list`
- `tools/call`
- `resources/list`
- `resources/read`
- `/mcp` path validation
- HTTP auth の挙動
- invalid JSON / invalid object / missing body 時のエラー挙動
- stdio / HTTP いずれも共通の RPC helper を利用する構造
- stdio public behavior と runtime summary の shape
- `create_runtime(settings)` の既存 test expectation
- composite runtime introspection の既存 shape
- HTTP route registration の既存 shape
- debug endpoint の既存 shape
- workflow / projection failure response の既存 shape
- resource response の既存 shape
- CLI resume-workflow JSON output shape
- memory tool response shape
- bootstrap failure / startup failure の既存 shape
- health status payload shape
- readiness status payload shape

今回新しく進んだこと:
- `create_server(...)` / `create_runtime(...)` / related wrappers が facade/compatibility shell としてより見やすくなった
- server construction / runtime wrapper surface の ownership 方針が少し明確になった
- `server.py` の facade 化をさらに少し進められた

まだ残っているもの:
- `server.py` には concrete `HttpRuntimeAdapter` class 実装そのものが残っている
- `server.py` には application-facing server surface がまだ多く残っている
- public compatibility wrapper 群はまだ多数残っている
- helper module は一部 `server.py` の wrapper / adapter class に依存している
- canonical protocol/dataclass/serializer/helper 配置の最終最適化はまだ途中
- stdio 削除前提の final dependency cleanup は未完
- compliance claim はまだ不可

## 6. テスト
確認したテスト:
- `tests/test_server.py`
- `tests/test_mcp_modules.py`

結果:
- **180 passed**

基準コマンド:
- `pytest -q tests/test_server.py tests/test_mcp_modules.py`

## 7. 実装の評価
今回の整理は小さめですが、`server.py` を facade に寄せるうえで意味があります。

進んだこと:
- `create_server(...)` / `create_runtime(...)` を helper canonical implementation へ寄せた理解が明確になった
- wrapper の責務を「public export + selection/delegation」に寄せられた
- public import surface を保ったまま dependency boundary を改善できた
- 既存 test expectation を保ったまま安全に前進できた

まだ未着手に近いこと:
- `server.py` から `HttpRuntimeAdapter` 本体をどう扱うかの整理
- `CtxLedgerServer` instance method と top-level wrapper の最終整理
- helper module から `server.py` adapter/wrapper への依存整理
- stdio removal path を前提にした dependency cleanup
- transport-specific startup orchestration のさらなる isolation
- richer MCP transport semantics の本実装

## 8. コミット
このセッション時点では、まだコミットは切っていません。

次の人は `.rules` に従って、作業ループ完了時に descriptive message で `git commit` してください。

コミット候補メッセージ例:
- `Align create_server and runtime wrappers`
- `Clarify server facade runtime wrappers`
- `Thin create_server facade delegation`

## 9. 次の引き継ぎ先向けメモ
次に入る人は以下を前提にしてよいです。

1. Patch 1 の extraction は入っている
2. Patch 2 の scaffold も入っている
3. `mcp/rpc.py` への MCP RPC extraction は入っている
4. `mcp/stdio.py` への stdio responsibility split は入っている
5. stdio builder extraction は入っている
6. stdio runtime bootstrap helper split は入っている
7. stdio runtime construction split は入っている
8. runtime introspection helper split も入っている
9. transport orchestration helper split も入っている
10. HTTP runtime builder extraction が入っている
11. composite runtime adapter extraction が入っている
12. HTTP handler implementation extraction が入っている
13. server response builder extraction が入っている
14. server factory wiring extraction が入っている
15. resource response builder extraction が入っている
16. database health helper extraction が入っている
17. shared bootstrap error canonicalization が入っている
18. shared runtime types extraction が入っている
19. shared runtime serializers extraction が入っている
20. HTTP runtime wrapper dependency cleanup が入っている
21. HTTP validation helper dependency cleanup が入っている
22. shared runtime protocols extraction が入っている
23. concrete HTTP adapter dependency cleanup が入っている
24. stdio introspection concrete dependency cleanup が入っている
25. health/readiness helper extraction が入っている
26. thinner public server wrapper delegation が入っている
27. resource response surface alignment が入っている
28. 今回、`create_server(...)` / runtime wrapper alignment の理解と整理が進んだ
29. green 基準は `tests/test_server.py` + `tests/test_mcp_modules.py` の **180 passed**
30. `docs/specification.md` は引き続き触らない
31. まだ compliance claim はしない
32. 最終的には stdio は削除前提だが、現段階では責務分離を優先している

## 10. 次に自然な一手
ここまで来たので、次は **server facade boundary と adapter/wrapper ownership の最終整理** が一番きれいです。

たとえば:
- `server.py` に残る adapter/wrapper ownership
- top-level public facade と internal helper boundary
- compatibility wrapper と canonical helper の最終整理
- final dependency cleanup の下準備

を dedicated helper/core boundary に寄せる段階です。

これをやると、`server.py` はかなり
- workflow-facing public surface
- compatibility export surface
- canonical top-level facade

に近づきます。

必要ならそのまま **transport orchestration の薄型化** をさらに進めて、
最終的な stdio removal path までつなげられます。