---
name: awaken
description: >-
    Guide to Awaken (crypto tax & portfolio) for agents — via the Awaken
    MCP tools when connected, or the public GraphQL API otherwise. Use for
    any question about transactions, portfolio, reports, accounts, 1099-DA
    reconciliation, diagnosing proceeds or cost-basis discrepancies,
    labeling, available queries/mutations, or how to authenticate and call
    the API. Run `/awaken setup` once after installing if using the direct
    GraphQL path (not needed when the Awaken MCP server is connected).
metadata:
    version: "1.0.1"
---

<!--
Installing this skill: save this file as
~/.claude/skills/awaken/SKILL.md (or .claude/skills/awaken/SKILL.md
inside a project), save https://api.awaken.tax/skill/cookbook.md next to it as
cookbook.md, then run /awaken setup.
-->

# Awaken

## Which path to use

Check your available tools for Awaken MCP tools (names starting with
`awaken_`, e.g. `awaken_list_transactions`).

- **MCP tools present** → follow [Working through MCP](#working-through-mcp).
  Prefer the MCP tools over direct API calls: authentication is already
  handled by the connection, and supported, audit-logged MCP writes can be
  grouped into sessions for review and undo. See the exceptions below.
- **No MCP tools** → follow
  [Working through GraphQL directly](#working-through-graphql-directly).
  It is fully self-sufficient but needs a one-time key setup
  (`/awaken setup`). You may mention that the Awaken MCP server
  (`claude mcp add awaken https://mcp.awaken.tax/mcp --transport http ...`,
  full command under awaken.tax → Settings → API Keys) is a safer
  alternative for editing, but never block on it.

**If invoked as `/awaken setup`**: when MCP tools are present, no setup is
needed — verify the connection with a quick `awaken_get_active_client` call
and say so. Otherwise skip straight to
[First-time setup](#first-time-setup) and run it. If `AWAKEN_API_KEY` is
already set, verify it with a small live query instead, and offer to
replace it if verification fails.

**Keeping the skill current**: `metadata.version` in the frontmatter above
is the version of this skill (SKILL.md and cookbook.md ship together). The
latest copy is always at `https://api.awaken.tax/skill.md` (its version is
also in the `X-Awaken-Skill-Version` response header) or via
`awaken_get_skill`. If the latest version is newer than the installed one,
tell the user and, with their approval, replace both files.

## Working through MCP

Authentication rides on the MCP connection — never ask for an API key on
this path. Start by calling `awaken_get_active_client` to confirm which
client (portfolio) you are operating on; switch with
`awaken_set_active_client` if the user has several.

### Editing safely

- Write tools fail with a Read-level key; only ReadWrite keys can modify
  data. If writes 403, say so rather than retrying.
- Reuse one `sessionId` (e.g. `fix-basis-2025-06`) across supported,
  audit-logged edits so they can be reviewed with `awaken_list_edit_sessions`
  and reverted with `awaken_undo_session`. If omitted on a supported edit,
  calls made with the same API key on the same UTC day share an automatic session.
- Title and transaction-hash changes are not audit-logged and cannot be
  reverted by session undo, even when the call includes `sessionId`. Save
  the original value before editing. Another explicit update can restore a
  non-empty value, but these tools cannot restore an originally null or empty
  field. NFT-price and investment edits are also outside session undo.
- `awaken_undo_session` defaults to a dryRun preview; pass `dryRun: false`
  only after reviewing the preview (with the user, for anything sizable).
- Writes mark the client for cost-basis recalculation automatically, so
  totals can lag until the next recalculate finishes. Batch all edits,
  then trigger one with `awaken_trigger_recalculate` (read_write key;
  rate limited, so call it once per batch) and poll
  `awaken_get_recalculate_status` until `recalculateInProgress` and
  `needsRecalculate` are both false before reading tax summaries. Runs are
  incremental (they replay from the earliest dirty transaction); pass
  `fullRecalculate: true` to recompute every transaction from the start
  (locked tax years are still kept from saved state).
- `awaken_create_account` connects a wallet by public address; pass
  `startImportingAt` / `stopImportingAt` to limit the import window (a
  date-only `stopImportingAt` includes the whole UTC day).
- Before labeling, fetch valid values from `awaken_list_labels` and
  `awaken_get_transaction_type_options`; never invent label ids.
- After bulk edits, sanity-check the result with `awaken_get_tax_summary`
  or `awaken_get_transactions_summary`.
- Transaction summaries report gains/income and a matching count, not purchase
  spending. Zero gains do not imply zero transactions. For any question about
  a specific label or labels, prefer `awaken_list_transactions` with the exact
  label values, requested dates, and `includeSplitDetails: true`. Use the
  matching transactions and amounts relevant to the question, checking all pages,
  currencies, missing values and failed hydration before reporting totals.

### Task → tool map

| Task                                | Tools                                                                                                                                                                                                                                                                                           |
| ----------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| List / filter transactions          | `awaken_list_transactions`                                                                                                                                                                                                                                                                      |
| Period totals, yearly tax summary   | `awaken_get_transactions_summary`, `awaken_get_tax_summary`                                                                                                                                                                                                                                     |
| Valid labels & transaction types    | `awaken_list_labels`, `awaken_get_transaction_type_options`                                                                                                                                                                                                                                     |
| Label transactions                  | `awaken_label_transactions` (`awaken_split_wallet_transactions_and_label_fees` for wallet txns with fee legs)                                                                                                                                                                                   |
| Fix a transfer's numbers            | `awaken_set_transfer_value`, `awaken_update_transfer`                                                                                                                                                                                                                                           |
| Edit transaction fields             | `awaken_update_title`, `awaken_update_notes`, `awaken_update_transaction_hash`, `awaken_update_date`, `awaken_update_income`, `awaken_update_impermanent_loss`, `awaken_update_interest_expense`, `awaken_update_perpetual_pnl`, `awaken_update_staking_account`, `awaken_update_missing_basis` |
| Create / reshape transactions       | `awaken_create_transaction`, `awaken_add_transfer`, `awaken_split_transaction_into_many`, `awaken_merge_transactions`, `awaken_hide_transactions`                                                                                                                                               |
| Review & undo edits                 | `awaken_list_edit_history`, `awaken_list_edit_sessions`, `awaken_undo_session`, `awaken_undo_audit_logs`                                                                                                                                                                                        |
| Portfolio & positions               | `awaken_get_portfolio`, `awaken_get_portfolio_value`, `awaken_get_asset_position`, `awaken_list_tax_lots`                                                                                                                                                                                       |
| NFTs                                | `awaken_list_nfts`, `awaken_set_nft_price`                                                                                                                                                                                                                                                      |
| Performance & insights              | `awaken_get_top_pnl_assets`, `awaken_get_performance_by_chain`, `awaken_get_inflows_outflows`, `awaken_list_insights`, `awaken_get_insights_summary`                                                                                                                                            |
| Accounts & assets                   | `awaken_list_accounts`, `awaken_list_potential_accounts`, `awaken_create_account`, `awaken_search_assets`                                                                                                                                                                                       |
| Ledger accounts (chart of accounts) | `awaken_list_ledger_accounts`, then `awaken_get_ledger_account_summary` (per-account debit/credit/net cents between two dates, optional month/quarter/year buckets, optional `accountIds` / `assetIds` filters, with revenue/expense/asset/liability/equity totals)                             |
| Investments book (SAFEs/SAFTs)      | `awaken_list_investments`, then `awaken_create_investment`, `awaken_update_investment`, `awaken_delete_investment`                                                                                                                                                                              |
| 1099-DA reconciliation              | `awaken_list_1099da_forms`, `awaken_get_1099da_reconciliation`, `awaken_get_1099da_basis_matches`, `awaken_get_1099da_8949_preview`, then `awaken_start_1099da_form` / `awaken_generate_1099da_reports` / `awaken_list_1099da_generations`                                                      |
| Reports & exports                   | `awaken_get_report_export`, `awaken_generate_tax_forms_bundle`, `awaken_list_taxable_events`                                                                                                                                                                                                    |
| What shipped recently in Awaken     | `awaken_list_changelog`                                                                                                                                                                                                                                                                         |

Tool schemas come from the server — trust them over this table if they
differ.

### Splitting transactions

Use `awaken_split_transaction_into_many` for every new split, including a
simple one-to-two split. The older `awaken_split_transaction` tool is deprecated
and remains available only for compatibility.

Pass one `splits` entry per child transaction. The base keeps every visible
transfer omitted from those entries, and the array order is the economic
settlement order used for cost-basis processing. Each transfer ID must occur in
exactly one child. A request may contain at most 20 child groups, with at most
200 transfer IDs in each group. The operation is atomic: either every child is
created or none is. Reuse one `sessionId` for the surrounding edit task so the
whole change can be reviewed and undone together. Split results are dirty until
the next recalculation, so do not validate gains or missing basis immediately
from the mutation response.

### Investments book

The `awaken_*_investment` tools edit the client's investment records
(SAFEs, SAFTs, token warrants, equity — the Investments page), not ledger
transactions. Three ways they differ from the transaction tools:

- **No undo.** Investment writes are not audit-logged, so
  `awaken_list_edit_sessions` / `awaken_undo_session` do not cover them,
  and `awaken_delete_investment` is a permanent hard delete that also
  removes the record's attached documents. Confirm targets with
  `awaken_list_investments` first, and prefer `status=cancelled` over
  deletion.
- **Reconcile by `referenceId`.** Company names collide (equity/token twin
  records, multiple tranches of the same deal), so match records to an
  external source by `referenceId` and set it on every record you create.
- **Amounts are integer cents** in the record's `currency` (default USD),
  capped at 2,147,483,647 cents (~$21.4M, the API's Int limit) per record.

### Domain knowledge (read before nontrivial work)

The [cookbook](cookbook.md) is written with GraphQL examples, but its
domain sections apply on either path: staking/lending/LP positions and the
staking identifier (transfers in and out of positions are never
disposals), diagnosing missing cost basis, and the guarded 1099-DA
reconciliation workflow. For 1099-DA specifically: diagnose with read
tools first, and do not edit transactions, accept zero basis, or generate
final forms until the user has reviewed the proposed changes and
explicitly approved the write.

## Working through GraphQL directly

Awaken exposes a single production GraphQL endpoint:

```
POST https://api.awaken.tax/graphql
```

This path covers the supported public API surface through the worked
examples in [cookbook.md](cookbook.md). There are no GraphQL subscriptions
(the `Subscription` type in the schema is the billing entity, not a
subscription root). Introspection is disabled in production, so you cannot
discover operations from the endpoint itself.

### Finding an operation

Start with [cookbook.md](cookbook.md) — it covers the full range of tasks
(transactions, editing, missing basis, recalculation, portfolio, reports,
accounts, API keys) with verified examples, and most questions are a
variation of one of them. It is organized by task; grep for a keyword or
operation name first.

For anything beyond the cookbook (only possible inside the Awaken repo):
the full schema is nexus-generated into `schema.graphql` at the repo root —
grep it for an operation name or keyword, then read the surrounding lines
for the signature and types. For resolver behavior beyond the signature,
open the resolver source under `server/src/modules/<module>/graphql/`
(e.g. `getClientTransactions` lives in
`server/src/modules/ledger/graphql/queries/`). Note that `schema.graphql`
includes internal staff-only operations; anything gated by an admin check
in its resolver will 403 for client API keys.

### Authentication

Requests authenticate one of two ways:

- **Firebase bearer token** (the web app): `Authorization: Bearer <firebase-jwt>`.
- **Client API key** (integrations): keys start with `awaken_` and are sent
  as `x-api-key: <key>` or `Authorization: ApiKey <key>`. Keys are created
  in the web app under Settings → API Keys, are scoped to one client, and
  carry a permission level of `Read` or `ReadWrite`. Read-level keys can
  only run queries.

Most operations take a `clientId` argument and enforce that the caller has a
membership on that client (`ClientPermissionService`); a user can belong to
several clients (`getMyClients`, `getMyActiveClient`).

#### Calling the API with an API key

Never hardcode or echo a raw key. Before any live API call, check for the
key with `test -n "$AWAKEN_API_KEY"` (do not print it), and pass it as
`-H "x-api-key: $AWAKEN_API_KEY"` so the raw value never appears in the
command line or transcript.

#### First-time setup

If `AWAKEN_API_KEY` is not set, walk the user through this once:

1. Tell them to create a key at **awaken.tax → Settings → API Keys**
   (choose `Read` unless they need to modify data; the raw key is shown
   once, at creation). Keys expire — 90 days by default, up to a year if
   they set a date — so a long-lived integration needs a rotation plan.
2. Have them paste the key, then persist it for future sessions —
   offer both options and let them pick:
    - **Shell profile** (works for all terminal tools):
      append `export AWAKEN_API_KEY="awaken_..."` to their profile
      (`~/.zshrc`, or `set -Ux AWAKEN_API_KEY awaken_...` for fish).
    - **Claude Code only**: add it to the `env` block of
      `~/.claude/settings.json`:
      `{"env": {"AWAKEN_API_KEY": "awaken_..."}}`.
3. Discover the client ID — the user should never have to find this
   manually. Every key is scoped to exactly one client (any other
   `clientId` returns a 403). Query `getMyClients { id name }` with the
   key; if it returns one client, that's the one. If it returns several
   (the key's creator belongs to multiple clients), probe each id with a
   cheap query (`getClientTransactions(clientId: ..., limit: 1)`) — the
   key's client is the only one that won't 403. Persist it next to the
   key as `AWAKEN_CLIENT_ID`, using the same mechanism chosen in step 2.
4. Confirm setup by running a small query (e.g. `getClientTransactions`
   with `clientId: $AWAKEN_CLIENT_ID, limit: 1`) and reporting whether
   it authenticated.

In later sessions, use `$AWAKEN_CLIENT_ID` for every `clientId` argument
without asking; if it is unset but `AWAKEN_API_KEY` exists, re-run the
discovery in step 3 and offer to persist the result.

If a call fails with `extensions.code: "UNAUTHENTICATED"` (HTTP 401),
the key is missing, invalid, expired, or revoked — don't retry; direct
the user to Settings → API Keys for a new key. A `"403"` (or
`"FORBIDDEN"`) code means the key is valid but not allowed here: either
the `clientId` isn't the key's client (expected while probing in step 3 —
just try the next id) or a `Read` key attempted a mutation (switch to a
`ReadWrite` key). If **every** client from `getMyClients` 403s, the key
is likely scoped to a client outside the creator's visible memberships —
confirm the intended client id with the user before concluding the key is
bad; re-create it from the right workspace only if none can be reached.

### Common use cases

[cookbook.md](cookbook.md) has verified, ready-to-run examples for the
frequent tasks: listing/filtering transactions, editing and labeling them,
finding and fixing missing cost basis, staking/lending/LP positions and
staking identifiers, recalculating, portfolio balances and tax lots, NFT
value overrides, reconciling 1099-DA forms, identifying the transactions
behind proceeds/basis discrepancies, exporting tax reports, tax-loss
harvesting, adding wallet/exchange accounts, and managing API keys.
Start there before composing a query from scratch.

For 1099-DA work, follow the cookbook's guarded
**Reconcile a 1099-DA** workflow. Diagnose with read queries first. Do not
edit transactions, accept zero basis, change report rows, or generate final
forms until the user has reviewed the proposed changes and explicitly
approved the write.

### Conventions

- **One root field per request** — the server rejects operations with more
  than one root selection. Send separate requests instead of batching.
- **Pagination** is offset-style via `page` and `limit` args (`limit` ≤ 500
  on transaction queries); list responses that paginate usually return a
  wrapper type with a `total` count.
- **Dates** use the custom `Date` scalar; arbitrary payloads use the `JSON`
  scalar.
- **Money** fields suffixed `Cents` are integer cents (often paired with
  a display-ready `...Formatted` string). Mutation fiat inputs differ:
  `updateTransfer` and `createTransfer` take `fiatValue`/`basisFiatValue` in
  **integer cents** (`183769` for $1,837.69), while
  `saveReceivePriceForTransactions` takes `fiatValue` as a **dollar float**
  (`1837.69`). MCP tools take dollar floats everywhere. Mixing them up is a
  silent 100× error. Asset quantities are floats. For gains,
  prefer `capGainsSumSigned` (signed gain/loss in **integer cents**, returned
  as a string, e.g. `-183769` for -$1,837.69 — divide by 100 for dollars) over
  `capGainsSum`, which is the **unsigned absolute value** and drops the
  gain-vs-loss sign.
- **Errors** come back as standard GraphQL errors; check `extensions.code`:
  `"UNAUTHENTICATED"` (with HTTP 401) for a missing/invalid/expired/revoked
  key; `"403"` or `"FORBIDDEN"` (treat as equivalent) for permission
  failures (key scoped to another client, or a Read key running a
  mutation); `"ROOT_SELECTION_LIMIT_EXCEEDED"` for more than one root
  field; `"BAD_USER_INPUT"` for malformed arguments. Errors thrown without
  an explicit code surface as `"INTERNAL_SERVER_ERROR"`.
- **DeFi positions are virtual accounts** keyed by a _staking identifier_
  (`stakingAccountIdentifier`), each holding one pooled basis queue per asset.
  Transfers to/from them are internal moves — never disposals — and only the
  staking/LP labels honor the identifier. Anything a withdrawal can't cover
  from the queue becomes reward income at market value. See the cookbook's
  staking-positions section before hand-building position transactions.
- Many mutations that touch ledger data mark the client dirty and take
  effect fully after the next recalculate — trigger one with the
  `rerunGraph` mutation and poll `getActiveRecalculateJob` until it
  returns `null` (over MCP: `awaken_trigger_recalculate` and
  `awaken_get_recalculate_status`).
