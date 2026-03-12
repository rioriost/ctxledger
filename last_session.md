Patch 2 の続きとして、今回は **facade wrapper alignment step** を進め、`server.py` に残っていた public facade / compatibility wrapper 群の並び方をさらに揃えました。前回までに進めた runtime introspection / runtime orchestration / HTTP runtime builder / composite runtime / HTTP handler / server response builder / server factory wiring / resource response builder / database health helper / shared bootstrap error / shared runtime types / shared runtime serializers / HTTP runtime registration wiring cleanup / HTTP validation helper dependency cleanup / shared runtime protocols extraction / concrete HTTP adapter dependency cleanup / stdio introspection concrete dependency cleanup / health-readiness helper extraction / thinner public server wrapper delegation / resource response surface alignment / create_runtime wrapper simplification / create_server and runtime wrapper alignment を土台にして、**`server.py` をより明確な top-level facade / compatibility shell に寄せる小さな整列** を実施しています。既存の公開 API と test expectation を壊さないことを優先して整理しました。

今回の実装でやったこと:

- `ctxledger/src/ctxledger/server.py` を更新して facade wrapper 群の役割をさらに揃えた
- `CtxLedgerServer.build_workspace_resume_resource_response(...)`
- `CtxLedgerServer.build_workflow_detail_resource_response(...)`
を top-level wrapper 経由に寄せ、resource surface も response surface と同じ考え方にした
- `create_runtime(...)` を builder selection + orchestration delegation の形で維持しつつ、wrapper としての shape をわかりやすく保った
- `create_server(...)` / `build_http_runtime_adapter(...)` / `build_workflow_service_factory(...)` / `_print_runtime_summary(...)`
などを含め、`server.py` 側は implementation ownership ではなく public facade である前提をさらに明確にした
- 回帰確認として `tests/test_server.py` と `tests/test_mcp_modules.py` を再実行
- 最終的に green を維持

## 1. 今回の要点
今回の整理は新しい canonical module を増やすよりも、**既に外へ出した canonical helper 群に対して `server.py` の wrapper surface を揃える** ことが中心です。

方針:
- implementation は helper module 側
- `server.py` は public surface と compatibility export
- dual surface がある場合は
  - top-level free function wrapper
  - `CtxLedgerServer` instance method
  のどちらも残してよい
- ただし ownership は helper module 側
- method ↔ wrapper の相互参照は避ける
- 可能な限り canonical helper 直 delegate に寄せる

## 2. `ctxledger/src/ctxledger/server.py`
今回の主な作業対象です。

整理した観点:
- response-related public wrapper
- resource-related public wrapper
- runtime construction wrapper
- server construction wrapper
- summary / helper export wrapper

### response/resource surface
前回までに:
- `runtime/server_responses.py` が canonical implementation
- `server.py` の top-level `build_*`
- `CtxLedgerServer.build_*`

が public surface という整理が進んでいました。

今回さらに揃えたこと:
- resource response 側も response-related helper と同じ考え方で整理
- `CtxLedgerServer.build_workspace_resume_resource_response(...)`
- `CtxLedgerServer.build_workflow_detail_resource_response(...)`
も facade method として扱い、canonical helper に寄せた
- top-level wrapper 群も helper canonical implementation を前提に見られる形を維持

### runtime/server wrapper surface
今回の確認ポイント:
- `create_runtime(...)` は orchestration 実装本体ではない
- `create_server(...)` は construction wiring 実装本体ではない
- `build_http_runtime_adapter(...)` は HTTP runtime registration 実装本体ではない
- `_print_runtime_summary(...)` は summary 実装本体ではない

これらはすべて:
- public import compatibility
- test/import surface 維持
- facade entrypoint

として残っていると見てよいです。

## 3. 現時点の canonical ownership
ここまでの整理込みで、今の ownership は次の理解でよいです。

- bootstrap error: `runtime/errors.py`
- response/status dataclass: `runtime/types.py`
- serializer: `runtime/serializers.py`
- shared helper protocol: `runtime/protocols.py`
- health/readiness helper: `runtime/status.py`
- HTTP handler implementation: `runtime/http_handlers.py`
- HTTP runtime route registration wiring: `runtime/http_runtime.py`
- server/resource response implementation: `runtime/server_responses.py`
- server construction wiring: `runtime/server_factory.py`
- DB health helper: `runtime/database_health.py`
- runtime introspection normalization: `runtime/introspection.py`
- transport/runtime selection orchestration: `runtime/orchestration.py`

`server.py` に主に残るもの:
- application-facing `CtxLedgerServer`
- concrete `HttpRuntimeAdapter`
- top-level public import surface
- compatibility wrapper
- convenience facade entrypoint

