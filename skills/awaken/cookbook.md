# Awaken API cookbook

> **Reading this over MCP (you have `awaken_*` tools)?** Use this document
> for the concepts and workflows — staking positions, missing cost basis,
> the guarded 1099-DA discipline — but execute with your MCP tools, not the
> GraphQL queries shown here: supported, audit-logged MCP writes can be grouped
> into undoable sessions. Title, transaction-hash, NFT-price, and investment
> edits are outside session undo. The task → tool map in [SKILL.md](SKILL.md)
> covers the translation. The queries below are for the direct-API path only.

Worked examples for everything a client API key can do. All examples assume
the setup described in [SKILL.md](SKILL.md): the key in `$AWAKEN_API_KEY` and
the client id in `$AWAKEN_CLIENT_ID` (both configured by `/awaken setup`).
The endpoint is always `https://api.awaken.tax/graphql`.

A reusable helper (POST a query with variables):

```bash
gql() {
  curl -s https://api.awaken.tax/graphql \
    -H 'content-type: application/json' \
    -H "x-api-key: $AWAKEN_API_KEY" \
    -d "$(jq -n --arg q "$1" --argjson v "${2:-{}}" '{query: $q, variables: $v}')"
}
```

Every example below is a query/variables pair you can pass to `gql`.

## Contents

