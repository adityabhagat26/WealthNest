<script lang="ts">
    import {onMount} from 'svelte';
    import {_} from '$lib/i18n';
    import {axiosInstance} from '$lib/api';
    import {RefreshCw, Search} from 'lucide-svelte';

    let loading = true;
    let error: string | null = null;
    let warning: string | null = null;
    let symbolInput = '';
    let marketSymbols = ['RELIANCE', 'TCS', 'INFY', 'HDFCBANK', 'SBIN', 'ICICIBANK'];
    let marketRows: {
        symbol: string;
        quote: {regular_market_price: number; currency: string} | null;
        history: {date: string; close: number}[];
        changePct: number | null;
        failed: boolean;
    }[] = [];

    onMount(async () => {
        await loadMarketData();
    });

    async function loadMarketData() {
        loading = true;
        error = null;
        warning = null;
        try {
            const settled = await Promise.allSettled(
                marketSymbols.map(async (symbol) => {
                    const quoteRes = await axiosInstance.get(`/api/v1/market/yahoo/quote/${symbol}`);
                    let history: {date: string; close: number}[] = [];
                    try {
                        const historyRes = await axiosInstance.get(`/api/v1/market/yahoo/history/${symbol}`, {params: {period_days: 90}});
                        history = ((historyRes.data?.points ?? []) as {date: string; close: number}[]);
                    } catch {
                        history = [];
                    }
                    const quote = quoteRes.data as {regular_market_price: number; currency: string};
                    const first = history[0]?.close ?? null;
                    const last = history[history.length - 1]?.close ?? null;
                    const changePct = first && last ? ((last - first) / first) * 100 : null;
                    return {symbol, quote, history, changePct, failed: false};
                })
            );
            marketRows = settled.map((item, index) => {
                if (item.status === 'fulfilled') return item.value;
                return {
                    symbol: marketSymbols[index],
                    quote: null,
                    history: [],
                    changePct: null,
                    failed: true
                };
            });
            const successCount = marketRows.filter(r => !r.failed).length;
            if (successCount === 0) {
                error = 'Failed to load Yahoo market data.';
            } else if (successCount < marketRows.length) {
                warning = `Loaded ${successCount}/${marketRows.length} symbols. Some were unavailable.`;
            }
        } catch (e) {
            console.error('Failed to load market data:', e);
            error = 'Failed to load Yahoo market data.';
            marketRows = [];
        } finally {
            loading = false;
        }
    }

    function addSymbol() {
        const cleaned = symbolInput.trim().toUpperCase();
        if (!cleaned || marketSymbols.includes(cleaned)) return;
        marketSymbols = [...marketSymbols, cleaned];
        symbolInput = '';
        void loadMarketData();
    }

    function formatCurrency(amount: number, currency = 'INR'): string {
        return new Intl.NumberFormat(undefined, {
            style: 'currency',
            currency,
            maximumFractionDigits: 2
        }).format(amount);
    }

    function formatPercent(value: number): string {
        return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`;
    }

    function sparklinePoints(history: {close: number}[]): string {
        if (history.length < 2) return '';
        const closes = history.map(h => h.close);
        const min = Math.min(...closes);
        const max = Math.max(...closes);
        const range = max - min || 1;
        return closes
            .map((value, index) => {
                const x = (index / (closes.length - 1)) * 100;
                const y = 100 - (((value - min) / range) * 100);
                return `${x},${y}`;
            })
            .join(' ');
    }
</script>

<div class="market-shell" data-testid="market-live-page">
    <section class="panel">
        <div class="panel-title-row">
            <div>
                <div class="panel-kicker">Live market</div>
                <h1>{$_('nav.marketLive')}</h1>
            </div>
            <div class="market-toolbar">
                <div class="symbol-input">
                    <Search size={14}/>
                    <input
                        bind:value={symbolInput}
                        placeholder="Add symbol (e.g. ITC)"
                        on:keydown={(e) => e.key === 'Enter' && addSymbol()}
                    />
                </div>
                <button class="ghost-btn" on:click={addSymbol}>Add</button>
                <button class="ghost-btn" on:click={loadMarketData} disabled={loading}>
                    <RefreshCw size={16} class={loading ? 'spin' : ''}/>
                    <span>{$_('common.refresh')}</span>
                </button>
            </div>
        </div>

        {#if loading}
            <div class="empty-panel">Loading Yahoo Finance quotes and charts...</div>
        {:else}
            {#if error}
                <div class="empty-panel">{error}</div>
            {/if}
            {#if warning}
                <div class="warning-panel">{warning}</div>
            {/if}
            <div class="market-grid">
                {#each marketRows as row}
                    <article class="market-card">
                        <div class="market-head">
                            <strong>{row.symbol}</strong>
                            <span class:positive={(row.changePct ?? 0) >= 0} class:negative={(row.changePct ?? 0) < 0}>
                                {row.changePct === null ? '--' : formatPercent(row.changePct)}
                            </span>
                        </div>
                        <div class="market-price">
                            {row.quote ? formatCurrency(row.quote.regular_market_price, row.quote.currency) : '--'}
                        </div>
                        {#if row.failed}
                            <div class="muted">Symbol unavailable</div>
                        {:else if row.history.length > 1}
                            <svg viewBox="0 0 100 100" preserveAspectRatio="none" class="sparkline">
                                <polyline
                                    fill="none"
                                    stroke={(row.changePct ?? 0) >= 0 ? '#34d399' : '#fb7185'}
                                    stroke-width="3"
                                    points={sparklinePoints(row.history)}
                                />
                            </svg>
                        {:else}
                            <div class="muted">History unavailable</div>
                        {/if}
                    </article>
                {/each}
            </div>
        {/if}
    </section>
</div>

<style>
    .market-shell {
        padding: 1.25rem;
        color: #e5eef7;
        background:
            radial-gradient(circle at top left, rgba(16, 185, 129, 0.12), transparent 28%),
            radial-gradient(circle at top right, rgba(56, 189, 248, 0.14), transparent 24%),
            linear-gradient(180deg, rgba(7, 15, 28, 0.98), rgba(9, 18, 32, 0.92));
    }
    .panel {
        border: 1px solid rgba(148, 163, 184, 0.16);
        background: linear-gradient(180deg, rgba(15, 23, 42, 0.88), rgba(10, 17, 31, 0.92));
        box-shadow: 0 24px 60px rgba(2, 6, 23, 0.24);
        border-radius: 1.4rem;
        padding: 1.2rem;
    }
    .panel-title-row {
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        gap: 1rem;
    }
    .panel-kicker {
        text-transform: uppercase;
        letter-spacing: 0.08em;
        font-size: 0.72rem;
        color: #94a3b8;
    }
    .market-toolbar { display: flex; gap: 0.55rem; align-items: center; flex-wrap: wrap; }
    .symbol-input { display: inline-flex; align-items: center; gap: 0.35rem; border: 1px solid rgba(148,163,184,0.18); border-radius: 999px; padding: 0.45rem 0.75rem; background: rgba(255,255,255,0.04); color: #cbd5e1; }
    .symbol-input input { border: 0; outline: none; background: transparent; color: #e2e8f0; width: 10rem; }
    .ghost-btn { display: inline-flex; align-items: center; gap: 0.45rem; border-radius: 999px; border: 1px solid rgba(148,163,184,0.18); background: rgba(255,255,255,0.04); color: #e2e8f0; padding: 0.6rem 0.9rem; cursor: pointer; }
    .ghost-btn:disabled { opacity: 0.6; cursor: wait; }
    .market-grid { margin-top: 1rem; display: grid; gap: 0.75rem; grid-template-columns: repeat(3, minmax(0, 1fr)); }
    .market-card { border-radius: 1rem; border: 1px solid rgba(148,163,184,0.14); background: rgba(255,255,255,0.03); padding: 0.9rem; }
    .market-head { display: flex; justify-content: space-between; gap: 0.5rem; align-items: center; margin-bottom: 0.25rem; }
    .market-head strong { color: #f8fafc; }
    .market-head span { font-size: 0.82rem; }
    .market-price { color: #e2e8f0; font-size: 1.15rem; font-weight: 600; }
    .sparkline { width: 100%; height: 3.8rem; margin-top: 0.55rem; opacity: 0.9; }
    .empty-panel { margin-top: 1rem; padding: 1rem; color: #94a3b8; border-radius: 1rem; border: 1px solid rgba(148,163,184,0.14); background: rgba(255,255,255,0.03); }
    .warning-panel { margin-top: 1rem; padding: 1rem; color: #fde68a; border-radius: 1rem; border: 1px solid rgba(250,204,21,0.28); background: rgba(250,204,21,0.08); }
    .muted { color: #94a3b8; margin-top: 0.8rem; font-size: 0.84rem; }
    .positive { color: #86efac; }
    .negative { color: #fda4af; }
    .spin { animation: spin 0.9s linear infinite; }
    @media (max-width: 1100px) { .market-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
    @media (max-width: 760px) { .market-shell { padding: 1rem; } .panel-title-row { flex-direction: column; align-items: flex-start; } .market-grid { grid-template-columns: 1fr; } }
    @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
</style>
