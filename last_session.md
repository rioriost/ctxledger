Patch 2 の続きとして、`server.py` に残っていた transport orchestration の一部をさらに外出ししました。今回のセッションでは、runtime introspection と runtime orchestration helper の抽出を進めつつ、既存の公開 API と test expectation を壊さない形で整理しています。

今回の実装でやったこと:

- `ctxledger/src/ctxledger/runtime/introspection.py` を新設
- `ctxledger/src/ctxledger/runtime/orchestration.py` を新設
- `ctxledger/src/ctxledger/server.py` を更新して、runtime introspection / runtime orchestration を新 helper module 経由に変更
- `server.py` に `_print_runtime_summary(...)` の互換ラッパーを残して、既存 test import を維持
- 抽出後の回帰を確認して `tests/test_server.py` と `tests/test_mcp_modules.py` を再実行

## 1. `ctxledger/src/ctxledger/runtime/introspection.py`
runtime introspection の責務を `server.py` から切り出すため、専用 module を追加しました。

追加したもの:
- `RuntimeIntrospection`
- `collect_runtime_introspection(...)`
- `serialize_runtime_introspection(...)`
- `serialize_runtime_introspection_collection(...)`

ポイント:
- `None` / `HttpRuntimeAdapter` / `StdioRuntimeAdapter` / `CompositeRuntimeAdapter` を横断して introspection を集約する責務をここへ移しました
- stdio introspection の shape 正規化
  - `transport`
  - `routes`
  - `tools`
  - `resources`
  をここで行うようにしました
- `server.py` 側は health / readiness / debug response の利用者に寄せています
- 循環 import を避けるため、型参照は `TYPE_CHECKING` と関数内 import を併用しています

## 2. `ctxledger/src/ctxledger/runtime/orchestration.py`
transport orchestration helper を `server.py` から分離する最初の本格ステップとして、新 module を追加しました。

追加したもの:
- `ServerRuntime`
- `build_stdio_runtime_adapter(...)`
- `create_runtime(...)`
- `apply_overrides(...)`
- `install_signal_handlers(...)`
- `print_runtime_summary(...)`
- `run_server(...)`

ポイント:
- stdio registration wiring を orchestration helper 側に寄せました
- `transport` / `host` / `port` override 適用ロジックを `server.py` 直書きから切り離しました
- signal handler 登録を helper 化しました
- startup summary の stderr 出力を helper 化しました
- `run_server(...)` の entrypoint orchestration を helper module 側へ移しました
- HTTP only のときは `server` が未構築でも `HttpRuntimeAdapter(settings)` を返すようにして、既存 `create_runtime(settings)` の test expectation を維持しました
- BOTH のときは `CompositeRuntimeAdapter` を返すようにし、既存 composite runtime 系 test expectation も維持しました

## 3. `ctxledger/src/ctxledger/server.py`
`server.py` は依然として中心 module ですが、transport orchestration と introspection の一部を新 module に移したことで、責務が少し薄くなりました。

変更したこと:
- runtime introspection 系 import を `runtime/introspection.py` へ切替
- `build_stdio_runtime_adapter(...)` と `run_server(...)` を `runtime/orchestration.py` から使うように変更
- `create_runtime(...)` は public API 互換のため `server.py` に残しつつ、実体は orchestration helper へ委譲する wrapper に変更
- `_print_runtime_summary(...)` は test と import 互換のため `server.py` に private wrapper として残置
- 旧 `_apply_overrides(...)` / `_install_signal_handlers(...)` / `_print_runtime_summary(...)` / in-file `run_server(...)` の本体責務は helper module 側へ移動
- in-file `collect_runtime_introspection(...)` / `serialize_runtime_introspection_collection(...)` / in-file stdio runtime construction 本体は削除

互換性面の配慮:
- 既存 import surface をなるべく壊さないように `server.py` の public export は維持
- test が直接 import していた `_print_runtime_summary(...)` は wrapper で残してあります
- `create_runtime(settings)` を test が直接呼ぶケースに合わせ、HTTP only / STDIO only / BOTH の挙動を以前と同じ shape に保っています

## 挙動面での現状
今回の変更は extraction 中心で、機能追加よりも orchestration の責務整理が主眼です。

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

今回新しく進んだこと:
- runtime introspection authority の一部を `runtime/introspection.py` に分離
- transport orchestration helper を `runtime/orchestration.py` に分離
- stdio runtime builder wiring を `server.py` からさらに外へ移設
- startup override / signal / runtime summary / CLI entrypoint orchestration を helper module 化
- `server.py` が持つ transport orchestration の密度をさらに下げた

