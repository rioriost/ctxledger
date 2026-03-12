Patch 2 の続きとして、`server.py` に残っていた transport orchestration の一部をさらに外出ししました。今回のセッションでは、runtime introspection と runtime orchestration helper の抽出を土台にして、さらに HTTP runtime builder と composite runtime adapter の分離まで進めています。既存の公開 API と test expectation を壊さないことを優先して整理しました。

今回の実装でやったこと:

- `ctxledger/src/ctxledger/runtime/composite.py` を新設
- `ctxledger/src/ctxledger/runtime/http_runtime.py` を新設
- 既存の `ctxledger/src/ctxledger/runtime/introspection.py` / `ctxledger/src/ctxledger/runtime/orchestration.py` と連携する形で責務分離を拡張
- `ctxledger/src/ctxledger/server.py` を更新して、HTTP runtime builder と composite runtime を新 helper module 経由に変更
- 抽出後の回帰を確認して `tests/test_server.py` と `tests/test_mcp_modules.py` を再実行
- 最終的に green を維持

## 1. `ctxledger/src/ctxledger/runtime/composite.py`
`CompositeRuntimeAdapter` を `server.py` から外出しするため、専用 module を追加しました。

追加したもの:
- `ServerRuntime`
- `CompositeRuntimeAdapter`

ポイント:
- 複数 transport runtime をまとめる lifecycle boundary を `server.py` から切り離しました
- `start()` 時の partial startup rollback
- `stop()` 時の reverse-order shutdown
- shutdown failure 時の logging
  といった振る舞いはそのまま維持しています
- `collect_runtime_introspection(...)` 側からは、これまで通り `CompositeRuntimeAdapter` として扱える状態を維持しています
- `server.py` は composite lifecycle 実装本体を持たず、利用側に近づきました

## 2. `ctxledger/src/ctxledger/runtime/http_runtime.py`
`build_http_runtime_adapter(...)` を `server.py` から切り出すため、HTTP runtime builder 用 helper module を追加しました。

追加したもの:
- `build_http_runtime_adapter(...)`

この helper が構成するもの:
- `mcp_rpc`
- `runtime_introspection`
- `runtime_routes`
- `runtime_tools`
- `workflow_resume`
- `workflow_closed_projection_failures`
- `projection_failures_ignore`
- `projection_failures_resolve`

ポイント:
- HTTP runtime の route registration wiring を `server.py` から分離しました
- 内部では
  - `build_mcp_http_handler(...)`
  - debug HTTP handlers
  - workflow / projection failure handlers
  を組み合わせるだけの builder に寄せています
- MCP over HTTP でも、引き続き stdio-style MCP runtime adapter を内部利用する構成を維持しています
- debug endpoint 有効/無効判定もここへ移りました

注意:
- route handler そのものの実装本体はまだ `server.py` にあります
- 今回は builder extraction までで、HTTP handler 全体の完全分離ではありません

## 3. `ctxledger/src/ctxledger/runtime/orchestration.py`
前回追加した orchestration helper を、今回の HTTP/composite 抽出に合わせて更新しました。

変更したこと:
- `CompositeRuntimeAdapter` を `runtime/composite.py` から使うように変更
- HTTP runtime 作成時に `runtime/http_runtime.py` の `build_http_runtime_adapter(...)` を使うように変更
- composite / HTTP-only / stdio-only の runtime selection を引き続きこの module が担う構成を維持
- `run_server(...)`
- `apply_overrides(...)`
- `install_signal_handlers(...)`
- `print_runtime_summary(...)`
  の責務は継続

ポイント:
- transport orchestration helper と HTTP runtime builder helper の境界が少し明確になりました
- `create_runtime(...)` は orchestration の中心として残しつつ、個別 transport の構築責務を外へ寄せています
- `server is None` の HTTP-only ケースでは、引き続き `HttpRuntimeAdapter(settings)` を返して既存 test expectation を維持しています

## 4. `ctxledger/src/ctxledger/runtime/introspection.py`
この session では大きなロジック変更はありませんが、`CompositeRuntimeAdapter` が新 module へ移ったあとも、runtime introspection の責務はこの module に維持されています。

維持しているもの:
- `RuntimeIntrospection`
- `collect_runtime_introspection(...)`
- `serialize_runtime_introspection(...)`
- `serialize_runtime_introspection_collection(...)`

ポイント:
- `CompositeRuntimeAdapter` / `HttpRuntimeAdapter` / `StdioRuntimeAdapter` を横断して正規化する役割は引き続きここ
- `server.py` が introspection の実装本体を抱えない方向は維持されています

## 5. `ctxledger/src/ctxledger/server.py`
今回の中心変更のひとつです。`server.py` はさらに薄くなりました。

変更したこと:
- `CompositeRuntimeAdapter` の実装本体を削除し、`runtime/composite.py` から import する形に変更
- `build_http_runtime_adapter(...)` の実装本体を削除し、`runtime/http_runtime.py` への wrapper に変更
- 既存の `create_runtime(...)` wrapper は維持しつつ、実体は `runtime/orchestration.py` 側へ委譲
- `_print_runtime_summary(...)` は引き続き test/import 互換のため private wrapper として残置
- public export surface は大きく壊さないよう維持

