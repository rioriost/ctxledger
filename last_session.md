Patch 2 の続きとして、今回は **create_runtime wrapper simplification** を進め、`server.py` に残っていた transport runtime wrapper の一部を少しだけ整理しました。前回までに進めた runtime introspection / runtime orchestration / HTTP runtime builder / composite runtime / HTTP handler / server response builder / server factory wiring / resource response builder / database health helper / shared bootstrap error / shared runtime types / shared runtime serializers / HTTP runtime registration wiring cleanup / HTTP validation helper dependency cleanup / shared runtime protocols extraction / concrete HTTP adapter dependency cleanup / stdio introspection concrete dependency cleanup / health-readiness helper extraction / thinner public server wrapper delegation / resource response surface alignment を土台にして、**server facade boundary と create_runtime wrapper surface の薄型化** を一歩進めています。既存の公開 API と test expectation を壊さないことを優先して整理しました。

今回の実装でやったこと:

- `ctxledger/src/ctxledger/server.py` の `create_runtime(...)` を少し整理
- `server is None` / `server is not None` で分かれていた return 分岐を、`http_runtime_builder` の選択に寄せる形へ整理
- そのうえで `create_runtime_orchestration(...)` 呼び出し自体は一本化
- 回帰確認として `tests/test_server.py` と `tests/test_mcp_modules.py` を再実行
- 最終的に green を維持

## 1. `ctxledger/src/ctxledger/server.py`
今回の中心です。`create_runtime(...)` は public surface 維持のため `server.py` に残っていますが、wrapper としての形を少しだけ明確にしました。

変更したこと:
- `server is None` の場合は placeholder `HttpRuntimeAdapter(settings)` を返す builder lambda
- `server is not None` の場合は canonical `build_http_runtime_adapter`
を選ぶようにして、
- その後の `create_runtime_orchestration(...)` 呼び出しは一本化

変更前のイメージ:
- `if server is None: return create_runtime_orchestration(...)`
- `else: return create_runtime_orchestration(...)`

変更後のイメージ:
- `http_runtime_builder = ...`
- `return create_runtime_orchestration(..., http_runtime_builder=http_runtime_builder)`

ポイント:
- public behavior は維持
- test expectation も維持
- wrapper としての責務が少し見やすくなった
- `server.py` が orchestration 実装を持つのではなく、builder selection を行う facade であることが少し明確になった

## 2. 今の `server.py` facade state
ここまでの整理込みで、`server.py` はかなり facade / compatibility shell に寄っています。

現時点での canonical ownership の大枠:
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

`server.py` に主に残っているもの:
- top-level public import surface
- compatibility wrapper
- application-facing `CtxLedgerServer`
- concrete `HttpRuntimeAdapter`
- 一部 public convenience entrypoint
- `create_runtime(...)` の public wrapper
- `create_server(...)` の public wrapper
- `_print_runtime_summary(...)` の compatibility wrapper

## 3. 挙動面での現状
今回の変更も extraction / canonicalization / boundary cleanup 中心で、機能追加ではなく責務整理を優先しています。

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
- `create_runtime(...)` wrapper が少し薄くなった
- builder selection と orchestration call の責務が少し分かりやすくなった
- `server.py` の facade / compatibility shell 化を一歩進められた
- adapter/wrapper ownership の整理を少し前に進められた

まだ残っているもの:
- `server.py` には concrete `HttpRuntimeAdapter` class 実装そのものが残っている
- `server.py` には application-facing server surface がまだ多く残っている
- public compatibility wrapper 群はまだ多数残っている
- helper module は一部 `server.py` の wrapper / adapter class に依存している
- canonical protocol/dataclass/serializer/helper 配置の最終最適化はまだ途中
- stdio 削除前提の final dependency cleanup は未完
- compliance claim はまだ不可

## 4. テスト
確認したテスト:
- `tests/test_server.py`
- `tests/test_mcp_modules.py`

結果:
- **180 passed**

実行コマンド:
- `pytest -q tests/test_server.py tests/test_mcp_modules.py`

補足:
- 今回の変更後、focused regression は green
- wrapper simplification 中心の変更で、behavioral regression は見えていません

## 5. 実装の評価
今回の整理はかなり小さいですが、`server.py` を facade に寄せるうえで意味があります。

進んだこと:
- `create_runtime(...)` の重複分岐を少し減らせた
- wrapper の責務を「builder selection + orchestration delegation」に寄せられた
- public import surface を保ったまま dependency boundary を改善できた
- 既存 test expectation を保ったまま安全に前進できた

まだ未着手に近いこと:
- `server.py` から `HttpRuntimeAdapter` 本体をどう扱うかの整理
- `CtxLedgerServer` instance method と top-level wrapper の最終整理
- helper module から `server.py` adapter/wrapper への依存整理
- stdio removal path を前提にした dependency cleanup
- transport-specific startup orchestration のさらなる isolation
- richer MCP transport semantics の本実装

## 6. コミット
このセッション時点では、まだコミットは切っていません。

次の人は `.rules` に従って、作業ループ完了時に descriptive message で `git commit` してください。

コミット候補メッセージ例:
- `Simplify create_runtime wrapper`
- `Thin create_runtime server facade wrapper`

## 7. 次の引き継ぎ先向けメモ
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
28. 今回、`create_runtime(...)` wrapper simplification が入った
29. `tests/test_server.py` と `tests/test_mcp_modules.py` を合わせて **180 passed**
30. `docs/specification.md` は引き続き触らない
31. まだ compliance claim はしない
32. 最終的には stdio は削除前提だが、現段階では責務分離を優先している

注意点:
- `server.py` はまだ大きいが、transport orchestration / composite lifecycle / HTTP runtime builder / HTTP handler implementation / server response building / server construction wiring / resource response building / database health helper / shared bootstrap error / shared runtime response types / shared runtime serializers / HTTP runtime wrapper dependency cleanup / HTTP validation helper dependency cleanup / shared runtime protocols extraction / concrete HTTP adapter dependency cleanup / stdio introspection concrete dependency cleanup / health-readiness helper extraction / thinner public server wrapper delegation / resource response surface alignment / create_runtime wrapper simplification の本体は外へ出始めた
- `create_runtime(...)` は public surface 維持のため `server.py` に wrapper として残っている
- `_print_runtime_summary(...)` も test/import 互換のため `server.py` に wrapper として残してある
- `build_http_runtime_adapter(...)` も public surface 維持のため `server.py` に wrapper を残してある
- HTTP handler 群も public surface 維持のため `server.py` には wrapper が残っている
- response builder 群と `create_server(...)` / `build_workflow_service_factory(...)` も public surface 維持のため `server.py` に wrapper が残っている
- resource response surface も helper canonical / wrapper public の方針で整理が進んだ
- `runtime/http_runtime.py` は HTTP runtime の registration wiring を持つ
- `runtime/http_handlers.py` は HTTP handler implementation の canonical module
- `runtime/server_responses.py` は server response building の canonical module
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

## 8. 次に自然な一手
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