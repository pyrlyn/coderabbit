# coderabbit

Central [CodeRabbit](https://coderabbit.ai) configuration for all pyrlyn repositories.

CodeRabbit reads `.coderabbit.yaml` from this repository for every pyrlyn repository that does
not have its own `.coderabbit.yaml`
([central configuration](https://docs.coderabbit.ai/configuration/central-configuration)).
A repository file replaces this configuration entirely, so repositories should not keep their
own `.coderabbit.yaml`. Change shared CodeRabbit behaviour here, through a pull request.

The CodeRabbit GitHub App must have access to this repository.

## CI

- `validate` (push/PR): checks `.coderabbit.yaml` against
  [schema.v2.json](https://coderabbit.ai/integrations/schema.v2.json) and asserts quiet mode
  (`reviews.auto_review.enabled`, `reviews.high_level_summary`, `reviews.review_status`,
  `reviews.poem`, `chat.auto_reply` are all `false`).
- `sync` (push to main, daily, manual): copies `.coderabbit.yaml` into the root of every
  non-archived pyrlyn repository. Own configs that differ, and stray `.coderabbit.yml` /
  `.github/.coderabbit.*`, are deleted by a direct commit to the default branch (if a ruleset
  blocks it, the deletion goes into the PR; rulesets are never bypassed). The central file is
  added via a PR from `chore/sync-coderabbit-config` with squash auto-merge. Identical repos
  are skipped.

### Token

Secret `CODERABBIT_SYNC_TOKEN` in this repository: a fine-grained PAT or GitHub App token on
organization pyrlyn, All repositories, with Contents: Read and write, Pull requests: Read and
write, Metadata: Read (a classic PAT needs `repo`).
