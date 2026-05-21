<script lang="ts">
    import {onMount} from 'svelte';
    import {_} from '$lib/i18n';
    import {zodiosApi} from '$lib/api';
    import {currentUser} from '$lib/stores/auth';
    import {userSettings} from '$lib/stores/settings';
    import {parseCurrencyAmount, safeCurrency} from '$lib/types';
    import type {Broker, BrokerSummary, Transaction} from '$lib/types';
    import {
        ArrowRightLeft,
        BarChart3,
        Briefcase,
        Coins,
        Landmark,
        PieChart,
        RefreshCw,
        TrendingDown,
        TrendingUp,
        Wallet
    } from 'lucide-svelte';

    let loading = true;
    let error: string | null = null;
    let brokers: Broker[] = [];
    let brokerSummaries: BrokerSummary[] = [];
    let recentTransactions: Transaction[] = [];

    $: avatarUrl = $userSettings?.avatar_url as string | null | undefined;
    $: baseCurrency = $userSettings?.base_currency ?? 'INR';

    const quickActions = [
        {
            href: '/brokers',
            icon: Briefcase,
            titleKey: 'nav.brokers',
            descKey: 'dashboard.manageBrokers',
            tone: 'sky'
        },
        {
            href: '/assets',
            icon: BarChart3,
            titleKey: 'nav.assets',
            descKey: 'dashboard.manageAssets',
            tone: 'emerald'
        },
        {
            href: '/transactions',
            icon: ArrowRightLeft,
            titleKey: 'nav.transactions',
            descKey: 'dashboard.manageTransactions',
            tone: 'amber'
        },
        {
            href: '/fx',
            icon: Coins,
            titleKey: 'nav.fx',
            descKey: 'dashboard.manageFx',
            tone: 'rose'
        }
    ];

    onMount(async () => {
        await loadDashboard();
    });

    async function loadDashboard() {
        loading = true;
        error = null;

        try {
            const brokerRows = await zodiosApi.list_brokers_api_v1_brokers_get() as Broker[];
            brokers = brokerRows;

            const [summaries, transactions] = await Promise.all([
                Promise.all(
                    brokerRows.map((broker) =>
                        zodiosApi
                            .get_broker_summary_api_v1_brokers__broker_id__summary_get({params: {broker_id: broker.id}})
                            .catch(() => null)
                    )
                ),
                zodiosApi.query_transactions_api_v1_transactions_get({queries: {limit: 8}}) as Promise<Transaction[]>
            ]);

            brokerSummaries = summaries.filter((summary): summary is BrokerSummary => summary !== null);
            recentTransactions = transactions;
        } catch (e) {
            console.error('Failed to load dashboard:', e);
            error = 'Failed to load dashboard';
        } finally {
            loading = false;
        }
    }

    function formatCurrency(amount: number, currency = baseCurrency): string {
        return new Intl.NumberFormat(undefined, {
            style: 'currency',
            currency,
            maximumFractionDigits: 2
        }).format(amount);
    }

    function formatCompactCurrency(amount: number, currency = baseCurrency): string {
        return new Intl.NumberFormat(undefined, {
            style: 'currency',
            currency,
            notation: 'compact',
            maximumFractionDigits: 1
        }).format(amount);
    }

    function formatPercent(value: number): string {
        return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`;
    }

    function formatTransactionDate(dateValue: string): string {
        return new Intl.DateTimeFormat(undefined, {dateStyle: 'medium'}).format(new Date(dateValue));
    }

    function brokerName(brokerId: number): string {
        return brokers.find((broker) => broker.id === brokerId)?.name ?? `Broker #${brokerId}`;
    }

    function transactionCashAmount(tx: Transaction): number {
        const cash = safeCurrency(tx.cash);
        return cash ? parseCurrencyAmount(cash.amount) : 0;
    }

    function transactionCashCode(tx: Transaction): string {
        const cash = safeCurrency(tx.cash);
        return cash?.code ?? baseCurrency;
    }

    function formatTransactionAmount(tx: Transaction): string {
        const cash = safeCurrency(tx.cash);
        if (!cash) return tx.quantity ? `${tx.quantity}` : '-';
        return formatCurrency(parseCurrencyAmount(cash.amount), cash.code);
    }

    function transactionTone(tx: Transaction): 'positive' | 'negative' | 'neutral' {
        const amount = transactionCashAmount(tx);
        if (amount > 0) return 'positive';
        if (amount < 0) return 'negative';
        return 'neutral';
    }

    function actionToneClass(tone: string): string {
        const classes: Record<string, string> = {
            sky: 'bg-sky-500/12 text-sky-200 ring-sky-400/20',
            emerald: 'bg-emerald-500/12 text-emerald-200 ring-emerald-400/20',
            amber: 'bg-amber-500/12 text-amber-200 ring-amber-400/20',
            rose: 'bg-rose-500/12 text-rose-200 ring-rose-400/20'
        };
        return classes[tone] ?? classes.sky;
    }

    $: totalPortfolioValue = brokerSummaries.reduce((sum, broker) => {
        const value = safeCurrency(broker.total_value_base_currency);
        return sum + (value ? parseCurrencyAmount(value.amount) : 0);
    }, 0);

    $: totalCashValue = brokerSummaries.reduce((sum, broker) => {
        return sum + broker.cash_balances.reduce((cashSum, cash) => {
            const safeCash = safeCurrency(cash);
            if (!safeCash) return cashSum;
            if (safeCash.code !== baseCurrency) return cashSum;
            return cashSum + parseCurrencyAmount(safeCash.amount);
        }, 0);
    }, 0);

    $: totalHoldingsValue = brokerSummaries.reduce((sum, broker) => {
        return sum + broker.holdings.reduce((holdingSum, holding) => {
            const currentValueBase = safeCurrency((holding as any).current_value_base_currency);
            if (currentValueBase) return holdingSum + parseCurrencyAmount(currentValueBase.amount);
            const currentValue = safeCurrency(holding.current_value);
            if (!currentValue || currentValue.code !== baseCurrency) return holdingSum;
            return holdingSum + parseCurrencyAmount(currentValue.amount);
        }, 0);
    }, 0);

    $: totalInvestedCost = brokerSummaries.reduce((sum, broker) => {
        return sum + broker.holdings.reduce((holdingSum, holding) => {
            const totalCostBase = safeCurrency((holding as any).total_cost_base_currency);
            if (totalCostBase) return holdingSum + parseCurrencyAmount(totalCostBase.amount);
            const totalCost = safeCurrency(holding.total_cost);
            if (!totalCost || totalCost.code !== baseCurrency) return holdingSum;
            return holdingSum + parseCurrencyAmount(totalCost.amount);
        }, 0);
    }, 0);

    $: totalUnrealizedPnl = brokerSummaries.reduce((sum, broker) => {
        return sum + broker.holdings.reduce((holdingSum, holding) => {
            const pnlBase = safeCurrency((holding as any).unrealized_pnl_base_currency);
            if (pnlBase) return holdingSum + parseCurrencyAmount(pnlBase.amount);
            const pnl = safeCurrency(holding.unrealized_pnl);
            if (!pnl || pnl.code !== baseCurrency) return holdingSum;
            return holdingSum + parseCurrencyAmount(pnl.amount);
        }, 0);
    }, 0);

    $: totalUnrealizedPnlPercent = totalInvestedCost > 0 ? (totalUnrealizedPnl / totalInvestedCost) * 100 : 0;
    $: totalHoldingsCount = brokerSummaries.reduce((sum, broker) => sum + broker.holdings.length, 0);
    $: activeBrokerCount = brokerSummaries.filter((broker) => broker.is_active).length;
    $: cashRatio = totalPortfolioValue > 0 ? (totalCashValue / totalPortfolioValue) * 100 : 0;

    $: brokerBreakdown = brokerSummaries
        .map((broker) => {
            const total = safeCurrency(broker.total_value_base_currency);
            const amount = total ? parseCurrencyAmount(total.amount) : 0;
            return {
                id: broker.id,
                name: broker.name,
                amount,
                cashCount: broker.cash_balances.length,
                holdingsCount: broker.holdings.length,
                isActive: broker.is_active
            };
        })
        .sort((a, b) => b.amount - a.amount)
        .slice(0, 4);

    $: recentFlow = recentTransactions.reduce((acc, tx) => {
        const amount = transactionCashAmount(tx);
        if (amount > 0) acc.inflow += amount;
        if (amount < 0) acc.outflow += Math.abs(amount);
        return acc;
    }, {inflow: 0, outflow: 0});

    $: statusMessage = totalPortfolioValue <= 0
        ? 'Start by adding a broker balance or importing transactions to unlock your portfolio overview.'
        : cashRatio > 35
            ? 'You currently hold a sizable cash buffer, which can help with flexibility and downside protection.'
            : totalUnrealizedPnl >= 0
                ? 'Your portfolio is in positive territory based on the latest priced holdings.'
                : 'Your portfolio is below cost basis right now, which may be useful for reviewing allocation and risk.';
