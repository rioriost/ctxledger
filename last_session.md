今回の変更
#### `ctxledger/src/ctxledger/server.py`
closed projection failure history の HTTP route 名と invalid path 時の error message の表記ゆれを揃えました。

反映内容:
- `build_http_runtime_adapter(...)` で登録する route 名を
  - `closed_projection_failures`
  から
  - `workflow_closed_projection_failures`
  に変更
- `build_closed_projection_failures_http_handler(...)` の 404 message を
  - `closed projection failure endpoint requires ...`
  から
  - `closed projection failures endpoint requires ...`
  に変更

意図:
- runtime introspection / debug routes / README examples / tests で使っている route 名
  `workflow_closed_projection_failures`
  と server 実装を一致させる
- singular / plural の message 表記ゆれを解消する

---

#### docs / tests / examples との整合性
今回の修正で、少なくとも以下の整合が取れた状態です。

- HTTP runtime route 名
  - `workflow_resume`
  - `workflow_closed_projection_failures`
- dedicated endpoint path
  - `/workflow-resume/{workflow_instance_id}/closed-projection-failures`
- invalid path 時の expected message
  - `closed projection failures endpoint requires /workflow-resume/{workflow_instance_id}/closed-projection-failures`

---

### 確認
- `ctxledger/src/ctxledger/server.py`: diagnostics 問題なし

### 現在の状態
closed projection failure history まわりは、少なくとも次の観点で揃っています。

- server 実装の route 登録名
- runtime/debug surface に出る route 名
- README の runtime example
- tests の期待値
- invalid path error message の文言

### 未実施
この時点では次はまだやっていません。

- `ctxledger/tests/test_server.py` の diagnostics 再確認
- 必要なら route 名変更分の最終 commit
- 今回の handoff を含めた git 状態の整理

### 次に自然な作業
次に自然なのは以下です。

1. `ctxledger/tests/test_server.py` と project 全体の diagnostics を確認
2. 必要なら README / docs の route 名表記を最終見直し
3. 変更一式を commit する

必要なら次セッションで、そのまま diagnostics 確認から commit まで続けます。