今回の結果として `server.py` に残る中心責務:
- application-facing server surface
- health / readiness
- workflow / projection failure response building
- HTTP route handler 実装本体
- MCP HTTP bridge function
- server construction entrypoint

外れたもの:
- composite runtime lifecycle 実装本体
- HTTP runtime route registration wiring 本体
- runtime introspection 実装本体
- transport override / signal / run entrypoint orchestration 本体

## 挙動面での現状
今回の変更も extraction 中心で、挙動変更より責務整理を優先しています。

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

今回新しく進んだこと:
- `CompositeRuntimeAdapter` の authority を `runtime/composite.py` に分離
- HTTP runtime route registration wiring を `runtime/http_runtime.py` に分離
- `server.py` から transport-specific builder 実装をさらに削減
- transport orchestration の helper 群と individual transport builder 群の境界を少し改善

まだ残っているもの:
- `server.py` はまだ HTTP route handler 実装の中心
- `build_mcp_http_handler(...)` と各 HTTP route handler はまだ `server.py`
- health/readiness/debug HTTP surface と runtime wiring の境界はまだ完全分離ではない
- stdio 削除前提の最終 dependency cleanup は未完
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
- 一度 `runtime/http_runtime.py` の relative import を誤って
  - top-level package を越える import
  - `ctxledger.orchestration` を探しに行く import
  の問題が出ましたが修正済みです
- 最終的に **180 passed** に戻しています

## コミット
このセッション時点では、まだコミットは切っていません。

次の人は `.rules` に従って、作業ループ完了時に descriptive message で `git commit` してください。

コミット候補メッセージ例:
- `Extract HTTP runtime builder helpers`
- `Move composite runtime adapter out of server`

## 注意
- この session では `last_session.md` 更新まで実施していますが、git commit は未実施です
- ワークツリー上には別件の変更が存在する可能性があります
- 今回の変更は HTTP/composite extraction が中心で、full transport rewrite ではありません

## 実装の評価
今回の抽出は、前回の orchestration helper split の自然な続きとして良い前進です。

進んだこと:
- `server.py` から composite runtime lifecycle 実装本体を外出し
- `server.py` から HTTP runtime route registration wiring を外出し
- runtime helper 群の責務分割が
  - introspection
  - orchestration
  - composite lifecycle
  - HTTP runtime builder
  の単位で見えやすくなった
- 将来 `server.py` を
  - health/readiness
  - workflow-facing server surface
  - HTTP handler 実装
  にさらに寄せやすくなった
- 既存 test expectation を保ったまま、小さく安全に前進できた

まだ未着手に近いこと:
- HTTP route handler 実装本体の外出し
- `build_mcp_http_handler(...)` の配置見直し
- `create_server(...)` と runtime builder boundary の整理
- debug HTTP endpoint 実装の dedicated helper 化
- stdio removal path を前提にした final dependency cleanup
- transport-specific startup orchestration のさらなる isolation

## 次にやること
次は以下のどれかが自然です。

候補:
1. HTTP route handler 実装群を `server.py` から外出しする
2. `build_mcp_http_handler(...)` を HTTP transport module 側へ寄せる
3. `create_server(...)` と runtime wiring の責務をさらに整理する
4. debug runtime/routes/tools HTTP endpoint 実装を専用 helper に寄せる
5. stdio removal path を意識して transport-specific code をさらに隔離する

特に安全そうなのは:
- debug HTTP handlers の抽出
- `build_mcp_http_handler(...)` の抽出
- `create_server(...)` と runtime construction の境界整理

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
10. 今回、HTTP runtime builder extraction が入った
11. 今回、composite runtime adapter extraction が入った
12. `tests/test_server.py` と `tests/test_mcp_modules.py` を合わせて **180 passed**
13. `docs/specification.md` は引き続き触らない
14. まだ compliance claim はしない
15. 最終的には stdio は削除前提だが、現段階では責務分離を優先している

注意点:
- `server.py` はまだ大きいが、transport orchestration / composite lifecycle / HTTP runtime builder の本体は外へ出始めた
- `create_runtime(...)` は public surface 維持のため `server.py` に wrapper として残っている
- `_print_runtime_summary(...)` も test/import 互換のため `server.py` に wrapper として残してある
- `build_http_runtime_adapter(...)` も public surface 維持のため `server.py` に wrapper を残してある
- `runtime/http_runtime.py` は HTTP runtime の registration wiring を持つ
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

### まだ `server.py` に残るもの
- `build_mcp_http_handler(...)`
- debug / workflow / projection failure の HTTP handler 実装本体
- `create_server(...)` の中心 wiring
- health/readiness/debug HTTP surface
- application-facing server surface 全般

## 次に自然な一手
ここまで来たので、次は **HTTP handler 実装本体の抽出** が一番きれいです。

たとえば:
- `build_mcp_http_handler(...)`
- `build_runtime_introspection_http_handler(...)`
- `build_runtime_routes_http_handler(...)`
- `build_runtime_tools_http_handler(...)`
- `build_workflow_resume_http_handler(...)`
- projection failure 系 HTTP handlers

を dedicated HTTP helper module に寄せる段階です。

これをやると、`server.py` はかなり
- health/readiness
- workflow-facing server surface
- bootstrap shell
- server object の公開面

に近づきます。

必要ならそのまま **transport orchestration の薄型化** をさらに進めて、
最終的な stdio removal path までつなげられます。