Patch 2 の scaffold 実装と、その追加テストまで進めました。

今回の実装でやったこと:

- `ctxledger/src/ctxledger/mcp/lifecycle.py` を新設
- `ctxledger/src/ctxledger/mcp/streamable_http.py` を新設
- `ctxledger/src/ctxledger/server.py` を更新して、MCP lifecycle / Streamable HTTP scaffold を経由するように変更
- `ctxledger/tests/test_server.py` に Patch 2 scaffold 向けの focused test を追加

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

## 3. `ctxledger/src/ctxledger/server.py`
`server.py` 側は Patch 2 の範囲で authority を少し移しました。

変更点:
- `handle_mcp_rpc_request(...)` が lifecycle helper を使うように変更
- `initialize` / `initialized` / `notifications/initialized` / `ping` / `shutdown` の分岐を lifecycle module 経由に変更
- JSON-RPC success envelope を lifecycle module の helper で返すように変更
- `StdioRuntimeAdapter` に `_mcp_lifecycle_state` を持たせました
- `build_mcp_http_handler(...)` が、直接 JSON parse / path validate / error mapping を行う形から、
  `mcp/streamable_http.py` の endpoint scaffold を使う形に変更されました

意図:
- protocol authority を少しずつ `server.py` 外へ動かす
- `/mcp` を「ただの generic route」ではなく、MCP endpoint scaffold 経由で扱う
- ただし transport rewrite を一気にやらず、安全に置き換える

## 4. `ctxledger/tests/test_server.py`
Patch 2 で追加した scaffold に対して、focused test を追加しました。

追加した主な確認:
- `build_initialize_result(...)` の payload
- `dispatch_lifecycle_method(...)` の initialize / `notifications/initialized`
- `build_jsonrpc_success_response(...)`
- `build_jsonrpc_error_response(...)`
- `handle_mcp_rpc_request(...)` が `notifications/initialized` を受けて lifecycle state を更新すること
- `build_streamable_http_not_found_response(...)`
- `build_streamable_http_invalid_request_response(...)`
- `build_streamable_http_rpc_error_response(...)`
- `StreamableHttpEndpoint` が notification で `202` を返すこと
- `StreamableHttpEndpoint` が RPC exception を JSON-RPC error payload に正規化すること
- `StreamableHttpEndpoint` が auth validator を RPC handler より先に評価すること

重要:
- 既存の `tests/test_server.py` に追記する形に留めています
- 新規 module 専用 test file に分離するところまではまだやっていません

## 5. 挙動面での現状
今回の Patch 2 は scaffold 中心なので、既存挙動を大きく変えないことを優先しています。

維持しているもの:
- `initialize` over HTTP
- `tools/list`
- `tools/call`
- 既存の `/mcp` path validation
- HTTP auth の挙動
- invalid JSON / invalid object / missing body 時のエラー挙動
- stdio / HTTP いずれも `handle_mcp_rpc_request(...)` を共通利用する構造

新しく入ったもの:
- `notifications/initialized` の受け口
- lifecycle state を runtime 側に保持する足場
- Streamable HTTP endpoint scaffold
- Patch 2 scaffold の focused test

まだ残っているもの:
- `server.py` が依然として transport orchestration の中心
- stdio / HTTP adapter はまだ `server.py` に強く残る
- `/mcp` は endpoint scaffold 化したが、本格的な stream transport 実装ではない
- result mapping や richer MCP semantics はまだ local envelope 寄り
- compliance claim はまだ不可

## テスト
確認したテスト:
- `tests/test_server.py`

結果:
- **175 passed**

前回の 163 passed から、Patch 2 scaffold test を足したうえで green を維持しています。

## コミット
コミット済みです。

- `1e56326`
- `Add MCP lifecycle and HTTP scaffolding`

このコミットには以下が含まれています:
- `mcp/lifecycle.py`
- `mcp/streamable_http.py`
- `server.py` の scaffold wiring
- `last_session.md` 更新

注意:
- ワークツリー上にはこのコミットに含めていない他の変更
  （例: `src/ctxledger/db/postgres.py` や `docs/plans/*` など）
  が別途存在している前提でした
- 今回のコミットは Patch 2 scaffold 関連だけを対象にしています

## 実装の評価
Patch 2 としては、かなり小さく安全に前進できています。

進んだこと:
- lifecycle authority の一部を `mcp/lifecycle.py` へ分離
- `/mcp` HTTP handling の transport-scaffold を `mcp/streamable_http.py` へ分離
- `server.py` が直接抱えていた protocol / endpoint 責務を少し削減
- 将来の stricter MCP transport 実装に向けた差し替えポイントができた
- scaffold 層の focused test が入り、今後の分離作業の安全性が少し上がった

まだ未着手に近いこと:
- stdio 側の protocol surface のさらに明確な分離
- HTTP/stdio の adapter 境界整理
- richer capability negotiation
- stream semantics / session semantics の本実装
- full MCP transport compliance に向けた gap 解消
- test の module 単位分離

## 次にやること
次は Patch 2 の仕上げ、または Patch 3 相当の整理に入るのが自然です。

候補:
1. `server.py` から `handle_mcp_rpc_request(...)` の残りの protocol branching をさらに剥がす
2. stdio adapter 側にも lifecycle / rpc dispatcher の責務分離を進める
3. HTTP endpoint scaffold を session-aware / richer transport-aware に育てる
4. capability surface をもう少し明示化する
5. `tests/test_server.py` 依存だけでなく、新規 module 単体テストへ分離する

特に安全そうなのは:
- `mcp/lifecycle.py` と `mcp/streamable_http.py` の test を `test_server.py` から独立させる
- `server.py` の `handle_mcp_rpc_request(...)` 残余分岐の薄型化
- stdio 側の protocol helper 抽出

## 次の引き継ぎ先向けメモ
次に入る人は以下を前提にしてよいです。

1. Patch 1 の extraction は入っている
2. Patch 2 の scaffold も入った
3. `tests/test_server.py` は **175 passed**
4. `docs/specification.md` は引き続き触らない
5. まだ compliance claim はしない
6. いまの変更は「authority の移設と scaffold 追加」であって、full transport rewrite ではない

注意点:
- `handle_mcp_rpc_request(...)` はまだ `server.py` に残っているが、lifecycle 部分は helper 化された
- `build_mcp_http_handler(...)` は streamable_http scaffold を使うようになった
- `tests/test_server.py` に scaffold test を足してあるので、次に test を触るなら
  module 単位への切り出しを優先すると整理しやすい
- 既存の green 状態は `175 passed` を基準に見てよい