## 4. 挙動面での現状
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
- `server.py` facade / compatibility shell の見通しが少し良くなった
- response/resource/runtime/server wrapper surface の考え方をより揃えられた
- canonical helper module と public facade の境界を少し明確にできた
- final dependency cleanup へ進むための下地が少し整った

まだ残っているもの:
- `server.py` には concrete `HttpRuntimeAdapter` class 実装そのものが残っている
- `server.py` には application-facing server surface がまだ多く残っている
- public compatibility wrapper 群はまだ多数残っている
- helper module は一部 `server.py` の wrapper / adapter class に依存している
- canonical protocol/dataclass/serializer/helper 配置の最終最適化はまだ途中
- stdio 削除前提の final dependency cleanup は未完
- compliance claim はまだ不可

## 5. テスト
確認したテスト:
- `tests/test_server.py`
- `tests/test_mcp_modules.py`

結果:
- **180 passed**

実行コマンド:
- `pytest -q tests/test_server.py tests/test_mcp_modules.py`

補足:
- focused regression は引き続き green
- facade/wrapper alignment 中心の変更で、behavioral regression は見えていません

## 6. 実装の評価
今回の整理は小さいですが、`server.py` を facade に寄せるうえで意味があります。

進んだこと:
- wrapper の role が少し揃った
- implementation ownership を helper module 側へ寄せる方向が一貫した
- public import surface を保ったまま dependency boundary を改善できた
- 既存 test expectation を保ったまま安全に前進できた

まだ未着手に近いこと:
- `server.py` から `HttpRuntimeAdapter` 本体をどう扱うかの整理
- `CtxLedgerServer` instance method と top-level wrapper の最終整理
- helper module から `server.py` adapter/wrapper への依存整理
- stdio removal path を前提にした dependency cleanup
- transport-specific startup orchestration のさらなる isolation
- richer MCP transport semantics の本実装

## 7. コミット
このセッション時点では、まだコミットは切っていません。

次の人は `.rules` に従って、作業ループ完了時に descriptive message で `git commit` してください。

コミット候補メッセージ例:
- `Align server facade wrappers`
- `Clarify facade wrapper ownership`
- `Refine server compatibility wrapper alignment`

## 8. 次の引き継ぎ先向けメモ
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
28. create_runtime wrapper simplification が入っている
29. 今回、facade wrapper alignment step が入った
30. `tests/test_server.py` と `tests/test_mcp_modules.py` を合わせて **180 passed**
31. `docs/specification.md` は引き続き触らない
32. まだ compliance claim はしない
33. 最終的には stdio は削除前提だが、現段階では責務分離を優先している

注意点:
- `server.py` はまだ大きいが、transport orchestration / composite lifecycle / HTTP runtime builder / HTTP handler implementation / server response building / server construction wiring / resource response building / database health helper / shared bootstrap error / shared runtime response types / shared runtime serializers / HTTP runtime wrapper dependency cleanup / HTTP validation helper dependency cleanup / shared runtime protocols extraction / concrete HTTP adapter dependency cleanup / stdio introspection concrete dependency cleanup / health-readiness helper extraction / thinner public server wrapper delegation / resource response surface alignment / create_runtime wrapper simplification / facade wrapper alignment step の本体は外へ出始めた
- `create_runtime(...)` は public surface 維持のため `server.py` に wrapper として残っている
- `_print_runtime_summary(...)` も test/import 互換のため `server.py` に wrapper として残してある
- `build_http_runtime_adapter(...)` も public surface 維持のため `server.py` に wrapper を残してある
- HTTP handler 群も public surface 維持のため `server.py` には wrapper が残っている
- response/resource builder 群と `create_server(...)` / `build_workflow_service_factory(...)` も public surface 維持のため `server.py` に wrapper が残っている
- `runtime/http_runtime.py` は HTTP runtime の registration wiring を持つ
- `runtime/http_handlers.py` は HTTP handler implementation の canonical module
- `runtime/server_responses.py` は server/resource response building の canonical module
- `runtime/server_factory.py` は server construction wiring の canonical module
- `runtime/database_health.py` は DB health helper の canonical module
- `runtime/errors.py` は shared bootstrap error の canonical module
- `runtime/types.py` は shared response/status dataclass の canonical module
- `runtime/serializers.py` は shared serializer の canonical module
- `runtime/protocols.py` は shared runtime helper protocol の canonical module
- `runtime/status.py` は health/readiness helper の canonical module
- `runtime/composite.py` は composite lifecycle の canonical 実装
- `runtime/orchestration.py` は runtime selection / run entrypoint orchestration の中心
- `runtime/introspection.py` は stdio/http/composite を横断して正規化する責務を持つ
- 既存 green 状態は **180 passed** を基準に見てよい

## 9. 次に自然な一手
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