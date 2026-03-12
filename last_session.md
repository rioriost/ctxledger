今回の変更
#### docs 更新
closed projection failure history の dedicated HTTP read surface に合わせて、関連ドキュメントを更新しました。

更新したファイル:
- `ctxledger/README.md`
- `ctxledger/docs/mcp-api.md`
- `ctxledger/docs/architecture.md`
- `ctxledger/docs/specification.md`

---

#### `ctxledger/README.md`
以下を反映しました。

- resume / projection failure lifecycle の説明に、dedicated HTTP history endpoint を追加
- `## MCP Surface` に concrete HTTP read endpoints を追加
  - `/workflow-resume/{workflow_instance_id}`
  - `/workflow-resume/{workflow_instance_id}/closed-projection-failures`
- closed failure history endpoint の response shape を追記
  - `workflow_instance_id`
  - `closed_projection_failures`
- 各 closed failure entry の主要 field を追記
  - `projection_type`
  - `target_path`
  - `attempt_id`
  - `error_code`
  - `error_message`
  - `occurred_at`
  - `resolved_at`
  - `open_failure_count`
  - `retry_count`
  - `status`
- debug/runtime と debug/routes の example route list を更新
  - `workflow_closed_projection_failures` を追加
- startup summary example の runtime route list も更新

---

#### `ctxledger/docs/mcp-api.md`
以下を反映しました。

- `## 3.4 Dedicated HTTP Read Surface` を新設
- `/workflow-resume/{workflow_instance_id}/closed-projection-failures` を明文化
- endpoint の位置づけを整理
  - canonical state 上の read-only assembled HTTP surface
  - full resume を取らずに closed failure history だけ読める narrow surface
  - MCP tools / resources の責務分離は維持
- `workflow_resume` 節にも、
  - 同じ closed failure history が dedicated HTTP route でも読めること
  - narrow payload が `workflow_instance_id` + `closed_projection_failures` であること
  を追記

---

#### `ctxledger/docs/architecture.md`
以下を反映しました。

- composite resume view の説明に、
  - assembled read model が concrete server-specific HTTP read surface としても expose されうること
  を追記
- projection failure visibility rules に、
  - dedicated HTTP read surface
    `/workflow-resume/{workflow_instance_id}/closed-projection-failures`
  - representative payload
    - `workflow_instance_id`
    - `closed_projection_failures`
  - closed failure entry field 群
  を追記
- この surface は canonical projection failure history 上の read-only convenience endpoint であり、
  PostgreSQL canonical / projection derived の原則は変わらないことを明記

---

#### `ctxledger/docs/specification.md`
以下を反映しました。

- `workflow_resume` の representative response contents に
  - closed projection failure history
  を追加
- resume 経由の closed history に加えて、
  dedicated HTTP read surface を追加
  - `GET /workflow-resume/{workflow_instance_id}/closed-projection-failures`
- representative response fields / behavior notes を追記
  - read-only assembled HTTP surface
  - closed lifecycle history only
  - open failures は引き続き resume warnings 側で可視化
  - closed lifecycle records は `resolved` または `ignored`

---

### 現在の状態
docs は、新しく追加済みの concrete server surface に概ね追従しました。

少なくとも次が docs 上で説明される状態です。

- resume 全体での closed projection failure history 可視化
- dedicated HTTP endpoint:
  - `/workflow-resume/{workflow_instance_id}/closed-projection-failures`
- route-level runtime examples における
  - `workflow_closed_projection_failures`
  の反映

### 未実施
この時点では次はまだやっていません。

- `ctxledger/docs/CHANGELOG.md` への今回 docs 変更の明示的追記
- `ctxledger/last_session.md` の今回内容への更新
- `git commit`

### 次に自然な作業
次に自然なのは以下です。

1. `ctxledger/last_session.md` を今回の docs 更新内容で更新
2. 必要なら `docs/CHANGELOG.md` に docs 反映や endpoint 追加の記述を整える
3. 変更一式を `git commit` する

必要なら次セッションで、そのまま handoff 更新と commit まで続けます。