Patch 2 の続きとして、今回は **serializer dependency と public surface boundary の整理** を進め、`server.py` に残っていた shared serializer 群の ownership をさらに分離しました。前回までに進めた runtime introspection / runtime orchestration / HTTP runtime builder / composite runtime / HTTP handler / server response builder / server factory wiring / resource response builder / database health helper / shared bootstrap error / shared runtime types の抽出を土台にして、**shared runtime serializers extraction** を実施しています。既存の公開 API と test expectation を壊さないことを優先して整理しました。

今回の実装でやったこと:

- `ctxledger/src/ctxledger/runtime/serializers.py` を新設
- `ctxledger/src/ctxledger/server.py` を更新して shared serializer 群を re-export する形に変更
- `ctxledger/src/ctxledger/runtime/server_responses.py` を更新して shared serializer 群を canonical import として使う形に変更
- `ctxledger/src/ctxledger/runtime/introspection.py` を更新して runtime introspection serializer を shared serializer module 経由に変更
- `ctxledger/src/ctxledger/__init__.py` を更新して CLI の resume workflow JSON 出力が shared serializer を使う形に変更
- `ctxledger/src/ctxledger/mcp/tool_handlers.py` を更新して memory tool handlers が shared serializer を使う形に変更
- 回帰確認として `tests/test_server.py` と `tests/test_mcp_modules.py` を再実行
- 最終的に green を維持

## 1. `ctxledger/src/ctxledger/runtime/serializers.py`
今回の中心です。`server.py` に残っていた shared serializer 群を専用 module に抽出しました。

追加したもの:
- `serialize_workflow_resume(...)`
- `serialize_closed_projection_failures_history(...)`
- `serialize_stub_response(...)`
- `serialize_runtime_introspection(...)`
- `serialize_runtime_introspection_collection(...)`

ポイント:
- helper module が `server.py` の serializer 定義そのものを依存しなくてよい形に寄せました
- serializer の canonical source を `runtime/serializers.py` に移せました
- response helper / CLI / MCP handler / introspection helper が shared serializer module を参照できるようになりました

## 2. `ctxledger/src/ctxledger/server.py`
`server.py` 側では serializer 定義の所有をやめ、shared serializer 群を import / re-export する形に変更しました。

変更したこと:
- in-file の shared serializer 定義を削除
- `runtime/serializers.py` から各 serializer を import
- 既存の `ctxledger.server.serialize_*` import surface は維持

維持しているもの:
- `ctxledger.server.serialize_workflow_resume`
- `ctxledger.server.serialize_closed_projection_failures_history`
- `ctxledger.server.serialize_stub_response`
- `ctxledger.server.serialize_runtime_introspection`
- `ctxledger.server.serialize_runtime_introspection_collection`

ポイント:
- external import surface は壊さずに canonical ownership だけ移せました
- `server.py` は application-facing facade / compatibility shell にさらに寄りました
- tests や利用側が `ctxledger.server` から import している前提を維持しています

## 3. `ctxledger/src/ctxledger/runtime/server_responses.py`
response helper は shared serializer module を使う形へ更新しました。

変更したこと:
- `serialize_workflow_resume(...)`
- `serialize_closed_projection_failures_history(...)`

を `runtime/serializers.py` から参照する形に変更

維持しているもの:
- workflow resume response payload shape
- closed projection failures response payload shape
- `server_not_ready` response shape
- projection failure action response shape
- runtime introspection / routes / tools response shape

ポイント:
- helper module から `server.py` への serializer dependency を一段減らせました
- response type は前回の `runtime/types.py`、serializer は今回の `runtime/serializers.py` に寄りました

## 4. `ctxledger/src/ctxledger/runtime/introspection.py`
introspection helper では serializer ownership を shared serializer module に寄せました。

変更したこと:
- local な `serialize_runtime_introspection(...)` 定義を削除
- local な `serialize_runtime_introspection_collection(...)` 定義を削除
- `runtime/serializers.py` から re-export する形に変更

ポイント:
- introspection helper は collection / normalization にさらに寄っています
- serializer responsibility を別 module に切り出せました
- import surface は維持しています

## 5. `ctxledger/src/ctxledger/__init__.py`
CLI entrypoint でも shared serializer を使う形に変更しました。

変更したこと:
- `resume-workflow --format json` が `server.py` ではなく `runtime/serializers.py` の `serialize_workflow_resume(...)` を使う形に変更

