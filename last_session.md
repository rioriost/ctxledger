今回の変更
#### `ctxledger/docs/workflow-model.md`
projection failure lifecycle の operator semantics を明確化する追記を行いました。

主な更新内容:
- `resolved` の operational meaning を追記
  - `resolved` は successful reconciliation や同等の成功的 closure を意味する
  - operator が warning を消したいだけの場合とは区別する
  - `resolved_at` は failure が open でなくなった時刻を表す
- `ignored` の operator-handling semantics を追記
  - operator または上位 policy による suppression として扱う
  - successful projection recovery とは別物であることを明記
  - known-noncritical projection や temporary acceptance の例を補足
  - `resolved_at` があっても、closure reason の truth は `status` にあることを明記
- projection failure visibility rules に、read-side surface と operator-facing interpretation を補足
  - closed failure history は operator ignore 後も inspect 可能であるべき
  - `ignored` と `resolved` は timestamp ではなく lifecycle `status` で区別すべき
  - operator action は unresolved warning を消しても diagnostic history を消さない
- read-side surface の例に、dedicated closed failure history HTTP surface を追加
  - implemented な場合の例として扱う

---

#### 今回 docs で明確になったこと
projection failure lifecycle の意味づけは少なくとも次のように整理された状態です。

- `open`
  - projection write failure がまだ active unresolved issue
- `resolved`
  - successful reconciliation など、成功的 closure によって open でなくなった
- `ignored`
  - operator / policy により active unresolved issue として扱わないことにした
  - recovery 成功を意味しない

特に重要な整理:
- `resolved_at` は `resolved` と `ignored` の両方で closure time を持ちうる
- closure reason の判別は `resolved_at` ではなく `status` を見る
- operator ignore 後も closed history は残り続ける
- warning visibility は変わっても canonical diagnostic history は消えない

---

#### docs 全体との関係
この更新により、少なくとも次の docs 群と整合しやすい形になっています。

- `ctxledger/docs/architecture.md`
- `ctxledger/docs/mcp-api.md`
- `ctxledger/docs/specification.md`
- `ctxledger/docs/workflow-model.md`

関連する既存の concrete surface:
- dedicated closed failure history endpoint
  - `/workflow-resume/{workflow_instance_id}/closed-projection-failures`
- runtime/debug route naming
  - `workflow_closed_projection_failures`

---

### 現在の状態
closed projection failure history と projection failure lifecycle については、少なくとも以下の観点でだいぶ揃っています。

- server 実装
- route registration
- tests
- README
- MCP API docs
- architecture docs
- specification docs
- workflow model docs
- deployment / security docs
- changelog

特に、operator が failure を `ignored` として閉じた場合の意味が、workflow model docs 上で以前より明確になりました。

---

### 補足
- `.gitignore` は保守対象外として扱う前提
- handoff でも `.gitignore` は作業対象に含めない

---

### 次に自然な作業
次に自然なのは、未完了の surface や action を前に進めることです。例えば:

1. projection failure lifecycle の operator action surface を concrete API として設計する
2. 他の HTTP surface の contract を docs と実装で横並び確認する
3. workflow / memory 系の未完成 surface 実装へ進む
4. deployment / security / debug endpoint 周辺の残りの表現統一を続ける

この時点では、projection failure lifecycle の read-side と operator semantics の docs はかなり整理された状態です。