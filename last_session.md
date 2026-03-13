このプロジェクトでは、Dockerコンテナで動作するリモートMCPサーバを作成しています。

直近の進捗:
- HTTP `/mcp` に対する最小MCP経路として、`initialize` / `tools/list` / `tools/call` の実装とテスト確認は完了しています。
- 追加で、HTTP側の `resources/list` / `resources/read` も実装・テスト確認できる状態にしました。
- `HttpRuntimeAdapter` は `registered_resources()` / `dispatch_resource()` を持ち、runtime introspection でも `tools` / `resources` を返すようになっています。
- `tests/test_server.py` を更新し、HTTP MCP の resource 系も含めて `pytest` 通過を確認しました。
- 現在のテスト結果は `169 passed` です。

ただし、pytestだけでは不十分です。
Docker環境は用意してあるので、次は以下を進める必要があります:
1. Docker環境でリモートMCPサーバを実際に起動する
2. minimumなMCPクライアントを用意する
3. そのクライアントから `/mcp` に接続し、少なくとも `0.1.0` の受け入れ対象機能が動くことを確認する
4. 可能ならその確認を再現可能なスクリプトまたは手順として repository に残す

次セッションで優先してやること:
- Docker compose / 起動手順の確認
- minimum MCP client の実装または簡易スクリプト化
- `initialize` → `tools/list` → `tools/call` のE2E確認
- 必要なら `resources/list` / `resources/read` もE2E確認
- README か docs に、実サーバ確認手順を反映