Patch 2 の scaffold 実装、MCP RPC extraction の一部、そして dedicated MCP module test split まで進めました。

今回の実装でやったこと:

- `ctxledger/src/ctxledger/mcp/lifecycle.py` を新設
- `ctxledger/src/ctxledger/mcp/streamable_http.py` を新設
- `ctxledger/src/ctxledger/mcp/rpc.py` を新設
- `ctxledger/src/ctxledger/server.py` を更新して、MCP lifecycle / Streamable HTTP scaffold / RPC helper を経由するように変更
- `ctxledger/tests/test_mcp_modules.py` を新設
- `ctxledger/tests/test_server.py` から MCP scaffold / RPC helper 向け focused test を分離

## 1. `ctxledger/src/ctxledger/mcp/lifecycle.py`
Patch 2 の lifecycle authority 移行の最初の足場として、MCP lifecycle 用の helper 群を追加しました。

追加したもの:
- `MCP_PROTOCOL_VERSION`
- `McpServerInfo`
- `McpLifecycleCapabilities`
- `McpInitializeResult`
- `McpJsonRpcSuccessResponse`
- `McpJsonRpcError`
- `McpJsonRpcErrorResponse`
- `McpLifecycleState`
- `McpLifecycleRuntime`
- `build_initialize_result(...)`
- `handle_initialize_request(...)`
- `handle_initialized_notification(...)`
- `handle_ping_request(...)`
- `handle_shutdown_request(...)`
- `is_initialized_notification(...)`
- `dispatch_lifecycle_method(...)`
- `build_jsonrpc_success_response(...)`
- `build_jsonrpc_error_response(...)`

ポイント:
- `initialize` の result 組み立てを `server.py` 直書きから外しました
- `initialized` に加えて `notifications/initialized` も lifecycle helper 側で受けられるようにしました
- lifecycle state として `initialized` / `negotiated_protocol_version` を持てるようにしています
- まだ strict compliance を主張する段階ではなく、あくまで scaffold です

## 2. `ctxledger/src/ctxledger/mcp/streamable_http.py`
HTTP `/mcp` を generic route の生実装から少し切り離すため、薄い Streamable HTTP scaffold を追加しました。

追加したもの:
- `StreamableHttpRequest`
- `StreamableHttpResponse`
- `StreamableHttpEndpoint`
- `StreamableHttpRuntime`
- `build_streamable_http_endpoint(...)`
- `default_streamable_http_headers(...)`
- `build_streamable_http_not_found_response(...)`
- `build_streamable_http_invalid_request_response(...)`
- `build_streamable_http_rpc_error_response(...)`

現在の責務:
- path が設定された MCP endpoint と一致するかを確認
- JSON-RPC body 必須を保証
- JSON parse / object shape を検証
- RPC handler へ委譲
- transport レベルの not_found / invalid_request / RPC error を正規化

注意:
- SSE や streaming 本体はまだありません
- つまり full Streamable HTTP transport 実装ではなく、endpoint scaffold です

## 3. `ctxledger/src/ctxledger/mcp/rpc.py`
`server.py` に残っていた MCP RPC branching の一部を、専用 helper module として抽出しました。

追加したもの:
- `McpRpcRuntime`
- `LIFECYCLE_METHODS`
- `ensure_lifecycle_state(...)`
- `handle_mcp_rpc_request(...)`
- `dispatch_rpc_method(...)`

内部 helper:
- `_dispatch_lifecycle_request(...)`
- `_build_tools_list_result(...)`
- `_build_tools_call_result(...)`
- `_build_resources_list_result(...)`
- `_build_resources_read_result(...)`

ポイント:
- `server.py` に残っていた `handle_mcp_rpc_request(...)` を `mcp/rpc.py` へ移しました
- lifecycle dispatch と non-lifecycle RPC branching の境界を少し明確にしました
- `tools/list`
- `tools/call`
- `resources/list`
- `resources/read`
  の JSON-RPC result 組み立てを RPC helper 側に寄せました
- `exit` も RPC helper 側で扱うようにしています

これは Patch 2 の延長として、
「protocol branching を server.py から少しずつ外へ出す」
作業です。

## 4. `ctxledger/src/ctxledger/server.py`
`server.py` 側は Patch 2 の範囲で authority をさらに少し移しました。

変更点:
- `handle_mcp_rpc_request(...)` の実装本体を削除し、`mcp/rpc.py` から import する形に変更
- lifecycle helper の直接利用箇所を減らし、RPC helper 経由へ寄せました
- `build_mcp_http_handler(...)` は引き続き `mcp/streamable_http.py` の endpoint scaffold を使う構造です
- `StdioRpcServer` は `mcp.rpc.handle_mcp_rpc_request(...)` を呼ぶ薄い wrapper になっています
- `StdioRuntimeAdapter` は引き続き `_mcp_lifecycle_state` を保持します

意図:
- protocol authority を少しずつ `server.py` 外へ動かす
- `/mcp` だけでなく RPC method branching 自体も分離していく
- ただし transport rewrite を一気にやらず、安全に置き換える

## 5. `ctxledger/tests/test_mcp_modules.py`
MCP scaffold / RPC helper 向けの focused test を、`tests/test_server.py` から独立した dedicated module に分離しました。