ポイント:
- top-level CLI helper も `server.py` serializer ownership 前提から少し外れました
- JSON output shape は維持しています

## 6. `ctxledger/src/ctxledger/mcp/tool_handlers.py`
memory tool handlers でも shared serializer を使う形に変更しました。

変更したこと:
- `build_memory_remember_episode_tool_handler(...)`
- `build_memory_search_tool_handler(...)`
- `build_memory_get_context_tool_handler(...)`

が `serialize_stub_response(...)` を `runtime/serializers.py` から使う形に変更

ポイント:
- MCP tool handler が `server.py` serializer に依存する必要を減らしました
- memory tool response payload shape は維持しています

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
- shared serializer の canonical source を `runtime/serializers.py` に分離
- helper module が `server.py` serializer 定義に依存する箇所を一部整理
- `server.py` は top-level facade / compatibility export としてさらに薄くなった
- `runtime/introspection.py` は normalization helper としてさらに明確になった

まだ残っているもの:
- `server.py` には application-facing server surface がまだ多く残っている
- helper module は一部 `server.py` の wrapper に依存している
- readiness / health / DB/bootstrap helper 境界の最終整理は未完
- canonical protocol/dataclass/serializer 配置の最終最適化はまだ途中
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
- 変更後の対象ファイル diagnostics も確認し、追加エラーなしを前提に整理しています
- focused regression は green です

## コミット
このセッション時点では、まだコミットは切っていません。

次の人は `.rules` に従って、作業ループ完了時に descriptive message で `git commit` してください。

コミット候補メッセージ例:
- `Extract shared runtime serializers`
- `Canonicalize shared runtime serializers`

## 注意
- この session では `last_session.md` 更新までを意図しています
- ワークツリー上には別件の変更が存在する可能性があります
- 今回の変更は shared runtime serializers extraction が中心で、behavioral rewrite ではありません

## 実装の評価
今回の整理は小さめですが、依存関係の見通しを良くするうえで意味があります。

進んだこと:
- serializer の canonical source を `runtime/serializers.py` に寄せられた
- response helper / CLI / MCP tool handler / introspection helper が shared serializer module を使う形に進んだ
- `server.py` が serializer 定義の所有者である必要がさらに薄れた
- public import surface を保ったまま dependency boundary を改善できた
- 既存 test expectation を保ったまま安全に前進できた

まだ未着手に近いこと:
- helper module から `server.py` wrapper への依存整理
- readiness / health / bootstrap boundary の整理
- stdio removal path を前提にした dependency cleanup
- transport-specific startup orchestration のさらなる isolation
- richer MCP transport semantics の本実装

## 次にやること
次は以下のどれかが自然です。

候補:
1. helper module から `server.py` wrapper への依存をさらに整理する
2. readiness / health / DB/bootstrap boundary を整理する
3. canonical protocol/dataclass/serializer の配置をさらに見直す
4. stdio removal path を意識して transport-specific code をさらに隔離する
5. `server.py` を application-facing server surface と compatibility shell により近づける

特に安全そうなのは:
- wrapper dependency と public surface boundary の整理
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
19. 今回、shared runtime serializers extraction が入った
20. `tests/test_server.py` と `tests/test_mcp_modules.py` を合わせて **180 passed**
21. `docs/specification.md` は引き続き触らない
22. まだ compliance claim はしない
23. 最終的には stdio は削除前提だが、現段階では責務分離を優先している

注意点:
- `server.py` はまだ大きいが、transport orchestration / composite lifecycle / HTTP runtime builder / HTTP handler implementation / server response building / server construction wiring / database health helper / shared bootstrap error / shared runtime response types / shared runtime serializers の本体は外へ出始めた
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

### まだ `server.py` に残るもの
- application-facing server surface 全般
- health/readiness public surface
- public compatibility wrapper 群
- helper 群の最終 dependency boundary 調整

## 次に自然な一手
ここまで来たので、次は **wrapper dependency と public surface boundary の整理** が一番きれいです。

たとえば:
- helper module から `server.py` wrapper への依存
- application-facing public surface と internal helper boundary の整理
- readiness / health helper の ownership
- transport helper と top-level facade の境界

を dedicated helper/core boundary に寄せる段階です。

これをやると、`server.py` はかなり
- health/readiness public surface
- workflow-facing public surface
- compatibility export surface
- canonical top-level facade

に近づきます。

必要ならそのまま **transport orchestration の薄型化** をさらに進めて、
最終的な stdio removal path までつなげられます。