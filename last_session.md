Patch 2 の続きとして、今回は **concrete HTTP adapter dependency cleanup** を進め、`runtime/http_runtime.py` と `runtime/introspection.py` に残っていた `server.py` concrete adapter 依存をさらに整理しました。前回までに進めた runtime introspection / runtime orchestration / HTTP runtime builder / composite runtime / HTTP handler / server response builder / server factory wiring / resource response builder / database health helper / shared bootstrap error / shared runtime types / shared runtime serializers / HTTP runtime registration wiring cleanup / HTTP validation helper dependency cleanup / shared runtime protocols extraction を土台にして、**HTTP adapter concrete type dependency の薄型化** を実施しています。既存の公開 API と test expectation を壊さないことを優先して整理しました。

今回の実装でやったこと:

- `ctxledger/src/ctxledger/runtime/protocols.py` を更新して `HttpRuntimeAdapterProtocol` を追加
- `ctxledger/src/ctxledger/runtime/http_runtime.py` を更新して concrete `HttpRuntimeAdapter` ではなく shared HTTP runtime protocol を使う形に変更
- `ctxledger/src/ctxledger/runtime/introspection.py` を更新して `isinstance(..., HttpRuntimeAdapter)` / `isinstance(..., CompositeRuntimeAdapter)` 依存を減らし、capability-based detection に寄せる形へ変更
- `ctxledger/src/ctxledger/server.py` を更新して `HttpRuntimeAdapterProtocol` を re-export する形に変更
- 回帰確認として `tests/test_server.py` と `tests/test_mcp_modules.py` を再実行
- 最終的に green を維持

## 1. `ctxledger/src/ctxledger/runtime/protocols.py`
今回の中心のひとつです。shared runtime protocol module に HTTP runtime adapter 用 protocol を追加しました。

追加したもの:
- `HttpRuntimeAdapterProtocol`

ポイント:
- `settings`
- `register_handler(...)`
- `registered_routes()`
- `introspect()`
- runtime lifecycle (`start()` / `stop()`)

のような HTTP runtime wiring 側に必要な capability を protocol として明示しました
- これにより `runtime/http_runtime.py` が concrete `HttpRuntimeAdapter` 型に直接依存しすぎない形へ進めました
- protocol ownership を `server.py` ではなく `runtime/protocols.py` に寄せられました

## 2. `ctxledger/src/ctxledger/runtime/http_runtime.py`
HTTP runtime wiring では、concrete `HttpRuntimeAdapter` 依存を一段薄くしました。

変更したこと:
- `register_http_runtime_handlers(...)` の引数/戻り値型を `HttpRuntimeAdapterProtocol` ベースに変更
- `build_http_runtime_adapter(...)` も戻り値型を shared HTTP runtime protocol ベースに変更

維持しているもの:
- route registration の既存 shape
- debug endpoint registration の既存 shape
- stdio runtime builder の利用構造
- HTTP runtime adapter の生成 shape

ポイント:
- 実際の concrete instance 生成は引き続き `HttpRuntimeAdapter(...)` ですが、registration helper の contract は protocol に寄りました
- wiring helper は concrete class 所有者に縛られず、「必要な capability を持つ HTTP runtime」に依存する形へ少し進みました
- public behavior は変えていません

## 3. `ctxledger/src/ctxledger/runtime/introspection.py`
今回のもうひとつの中心です。runtime introspection helper で、concrete adapter class に対する `isinstance(...)` 依存を減らしました。

変更したこと:
- `CompositeRuntimeAdapter` に対する `isinstance(...)` 依存をやめ、`_runtimes` attribute を持つ composite-like runtime を辿る形へ変更
- `HttpRuntimeAdapter` に対する `isinstance(...)` 依存をやめ、`introspect()` callable を持つ runtime から introspection-like object を読む capability-based detection に変更
- `_is_runtime_introspection_like(...)` helper を追加

維持しているもの:
- stdio/http/composite を横断した introspection result の shape
- `transport`
- `routes`
- `tools`
- `resources`
の normalized shape
- `collect_runtime_introspection(...)` の public expectation

ポイント:
- helper は concrete adapter identity ではなく「introspection capability」「nested runtime collection capability」に寄って動くようになりました
- stdio runtime だけは引き続き special case を残していますが、HTTP/composite dependency は少し緩みました
- `server.py` の concrete adapter class に対する dependency を一段減らせました

## 4. `ctxledger/src/ctxledger/server.py`
`server.py` 側では shared HTTP runtime protocol を import / re-export する形に変更しました。

