今回の変更
#### `ctxledger/docs/mcp-api.md`
projection failure lifecycle の HTTP action surface について、**auth enabled / disabled の両方の request example** を docs に追加しました。

今回の方針:
- すでに実装済みの HTTP route surface を、運用時の auth 有無の違いまで docs 上で明確化
- query-parameter ベースの current contract を、そのまま読んで使える例として整理
- 既存の success / validation error example と整合する形で説明粒度を揃える

---

### `docs/mcp-api.md` で追加・更新した内容
#### 1. auth enabled 時の HTTP request example を明確化
既存の representative request examples を、**authentication is enabled** の例であることが分かるように更新しました。

対象:
- `projection_failures_ignore`
- `projection_failures_resolve`

example で表現している内容:
- `Authorization: Bearer ...` を付ける形
- `workspace_id`
- `workflow_instance_id`
- `projection_type` (optional)
を query parameter で指定する current contract

---

#### 2. auth disabled 時の HTTP request example を追加
HTTP auth が無効な環境向けに、`Authorization` header を含まない representative request examples を追加しました。

追加した example 対象:
- `projection_failures_ignore`
- `projection_failures_resolve`

これにより docs 上で、
- auth enabled のときは bearer token が必要
- auth disabled のときは query parameter のみで request する
という運用差分が読み取れる状態になりました。

---

#### 3. 既存の action route docs との整合を維持
今回追加した request examples は、すでに docs に反映済みの以下と整合する形にしています。

整合対象:
- implemented HTTP action routes
  - `projection_failures_ignore`
  - `projection_failures_resolve`
- request shape
  - `path: str` contract 維持
  - query parameter 方式
- representative response fields
  - `workspace_id`
  - `workflow_instance_id`
  - `projection_type`
  - `updated_failure_count`
  - `status`
- representative validation error shape
  - `error.code = "invalid_request"`

---

#### `ctxledger/docs/SECURITY.md`
security docs に、HTTP projection failure action routes の **運用上の注意** を追加しました。

反映した主な内容:
- document purpose に
  - `operational cautions for HTTP action routes`
  を追加
- `/debug/*` 関連の route visibility 例に
  - `projection_failures_ignore`
  - `projection_failures_resolve`
  を追加
- 新しい節として `4.4 HTTP Action Route Cautions` を追加

`4.4` で明記した主なポイント:
- action routes は diagnostic read ではなく canonical state mutation surface であること
- HTTP auth 有効時は他の protected routes と同じ bearer-auth boundary で守ること
- untrusted caller に公開しないこと
- reverse proxy / VPN / private network など trusted operator path を推奨すること
- `projection_failures_ignore` は repair ではなく visibility closure であること
- `projection_failures_resolve` は reconciliation evidence があるときに使うこと
- manual lifecycle closure action をログで追跡できるようにすること

代表的な operational risk として:
- active failure visibility を早すぎるタイミングで隠してしまうこと
- recovery semantics を早すぎるタイミングで主張してしまうこと
- broad caller に workflow-related operational state mutation を許してしまうこと
- projection artifact state と failure lifecycle state を混同すること

も記載しました。

---

#### `ctxledger/docs/deployment.md`
deployment docs に、HTTP projection failure action routes の **運用 guidance** を追加しました。

反映した主な内容:
- `/debug/*` で見える representative route list に
  - `projection_failures_ignore`
  - `projection_failures_resolve`
  を追加
- `/debug/*` payload が reveal しうる route list にも同じ 2 route を追加
- `/debug/*` の話に続けて、HTTP projection failure action routes を
  **operational mutation surfaces**
  として扱う guidance を追加

deployment guidance で追記した主な内容:
- action routes も protected HTTP endpoints と同じ auth boundary で守ること
- trusted operators / trusted automation のみに expose すること
- network-accessible な環境では TLS termination と reverse-proxy access control を使うこと
- `workspace_id` / `workflow_instance_id` / optional `projection_type` は、logs や access traces で internal workflow metadata を示しうる operational identifiers として扱うこと
- general client-facing API として使わないこと
- `ignored` と `resolved` の意味論を運用で混同しないこと

---

### 今回変更したファイル
- `ctxledger/docs/mcp-api.md`
- `ctxledger/docs/SECURITY.md`
- `ctxledger/docs/deployment.md`
- `ctxledger/last_session.md`

---

### 確認結果
今回確認できている範囲:
- `ctxledger/docs/mcp-api.md`: diagnostics 問題なし
- `ctxledger/docs/SECURITY.md`: diagnostics 問題なし
- `ctxledger/docs/deployment.md`: diagnostics 問題なし

前回までに確認済みの状態:
- `ctxledger/src/ctxledger/server.py`: diagnostics 問題なし
- `ctxledger/tests/test_server.py`: diagnostics 問題なし
- `pytest -q tests/test_server.py`
  - `103 passed`

今回は docs 更新のみで、追加の test 実行は未実施です。

---

### git commit
- 今回の security / deployment / mcp-api docs 更新については、まだ git commit 未実施

---

### 補足
- `.gitignore` は引き続き変更対象に含めない前提
- この handoff は security / deployment docs の運用補足まで含む状態に更新
- 今回の作業では実装コード自体の変更は行っていない

---

### 現在の状態
projection failure lifecycle の public surface は、少なくとも以下が docs / implementation 上で整合しています。

#### read-side
- `workflow_resume`
- `/workflow-resume/{workflow_instance_id}/closed-projection-failures`

#### mutation-side (MCP / stdio)
- `projection_failures_ignore`
- `projection_failures_resolve`

#### mutation-side (HTTP runtime route surface)
- `projection_failures_ignore`
- `projection_failures_resolve`

#### docs
- `docs/mcp-api.md`
  - auth enabled / disabled の request example を追加済み
  - success / validation error example も反映済み
- `docs/SECURITY.md`
  - HTTP action route cautions を追加済み
- `docs/deployment.md`
  - HTTP action routes の deployment guidance を追加済み

---

### 次に自然な作業
次に自然なのは以下です。

1. 今回の docs 更新を descriptive message で git commit する
2. 必要なら `docs/CHANGELOG.md` に security / deployment docs 反映の補足を追加する
3. HTTP-oriented integration coverage を広げる
4. action routes の representative operational logging guidance を docs でもう少し具体化する