</script>

<div class="dashboard-shell" data-testid="dashboard-page">
    <h1 class="sr-only">{$_('nav.dashboard')}</h1>

    {#if $currentUser}
        <section class="hero-card">
            <div class="hero-copy">
                <div class="eyebrow">Portfolio command center</div>
                <h2>{$_('dashboard.welcomeBack')}, {$currentUser.username}!</h2>
                <p>{statusMessage}</p>

                <div class="hero-metrics">
                    <div class="hero-chip">
                        <span>Net worth</span>
                        <strong>{loading ? '...' : formatCompactCurrency(totalPortfolioValue)}</strong>
                    </div>
                    <div class="hero-chip">
                        <span>Cash ratio</span>
                        <strong>{loading ? '...' : `${cashRatio.toFixed(1)}%`}</strong>
                    </div>
                    <div class="hero-chip">
                        <span>Active brokers</span>
                        <strong>{loading ? '...' : activeBrokerCount}</strong>
                    </div>
                </div>
            </div>

            <div class="hero-avatar">
                {#if avatarUrl}
                    <img src={avatarUrl} alt="Avatar" class="avatar-image" />
                {:else}
                    <span>{$currentUser.username.charAt(0).toUpperCase()}</span>
                {/if}
            </div>
        </section>
    {/if}

    <section class="stats-grid">
        <article class="stat-card featured">
            <div class="stat-head">
                <div>
                    <span class="stat-label">{$_('dashboard.totalValue')}</span>
                    <strong>{loading ? 'Loading...' : formatCurrency(totalPortfolioValue)}</strong>
                </div>
                <div class="stat-icon mint">
                    <Wallet size={22}/>
                </div>
            </div>
            <p class="stat-foot">
                {loading ? 'Calculating portfolio totals...' : `${brokerSummaries.length} broker accounts included`}
            </p>
        </article>

        <article class="stat-card">
            <div class="stat-head">
                <div>
                    <span class="stat-label">{$_('dashboard.totalGain')}</span>
                    <strong class:positive={totalUnrealizedPnl >= 0} class:negative={totalUnrealizedPnl < 0}>
                        {loading ? 'Loading...' : formatCurrency(totalUnrealizedPnl)}
                    </strong>
                </div>
                <div class="stat-icon blue">
                    {#if totalUnrealizedPnl >= 0}
                        <TrendingUp size={22}/>
                    {:else}
                        <TrendingDown size={22}/>
                    {/if}
                </div>
            </div>
            <p class="stat-foot">
                {loading ? 'Waiting for holdings data...' : `${formatPercent(totalUnrealizedPnlPercent)} vs cost basis`}
            </p>
        </article>

        <article class="stat-card">
            <div class="stat-head">
                <div>
                    <span class="stat-label">Cash available</span>
                    <strong>{loading ? 'Loading...' : formatCurrency(totalCashValue)}</strong>
                </div>
                <div class="stat-icon amber">
                    <Coins size={22}/>
                </div>
            </div>
            <p class="stat-foot">
                {loading ? 'Measuring liquidity...' : `${cashRatio.toFixed(1)}% of portfolio kept in cash`}
            </p>
        </article>

        <article class="stat-card">
            <div class="stat-head">
                <div>
                    <span class="stat-label">{$_('dashboard.assetCount')}</span>
                    <strong>{loading ? 'Loading...' : totalHoldingsCount}</strong>
                </div>
                <div class="stat-icon rose">
                    <PieChart size={22}/>
                </div>
            </div>
            <p class="stat-foot">
                {loading ? 'Scanning positions...' : `${activeBrokerCount} active brokers, ${brokers.length - activeBrokerCount} inactive`}
            </p>
        </article>
    </section>

    {#if error}
        <section class="panel error-panel">
            <div>
                <h3>Dashboard data could not be loaded</h3>
                <p>{error}</p>
            </div>
            <button class="ghost-btn" on:click={loadDashboard} disabled={loading}>
                <RefreshCw size={16} class={loading ? 'spin' : ''}/>
                <span>{$_('error.tryAgain')}</span>
            </button>
        </section>
    {/if}

    <section class="insight-grid">
        <article class="panel spotlight">
            <div class="panel-title-row">
                <div>
                    <div class="panel-kicker">Portfolio mix</div>
                    <h3>Where your money sits</h3>
                </div>
                <div class="ring-chart" style={`--cash:${Math.min(Math.max(cashRatio, 0), 100)};`}>
                    <span>{loading ? '--' : `${cashRatio.toFixed(0)}%`}</span>
                </div>
            </div>

            <div class="mix-grid">
                <div class="mix-card">
                    <span>Invested holdings</span>
                    <strong>{loading ? '...' : formatCurrency(totalHoldingsValue)}</strong>
                </div>
                <div class="mix-card">
                    <span>Cash reserves</span>
                    <strong>{loading ? '...' : formatCurrency(totalCashValue)}</strong>
                </div>
                <div class="mix-card">
                    <span>Cost basis tracked</span>
                    <strong>{loading ? '...' : formatCurrency(totalInvestedCost)}</strong>
                </div>
                <div class="mix-card">
                    <span>Recent inflow</span>
                    <strong>{loading ? '...' : formatCurrency(recentFlow.inflow)}</strong>
                </div>
            </div>
        </article>

        <article class="panel">
            <div class="panel-title-row compact">
                <div>
                    <div class="panel-kicker">Broker ranking</div>
                    <h3>Top accounts by value</h3>
                </div>
                <a class="ghost-link" href="/brokers">View all</a>
            </div>

            {#if loading}
                <div class="empty-panel">Loading broker summaries...</div>
            {:else if brokerBreakdown.length === 0}
                <div class="empty-panel">No broker balances available yet.</div>
            {:else}
                <div class="broker-list">
                    {#each brokerBreakdown as broker, index}
                        <div class="broker-row">
                            <div class="broker-rank">{index + 1}</div>
                            <div class="broker-main">
                                <strong>{broker.name}</strong>
                                <span>{broker.holdingsCount} holdings • {broker.cashCount} cash balances</span>
                            </div>
                            <div class="broker-side">
                                <strong>{formatCompactCurrency(broker.amount)}</strong>
                                <span class:active={broker.isActive}>{broker.isActive ? 'Active' : 'Inactive'}</span>
                            </div>
                        </div>
                    {/each}
                </div>
            {/if}
        </article>
    </section>

    <section class="content-grid">
        <article class="panel">
            <div class="panel-title-row compact">
                <div>
                    <div class="panel-kicker">Activity</div>
                    <h3>Recent transactions</h3>
                </div>
                <a class="ghost-link" href="/transactions">Open ledger</a>
            </div>

            {#if loading}
                <div class="empty-panel">Loading recent activity...</div>
            {:else if recentTransactions.length === 0}
                <div class="empty-panel">No transactions yet. Import a broker report to populate this dashboard.</div>
            {:else}
                <div class="activity-list">
                    {#each recentTransactions as tx}
                        <div class="activity-row">
                            <div class={`activity-icon ${transactionTone(tx)}`}>
                                <ArrowRightLeft size={16}/>
                            </div>
                            <div class="activity-main">
                                <strong>{tx.type}</strong>
                                <span>{brokerName(tx.broker_id)} • {formatTransactionDate(tx.date)}</span>
                            </div>
                            <div class="activity-side">
                                <strong class={transactionTone(tx)}>{formatTransactionAmount(tx)}</strong>
                                <span>{transactionCashCode(tx)}</span>
                            </div>
                        </div>
                    {/each}
                </div>
            {/if}
        </article>

        <article class="panel">
            <div class="panel-title-row compact">
                <div>
                    <div class="panel-kicker">Next steps</div>
                    <h3>Move around your workspace</h3>
                </div>
                <button class="ghost-btn" on:click={loadDashboard} disabled={loading}>
                    <RefreshCw size={16} class={loading ? 'spin' : ''}/>
                    <span>{$_['common.refresh'] || 'Refresh'}</span>
                </button>
            </div>

            <div class="actions-grid">
                {#each quickActions as action}
                    <a href={action.href} class="action-card">
                        <div class={`action-icon ${actionToneClass(action.tone)}`}>
                            <svelte:component this={action.icon} size={20}/>
                        </div>
                        <div class="action-copy">
                            <strong>{$_(action.titleKey)}</strong>
                            <span>{$_(action.descKey)}</span>
                        </div>
                    </a>
                {/each}
            </div>

            <div class="status-strip">
                <div class="status-pill">
                    <Landmark size={15}/>
                    <span>{loading ? '...' : `${brokers.length} brokers connected`}</span>
                </div>
                <div class="status-pill">
                    <BarChart3 size={15}/>
                    <span>{loading ? '...' : `${totalHoldingsCount} priced positions tracked`}</span>
                </div>
            </div>
        </article>
    </section>
</div>

<style>
    .dashboard-shell {
        padding: 1.25rem;
        display: flex;
        flex-direction: column;
        gap: 1rem;
        color: #e5eef7;
        background:
            radial-gradient(circle at top left, rgba(16, 185, 129, 0.12), transparent 28%),
            radial-gradient(circle at top right, rgba(56, 189, 248, 0.14), transparent 24%),
            linear-gradient(180deg, rgba(7, 15, 28, 0.98), rgba(9, 18, 32, 0.92));
    }

    .hero-card,
    .panel,
    .stat-card {
        border: 1px solid rgba(148, 163, 184, 0.16);
        background: linear-gradient(180deg, rgba(15, 23, 42, 0.88), rgba(10, 17, 31, 0.92));
        box-shadow: 0 24px 60px rgba(2, 6, 23, 0.24);
    }

    .hero-card {
        display: flex;
        justify-content: space-between;
        gap: 1rem;
        padding: 1.4rem;
        border-radius: 1.5rem;
        overflow: hidden;
        position: relative;
    }

    .hero-card::after {
        content: '';
        position: absolute;
        inset: auto -3rem -3rem auto;
        width: 12rem;
        height: 12rem;
        border-radius: 999px;
        background: radial-gradient(circle, rgba(16, 185, 129, 0.3), transparent 68%);
        pointer-events: none;
    }

    .hero-copy {
        max-width: 44rem;
        display: flex;
        flex-direction: column;
        gap: 0.85rem;
    }

    .eyebrow,
    .panel-kicker,
    .stat-label {
        text-transform: uppercase;
        letter-spacing: 0.08em;
        font-size: 0.72rem;
        color: #94a3b8;
    }

    .hero-copy h2,
    .panel h3 {
        margin: 0;
    }

    .hero-copy h2 {
        font-size: clamp(1.5rem, 2vw, 2.15rem);
        line-height: 1.1;
        color: #f8fafc;
    }

    .hero-copy p {
        margin: 0;
        color: #cbd5e1;
        max-width: 40rem;
    }

    .hero-metrics {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 0.75rem;
    }

    .hero-chip {
        padding: 0.9rem 1rem;
        border-radius: 1rem;
        background: rgba(255, 255, 255, 0.04);
        border: 1px solid rgba(148, 163, 184, 0.14);
        display: flex;
        flex-direction: column;
        gap: 0.25rem;
    }

    .hero-chip span {
        color: #94a3b8;
        font-size: 0.8rem;
    }

    .hero-chip strong {
        color: #f8fafc;
        font-size: 1.15rem;
    }

    .hero-avatar {
        width: 5rem;
        height: 5rem;
        border-radius: 1.4rem;
        background: linear-gradient(135deg, rgba(16, 185, 129, 0.28), rgba(56, 189, 248, 0.26));
        border: 1px solid rgba(255, 255, 255, 0.12);
        display: flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
        overflow: hidden;
        color: #f8fafc;
        font-size: 2rem;
        font-weight: 700;
    }

    .avatar-image {
        width: 100%;
        height: 100%;
        object-fit: cover;
    }

    .stats-grid,
    .insight-grid,
    .content-grid {
        display: grid;
        gap: 1rem;
    }

    .stats-grid {
        grid-template-columns: repeat(4, minmax(0, 1fr));
    }

    .insight-grid {
        grid-template-columns: 1.3fr 1fr;
    }

    .content-grid {
        grid-template-columns: 1.2fr 1fr;
    }

    .stat-card {
        padding: 1.15rem;
        border-radius: 1.25rem;
    }

    .stat-card.featured {
        background: linear-gradient(135deg, rgba(5, 150, 105, 0.22), rgba(15, 23, 42, 0.92));
    }

    .stat-head,
    .panel-title-row,
    .broker-row,
    .activity-row {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 1rem;
    }

    .stat-head strong {
        display: block;
        margin-top: 0.25rem;
        color: #f8fafc;
        font-size: 1.45rem;
        line-height: 1.15;
    }

    .stat-head strong.positive,
    .activity-side strong.positive {
        color: #86efac;
    }

    .stat-head strong.negative,
    .activity-side strong.negative {
        color: #fda4af;
    }

    .stat-icon,
    .activity-icon,
    .action-icon {
        width: 2.8rem;
        height: 2.8rem;
        border-radius: 0.95rem;
        display: flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
    }

    .stat-icon.mint {
        background: rgba(16, 185, 129, 0.14);
        color: #6ee7b7;
    }

    .stat-icon.blue {
        background: rgba(59, 130, 246, 0.14);
        color: #93c5fd;
    }

    .stat-icon.amber {
        background: rgba(245, 158, 11, 0.14);
        color: #fcd34d;
    }

    .stat-icon.rose {
        background: rgba(244, 63, 94, 0.14);
        color: #fda4af;
    }

    .stat-foot {
        margin: 0.8rem 0 0;
        color: #94a3b8;
        font-size: 0.88rem;
    }

    .panel {
        border-radius: 1.4rem;
        padding: 1.2rem;
    }

    .panel-title-row.compact {
        align-items: flex-start;
    }

    .ring-chart {
        --cash: 0;
        width: 5.25rem;
        height: 5.25rem;
        border-radius: 999px;
        display: grid;
        place-items: center;
        background:
            radial-gradient(circle at center, rgba(15, 23, 42, 1) 58%, transparent 59%),
            conic-gradient(#10b981 calc(var(--cash) * 1%), rgba(30, 41, 59, 0.96) 0);
        color: #f8fafc;
        font-weight: 700;
    }

    .mix-grid,
    .actions-grid {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 0.75rem;
        margin-top: 1rem;
    }

    .mix-card,
    .action-card,
    .empty-panel {
        border-radius: 1rem;
        border: 1px solid rgba(148, 163, 184, 0.14);
        background: rgba(255, 255, 255, 0.03);
    }

    .mix-card {
        padding: 0.95rem;
        display: flex;
        flex-direction: column;
        gap: 0.35rem;
    }

    .mix-card span,
    .broker-main span,
    .broker-side span,
    .activity-main span,
    .activity-side span,
    .action-copy span {
        color: #94a3b8;
        font-size: 0.84rem;
    }

    .mix-card strong,
    .broker-main strong,
    .broker-side strong,
    .activity-main strong,
    .activity-side strong,
    .action-copy strong {
        color: #f8fafc;
    }

    .broker-list,
    .activity-list {
        margin-top: 1rem;
        display: grid;
        gap: 0.75rem;
    }

    .broker-row,
    .activity-row {
        padding: 0.85rem 0.95rem;
        border-radius: 1rem;
        background: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(148, 163, 184, 0.1);
    }

    .broker-rank {
        width: 2rem;
        height: 2rem;
        border-radius: 999px;
        display: flex;
        align-items: center;
        justify-content: center;
        background: rgba(56, 189, 248, 0.14);
        color: #bfdbfe;
        font-weight: 700;
        flex-shrink: 0;
    }

    .broker-main,
    .broker-side,
    .activity-main,
    .activity-side,
    .action-copy {
        display: flex;
        flex-direction: column;
        gap: 0.18rem;
        min-width: 0;
    }

    .broker-main {
        flex: 1;
    }

    .broker-side,
    .activity-side {
        align-items: flex-end;
        text-align: right;
    }

    .broker-side span.active {
        color: #86efac;
    }

    .activity-icon.positive {
        background: rgba(16, 185, 129, 0.14);
        color: #86efac;
    }

    .activity-icon.negative {
        background: rgba(244, 63, 94, 0.14);
        color: #fda4af;
    }

    .activity-icon.neutral {
        background: rgba(148, 163, 184, 0.14);
        color: #cbd5e1;
    }

    .action-card {
        padding: 0.95rem;
        display: flex;
        align-items: center;
        gap: 0.85rem;
        text-decoration: none;
        transition: transform 0.18s ease, border-color 0.18s ease;
    }

    .action-card:hover {
        transform: translateY(-1px);
        border-color: rgba(148, 163, 184, 0.28);
    }

    .status-strip {
        margin-top: 1rem;
        display: flex;
        flex-wrap: wrap;
        gap: 0.75rem;
    }

    .status-pill,
    .ghost-btn,
    .ghost-link {
        display: inline-flex;
        align-items: center;
        gap: 0.45rem;
        border-radius: 999px;
        border: 1px solid rgba(148, 163, 184, 0.18);
        background: rgba(255, 255, 255, 0.04);
        color: #e2e8f0;
        padding: 0.6rem 0.9rem;
        text-decoration: none;
    }

    .ghost-btn {
        cursor: pointer;
    }

    .ghost-btn:disabled {
        opacity: 0.6;
        cursor: wait;
    }

    .empty-panel {
        margin-top: 1rem;
        padding: 1rem;
        color: #94a3b8;
    }

    .error-panel {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 1rem;
        border-color: rgba(248, 113, 113, 0.25);
        background: linear-gradient(180deg, rgba(69, 10, 10, 0.52), rgba(31, 13, 18, 0.88));
    }

    .error-panel h3,
    .error-panel p {
        margin: 0;
    }

    .spin {
        animation: spin 0.9s linear infinite;
    }

    @media (max-width: 1100px) {
        .stats-grid,
        .insight-grid,
        .content-grid {
            grid-template-columns: 1fr 1fr;
        }

        .stats-grid {
            grid-template-columns: repeat(2, minmax(0, 1fr));
        }
    }

    @media (max-width: 760px) {
        .dashboard-shell {
            padding: 1rem;
        }

        .hero-card,
        .panel-title-row,
        .stat-head,
        .broker-row,
        .activity-row {
            flex-direction: column;
            align-items: flex-start;
        }

        .hero-avatar,
        .ring-chart {
            align-self: flex-start;
        }

        .hero-metrics,
        .stats-grid,
        .insight-grid,
        .content-grid,
        .mix-grid,
        .actions-grid {
            grid-template-columns: 1fr;
        }

        .broker-side,
        .activity-side {
            align-items: flex-start;
            text-align: left;
        }
    }

    @keyframes spin {
        from { transform: rotate(0deg); }
        to { transform: rotate(360deg); }
    }
</style>