まだ残っているもの:
- `server.py` はまだ HTTP runtime construction と application-facing server surface の中心
- `build_http_runtime_adapter(...)` 自体は `server.py` に残っている
- `CompositeRuntimeAdapter` はまだ `server.py` 側
- health/readiness/debug HTTP surface と runtime wiring の境界はまだ完全分離ではない
- stdio 削除前提の最終 boundary 整理は未完
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
- 一度 `_print_runtime_summary(...)` の import 互換が崩れて test collection error が出たため、`server.py` に private wrapper を戻しました
- 一度 orchestration helper 側の `create_runtime(...)` で
  - HTTP only 時に `None` が返る
  - BOTH 時に `CompositeRuntimeAdapter` 解決が欠ける
  問題が出ましたが修正済みです
- 最終的に **180 passed** で green に戻しています

## コミット
このセッション時点では、まだコミットは切っていません。

次の人は `.rules` に従って、作業ループ完了時に descriptive message で `git commit` してください。

コミット候補メッセージ例:
- `Extract runtime orchestration helpers`
- `Split runtime introspection from server module`

## 注意
- このセッションでは `last_session.md` の更新まで実施していますが、git commit は未実施です
- 既存ワークツリー上に別件の変更がある可能性は引き続きあります
- 今回の変更は transport orchestration / runtime introspection の extraction が中心で、full transport rewrite ではありません

## 実装の評価
今回の抽出は、Patch 2 の仕上げとしてかなり自然な前進です。

進んだこと:
- `server.py` から runtime introspection の本体を外出し
- `server.py` から transport override / signal / startup summary / CLI orchestration の本体を外出し
- stdio runtime adapter builder wiring を orchestration helper に寄せた
- `create_runtime(...)` の責務を wrapper + helper へ寄せた
- 将来 `server.py` を
  - health/readiness
  - workflow-facing server surface
  - HTTP runtime construction
  に近い責務へ寄せやすくなった
- composite runtime / HTTP only / stdio only の既存 expectation を維持したまま整理できた

まだ未着手に近いこと:
- `build_http_runtime_adapter(...)` の外出し
- `CompositeRuntimeAdapter` の配置見直し
- `create_server(...)` と runtime builder の境界再整理
- debug HTTP endpoints と runtime introspection の責務境界整理
- stdio deletion path を前提にした最終 dependency cleanup
- transport-specific startup orchestration の完全隔離

## 次にやること
次は以下のどれかが自然です。

候補:
1. `build_http_runtime_adapter(...)` を orchestration 側または dedicated transport module に外出しする
2. `CompositeRuntimeAdapter` を transport/runtime helper 側へ移して `server.py` 依存をさらに薄くする
3. `create_server(...)` と runtime builder の境界を整理して、server construction をさらに明確化する
4. debug/runtime introspection HTTP endpoints の責務を専用 helper へ寄せる
5. stdio removal path を意識して `server.py` から transport-specific startup orchestration をさらに隔離する

特に安全そうなのは:
- `build_http_runtime_adapter(...)` の抽出
- `CompositeRuntimeAdapter` の移設
- `create_server(...)` / `create_runtime(...)` の wiring 境界をさらに明確にすること

## 次の引き継ぎ先向けメモ
次に入る人は以下を前提にしてよいです。

1. Patch 1 の extraction は入っている
2. Patch 2 の scaffold も入っている
3. `mcp/rpc.py` への MCP RPC extraction は入っている
4. `mcp/stdio.py` への stdio responsibility split は入っている
5. stdio builder extraction は入っている
6. stdio runtime bootstrap helper split は入っている
7. stdio runtime construction split は入っている
8. 今回、runtime introspection helper split も入った
9. 今回、transport orchestration helper split も入った
10. `tests/test_server.py` と `tests/test_mcp_modules.py` を合わせて **180 passed**
11. `docs/specification.md` は引き続き触らない
12. まだ compliance claim はしない
13. 最終的には stdio は削除前提だが、現段階では責務分離を優先している

注意点:
- `server.py` はまだ大きいが、runtime introspection と run entrypoint orchestration の本体は外へ出始めた
- `create_runtime(...)` は public surface 維持のため `server.py` に wrapper として残っている
- `_print_runtime_summary(...)` も test/import 互換のため `server.py` に wrapper として残してある
- `runtime/orchestration.py` は `server.py` への依存を関数内 import で抑えつつ構成している
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

### まだ `server.py` に残るもの
- `build_http_runtime_adapter(...)`
- `CompositeRuntimeAdapter`
- `create_server(...)` の中心 wiring
- health/readiness/debug HTTP surface
- application-facing server surface 全般

## 次に自然な一手
ここまで来たので、次は **HTTP runtime construction と composite runtime の抽出** が一番きれいです。

たとえば:
- `build_http_runtime_adapter(...)`
- `CompositeRuntimeAdapter`
- `create_server(...)` の runtime wiring 補助

を別 helper / module に寄せる段階です。

これをやると、`server.py` はかなり
- health/readiness
- workflow-facing server surface
- bootstrap shell
- HTTP handler composition の最小面

に近づきます。

必要ならそのまま **transport orchestration の薄型化** をさらに進めて、
最終的な stdio removal path までつなげられます。