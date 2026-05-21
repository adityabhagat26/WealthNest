<script lang="ts">
    import {onMount} from 'svelte';
    import {_} from '$lib/i18n';
    import {zodiosApi} from '$lib/api';
    import {portfolioImportVersion} from '$lib/stores/importRefresh';
    import type {AssetInfo, Broker, Transaction} from '$lib/types';
    import {parseCurrencyAmount, safeCurrency} from '$lib/types';
    import {ArrowRightLeft, CalendarDays, Landmark, RefreshCw, Search, Wallet} from 'lucide-svelte';

    let loading = true;
    let error: string | null = null;
    let transactions: Transaction[] = [];
    let brokers = new Map<number, string>();
    let assets = new Map<number, string>();
    let search = '';
    let lastSeenImportVersion = 0;

    onMount(async () => {
        await loadTransactions();
    });

    $: if ($portfolioImportVersion > lastSeenImportVersion) {
        lastSeenImportVersion = $portfolioImportVersion;
        if (!loading) {
            loadTransactions();
        }
    }

    async function loadTransactions() {
        loading = true;
        error = null;

        try {
            const [txRows, brokerRows, assetRows] = await Promise.all([
                zodiosApi.query_transactions_api_v1_transactions_get({queries: {limit: 250}}) as Promise<Transaction[]>,
                zodiosApi.list_brokers_api_v1_brokers_get() as Promise<Broker[]>,
                zodiosApi.get_all_assets_api_v1_assets_all_get() as Promise<AssetInfo[]>
            ]);

            transactions = txRows;
            brokers = new Map(brokerRows.map((broker) => [broker.id, broker.name]));
            assets = new Map(assetRows.map((asset) => [asset.id, asset.display_name]));
        } catch (e) {
            console.error('Failed to load transactions:', e);
            error = 'Failed to load transactions';
        } finally {
            loading = false;
        }
    }

    function formatDate(dateValue: string): string {
        return new Intl.DateTimeFormat(undefined, {
            dateStyle: 'medium'
        }).format(new Date(dateValue));
    }

    function formatAmount(tx: Transaction): string {
        const cash = safeCurrency(tx.cash);
        if (!cash) {
            return tx.quantity ? `${tx.quantity}` : '-';
        }

        const amount = parseCurrencyAmount(cash.amount);
        return new Intl.NumberFormat(undefined, {
            style: 'currency',
            currency: cash.code,
            maximumFractionDigits: 2
        }).format(amount);
    }

    function getAmountTone(tx: Transaction): string {
        const cash = safeCurrency(tx.cash);
        const amount = cash ? parseCurrencyAmount(cash.amount) : 0;
        if (amount > 0 || (!cash && Number(tx.quantity) > 0)) return 'positive';
        if (amount < 0 || (!cash && Number(tx.quantity) < 0)) return 'negative';
        return 'neutral';
    }

    function assetLabel(tx: Transaction): string {
        if (!tx.asset_id) return 'Cash / System';
        return assets.get(tx.asset_id) || `Asset #${tx.asset_id}`;
    }

    function brokerLabel(tx: Transaction): string {
        return brokers.get(tx.broker_id) || `Broker #${tx.broker_id}`;
    }

    function transactionMatchesSearch(tx: Transaction, needle: string): boolean {
        if (!needle) return true;
        return [
            tx.type,
            tx.description,
            assetLabel(tx),
            brokerLabel(tx),
            safeCurrency(tx.cash)?.code
        ].some((value) => value?.toLowerCase().includes(needle));
    }

    $: searchNeedle = search.trim().toLowerCase();
    $: filteredTransactions = transactions.filter((tx) => transactionMatchesSearch(tx, searchNeedle));
    $: transactionTypeBreakdown = Array.from(
        filteredTransactions.reduce((acc, tx) => {
            acc.set(tx.type, (acc.get(tx.type) || 0) + 1);
            return acc;
        }, new Map<string, number>())
    ).sort((a, b) => b[1] - a[1]).slice(0, 4);
</script>