- [Client info & settings](#client-info--settings)
- [What's new in Awaken](#whats-new-in-awaken)
- [Transactions](#transactions)
- [Reviewing & editing](#reviewing--editing-readwrite-key)
- [Missing cost basis](#missing-cost-basis)
- [Recalculating](#recalculating)
- [Portfolio](#portfolio)
- [Reports & tax forms](#reports--tax-forms)
    - [Reconcile a 1099-DA](#reconcile-a-1099-da)
- [Wallets & exchange accounts](#wallets--exchange-accounts)
- [End-to-end workflow](#putting-it-together-new-wallet--final-report)
- [Troubleshooting](#troubleshooting)

**Hard limits to know up front:**

- **One root field per request.** The server rejects operations with more
  than one root selection (`"Operation exceeds maximum allowed root
selections (1)"`). Never batch root fields or use aliases to combine
  queries — send separate requests.
- `limit` on transaction queries is capped at **500** — exceeding it fails
  with `"Limit must be less than or equal to 500"` (surfaced under
  `extensions.code: "INTERNAL_SERVER_ERROR"`, not a validation code).
- **300 requests/minute per IP** across the whole API. HTTP 429 means back
  off; the `RateLimit-Remaining`/`RateLimit-Reset` response headers show
  the budget. Poll jobs every 5–10 seconds, never in a tight loop.
- **Money units differ by field.** Anything suffixed `Cents` is integer
  cents. `updateTransfer` and `createTransfer` also take
  `fiatValue`/`basisFiatValue` in integer cents (`183769` for $1,837.69);
  `saveReceivePriceForTransactions` takes `fiatValue` as a dollar float
  (`1837.69`). Mixing them up is a silent 100× error.
- Mutations need a **ReadWrite** key; `Read` keys can only run queries.
- Ledger mutations mark the client dirty — totals are final only after a
  recalculate (see [Recalculating](#recalculating)).

---

## Client info & settings

Who am I / which clients can I see (works with any valid key; the key can
only _query_ its own client):

```graphql
query {
    getMyClients {
        id
        name
    }
}
```

Client profile — country, currency, and cost-basis settings drive how gains
are computed:

```graphql
query ($clientId: String!) {
    getClientById(clientId: $clientId) {
        id
        name
        country
        currency
        timezone
        costBasisAlgorithm
    }
}
```

Change the cost-basis algorithm (values: `FIFO`, `HIFO`, `LIFO`,
`UniversalFIFO`, `UniversalHIFO`, `UniversalLIFO`, `ACB`,
`AverageCostBasis`, `AverageCostBasisPerWallet`, `SharePooling`, …):

```graphql
mutation ($clientId: ID!) {
    updateClientCostBasisAlgorithm(
        clientId: $clientId
        costBasisAlgorithm: HIFO
    ) {
        id
        costBasisAlgorithm
    }
}
```

General settings (name, country, currency, timezone, fiscal year, …) go
through `updateClient(clientId: ..., name: ..., country: ..., currency: ...)`.

---

## What's new in Awaken

The product changelog is the same list Awaken shows users in its What's New
modal: what shipped, when, and any action the reader should take. It is not
client-scoped, so it needs no active client and works with a Read key.

Over MCP: `awaken_list_changelog` (`limit`, default 10, max 50; `offset` to
page further back). Over GraphQL:

```graphql
query ($limit: Int, $offset: Int) {
    getChangelogUpdates(limit: $limit, offset: $offset) {
        date
        version
        category
        title
        summary
        action
    }
}
```

`category` is `Feature`, `Improvement`, or `BugFix`, and entries come back
newest first. `getChangelogUpdatesCount` gives the total for paging, in its own
request (one root field per operation). Reach for
this when a user asks what changed recently, or when behaviour you remember
from an earlier session may have shipped differently since.

---

## Transactions

### List & filter

`getClientTransactions` is the workhorse — pagination is `page` (0-based) +
`limit` (max 500), with `total` in the response, and ~50 optional filters.
On large clients the count behind `total` is the slow half of the request;
pass `skipTotal: true` when you do not need it (`total` comes back null) or
read `total` from `getClientTransactionsSummary`, which computes it anyway.
`getClientTransactionsSummary` also accepts `allowCache: true`, which serves
the unfiltered summary from a server cache without running the aggregate;
a miss or any filtered request returns every field null, so treat it as a
fast first read and follow up without the flag for the real numbers.
The useful ones, grouped:

- **Date**: `startDate`, `endDate`
- **Asset**: `assetIds`, `assetSymbolOrName`, `assetType`
- **Account / address**: `accountIds`, `providers` (chain/exchange slugs),
  `fromAddress`, `toAddress`, `fromOrToAddress`, `involvedAddresses`
- **Status flags**: `reviewed`, `isMissingBasis`, `hasIncome`,
  `onlyDisposals`, `onlyWashSales`, `isNegativeBalance`, `hasNotes`,
  `includeHidden`, `includeSpam`
- **Labels / text**: `labels`, `labelFilterMode`, `search` (free text)
- **Shape**: `sortBy`, `ascending`, `includeSummary` (adds
  `costBasisPercent` to the response), `includeBalances`

```graphql
query ($clientId: ID!) {
    getClientTransactions(
        clientId: $clientId
        startDate: "2025-01-01"
        endDate: "2025-12-31"
        reviewed: false
        limit: 25
        page: 0
        sortBy: "date"
        ascending: false
    ) {
        total
        transactions {
            id
            title
            createdAt
            provider
            capGainsSumSigned
            incomeSum
        }
    }
}
```

Fetch every page — stop when `page * limit` reaches `total`. Treat a
non-JSON or error page as a failure (not the end of the data), and keep
the `sleep`: it holds large ledgers under the 300 req/min rate limit.
If you only need a count, read `total` from page 0; for period totals
use `getClientTransactionsSummary` (below) instead of paginating.

```bash
q='query ($clientId: ID!, $page: Int!, $limit: Int!) {
  getClientTransactions(clientId: $clientId, limit: $limit, page: $page) {
    total
    transactions { id title }
  }
}'
limit=500 page=0 total=1
while [ $((page * limit)) -lt "$total" ]; do
  resp=$(gql "$q" "{\"clientId\":\"$AWAKEN_CLIENT_ID\",\"page\":$page,\"limit\":$limit}")
  if ! total=$(jq -e '.data.getClientTransactions.total' <<<"$resp" 2>/dev/null); then
    echo "page $page failed (rate limit or error): $resp" >&2
    exit 1
  fi
  jq -r '.data.getClientTransactions.transactions[] | [.id, .title] | @tsv' <<<"$resp"
  page=$((page + 1))
  sleep 0.25   # ~240 req/min, under the 300/min cap
done
```

To find `assetIds` for the asset filters (or `assetId` inputs on
mutations), enumerate the client's assets (`limit` is silently capped
at 100 here — page through):

```graphql
query ($clientId: ID!) {
    getClientAssetsOptions(
        clientId: $clientId
        hideSpamAssets: true
        limit: 100
        page: 0
    ) {
        assets {
            id
            symbol
            name
        }
    }
}
```

Commonly used `Transaction` fields: `id`, `title`, `createdAt`, `provider`,
`txnHash`, `capGainsSumSigned` (signed gain/loss in **integer cents** as a
string — divide by 100 for dollars; the plain `capGainsSum` is the **unsigned
absolute value**, so prefer the signed field), `incomeSum` (**integer cents**), `isMissingBasis`,
`reviewStatus`, `labelUsed`, `notes`, `sourceAccountId`, `fees`,
`transfers` (see next section).

To link a transaction in the Awaken web app, use
`https://awaken.tax/clients/<clientId>/transactions?transactionId=<transactionId>`
(the `transactionId` query param opens the transaction's detail modal on the
Transactions page). There is no `/transactions/<transactionId>` path route.

### One transaction in depth

```graphql
query ($clientId: ID!, $transactionId: ID!) {
    getTransaction(clientId: $clientId, transactionId: $transactionId) {
        id
        title
        createdAt
        provider
        txnHash
        labelUsed
        notes
        capGainsSumSigned
        incomeSum
        isMissingBasis
        transfers {
            id
            value # token quantity (there is no `amount` field)
            fiatAmountCents
            basis
            isMissingBasis
            transferCategory # sent | received | internal | …
            fromAccountId
            toAccountId
            fromAddress
            toAddress
            fullAsset {
                symbol
                name
            }
        }
    }
}
```

For the raw on-chain payload behind a transaction:
`getRawTransactionJSON(clientId: ..., transactionId: ...)`.
Batch fetch by ids: `getTransactions(clientId: ..., transactionIds: [...])`.

### Totals for a period

```graphql
query ($clientId: ID!) {
    getClientTransactionsSummary(
        clientId: $clientId
        startDate: "2025-01-01"
        endDate: "2025-12-31"
    ) {
        totalCapGainsFormatted # "$160,372.75"
        totalIncomeFormatted
        totalCapGainCents # note: CapGain, not CapGains
        totalIncomeCents
        costBasisPercent # 0-1; fraction of basis coverage
    }
}
```

It accepts the same filters as `getClientTransactions`, so you can total
any slice (one wallet, one asset, only disposals, …).

### Yearly tax summary

`getTaxYears(clientId: ...)` returns the years with activity. Then:

```graphql
query ($clientId: ID!) {
    getIncomeAndCapGains(clientId: $clientId, year: "2025") {
        capGainsShortTerm
        capGainsLongTerm
        capGainsTotal
        incomeTotal
    }
}
```

Values are formatted strings (`"-$4,863.81"`).

---

## Reviewing & editing (ReadWrite key)

### Update a transaction

When working through MCP, there is deliberately no broad
`awaken_update_transaction` tool. Use the field-scoped tool so unrelated
values cannot leak into the mutation. Each tool takes `transactionId`, its
single named field, and optional `clientId` / `sessionId`:

```jsonc
// Set computed income to exactly $0.00. The value is cents.
{
    "tool": "awaken_update_income",
    "arguments": {
        "transactionId": "txn_123",
        "overrideIncomeCents": 0,
        "sessionId": "income-review-2025"
    }
}

// Move the transaction to a corrected UTC calendar date.
{
    "tool": "awaken_update_date",
    "arguments": {
        "transactionId": "txn_123",
        "createdAt": "2025-09-10",
        "sessionId": "income-review-2025"
    }
}

// Perpetual PnL is in display-currency units, not cents, and is valid only
// for supported Hyperliquid perpetual transactions.
{
    "tool": "awaken_update_perpetual_pnl",
    "arguments": {
        "transactionId": "txn_hl_123",
        "dataHyperliquidPnL": -576.73,
        "sessionId": "perp-review-2025"
    }
}
```

The other scoped tools are `awaken_update_title`, `awaken_update_notes`,
`awaken_update_transaction_hash`, `awaken_update_impermanent_loss`,
`awaken_update_interest_expense`, `awaken_update_staking_account`, and
`awaken_update_missing_basis`. Use `awaken_label_transactions` for labels and
`awaken_hide_transactions` for visibility.

For direct GraphQL clients, the underlying mutation remains
`updateTransaction`. It treats `title`, `notes`, and `label` as a
replace-style group: fetch the transaction first and carry their current
values forward, along with the required `overrideLabel`. Beyond those
preservation values, submit only the intended editable field. Never copy an
unrelated PnL or income field from another transaction:

Editable fields on `UpdateTransactionInput`: `title`, `notes`, `label`,
`overrideLabel` (required Boolean), `isHidden`, `createdAt`, `txnHash`,
`overrideIncomeCents`, `overrideIsMissingBasis`, `interestExpenseCents`,
`impermanentLossCents`, `dataHyperliquidPnL`, `globalRuleName`,
`stakingAccountIdentifier`.

```graphql
mutation (
    $clientId: ID!
    $transactionId: ID!
    $currentTitle: String!
    $currentLabel: String
) {
    updateTransaction(
        clientId: $clientId
        transactionId: $transactionId
        createDefaultRule: false
        updates: {
            title: $currentTitle
            notes: "reviewed via API"
            label: $currentLabel
            overrideLabel: false
        }
    ) {
        transaction {
            id
        }
    }
}
```

Setting income to zero through GraphQL:

```graphql
mutation (
    $clientId: ID!
    $transactionId: ID!
    $currentTitle: String!
    $currentNotes: String
    $currentLabel: String
) {
    updateTransaction(
        clientId: $clientId
        transactionId: $transactionId
        createDefaultRule: false
        updates: {
            title: $currentTitle
            notes: $currentNotes
            label: $currentLabel
            overrideIncomeCents: 0
            overrideLabel: false
        }
    ) {
        transaction {
            id
            overrideIncomeCents
        }
    }
}
```

Do not include `dataHyperliquidPnL` in that income edit. It is a separate,
unsuffixed display-currency value and the server rejects it on anything other
than a supported Hyperliquid perpetual transaction.

Setting `createDefaultRule: true` turns the edit into a rule that
auto-applies to similar future transactions. `stakingAccountIdentifier` has
its own rules — see
[Staking, lending & LP positions](#staking-lending--lp-positions-virtual-accounts).

### Labels

Label values are namespaced strings like `v1:swap`, `v1:coin_buy`,
`v1:coin_sell`, `v1:nft_buy`, `v1:staking_reward`, `v1:airdrop`, … —
enumerate them (with display names and categories) via:

```graphql
query {
    getLabels {
        label
        value
        category
    }
}
```

Bulk-apply a label (or notes) to many transactions:

```graphql
mutation ($clientId: ID!, $transactionIds: [ID!]!) {
    labelTransactions(
        clientId: $clientId
        transactionIds: $transactionIds
        label: "v1:swap"
    ) {
        id
        labelUsed
    }
}
```

Per-transaction valid options: `getLabelOptionsForTransactions` /
`getTransactionTypeOptions`.

### Fix a transfer's numbers

`updateTransfer` edits one leg of a transaction — token amount, fiat value,
basis, or the accounts it moves between:

```graphql
mutation ($clientId: ID!, $transactionId: ID!, $transferId: ID!) {
    updateTransfer(
        clientId: $clientId
        transactionId: $transactionId
        transferId: $transferId
        fiatValue: 183769
        basisFiatValue: 196499
    ) {
        id
    }
}
```

Which field to edit:

- **Received asset** → `basisFiatValue` (MCP: `awaken_set_transfer_value`
  with `field: "basis"`). Example: an income receive showing
  "Cost basis £0.00" — set its basis with `basisFiatValue`.
- **Sent asset** → `fiatValue` (`field: "snapshot"`) for the proceeds/sale
  price; `basisFiatValue` (`field: "basis"`) for the cost basis consumed.

### Hide / unhide

`hideTransaction(clientId, transactionId, isHidden: true)` for one;
`hideMultipleTransactions` / `unhideMultipleTransactions` with
`transactionIds` for many. Hidden transactions are excluded from gains.

### Link wallet-to-wallet movements

- Same chain: `markInternalTransfer(clientId, fromTransactionId, toTransactionId)`
  (undo: `unmarkInternalTransfer`) — marks a send+receive pair as internal so
  the receive isn't treated as income and basis carries over.
- Cross-chain: `bridgeTransactions(clientId, fromTransactionId, toTransactionId)`;
  cross-chain swaps: `crossChainSwap`.

### Manual transactions

```graphql
mutation ($clientId: ID!, $accountId: ID!) {
    createTransaction(
        clientId: $clientId
        accountId: $accountId
        createdAt: "2025-06-01"
    ) {
        id
    }
}
```

Then add legs with `createTransfer(clientId, transactionId, assetId,
amount, fromAccountId/toAccountId, fiatValue)`. Duplicate an existing one
with `duplicateTransaction`; merge related ones with `mergeTransactions`.

### Split one transaction into many

Use `splitTransactionIntoMany` for all new split operations, including an
ordinary one-to-two split. `splitTransaction` is deprecated and remains only
for compatibility. The base transaction keeps transfers omitted from `splits`;
each input entry creates one child, and input order is the economic settlement
order:

```graphql
mutation ($clientId: ID!, $transactionId: ID!) {
    splitTransactionIntoMany(
        clientId: $clientId
        baseTransactionId: $transactionId
        splits: [
            { transferIds: ["transfer-acquisition"] }
            { transferIds: ["transfer-swap"] }
            { transferIds: ["transfer-bridge"] }
        ]
    ) {
        id
        createdAt
        isSplitTxn
    }
}
```

Every group must contain at least one visible transfer, and a transfer may
appear in only one group. All children are created atomically. The edit marks
the affected transactions dirty; wait for recalculation before checking gains,
income, or missing basis.

### Audit trail & undo

Every edit is logged: `getClientAuditLogs(clientId, limit, page)` (filter by
`transactionIds` or `userId`). Undo specific edits with
`undoAuditLogs(clientId, auditLogIds)`, or **everything** with
`undoAllEdits(clientId)` (destructive — confirm with the user first).

---

## Missing cost basis

Find transactions with missing basis (Awaken assumed $0 cost for some
acquired asset — usually an incomplete import or unlinked transfer):

```graphql
query ($clientId: ID!) {
    getClientTransactions(
        clientId: $clientId
        isMissingBasis: true
        limit: 100
        page: 0
    ) {
        total
        transactions {
            id
            title
            createdAt
            provider
            sourceAccountId
        }
    }
}
```

Coverage headline: pass `includeSummary: true` and read `costBasisPercent`.
Per-transfer detail: `transfers { isMissingBasis basis }` on any transaction.

Fixes, in order of preference:

1. **Import the missing wallet/exchange** the asset came from (see
   [Wallets & exchange accounts](#wallets--exchange-accounts)) — the real
   acquisition then supplies the basis.
2. **Link the transfer**: if both sides exist, `markInternalTransfer` or
   `bridgeTransactions` (above).
3. **Set the receive price** when the source can't be imported:

```graphql
mutation ($clientId: ID!, $transactionIds: [ID!]!) {
    saveReceivePriceForTransactions(
        clientId: $clientId
        transactionIds: $transactionIds
        fiatValue: 1250.00
    ) {
        id
    }
}
```

4. **Accept zero basis** (stop the warning, keep $0 cost):
   `updateMultiTransactionsCostBasis(clientId, transactionIds,
isMissingBasis: false, overrideIsMissingBasis: true)`.

---

## Staking, lending & LP positions (virtual accounts)

A DeFi position — native staking, a lending market, an LP or farm — is a
**virtual account** (`importType: VirtualAccount`) that automation creates and
owns. Deposits are internal transfers wallet → position, withdrawals are
position → wallet. Each position holds **one pooled basis queue per asset**:
deposits enqueue lots, withdrawals dequeue them under the client's algorithm
(FIFO/LIFO/HIFO). Anything a withdrawal cannot cover from the queue is booked
as **reward income at market value with a fresh purchase date** — the cause of
almost every "unstaking created phantom income / reset my holding period"
report.

### The staking identifier

A position's identity is its **staking identifier**: the string stored as the
virtual account's `walletAddress`. Two transactions share a position exactly
when they resolve to the same identifier. Automation derives it from the
protocol (program/contract id), falling back to `<stake program>:<wallet>` for
native SOL staking or to the counterparty address. When a deposit and a
withdrawal derive _different_ identifiers you get two positions, the
withdrawal's queue is empty, and the whole withdrawal turns into income.

List positions and their identifiers:

```graphql
query ($clientId: String!) {
    getClientAccounts(clientId: $clientId, includeVirtual: true) {
        id
        description
        importType
        walletAddress
    }
}
```

For an auto-detected position, list its legs by the virtual account id from that
query (deposits, withdrawals and rewards all carry a ledger entry on it):

```graphql
query ($clientId: ID!, $virtualAccountId: ID!) {
    getClientTransactions(
        clientId: $clientId
        accountIds: [$virtualAccountId]
        limit: 500
    ) {
        total
        transactions {
            id
            createdAt
            title
            labelUsed
            stakingAccountIdentifier
        }
    }
}
```

The `stakeAccountIdentifier` filter matches the transaction column instead, so it
returns only transactions whose identifier was set by hand (below) — useful for
auditing your own overrides, not for enumerating a detected position. It matches
with or without the `user_override:` prefix, so pass the identifier raw:

```graphql
query ($clientId: ID!, $identifier: String!) {
    getClientTransactions(
        clientId: $clientId
        stakeAccountIdentifier: $identifier
        limit: 500
    ) {
        total
        transactions {
            id
            createdAt
            title
            labelUsed
            stakingAccountIdentifier
        }
    }
}
```

`transaction.stakingAccountIdentifier` is non-null only when someone has
overridden it; otherwise read the identifier off the virtual account on the
transaction's ledger entries.

### Pinning a transaction to a position

`updateTransaction`'s `stakingAccountIdentifier` overrides detection. It is the
repair tool for a split position and the way to steer manual transactions into
one:

```graphql
mutation ($clientId: ID!, $transactionId: ID!) {
    updateTransaction(
        clientId: $clientId
        transactionId: $transactionId
        createDefaultRule: false
        updates: {
            stakingAccountIdentifier: "eth-nft-vault"
            overrideLabel: false
        }
    ) {
        transaction {
            id
            stakingAccountIdentifier
        }
    }
}
```

Rules for using it:

- **The value is namespaced to `user_override:<value>` when applied**, so an
  override never joins an auto-detected position — it defines a new one. Set
  the _same_ string on **every** leg that must share the queue (all deposits
  and all withdrawals). Overriding only the withdrawal strands the deposited
  basis in the old position and books the withdrawal as income.
- **Only position-aware labels read it**: `v1:staking`, `v1:unstaking`,
  `v1:liquidity_deposit`, `v1:liquidity_withdraw` (on Solana the override wins
  over protocol detection for the whole staking family). Every other label
  ignores it, so set the label first — see [Labels](#labels) — then the
  identifier.
- It only takes effect on the next recalculate (`rerunGraph`).

### Transfers in and out of a position are never disposals

A transfer whose counterparty is a virtual account is an internal move
(`sent_to_virtual` / `received_from_virtual`): non-taxable, no gain/loss, and it
does not touch the source's tax lots no matter what `fiatValue` you give it.
Adding a zero-value leg out of a position to record "the protocol kept my
coins" therefore changes nothing. Build manual transactions on the real wallet
too, not on the virtual account: automation owns positions and rebuilds their
entries on every recalculate, so hand-made transactions sourced on one are
unreliable — create them on the wallet and steer them with the identifier.

To make position principal genuinely leave the ledger at zero proceeds (e.g.
collateral consumed at settlement, which must not become the acquired asset's
basis and must not book income), use two legs so basis flows out of the queue
first:

1. **Withdraw it from the position into the wallet.** Label the transaction
   `v1:unstaking` (or `v1:liquidity_withdraw` for an LP) and set
   `stakingAccountIdentifier` to the position's identifier. The lots leave the
   queue and land in the wallet with their original cost and purchase dates.
2. **Dispose of it from the wallet.** Label that transaction `v1:coin_sell` and
   set proceeds to zero on the outgoing leg with
   `updateTransfer(clientId, transactionId, transferId, fiatValue: 0)`: a
   $0-proceeds sale, so the consumed basis becomes a capital loss, nothing is
   recorded as income, and any other asset in the transaction keeps its own
   basis. If the coins should instead disappear with **no** recognized gain or
   loss, label the transaction `v1:burn` — basis is removed against equity.

Then `rerunGraph` and verify: the position's remaining balance in the portfolio
(see [Portfolio](#portfolio)) and `capGainsSumSigned` on the disposal.

### Diagnosing a position that booked phantom income

1. Pull the position list above and look for **two accounts for one protocol**,
   one deposit-heavy and one withdrawal-only — that is a split identifier; fix
   it with the override on both sides.
2. If deposits and withdrawals do share one account, the queue was
   short-funded: the wallet had missing basis when it deposited. Find it with
   `isMissingBasis: true` (see [Missing cost basis](#missing-cost-basis)) and
   import the funding history rather than patching the withdrawal.
3. `overrideIncomeCents` on the withdrawal only silences the income line; it
   does not undo the market-value basis step-up or the purchase-date reset on
   the misclassified coins. Fix the cause, then recalculate.

---

## Recalculating

Ledger edits and imports mark transactions dirty; gains/basis numbers are
final only after a recalculate.

```graphql
query ($clientId: ID!) {
    countDirty(clientId: $clientId)
}
```

Trigger a recalculate (the mutation is named `rerunGraph` — there is no
`recalculate` mutation; over MCP use `awaken_trigger_recalculate` and poll
`awaken_get_recalculate_status`):

```graphql
mutation ($clientId: ID!) {
    rerunGraph(clientId: $clientId)
}
```

Then poll until it returns `null`:

```graphql
query ($clientId: ID!) {
    getActiveRecalculateJob(clientId: $clientId) {
        status
        step
        numberOfTransactionsLeft
        finishEta
    }
}
```

Account syncs trigger a recalculate automatically unless called with
`skipRecalculate: true`.

---

## Portfolio

Portfolio totals and coin/DeFi positions:

```graphql
query ($clientId: ID!) {
    getPortfolioV2(
        clientId: $clientId
        includeCoins: true
        includeDefi: true
        includeNFTs: true
    ) {
        balanceTotalValueCents
        coinTotalValueCents
        defiTotalValueCents
        nftTotalValueCents
        balances {
            # coins; sorted by value
            symbol
            name
            provider
            assetPricingKey # input for getTaxLots (below)
            totalAmount # token quantity
            totalFiatAmountCents # current value
            costBasisCents
            gainLossCents
        }
        defiPositions {
            name
            provider
            totalValueCents
        }
    }
}
```

`getPortfolioV2(includeNFTs: true)` is deprecated: it returns only the first
100 cached NFTs and an empty `collections` array. NFT totals still cover all
holdings in the selected accounts. A cold NFT cache yields an empty NFT section
with `isRefreshing: true`; the NFT read does not wait for the worker to build it.

Use `getPortfolioNFTs` for NFT pages, and `collectionsOnly: true` for collection
pages. Keep the first page's `generationId` when requesting subsequent pages;
see the NFT query example below.

Headline number only: `getPortfolioValue(clientId, useCacheIfAvailable:
true) { valueCents timestamp }` (may return 0 until the cache warms —
prefer `getPortfolioV2` for accuracy).

Historical value chart: `getChart(clientId, interval: Month)` — intervals:
`Day`, `Week`, `Month`, `ThreeMonth`, `Year`, `YearToDate`, `All`.

Open tax lots for an asset (what you'd sell and its basis):

```graphql
query ($clientId: ID!) {
    getTaxLots(
        clientId: $clientId
        assetPricingKey: "<from portfolio balances.assetPricingKey>"
    ) {
        lots {
            amount
            fiatAmountCents
            purchasedAt
            accountId
            algorithm
        }
    }
}
```

### NFTs: reading values & price overrides

Use `getPortfolioNFTs` for bounded reads. Each NFT row exposes Awaken's
price inputs and any user override. Pass the returned `generationId` on
subsequent pages so a refresh cannot change the inventory midway through paging.

```graphql
query ($clientId: ID!, $page: Int, $generationId: ID) {
    getPortfolioNFTs(
        clientId: $clientId
        limit: 100
        page: $page
        generationId: $generationId
    ) {
        generationId
        totalCount
        nftTotalValueCents
        isRefreshing
        errors {
            type
            message
        }
        nfts {
            assetId
            assetKey
            name
            tokenId
            contractAddress
            provider
            fiatPriceCents
            overrideCurrentValueCents
            isUserSet
            useAwakenPrice
            floorPriceCents
            costBasisCents
        }
    }
}
```

Start with page 1 and no generation ID, then increment the page until all
`totalCount` matching rows have been read. If the initial response has no
generation and `isRefreshing` is true, poll while the background build runs.
On `NFT_SNAPSHOT_EXPIRED`, restart from page 1 without a generation ID.

For collection summaries, use `collectionsOnly: true` and select `collections`.
Summaries intentionally omit nested holdings; read those with `collectionId`
on the NFT query. Account-scoped collection summaries honor
`onlyIncludedAccountIds`, including their counts and values. Existing mobile
and MCP consumers of `getPortfolioV2(includeNFTs: true)` must use this query
to read beyond the first 100 NFTs or retrieve collections.

- `fiatPriceCents` is the value that rolls up into `totalValueCents` /
  `nftTotalValueCents`. Priority: the override if set, else the floor when
  `useAwakenPrice` (or the client's default-to-floor setting) is on, else 0.
- `floorPriceCents` is **not** guaranteed to be a live collection floor —
  when no live floor is available it can fall back to a cost-derived mark
  and can differ per token within one collection. Don't treat it as a
  market quote.
- Money fields here are floats despite the `Cents` suffix; compare with a
  tolerance, not equality.

### Set or clear an NFT value override (ReadWrite key)

`updateAsset` writes a manual value for one asset (NFT or token).
`overrideCurrentValue` is **cents in the client's own fiat currency**
(e.g. `20724` = A$207.24 for an AUD client) despite the missing `Cents`
suffix:

```graphql
mutation ($assetId: ID!) {
    updateAsset(assetId: $assetId, overrideCurrentValue: 20724) {
        id
        overrideCurrentValueCents
        useAwakenPrice
    }
}
```

- Setting an override automatically flips `useAwakenPrice` to `false`;
  clearing it (`overrideCurrentValue: null`) flips it back to `true`.
  Pass `useAwakenPrice` explicitly to control it independently.
- Clearing is a fallback, **not an undo**: there is no server-side history
  of overrides, so record the previous value yourself before overwriting
  if you may need to roll back.
- Value overrides are display/portfolio-only and tax-inert: they change
  no cost basis, gains, or transactions, and the portfolio total updates
  immediately without a recalculate.
- `upsertNftAsset(clientId, assetKey, contractAddress, tokenId, name,
provider, ...)` is the create-or-update variant for NFTs Awaken hasn't
  indexed; it accepts the same `overrideCurrentValue` / `useAwakenPrice` /
  `isHidden` args (only fields you pass are touched) and returns the
  affected assets.
- The stored override is also readable on `Asset` via
  `getClientAssets(clientId) { assets { id overrideCurrentValueCents
useAwakenPrice isHidden } }`.

---

## Reports & tax forms

### Reconcile a 1099-DA

The goal is not simply to make two totals equal. Match the exchange's
1099-DA proceeds to Awaken's proceeds, preserve all legitimate disposals,
and use Awaken's ledger to produce the most accurate available cost basis.
The safe loop is:

1. discover the parsed form and linked exchange accounts;
2. read the reconciliation summary and exact issue transactions;
3. explain each discrepancy, including split-row false mismatches;
4. propose transaction-level corrections;
5. get explicit approval before any write;
6. edit, recalculate, and verify that the discrepancy improved;
7. preview the final rows and get explicit approval before generation.

Be cautious about editing transactions merely to force the totals to
tie — prefer corrections backed by evidence, and record legitimate
divergences as no-edit explanations. A tie-forcing edit is occasionally
the right call, but only after the trade-off is explained and the user
explicitly approves it. Never accept zero basis, alter preview rows, or
generate a final report without the user's explicit approval. Initial 1099-DA upload is easiest in the web app;
this workflow starts after Awaken has parsed the form.

#### 1. Find the form

Fetch the year's statuses, then select the entry whose `formType` is
`Form1099DA` and whose provider is the exchange being reconciled. Do the
filtering client-side; do not assume the first status is the right form.

```graphql
query ($clientId: ID!, $year: Int!) {
    getTaxFormStatuses(clientId: $clientId, year: $year) {
        statuses {
            formType
            provider
            providerDisplayName
            status
            accountIds
            numberOfTransactions
            taxForm {
                id
                status
                processingStep
                provider
                linkedAccountId
                taxYear
                useBrokerDataForBoxG
                generatedReports
            }
        }
    }
}
```

If no parsed `Form1099DA` exists, guide the user to **Tax Forms**, choose
the exchange's 1099-DA, and upload it. If the form is still processing,
wait rather than diagnosing incomplete data.

Before comparing numbers, make sure the linked exchange import is complete
and Awaken is not dirty: check import jobs, `countDirty`, and
`getActiveRecalculateJob`. Follow [Recalculating](#recalculating) before
continuing if needed.

#### 2. Read the normalized baseline

```graphql
query ($clientId: ID!, $taxFormId: ID!) {
    getTaxFormReconciliation(clientId: $clientId, taxFormId: $taxFormId) {
        parsedTotalProceeds
        parsedTotalCostBasis
        awakenTotalProceeds
        awakenTotalBasis
        totalAdjustedProceeds
        totalAdjustedCostBasis
        awakenRowCount
        proceedsDifference
        basisCoveragePercentage
        basisReportedCount
        basisNotReportedCount
        basisNotReportedRows {
            assetName
            assetSymbol
            proceeds
            basis
            profit
            transactionCount
        }
        proceedsByAsset {
            assetName
            assetSymbol
            parsedProceeds
            awakenProceeds
            transactionCount
        }
        issues {
            date
            assetName
            assetSymbol
            parsedProceeds
            awakenProceeds
            difference
            transactionCount
            transactions {
                transactionId
                proceeds
                title
                description
                createdAt
                provider
                boxChecked
            }
        }
    }
}
```

Interpret these fields carefully:

- Use `totalAdjustedProceeds - parsedTotalProceeds` as the actionable
  proceeds discrepancy. A negative result means Awaken is below the
  broker amount; a positive result means Awaken has additional proceeds.
- `proceedsDifference` is the raw opposite-sign comparison
  (`parsedTotalProceeds - awakenTotalProceeds`). Do not use it as the
  primary pass/fail value.
- Stablecoins are deliberately normalized: adjusted totals retain the
  broker's stablecoin proceeds and use them as stablecoin basis. They are
  excluded from normal issue matching, so do not mutate stablecoin
  transactions to eliminate a raw-total difference.
- `issues[].difference` is `awakenProceeds - parsedProceeds` for that
  date and asset. Issues below one cent and adjacent-day differences that
  cancel within tolerance are already suppressed.
- Cost basis is not expected to equal the broker's basis. The broker may
  omit basis; Awaken should derive it from the complete ledger. Investigate
  missing basis and implausible acquisition history, not mere inequality.

Report the baseline before proposing changes: broker proceeds, adjusted
Awaken proceeds, signed difference, basis coverage, missing-basis count,
and issue count.

#### 3. Identify the exact transactions

Start with `issues[].transactions[].transactionId`; these are the source
Awaken transactions contributing to each date-and-asset mismatch. To turn
the response into a review queue:

```bash
jq -r '
  .data.getTaxFormReconciliation.issues[] as $issue
  | $issue.transactions[]
  | [
      $issue.date,
      ($issue.assetSymbol // $issue.assetName),
      ($issue.difference | tostring),
      .transactionId,
      (.title // ""),
      (.proceeds | tostring)
    ]
  | @tsv
'
```

Inspect each id with `getTransaction` and, when importer evidence matters,
`getRawTransactionJSON` from [One transaction in depth](#one-transaction-in-depth).
For the full candidate set behind an asset total:

```graphql
query ($clientId: ID!, $taxFormId: ID!) {
    getTaxFormReconciliationProceedsByAsset(
        clientId: $clientId
        taxFormId: $taxFormId
    ) {
        assetName
        assetSymbol
        parsedProceeds
        awakenProceeds
        transactionCount
        transactions {
            transactionId
            proceeds
            title
            description
            createdAt
            provider
            boxChecked
        }
    }
}
```

Also inspect the broker-to-Awaken row matcher:

```graphql
query ($clientId: ID!, $taxFormId: ID!) {
    getBasisMatches(clientId: $clientId, taxFormId: $taxFormId) {
        matchedCount
        unmatchedParsedCount
        unmatchedAwakenCount
        unreviewedCount
        totalParsedProceeds
        totalAwakenProceeds
        totalParsedBasis
        totalAwakenBasis
        matches {
            parsedIdentifier
            parsedDescription
            parsedAssetSymbol
            parsedDateSold
            parsedProceeds
            parsedCostBasis
            parsedUnits
            awakenTransactionId
            awakenAssetSymbol
            awakenDateSold
            awakenProceeds
            awakenBasis
            awakenAmount
            proceedsDiff
            basisDiff
            matchStatus
            reviewStatus
        }
    }
}
```

`getBasisMatches` is a diagnostic aid, not proof of a bad transaction. It
matches rows one-to-one by normalized sale date and asset, choosing the
closest proceeds. One exchange row can legitimately correspond to several
Awaken capital-gain rows, especially for BTC, ETH, and SOL. Before calling
a large row mismatch real:

1. group parsed and Awaken rows by sale date and normalized asset;
2. sum every Awaken split, deduplicating repeated
   `awakenTransactionId` values;
3. compare the grouped proceeds and units to the broker group;
4. if the grouped proceeds tie within rounding tolerance, mark it as a
   split-row explanation and do not edit the ledger.

For a broker row with no Awaken candidate, search
`getClientTransactions` over the linked `accountIds`, same asset, and at
least one day on either side. Use `onlyDisposals: true`,
`includeHidden: true`, and `includeSpam: true` so hidden, spam-classified,
or timezone-shifted transactions are not missed.

#### 4. Classify the cause and propose a fix

| Evidence                                                                                            | Likely cause                                                                                                                             | Next action                                                                                                               |
| --------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| Awaken is lower and broker row has no candidate                                                     | incomplete import, hidden/spam disposal, wrong date/asset, or missing transaction                                                        | inspect raw data and import jobs; sync or correct only the evidenced transaction                                          |
| Awaken is higher                                                                                    | duplicate, transfer mislabeled as a disposal, or legitimate Awaken-only disposal                                                         | inspect transaction and transfer legs; preserve legitimate extra proceeds for the proper report group                     |
| Split Awaken rows sum to the broker row                                                             | one-to-many row shape, not a ledger error                                                                                                | record the explanation; no write                                                                                          |
| Same asset differences cancel on adjacent dates                                                     | timezone boundary                                                                                                                        | verify timestamps; usually no write                                                                                       |
| Proceeds tie but basis is missing or implausible                                                    | incomplete acquisition history, unlinked transfer, or missing-basis choice                                                               | follow [Missing cost basis](#missing-cost-basis), then recalculate                                                        |
| Stablecoin raw totals differ                                                                        | expected stablecoin normalization                                                                                                        | use adjusted totals; no forced edit                                                                                       |
| One issue row dominates; Awaken txn is a "Bridge Transfer Send" and the broker row's units are tiny | staked/earn-ticker withdrawal booked as a taxable cross-chain swap ("Bridging Non-Taxable" off)                                          | see the warning below; check the tax setting                                                                              |
| Awaken books the full withdrawal value; the broker's rows for that date are fee-sized dust          | withdrawal to an address the user does not own, or one labeled as a disposal (ex. "Coin Sell"); the broker only reports the withheld fee | expected divergence — Awaken is correct; record the explanation, no write                                                 |
| Awaken is slightly higher on many rows; each delta is roughly that trade's fee                      | broker excludes trade fees from proceeds while Awaken reports them gross                                                                 | expected divergence — record the explanation, no write                                                                    |
| Units match the broker row but the implied unit price is slightly off                               | price-feed deviation — Awaken priced the sale from a market feed, the broker from the actual execution                                   | if Awaken is lower, align the transfer's `fiatValue` to the broker price (with approval); if higher, aligning is optional |

**Price-feed deviation on the sale.** Awaken values a disposal from a
market price feed at the transaction's timestamp, while the broker
reports the actual execution proceeds, so the two can differ slightly
even when the units tie exactly. The signature: the broker and Awaken
rows match on date, asset, and units, but the implied unit price
(proceeds ÷ units) deviates by a small percentage. The broker's
execution price is the better number for that sale. When Awaken's price
is lower — making Awaken's proceeds fall short of the broker's — it is
best to align: edit the disposal leg's `fiatValue` to the broker's
proceeds via [Fix a transfer's numbers](#fix-a-transfers-numbers), with
the user's approval, then recalculate. When the deviation runs the other
way (Awaken slightly higher), aligning is optional — the user can edit
for an exact tie or leave it and record a no-edit explanation.

**Expected divergence — trade fees counted in proceeds.** Some exchanges
report proceeds net of trading fees on the 1099-DA, while Awaken reports
gross proceeds with the fee accounted for separately. The signature is
many small positive `issues[].difference` values, each roughly equal to
the fee on that trade, rather than one dominant row. This makes Awaken's
reported proceeds slightly higher than the broker's, which is perfectly
fine — these cases can be ignored. Record them as no-edit explanations;
do not shave proceeds or edit fees to make the rows tie.

**Expected divergence — withdrawals to addresses the user does not own
(ex. "Coin Sell").** For a token withdrawal, an exchange's 1099-DA
reports only the withheld network fee as a disposal — tiny same-day rows
whose units equal each withdrawal's fee — because the broker treats
every withdrawal as a transfer to an unknown wallet. Awaken has more
context: when the destination address is _not_ one of the user's own
wallets, the tokens actually left the user's control, so Awaken books
the disposal at the fee **plus** the full token value. The same happens
when a person applied a disposal label (ex. `v1:coin_sell`). In both
cases Awaken is correct and the broker is under-inclusive; this is a
legitimate Awaken-only disposal, not a ledger error, and the difference
can be ignored. The default is a no-edit explanation that keeps the
Awaken rows in their proper report group; remove the label or edit the
transaction only if the user, understanding this, explicitly directs it
(for instance, the destination really is theirs — then link it via
[Link wallet-to-wallet movements](#link-wallet-to-wallet-movements)
instead of editing values). Contrast with the staked-ticker warning
below: there the destination _is_ the user's own wallet and an
automation booked the self-transfer as a swap, so the tax setting
governs; here the tokens left the user's control (or a person labeled
the disposal), and that governs.

**Warning — staked/earn tickers withdrawn on-chain (e.g. Kraken `SOL.F` →
`SOL`).** If one `issues[]` row explains nearly the whole discrepancy,
recognize this signature before proposing any edit:

- The broker row's units are tiny — roughly the withdrawal fee (e.g.
  `0.005 SOL`, ~$1 proceeds) — while Awaken books the full withdrawal at
  fair market value (hundreds or thousands of dollars).
- The Awaken transaction is titled "Bridge Transfer Send", has
  `autoReviewReason: v1:bridge_transfer`, a `transactionGroupId` starting
  with `bdg_`, and a `linkedTransactionId` pointing at a receive on the
  user's own wallet.
- The exchange leg uses a suffixed staking/earn ticker (Kraken `.F`/`.S`/
  `.B`, e.g. `SOL.F`) while the on-chain leg is the native asset (`SOL`),
  often for a slightly larger amount (accrued staking rewards paid out
  with the withdrawal).

What is happening: the broker treats the withdrawal as a non-taxable
transfer and reports only the withheld fee as a disposal. Awaken's bridge
automation could not prove the suffixed exchange ticker and the on-chain
asset are the same asset (suffixed tickers have no price-feed id), so it
booked the pair as a taxable cross-chain swap — full proceeds at the
receive-side value. This only happens when the client's "Bridging
Non-Taxable" advanced tax setting is off; when it is on, bridge pairs
carry basis instead of realizing gains. Neither side's import is missing
data.

What to do: confirm the linked receive leg belongs to the user, then
check the setting with `client { taxFeatures { bridging } }`. If it is
not `true`, explain the trade-off and ask whether bridges should carry
basis — this is a tax-position decision that needs the user's explicit
approval. With approval, enable it. The mutation **replaces the whole
settings object**, so read the current `taxFeatures` first and send every
field back with only `bridging` changed:

```graphql
mutation ($clientId: ID!, $taxSettings: AdvancedTaxFeaturesInput!) {
    updateClientTaxSettings(clientId: $clientId, taxSettings: $taxSettings) {
        id
        taxFeatures {
            wrapping
            stakingSwap
            lsts
            airdrops
            stakingRewards
            bridging
            liquidity
        }
    }
}
```

The mutation needs a paid tier or full service and marks the client
dirty — run the full recalculate loop, then re-read the reconciliation.
The discrepancy should collapse to the fee-only disposal (small
price-feed noise). Zeroing out proceeds, relabeling, or overriding
transfer values to force the totals to tie should be a last resort,
taken only at the user's explicit direction.

The proposed plan must identify each target transaction id, the evidence,
the exact mutation or sync action, the expected effect on proceeds/basis,
and confidence. Keep diagnosis read-only until the user approves that
plan. If evidence is ambiguous, ask rather than guessing.

Present every diagnostic run in this order:

1. **Baseline:** broker proceeds, adjusted Awaken proceeds, signed
   discrepancy, basis coverage, and recalculation/import status.
2. **Discrepancy queue:** one row per date and asset with broker proceeds,
   Awaken proceeds, delta, exact transaction ids, likely cause, proposed
   action, and confidence.
3. **No-edit explanations:** split rows, stablecoin normalization,
   timezone offsets, and legitimate Awaken-only disposals.
4. **Approval request:** list only the writes that would occur and their
   expected numeric effect. If there are no justified writes, say so.
5. **Verification:** after approved writes, show before/after discrepancy,
   issue count, basis coverage, and any remaining exceptions.

After approval, apply the smallest relevant mutation from
[Reviewing & editing](#reviewing--editing-readwrite-key), preserve the
pre-edit values for rollback, then run the full recalculate loop. Re-query
the reconciliation after every logical batch. Stop and report if the
absolute adjusted discrepancy grows, issue count increases unexpectedly,
or unrelated totals change.

#### 5. Preview, verify, and generate

The server preview is authoritative for checkbox grouping and final row
shape. Do not infer report boxes from a null broker basis or construct rows
from the reconciliation response.

```graphql
query ($clientId: ID!, $taxFormId: ID!, $brokerBoxG: Boolean) {
    getTaxForm8949Preview(
        clientId: $clientId
        taxFormId: $taxFormId
        useBrokerDataForBoxG: $brokerBoxG
    ) {
        saleTransactionId
        assetName
        assetSymbol
        checkbox
        checkboxGroup
        term
        description
        dateAcquired
        dateSold
        proceeds
        costBasis
        adjustmentCode
        adjustmentAmount
        gainOrLoss
        units
    }
}
```

Cross-check its totals and group counts:

```graphql
query ($clientId: ID!, $taxFormId: ID!) {
    getReportInfo(clientId: $clientId, taxFormId: $taxFormId) {
        boxH {
            proceeds
            basis
            gain
            rowCount
        }
        boxI {
            proceeds
            basis
            gain
            rowCount
        }
        total {
            proceeds
            basis
            gain
            rowCount
        }
    }
}
```

Ready to generate means:

- no unexplained negative adjusted proceeds discrepancy remains;
- every material issue is fixed or explicitly explained;
- split rows were assessed in aggregate rather than edited individually;
- missing basis was corrected or explicitly accepted by the user;
- imports and recalculation are complete;
- preview and report-info totals are internally consistent.

A positive adjusted discrepancy can be valid when Awaken contains genuine
disposals absent from the exchange form; explain where the extra proceeds
will be reported instead of deleting them.

Only after the user reviews this final summary and explicitly confirms,
pass the preview rows unchanged as `Generate1099DATransactionInput`:

```graphql
mutation Generate1099DA(
    $clientId: ID!
    $taxFormId: ID!
    $brokerBoxG: Boolean
    $transactions: [Generate1099DATransactionInput!]!
) {
    generate1099DAReports(
        clientId: $clientId
        taxFormId: $taxFormId
        useBrokerDataForBoxG: $brokerBoxG
        transactions: $transactions
    ) {
        reports {
            title
            url
        }
    }
}
```

This mutation requires a `ReadWrite` key and starts asynchronous
generation; an empty immediate `reports` list is not necessarily failure.
Poll status and generation history every 5–10 seconds:

```graphql
query ($clientId: ID!, $taxFormId: ID!) {
    taxFormGenerations(clientId: $clientId, taxFormId: $taxFormId) {
        id
        createdAt
        updatedAt
        generationInput
        generatedReports
    }
}
```

In the web app, the ordinary path is **Tax Forms → the exchange's
1099-DA → Review Data → Compare**. The compare page shows the row-level
proceeds issues and exact transactions. The advanced Basis Matches page
exists but may not be linked in every UI version; the API query above is
the reliable fallback. An exact transaction opens at
`/clients/<clientId>/transactions?transactionId=<transactionId>`.

### Export a report

`getReportExportV2` kicks off an export on a background worker. With
`shouldDownload: true` it returns a `requestId`; poll
`getReportExportStatus(clientId, requestId) { status downloadUrl error }`
every few seconds until `status` is `ready` (then use `downloadUrl`) or
`failed`. Without it the report is emailed and only `message` is set. Common `type`
values: `Irs8949`, `Irs8949Aggregated`, `IrsScheduleD`, `IrsSchedule1`,
`IncomeReport`, `BalanceReport`, `SalesCSV`, `CanadianSchedule3`,
`HmrcSa108` (full list: `ReportExportTypeEnum`). `dateQueryType` is `year`
or `date_range` (lowercase — `TaxYear` is not a valid value):

```graphql
query ($clientId: ID!) {
    getReportExportV2(
        clientId: $clientId
        type: Irs8949
        dateQueryType: year
        year: "2025"
        shouldDownload: true
    ) {
        requestId
        message
    }
}
```

For an arbitrary window use `dateQueryType: date_range` with
`startDate`/`endDate`. Previously generated reports:
`getReports(clientId) { id title type createdAt }` then
`getReportDownloadUrl(reportId)`.

### Filtered transaction-history CSV

`getTransactionHistoryReportV2` accepts the transaction filters (dates,
accounts, assets, labels, `isMissingBasis`, …) and returns a
`downloadUrl` — the way to export an arbitrary filtered slice.

### Tax-loss harvesting

Unrealized losses you could harvest as of a date:

```graphql
query ($clientId: ID!) {
    getHarvestableLosses(clientId: $clientId, date: "2025-12-15") {
        rows {
            assetSymbol
            assetName
            balance
            costBasisCents
            fiatValueCents
            lossCents
            accountName
            provider
        }
    }
}
```

Related: `getClientInsights(clientId, type: TAX_LOSS)` and
`getInsightsSummary(clientId) { potentialSavingsCents }` (types:
`TAX_LOSS`, `AIRDROP`, `PROFIT_TAKE`).

---

## Wallets & exchange accounts

List existing accounts:

```graphql
query ($clientId: String!) {
    getClientAccounts(clientId: $clientId) {
        id
        description
        provider
        walletAddress
        importType
        integrationStatus
    }
}
```

Add a wallet by address (`provider` is a lowercase slug: `ethereum`,
`base`, `arbitrum`, `polygon`, `optimism`, `solana`, `bitcoin`,
`hyperliquid`, …):

```graphql
mutation ($clientId: String!) {
    createAccount(
        clientId: $clientId
        provider: "ethereum"
        type: Wallet
        importType: Address
        address: "0xabc..."
        label: "Treasury wallet"
    ) {
        id
    }
}
```

`createAccount` returns a **list** of accounts (`[Account!]!`) — one call
can create several (see `shouldUploadAllEVM` below) — so read the ids as
`.data.createAccount[].id`, not `.data.createAccount.id`.

- **One EVM address, all chains**: pass `shouldUploadAllEVM: true` (or
  `providers: [...]` for a specific set). `getUsedChains(address)` shows
  which chains an address has activity on.
- **Exchanges** (Coinbase, Kraken, …): `importType: ApiKey` with
  `apiKey`/`secretKey` (+ `passphrase` for some), `type: Exchange`, or an
  OAuth flow via `getOAuthLink`. Rotate credentials later with
  `refreshApiKey`.
- **Many wallets at once**: `createBatchWallets(clientId, wallets: [...])`.
- **CSV/manual imports** exist (`importType: FileUpload` +
  `fileObjectKey`, `uploadManualTransactions`) but the upload handshake is
  easiest through the web app.

Imports run async — check `getTransactionImportJobs(clientId)` or
`getJobsForAccount(accountId)`; transactions appear after import +
recalculate finish.

Maintain accounts: `syncAccount(accountId)` (one),
`syncAllClientAccounts(clientId, isContinuousSync: false)` (all),
`hardRefreshAccount(accountId)` (full re-import),
`renameAccount(accountId, newName)`,
`retireAccount(accountId, stopImportingAt)` (keep history, stop syncing),
`deleteAccount(accountId)` (destructive — confirm with the user first).

---

## Putting it together: new wallet → final report

The API is asynchronous end to end; this is the rhythm every larger task
follows (each step references a section above):

1. **Add the wallet** — `createAccount(...)` (see
   [Wallets & exchange accounts](#wallets--exchange-accounts)). The
   import starts automatically.
2. **Wait for the import** — poll `getTransactionImportJobs(clientId)`
   every 5–10s until the job leaves `active` (jobs carry `status`,
   `step`, `finishEta`, `numberOfTransactionsLeft`); anything under
   `failed` has a `failures` list saying why.
3. **Recalculate if dirty** — imports normally trigger one automatically;
   confirm with `countDirty` and run `rerunGraph` if it's > 0, then poll
   `getActiveRecalculateJob` until `null`
   (see [Recalculating](#recalculating)).
4. **Check basis coverage** — `getClientTransactions(...,
isMissingBasis: true)`; fix what it finds
   (see [Missing cost basis](#missing-cost-basis)) and recalculate again.
5. **Export** — `getReportExportV2(...)`; if `downloadUrl` is null and
   `message` says the report is generating, fetch it shortly after via
   `getReports` + `getReportDownloadUrl(reportId)`.

Numbers are only final once `countDirty` is 0 and no recalculate job is
active — totals read before that may be stale.

---

## Troubleshooting

| Symptom                                                                          | Cause                                                                                                               | Fix                                                                                                        |
| -------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| `extensions.code: "UNAUTHENTICATED"` (HTTP 401)                                  | Key missing, invalid, expired, or revoked                                                                           | Re-run `/awaken setup`; re-create the key at Settings → API Keys                                           |
| `extensions.code: "403"` or `"FORBIDDEN"` (equivalent)                           | `clientId` isn't the key's client, or a `Read` key ran a mutation                                                   | Re-discover the id via `getMyClients` probing (SKILL.md setup step 3); use a `ReadWrite` key for mutations |
| `ROOT_SELECTION_LIMIT_EXCEEDED`                                                  | More than one root field in one operation                                                                           | Split into separate requests                                                                               |
| `"Limit must be less than or equal to 500"`                                      | `limit` above the cap                                                                                               | Page with `limit: 500` (recipe under [List & filter](#list--filter))                                       |
| HTTP 429                                                                         | Over 300 requests/min from one IP                                                                                   | Back off; watch the `RateLimit-Remaining` header; slow job polling                                         |
| Withdrawal from a staking/lending position booked as income, purchase date reset | Deposit and withdrawal resolved to different staking identifiers, or the wallet had missing basis when it deposited | [Staking, lending & LP positions](#staking-lending--lp-positions-virtual-accounts)                         |
| Totals look wrong or stale                                                       | Ledger dirty after edits/imports                                                                                    | `countDirty` → `rerunGraph` → poll `getActiveRecalculateJob`                                               |
| `getReportExportV2` returns only `message`                                       | Report still generating (or delivered by email)                                                                     | Retry shortly via `getReports` + `getReportDownloadUrl(reportId)`                                          |
| New account shows no transactions                                                | Import or recalculate still running                                                                                 | `getTransactionImportJobs` — wait for `active` to drain; inspect `failed`                                  |
