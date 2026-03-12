Patch 2 の続きとして、今回は **stdio introspection concrete dependency cleanup** を進め、`runtime/introspection.py` に残っていた stdio runtime の concrete special case をさらに整理しました。前回までに進めた runtime introspection / runtime orchestration / HTTP runtime builder / composite runtime / HTTP handler / server response builder / server factory wiring / resource response builder / database health helper / shared bootstrap error / shared runtime types / shared runtime serializers / HTTP runtime registration wiring cleanup / HTTP validation helper dependency cleanup / shared runtime protocols extraction / concrete HTTP adapter dependency cleanup を土台にして、**runtime introspection の transport detection をさらに capability-based に寄せる整理** を実施しています。既存の公開 API と test expectation を壊さないことを優先して整理しました。

今回の実装でやったこと:

- `ctxledger/src/ctxledger/runtime/introspection.py` を更新して stdio runtime の concrete protocol/isinstance 前提を外す形に変更
- `ctxledger/src/ctxledger/runtime/protocols.py` は前セッションで `StdioRuntimeAdapterProtocol` を追加していましたが、実行時 `isinstance(...)` には使わず、attribute/capability ベースの判定へ寄せる形に整理
- 回帰確認として `tests/test_server.py` と `tests/test_mcp_modules.py` を再実行
- 最終的に green を維持

## 1. `ctxledger/src/ctxledger/runtime/introspection.py`
今回の中心です。`collect_runtime_introspection(...)` に残っていた stdio runtime の concrete special case を、より capability-based な判定へ寄せました。

変更したこと:
- `_is_stdio_runtime_like(...)` が runtime protocol に対する `isinstance(...)` を使わない形に変更
- `registered_tools`
- `registered_resources`
- `tool_schema`
- `introspect`
といった stdio-like capability の存在で判定する形へ整理

背景:
- 一度 `StdioRuntimeAdapterProtocol` に対して `isinstance(...)` を使う形に寄せたところ、protocol が `@runtime_checkable` ではないため、実行時に `TypeError` が発生
- startup/readiness/health/introspection 系テストが広く落ちたため、attribute-based detection に戻して修正しました

ポイント:
- stdio runtime の concrete class identity に依存しない方向を保ちつつ、実行時安全性も維持できました
- runtime introspection helper は「その runtime が何者か」よりも「何をできるか」で判定する方向にさらに寄りました
- concrete class / runtime-checkable protocol に強く依存しないので、今後の stdio removal path にも悪くありません

## 2. `ctxledger/src/ctxledger/runtime/protocols.py`
前セッションで追加した shared runtime protocol module は引き続き有効です。今回の観点では、protocol を型表現として使うことと、実行時判定に使うことは分けるべきだと確認できました。

今回の整理で明確になったこと:
- `StdioRuntimeAdapterProtocol` は type contract としては有用
- ただし runtime 判定は `isinstance(...)` に頼らず capability-based に寄せたほうが安全
- protocol extraction 自体の方向性は維持してよい

ポイント:
- protocol は ownership 分離に有効
- runtime detection は duck typing に寄せたほうが今の構造には合う
- その線引きが今回少し明確になりました

## 挙動面での現状
今回の変更も extraction / canonicalization 中心で、機能追加ではなく責務整理と依存関係整理を優先しています。

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

今回新しく進んだこと:
- runtime introspection の stdio detection を concrete/runtime-protocol 判定よりも capability-based 判定へ寄せられた
- runtime protocol と runtime detection の責務を少し切り分けられた
- `server.py` concrete adapter class への indirect dependency を一段薄くできた
- startup/readiness/health/introspection 周辺で安全に green を維持できた

まだ残っているもの:
- `server.py` には concrete `HttpRuntimeAdapter` class 実装そのものが残っている
- helper module は一部 `server.py` の wrapper / adapter class に依存している
- readiness / health / DB/bootstrap helper 境界の最終整理は未完
- canonical protocol/dataclass/serializer/helper 配置の最終最適化はまだ途中
- stdio 削除前提の final dependency cleanup は未完
- compliance claim はまだ不可

## テスト
確認したテスト:
- `tests/test_server.py`
- `tests/test_mcp_modules.py`

結果:
- **180 passed**

実行コマンド:
- `pytest -q tests/test_server.py tests/test_mcp_modules.py`

補足:
- 一度 protocol に対する実行時 `isinstance(...)` により多数のテストが落ちた
- capability-based detection に戻して修正後、focused regression は green
- 最終状態は **180 passed** を維持

## コミット
このセッション時点では、まだコミットは切っていません。

次の人は `.rules` に従って、作業ループ完了時に descriptive message で `git commit` してください。

コミット候補メッセージ例:
- `Clean up stdio introspection dependencies`
- `Use capability-based stdio runtime introspection`

## 注意
- この session では `last_session.md` 更新までを意図しています
- ワークツリー上には別件の変更が存在する可能性があります
- 今回の変更は stdio introspection concrete dependency cleanup が中心で、behavioral rewrite ではありません

## 実装の評価
今回の整理はかなり小さいですが、依存関係と実行時安全性の両方を整えるうえで意味があります。