変更したこと:
- `runtime/protocols.py` から `HttpRuntimeAdapterProtocol` を import
- `ctxledger.server.HttpRuntimeAdapterProtocol` として import surface を維持する形にした

ポイント:
- concrete `HttpRuntimeAdapter` class 自体は引き続き `server.py` にあります
- ただし helper modules 側が「adapter contract」と「adapter implementation」を分けて参照しやすくなりました
- `server.py` は facade / compatibility shell としてさらに寄っています

## 挙動面での現状
今回の変更も extraction / canonicalization 中心で、機能追加ではなく責務整理を優先しています。

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
- concrete HTTP runtime adapter dependency を protocol ベースへ一段寄せられた
- runtime introspection helper が capability-based detection を使う形へ進んだ
- `server.py` concrete adapter class への helper module 依存を一部整理できた
- `server.py` は top-level facade / compatibility export としてさらに薄くなった

まだ残っているもの:
- `server.py` には concrete `HttpRuntimeAdapter` class 実装そのものが残っている
- `runtime/introspection.py` は stdio runtime をまだ concrete special case で扱っている
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
- 今回の変更後、focused regression は green です
- concrete adapter dependency cleanup 中心の変更で、behavioral regression は見えていません

## コミット
このセッション時点では、まだコミットは切っていません。

次の人は `.rules` に従って、作業ループ完了時に descriptive message で `git commit` してください。

コミット候補メッセージ例:
- `Reduce concrete HTTP runtime adapter dependencies`
- `Use protocol-based HTTP runtime adapter typing`

## 注意
- この session では `last_session.md` 更新までを意図しています
- ワークツリー上には別件の変更が存在する可能性があります
- 今回の変更は concrete HTTP adapter dependency cleanup が中心で、behavioral rewrite ではありません

## 実装の評価
今回の整理は小さめですが、依存関係の見通しを良くするうえで意味があります。

進んだこと:
- HTTP runtime wiring が concrete adapter class より protocol contract に寄った
- runtime introspection が concrete adapter identity より capability-based detection に寄った
- `server.py` が concrete type 定義の所有者である必要を少しずつ薄くできた
- public import surface を保ったまま dependency boundary を改善できた
- 既存 test expectation を保ったまま安全に前進できた

まだ未着手に近いこと:
- `server.py` から `HttpRuntimeAdapter` 本体をどう扱うかの整理
- stdio runtime 側の concrete special case の整理
- readiness / health / bootstrap boundary の整理
- stdio removal path を前提にした dependency cleanup
- transport-specific startup orchestration のさらなる isolation
- richer MCP transport semantics の本実装

## 次にやること
次は以下のどれかが自然です。

候補:
1. `runtime/introspection.py` の stdio concrete special case をさらに整理する
2. readiness / health / DB/bootstrap boundary を整理する
3. canonical protocol/dataclass/serializer/helper の配置をさらに見直す
4. stdio removal path を意識して transport-specific code をさらに隔離する
5. `server.py` を application-facing server surface と compatibility shell により近づける

特に安全そうなのは:
- runtime introspection dependency の整理
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
23. 今回、concrete HTTP adapter dependency cleanup が入った
24. `tests/test_server.py` と `tests/test_mcp_modules.py` を合わせて **180 passed**
25. `docs/specification.md` は引き続き触らない
26. まだ compliance claim はしない
27. 最終的には stdio は削除前提だが、現段階では責務分離を優先している

注意点:
- `server.py` はまだ大きいが、transport orchestration / composite lifecycle / HTTP runtime builder / HTTP handler implementation / server response building / server construction wiring / database health helper / shared bootstrap error / shared runtime response types / shared runtime serializers / HTTP runtime wrapper dependency cleanup / HTTP validation helper dependency cleanup / shared runtime protocols extraction / concrete HTTP adapter dependency cleanup の本体は外へ出始めた
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

### まだ `server.py` に残るもの
- application-facing server surface 全般
- health/readiness public surface
- public compatibility wrapper 群
- helper 群の最終 dependency boundary 調整

## 次に自然な一手
ここまで来たので、次は **runtime introspection concrete dependency と public surface boundary の整理** が一番きれいです。

たとえば:
- `runtime/introspection.py` の stdio concrete special case
- transport detection contract の整理
- `server.py` に残る adapter/wrapper ownership
- readiness / health helper の ownership

を dedicated helper/core boundary に寄せる段階です。

これをやると、`server.py` はかなり
- health/readiness public surface
- workflow-facing public surface
- compatibility export surface
- canonical top-level facade

に近づきます。

必要ならそのまま **transport orchestration の薄型化** をさらに進めて、
最終的な stdio removal path までつなげられます。