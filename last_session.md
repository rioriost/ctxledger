今回の変更
#### `ctxledger/docs/mcp-api.md`
projection failure lifecycle の operator action surface を concrete API 設計として整理する追記を行いました。

主な追加内容:
- dedicated closed failure history read surface に加えて、
  operator action surface の存在意義を明文化
- representative operator action intents を追加
  - matching open projection failures を `ignored` にする
  - matching open projection failures を `resolved` にする
  - 単一 `projection_type` または workflow 全体で scope できる
- action surface の design constraints を追加
  - canonical projection failure lifecycle state を mutate する
  - projection file contents を直接 mutate するものではない
  - failure history は削除せず保持する
  - `ignored` と `resolved` の意味を混同しない
  - narrow read-only history endpoint とは責務を分ける

---

#### `workflow_resume` 節で整理した operator action API design
`docs/mcp-api.md` の `workflow_resume` / projection lifecycle 節に、
representative future tool design として以下を追記しました。

Representative future tool examples:
- `projection_failures_ignore`
- `projection_failures_resolve`

Representative intended behavior:
- `projection_failures_ignore`
  - matching `open` projection failure records を `ignored` として close
  - closed history は保持
  - `open projection failure` warning は消える
  - successful projection repair を主張しない
- `projection_failures_resolve`
  - matching `open` projection failure records を `resolved` として close
  - closed history は保持
  - successful reconciliation または recovery-oriented closure を記録
  - `open projection failure` warning は消える

Representative selector fields:
- `workspace_id`
- `workflow_instance_id`
- `projection_type`

Representative response fields:
- `workspace_id`
- `workflow_instance_id`
- `projection_type` (scoped の場合)
- `updated_failure_count`
- `status`

Representative response status values:
- `ignored`
- `resolved`

Representative error cases:
- workspace not found
- workflow not found
- workflow/workspace mismatch
- authentication failure
- persistence failure

Design note として明記したこと:
- canonical projection failure lifecycle state を操作する API である
- failure history は delete しない
- projection write / reconciliation 自体を代替する API ではない
- `ignored` と `resolved` の差分は、その後の resume / closed history でも見え続けるべき

---

#### 既存実装との関係
この設計追記は、少なくとも既存の service / repository にある次の capability と整合する想定です。

- `resolve_resume_projection_failures(...)`
- `ignore_resume_projection_failures(...)`

つまり今回の docs は、
完全な新概念を追加したというより、

- 既存の internal capability
- 既存の read-side lifecycle semantics
- 今後の public mutation surface

をつなぐための API design 整理です。

---

#### read-side との責務分離
この時点で projection failure lifecycle の surface は、概念上は次の 2 系統に分けて整理されています。

1. read-side
- `workflow_resume`
- dedicated history endpoint
  - `/workflow-resume/{workflow_instance_id}/closed-projection-failures`

2. operator action / mutation-side
- future MCP tools
  - `projection_failures_ignore`
  - `projection_failures_resolve`

重要な整理:
- read-side は assembled view を返す
- mutation-side は canonical lifecycle state を更新する
- read-side と mutation-side を混同しない
- `ignored` は visibility/handling closure
- `resolved` は recovery/evidence-backed closure

---

### 現在の状態
projection failure lifecycle まわりは、少なくとも docs 上では次の観点でかなり揃っています。

- lifecycle semantics
  - `open`
  - `resolved`
  - `ignored`
- closed failure history read-side
- dedicated HTTP history endpoint
- runtime/debug route naming
- operator semantics
- future operator action API design

特に、次の整理が docs 上で明確です。

- `/workflow-resume/{workflow_instance_id}/closed-projection-failures`
  は narrow read-only history surface
- `projection_failures_ignore` / `projection_failures_resolve`
  は future mutation surface の representative design
- `ignored` と `resolved` は後続の resume / history でも区別され続けるべき

---

### 補足
- `.gitignore` は保守対象外として扱う前提
- この handoff でも `.gitignore` は作業対象に含めない

---

### 次に自然な作業
次に自然なのは、docs 設計から implementation へ進めることです。例えば:

1. `projection_failures_ignore` / `projection_failures_resolve` の public surface を実装する
   - MCP tool として出すか
   - HTTP action endpoint としても出すか
   - あるいは両方出すか
2. request / response schema を具体化する
3. auth / error mapping / tests を追加する
4. docs と implementation を同時に前進させる

この時点では、operator action surface の API design は docs 上でかなり整理された状態です。