進んだこと:
- runtime protocol の型用途と runtime detection の実行時用途を切り分けられた
- stdio introspection 判定をより素直な duck typing に寄せられた
- protocol extraction の方向性を壊さずに runtime failure を避けられた
- 既存 test expectation を保ったまま安全に前進できた

まだ未着手に近いこと:
- `server.py` から `HttpRuntimeAdapter` 本体をどう扱うかの整理
- helper module から `server.py` adapter/wrapper への依存整理
- readiness / health / bootstrap boundary の整理
- stdio removal path を前提にした dependency cleanup
- transport-specific startup orchestration のさらなる isolation
- richer MCP transport semantics の本実装

## 次にやること
次は以下のどれかが自然です。

候補:
1. `server.py` に残る adapter/wrapper ownership をさらに整理する
2. readiness / health / DB/bootstrap boundary を整理する
3. canonical protocol/dataclass/serializer/helper の配置をさらに見直す
4. stdio removal path を意識して transport-specific code をさらに隔離する
5. `server.py` を application-facing server surface と compatibility shell により近づける

特に安全そうなのは:
- runtime introspection / adapter dependency の整理
- readiness / health surface の整理
- bootstrap / response / transport helper の境界整理

## 次の引き継ぎ先向けメモ
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
24. 今回、stdio introspection concrete dependency cleanup が入った
25. `tests/test_server.py` と `tests/test_mcp_modules.py` を合わせて **180 passed**
26. `docs/specification.md` は引き続き触らない
27. まだ compliance claim はしない
28. 最終的には stdio は削除前提だが、現段階では責務分離を優先している

注意点:
- `server.py` はまだ大きいが、transport orchestration / composite lifecycle / HTTP runtime builder / HTTP handler implementation / server response building / server construction wiring / database health helper / shared bootstrap error / shared runtime response types / shared runtime serializers / HTTP runtime wrapper dependency cleanup / HTTP validation helper dependency cleanup / shared runtime protocols extraction / concrete HTTP adapter dependency cleanup / stdio introspection concrete dependency cleanup の本体は外へ出始めた
- `create_runtime(...)` は public surface 維持のため `server.py` に wrapper として残っている
- `_print_runtime_summary(...)` も test/import 互換のため `server.py` に wrapper として残してある
- `build_http_runtime_adapter(...)` も public surface 維持のため `server.py` に wrapper を残してある
- HTTP handler 群も public surface 維持のため `server.py` には wrapper が残っている
- response builder 群と `create_server(...)` / `build_workflow_service_factory(...)` も public surface 維持のため `server.py` に wrapper が残っている
- `runtime/http_runtime.py` は HTTP runtime の registration wiring を持つ
- `runtime/http_handlers.py` は HTTP handler implementation の canonical module
- `runtime/server_responses.py` は server response building の canonical module
- `runtime/server_factory.py` は server construction wiring の canonical module
- `runtime/database_health.py` は DB health helper の canonical module
- `runtime/errors.py` は shared bootstrap error の canonical module
- `runtime/types.py` は shared response/status dataclass の canonical module
- `runtime/serializers.py` は shared serializer の canonical module
- `runtime/protocols.py` は shared runtime helper protocol の canonical module
- `runtime/composite.py` は composite lifecycle の canonical 実装
- `runtime/orchestration.py` は runtime selection / run entrypoint orchestration の中心
- `runtime/introspection.py` は stdio/http/composite を横断して正規化する責務を持つ
- 既存 green 状態は **180 passed** を基準に見てよい

### すでに外出し済み
- MCP lifecycle helper
- Streamable HTTP scaffold
- MCP RPC helper
- stdio adapter
- stdio RPC server
- stdio dispatch helper
- stdio builder wiring
- stdio runtime bootstrap helper
- stdio runtime construction helper
- runtime introspection helper
- transport override / signal / summary / run entrypoint helper
- composite runtime lifecycle
- HTTP runtime route registration wiring
- HTTP auth helper
- HTTP path/query parsing helper
- HTTP handler implementation
- MCP HTTP bridge implementation
- server response building
- server construction wiring
- database health helper
- resource response building
- shared bootstrap error
- shared runtime response/status dataclasses
- shared runtime serializers
- HTTP runtime registration wiring cleanup
- HTTP validation helper dependency cleanup
- shared runtime helper protocols
- concrete HTTP adapter dependency cleanup
- stdio introspection concrete dependency cleanup

### まだ `server.py` に残るもの
- application-facing server surface 全般
- health/readiness public surface
- public compatibility wrapper 群
- helper 群の最終 dependency boundary 調整

## 次に自然な一手
ここまで来たので、次は **server facade boundary と readiness/health ownership の整理** が一番きれいです。

たとえば:
- readiness / health helper の ownership
- `server.py` に残る adapter/wrapper ownership
- top-level public facade と internal helper boundary
- transport helper と application-facing surface の分離

を dedicated helper/core boundary に寄せる段階です。

これをやると、`server.py` はかなり
- health/readiness public surface
- workflow-facing public surface
- compatibility export surface
- canonical top-level facade

に近づきます。

必要ならそのまま **transport orchestration の薄型化** をさらに進めて、
最終的な stdio removal path までつなげられます。