<div class="transactions-page">
    <div class="page-header">
        <div>
            <h2>{$_['transactions.title']}</h2>
            <p>{$_['transactions.subtitle']}</p>
        </div>
        <button class="refresh-btn" on:click={loadTransactions} disabled={loading}>
            <RefreshCw size={16} class={loading ? 'spin' : ''}/>
            <span>{$_['common.refresh'] || 'Refresh'}</span>
        </button>
    </div>

    {#if error}
        <div class="state-banner error">{error}</div>
    {/if}

    {#if loading}
        <div class="state-card">
            <RefreshCw size={22} class="spin"/>
            <span>{$_['common.loading']}</span>
        </div>
    {:else if transactions.length === 0}
        <div class="state-card empty">
            <ArrowRightLeft size={28}/>
            <div>
                <h3>No transactions yet</h3>
                <p>Upload a broker report to populate this page automatically.</p>
            </div>
        </div>
    {:else}
        <div class="toolbar">
            <label class="search-box">
                <Search size={16}/>
                <input bind:value={search} placeholder="Search by asset, broker, type, or note"/>
            </label>
            <div class="type-strip">
                {#each transactionTypeBreakdown as [type, count]}
                    <span class="type-chip">{type} {count}</span>
                {/each}
            </div>
        </div>

        <div class="summary-strip">
            <div class="summary-card">
                <span class="summary-label">Rows</span>
                <strong>{filteredTransactions.length}</strong>
            </div>
            <div class="summary-card">
                <span class="summary-label">Brokers</span>
                <strong>{new Set(filteredTransactions.map((tx) => tx.broker_id)).size}</strong>
            </div>
            <div class="summary-card">
                <span class="summary-label">Assets</span>
                <strong>{new Set(filteredTransactions.map((tx) => tx.asset_id).filter(Boolean)).size}</strong>
            </div>
        </div>

        <div class="mobile-list">
            {#each filteredTransactions as tx}
                <article class="transaction-card">
                    <div class="card-top">
                        <div>
                            <p class="tx-type">{tx.type}</p>
                            <h3>{assetLabel(tx)}</h3>
                        </div>
                        <span class={`amount-pill ${getAmountTone(tx)}`}>{formatAmount(tx)}</span>
                    </div>
                    <div class="meta-grid">
                        <div>
                            <span class="meta-label"><CalendarDays size={14}/> Date</span>
                            <span>{formatDate(tx.date)}</span>
                        </div>
                        <div>
                            <span class="meta-label"><Landmark size={14}/> Broker</span>
                            <span>{brokerLabel(tx)}</span>
                        </div>
                        <div>
                            <span class="meta-label"><Wallet size={14}/> Quantity</span>
                            <span>{tx.quantity}</span>
                        </div>
                        <div>
                            <span class="meta-label">Description</span>
                            <span>{tx.description || '-'}</span>
                        </div>
                    </div>
                </article>
            {/each}
        </div>

        <div class="desktop-table-wrap">
            <table class="transactions-table">
                <thead>
                    <tr>
                        <th>Date</th>
                        <th>Type</th>
                        <th>Asset</th>
                        <th>Broker</th>
                        <th>Quantity</th>
                        <th>Cash</th>
                        <th>Description</th>
                    </tr>
                </thead>
                <tbody>
                    {#each filteredTransactions as tx}
                        <tr>
                            <td>{formatDate(tx.date)}</td>
                            <td><span class="type-badge">{tx.type}</span></td>
                            <td>{assetLabel(tx)}</td>
                            <td>{brokerLabel(tx)}</td>
                            <td>{tx.quantity}</td>
                            <td class={getAmountTone(tx)}>{formatAmount(tx)}</td>
                            <td>{tx.description || '-'}</td>
                        </tr>
                    {/each}
                </tbody>
            </table>
        </div>
    {/if}
</div>

<style>
    .transactions-page {
        padding: 1.25rem;
        display: flex;
        flex-direction: column;
        gap: 1rem;
    }

    .page-header {
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        gap: 1rem;
        flex-wrap: wrap;
    }

    .page-header h2 {
        margin: 0;
        font-size: 1.5rem;
        font-weight: 700;
        color: #e5e7eb;
    }

    .page-header p {
        margin: 0.35rem 0 0;
        color: #94a3b8;
    }

    .toolbar {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 0.75rem;
        flex-wrap: wrap;
    }

    .search-box {
        min-width: min(100%, 320px);
        flex: 1;
        display: inline-flex;
        align-items: center;
        gap: 0.65rem;
        padding: 0.85rem 1rem;
        border-radius: 999px;
        border: 1px solid rgba(148, 163, 184, 0.18);
        background: rgba(15, 23, 42, 0.76);
        color: #94a3b8;
    }

    .search-box input {
        width: 100%;
        background: transparent;
        border: none;
        color: #f8fafc;
        outline: none;
    }

    .search-box input::placeholder {
        color: #94a3b8;
    }

    .type-strip {
        display: flex;
        flex-wrap: wrap;
        gap: 0.5rem;
    }

    .type-chip {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        padding: 0.45rem 0.7rem;
        border-radius: 999px;
        background: rgba(30, 41, 59, 0.8);
        border: 1px solid rgba(148, 163, 184, 0.18);
        color: #cbd5e1;
        font-size: 0.78rem;
        white-space: nowrap;
    }

    .refresh-btn {
        display: inline-flex;
        align-items: center;
        gap: 0.5rem;
        border: 1px solid rgba(148, 163, 184, 0.25);
        background: rgba(15, 23, 42, 0.55);
        color: #e2e8f0;
        border-radius: 999px;
        padding: 0.7rem 1rem;
    }

    .refresh-btn:disabled {
        opacity: 0.7;
    }

    .spin {
        animation: spin 0.9s linear infinite;
    }

    .state-banner,
    .state-card,
    .summary-card,
    .transaction-card,
    .desktop-table-wrap {
        border: 1px solid rgba(148, 163, 184, 0.18);
        background: rgba(15, 23, 42, 0.76);
        border-radius: 1rem;
    }

    .state-banner.error {
        padding: 0.85rem 1rem;
        color: #fecaca;
        background: rgba(127, 29, 29, 0.38);
        border-color: rgba(248, 113, 113, 0.25);
    }

    .state-card {
        padding: 2rem;
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 0.85rem;
        color: #cbd5e1;
        text-align: center;
    }

    .state-card.empty {
        flex-direction: column;
    }

    .state-card h3,
    .state-card p {
        margin: 0;
    }

    .summary-strip {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 0.75rem;
    }

    .summary-card {
        padding: 1rem;
        display: flex;
        flex-direction: column;
        gap: 0.35rem;
    }

    .summary-label {
        color: #94a3b8;
        font-size: 0.8rem;
        text-transform: uppercase;
        letter-spacing: 0.04em;
    }

    .summary-card strong {
        color: #f8fafc;
        font-size: 1.35rem;
    }

    .mobile-list {
        display: grid;
        gap: 0.75rem;
    }

    .transaction-card {
        padding: 1rem;
        display: flex;
        flex-direction: column;
        gap: 0.9rem;
        overflow: hidden;
    }

    .card-top {
        display: flex;
        justify-content: space-between;
        gap: 1rem;
        align-items: flex-start;
    }

    .tx-type {
        margin: 0;
        color: #38bdf8;
        font-size: 0.78rem;
        text-transform: uppercase;
        letter-spacing: 0.06em;
    }

    .transaction-card h3 {
        margin: 0.2rem 0 0;
        color: #f8fafc;
        font-size: 1rem;
        overflow-wrap: anywhere;
    }

    .amount-pill,
    .type-badge {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        border-radius: 999px;
        padding: 0.4rem 0.7rem;
        font-size: 0.78rem;
        font-weight: 600;
        white-space: nowrap;
    }

    .type-badge {
        background: rgba(59, 130, 246, 0.18);
        color: #bfdbfe;
    }

    .amount-pill.positive,
    td.positive {
        color: #86efac;
    }

    .amount-pill.negative,
    td.negative {
        color: #fca5a5;
    }

    .amount-pill.neutral,
    td.neutral {
        color: #e2e8f0;
    }

    .meta-grid {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 0.75rem;
    }

    .meta-grid > div {
        display: flex;
        flex-direction: column;
        gap: 0.25rem;
        color: #e2e8f0;
        min-width: 0;
        overflow-wrap: anywhere;
    }

    .meta-label {
        display: inline-flex;
        align-items: center;
        gap: 0.35rem;
        color: #94a3b8;
        font-size: 0.8rem;
    }

    .desktop-table-wrap {
        overflow-x: auto;
        display: none;
    }

    .transactions-table {
        width: 100%;
        border-collapse: collapse;
        min-width: 860px;
    }

    .transactions-table th,
    .transactions-table td {
        padding: 0.95rem 1rem;
        border-bottom: 1px solid rgba(148, 163, 184, 0.12);
        text-align: left;
        color: #e2e8f0;
    }

    .transactions-table th {
        color: #94a3b8;
        font-size: 0.8rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }

    .transactions-table tbody tr:hover {
        background: rgba(30, 41, 59, 0.55);
    }

    @media (min-width: 900px) {
        .mobile-list {
            display: none;
        }

        .desktop-table-wrap {
            display: block;
        }
    }

    @media (max-width: 640px) {
        .transactions-page {
            padding: 1rem;
        }

        .summary-strip,
        .meta-grid {
            grid-template-columns: 1fr;
        }

        .search-box {
            min-width: 100%;
        }

        .card-top {
            flex-direction: column;
        }

        .amount-pill {
            align-self: flex-start;
        }
    }

    @keyframes spin {
        from { transform: rotate(0deg); }
        to { transform: rotate(360deg); }
    }
</style>