追加した主な確認:
- `build_initialize_result(...)` の payload
- `dispatch_lifecycle_method(...)` の initialize / `notifications/initialized`
- `build_jsonrpc_success_response(...)`
- `build_jsonrpc_error_response(...)`
- `handle_mcp_rpc_request(...)` が `notifications/initialized` を受けて lifecycle state を更新すること
- `handle_mcp_rpc_request(...)` の initialize / `tools/list` / `tools/call` / `resources/list` / `resources/read`
- `build_streamable_http_not_found_response(...)`
- `build_streamable_http_invalid_request_response(...)`
- `build_streamable_http_rpc_error_response(...)`
- `StreamableHttpEndpoint` が notification で `202` を返すこと
- `StreamableHttpEndpoint` が RPC exception を JSON-RPC error payload に正規化すること
- `StreamableHttpEndpoint` が auth validator を RPC handler より先に評価すること

ポイント:
- これまで `tests/test_server.py` に追記していた scaffold test を切り出しました
- module 単位で責務が見やすくなりました
- 今後 `mcp/lifecycle.py` / `mcp/streamable_http.py` / `mcp/rpc.py` を触る際の影響範囲確認がしやすくなりました

## 6. `ctxledger/tests/test_server.py`
`test_server.py` からは、MCP scaffold / RPC helper 直属の focused test を外し、server wiring / runtime integration / route behavior 中心の構成へ少し戻しました。

現在こちらに残している主な責務:
- server bootstrap / readiness / health
- runtime adapter behavior
- HTTP route behavior
- stdio runtime wiring
- tool / resource handler integration
- transport-level integration 的な確認

## 7. 挙動面での現状
今回の Patch 2 は scaffold と extraction 中心なので、既存挙動を大きく変えないことを優先しています。

維持しているもの:
- `initialize` over HTTP
- `tools/list`
- `tools/call`
- `resources/list`
- `resources/read`
- 既存の `/mcp` path validation
- HTTP auth の挙動
- invalid JSON / invalid object / missing body 時のエラー挙動
- stdio / HTTP いずれも共通の RPC helper を利用する構造

新しく入ったもの:
- `notifications/initialized` の受け口
- lifecycle state を runtime 側に保持する足場
- Streamable HTTP endpoint scaffold
- MCP RPC helper module
- dedicated MCP module tests
- `test_server.py` と MCP module test の責務分離

まだ残っているもの:
- `server.py` が依然として transport orchestration の中心
- stdio / HTTP adapter はまだ `server.py` に強く残る
- `/mcp` は endpoint scaffold 化したが、本格的な stream transport 実装ではない
- result mapping や richer MCP semantics はまだ local envelope 寄り
- compliance claim はまだ不可

## テスト
確認したテスト:
- `tests/test_server.py`
- `tests/test_mcp_modules.py`

結果:
- **180 passed**

内訳イメージ:
- `test_server.py`: 既存 integration / wiring 系中心
- `test_mcp_modules.py`: scaffold / RPC helper 系

Patch 2 scaffold test の分離後も green を維持しています。

## コミット
コミット済みです。

- `1e56326`
- `Add MCP lifecycle and HTTP scaffolding`

- `54ce889`
- `Add tests for MCP lifecycle scaffolding`

- `da76b3b`
- `Extract MCP RPC dispatcher helpers`

## 注意
- ワークツリー上にはこのコミット群に含めていない他の変更
  （例: `src/ctxledger/db/postgres.py` や `docs/plans/*` など）
  が別途存在している前提でした
- 今回のコミット群は Patch 2 scaffold 関連、test 追加、RPC extraction を中心にしています

## 実装の評価
Patch 2 としては、かなり小さく安全に前進できています。

進んだこと:
- lifecycle authority の一部を `mcp/lifecycle.py` へ分離
- `/mcp` HTTP handling の transport-scaffold を `mcp/streamable_http.py` へ分離
- `handle_mcp_rpc_request(...)` を `mcp/rpc.py` に抽出
- `server.py` が直接抱えていた protocol / endpoint / RPC branching 責務を少し削減
- MCP module 向け focused test を dedicated file に分離
- scaffold 層の変更に対する安全性と見通しが少し上がった

まだ未着手に近いこと:
- stdio 側の protocol surface のさらに明確な分離
- HTTP/stdio の adapter 境界整理
- richer capability negotiation
- stream semantics / session semantics の本実装
- full MCP transport compliance に向けた gap 解消

## 次にやること
次は Patch 2 の仕上げ、または Patch 3 相当の整理に入るのが自然です。

候補:
1. stdio adapter 側にも lifecycle / rpc dispatcher の責務分離を進める
2. HTTP endpoint scaffold を session-aware / richer transport-aware に育てる
3. capability surface をもう少し明示化する
4. `server.py` に残る transport orchestration の薄型化を進める
5. MCP module 側の test utility を共通化する

特に安全そうなのは:
- stdio 側の protocol helper 抽出
- HTTP/stdio で共有する RPC runtime adapter 境界の整理
- `test_mcp_modules.py` の fake runtime / settings helper の整理

## 次の引き継ぎ先向けメモ
次に入る人は以下を前提にしてよいです。

1. Patch 1 の extraction は入っている
2. Patch 2 の scaffold も入った
3. `mcp/rpc.py` への MCP RPC extraction も一部入った
4. `tests/test_server.py` と `tests/test_mcp_modules.py` を合わせて **180 passed**
5. `docs/specification.md` は引き続き触らない
6. まだ compliance claim はしない
7. いまの変更は「authority の移設と scaffold / RPC helper 追加」であって、full transport rewrite ではない

注意点:
- `server.py` から `handle_mcp_rpc_request(...)` 本体は外れたが、transport orchestration 自体はまだ強く残る
- `build_mcp_http_handler(...)` は streamable_http scaffold を使うようになっている
- MCP scaffold / helper 系 test は `tests/test_mcp_modules.py` に分離済み
- 既存の green 状態は **180 passed** を基準に見てよい