今回の変更
#### expose MCP tool input schemas so clients can discover correct arguments for stdio tools

直前の確認で、`workspace_register` などの MCP ツールは**実装上は正しい引数を要求している**一方、`tools/list` で返す `inputSchema` が空だったため、MCP クライアントが事前に正しい引数を知れない状態になっていました。

今回の方針:
- stdio MCP runtime で **各ツールの入力 schema を明示的に保持・公開**する
- `tools/list` が空 schema ではなく、実際の引数仕様を返すようにする
- `workspace_register` だけでなく、現在公開している workflow / projection failure / memory tools まで含めて schema を揃える
- 追加した schema 公開が壊れていないことを tests で確認する

---

### 今回の実装変更
#### 1. `ctxledger/src/ctxledger/server.py`
主な変更内容:
- `McpToolSchema` dataclass を追加
- `StdioRuntimeAdapter` に
  - tool schema 保持
  - `tool_schema(tool_name)` 参照
  - handler 登録時の schema 登録
  を追加
- `tools/list` が各ツールの `inputSchema` を返すように更新
- schema serialization helper を追加
- 各 stdio tool に対応する schema 定義を追加

追加した主な schema:
- `workspace_register`
  - required:
    - `repo_url`
    - `canonical_path`
    - `default_branch`
  - optional:
    - `workspace_id`
    - `metadata`
- `workflow_resume`
  - required:
    - `workflow_instance_id`
- `workflow_start`
  - required:
    - `workspace_id`
    - `ticket_id`
- `workflow_checkpoint`
  - required:
    - `workflow_instance_id`
    - `attempt_id`
    - `step_name`
  - optional:
    - `summary`
    - `checkpoint_json`
    - `verify_status`
    - `verify_report`
- `workflow_complete`
  - required:
    - `workflow_instance_id`
    - `attempt_id`
    - `workflow_status`
  - optional:
    - `summary`
    - `verify_status`
    - `verify_report`
    - `failure_reason`
- `projection_failures_ignore`
- `projection_failures_resolve`
  - required:
    - `workspace_id`
    - `workflow_instance_id`
  - optional:
    - `projection_type`
- memory stub tools:
  - `memory_remember_episode`
  - `memory_search`
  - `memory_get_context`

これにより、stdio MCP クライアントは `tools/list` の結果から:
- required fields
- optional fields
- UUID / enum / boolean / integer などの型情報

を事前に把握できるようになった。

---

### 今回の根本改善
修正前の問題:
- `tools/list` は各ツールに対して
  - `type: object`
  - `properties: {}`
  しか返していなかった
- そのためクライアントは
  - `workspace_register` の存在は見える
  - でも `repo_url` / `canonical_path` / `default_branch` を知らない
  という状態だった

修正後:
- `tools/list` が、各ツールの実引数仕様を返す
- その結果、MCP クライアントは正しいフォーム生成・入力補助・事前検証を行える

今回の意味合い:
- これは単なる docs 補強ではなく、**MCP server/client interoperability の修正**
- これで `workspace_register` のようなツールは、エラーメッセージ頼みではなく **機械可読な schema で discoverable** になった

---

### 追加したテスト
#### 2. `ctxledger/tests/test_server.py`
今回追加・更新した主な確認:
- `build_stdio_runtime_adapter()` が tool schema を保持していること
- `runtime.tool_schema("workspace_register")` から required fields を取得できること
- `runtime.tool_schema("memory_get_context")` から boolean fields を取得できること
- `StdioRpcServer.handle_request()` の `tools/list` が
  - `workspace_register`
  - `workflow_start`
  - `workflow_complete`
  - `memory_get_context`
  などに対して期待通りの `inputSchema` を返すこと

これにより、
- runtime 内部保持
- MCP `tools/list` 公開面
の両方がテストでカバーされた。

---

### テスト結果
実行した確認:
- `pytest -q tests/test_server.py`

結果:
- `153 passed`

前回 handoff 時点では `152 passed` だったため、
今回の schema exposure 対応と追加テスト込みで `153 passed` に増えた。

---

### 変更ファイル
今回変更したファイル:
- `ctxledger/src/ctxledger/server.py`
- `ctxledger/tests/test_server.py`
- `ctxledger/last_session.md`

---

### 現在の評価
この時点で、以前の main open issue だった
- MCP クライアントが `workspace_register` の正しい引数を知れない
という問題については、**stdio MCP surface として修正済み**と見てよい。

現状の理解:
- 実装上の required fields は以前から正しかった
- 欠けていたのは schema exposure
- 今回それを runtime に実装し、tests で確認した

つまり `workspace_register` の問題は、
**ツール本体の validation 不足ではなく、tool schema publication 不足だった**
という整理で確定できる。

---

### 次に自然な作業
次に自然なのは以下。
1. `README.md` / `docs/mcp-api.md` に
   - stdio `tools/list` が input schema を返すこと
   - `workspace_register` の required / optional fields
   を明記する
2. 必要なら debug/introspection docs に、tool schema discoverability の観点を追記する
3. repo housekeeping として、この変更を descriptive message で commit する

### 要約
- stdio MCP runtime に tool input schema 公開を実装
- `tools/list` が空 schema ではなく、実引数仕様を返すように修正
- `workspace_register` を含む公開 stdio tools に schema を付与
- `tests/test_server.py` に schema exposure の確認を追加
- `pytest -q tests/test_server.py` は `153 passed`
