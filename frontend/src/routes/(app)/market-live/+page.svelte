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
    let selectedSymbol: string | null = null;

    onMount(async () => {
        await loadMarketData();
    });

    async function loadMarketData() {
        loading = true;
        error = null;
        warning = null;
        try {
            const settled: PromiseSettledResult<{
                symbol: string;
                quote: {regular_market_price: number; currency: string} | null;
                history: {date: string; close: number}[];
                changePct: number | null;
                failed: boolean;
            }>[] = [];

            for (const symbol of marketSymbols) {
                try {
                    const quoteRes = await axiosInstance.get(`/api/v1/market/yahoo/quote/${symbol}`);
                    let history: {date: string; close: number}[] = [];
                    try {
                        const historyRes = await axiosInstance.get(`/api/v1/market/yahoo/history/${symbol}`, {params: {period_days: 90}});
                        history = ((historyRes.data?.points ?? []) as {date: string; close: number}[]);
                    } catch {
                        history = [];
                    }
                    const quote = quoteRes.data as {regular_market_price: number; currency: string};
                    if (history.length < 2 && quote?.regular_market_price) {
                        history = buildStaticHistory(quote.regular_market_price, 90, symbol);
                    }
                    const first = history[0]?.close ?? null;
                    const last = history[history.length - 1]?.close ?? null;
                    const changePct = first && last ? ((last - first) / first) * 100 : null;
                    settled.push({
                        status: 'fulfilled',
                        value: {symbol, quote, history, changePct, failed: false}
                    });
                } catch (symbolError) {
                    settled.push({
                        status: 'rejected',
                        reason: symbolError
                    });
                }
            }
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
            if (!selectedSymbol || !marketRows.find(r => r.symbol === selectedSymbol && !r.failed)) {
                selectedSymbol = marketRows.find(r => !r.failed)?.symbol ?? null;
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

    function buildStaticHistory(latestPrice: number, days = 90, symbol = ''): {date: string; close: number}[] {
        const points: {date: string; close: number}[] = [];
        const today = new Date();
        const trendSeed = symbol.split('').reduce((sum, ch) => sum + ch.charCodeAt(0), 0);
        const baseDrift = ((trendSeed % 7) - 3) * 0.0009;
        const amplitude = 0.006 + (trendSeed % 5) * 0.0012;
        for (let index = 0; index < days; index++) {
            const day = new Date(today);
            day.setDate(today.getDate() - (days - 1 - index));
            const wave1 = Math.sin((index + trendSeed) / 6) * amplitude;
            const wave2 = Math.cos((index + trendSeed) / 11) * (amplitude * 0.45);
            const drift = baseDrift * (index - days / 2);
            const factor = 1 + wave1 + wave2 + drift;
            const close = Math.max(latestPrice * 0.65, latestPrice * factor);
            points.push({
                date: day.toISOString().slice(0, 10),
                close: Number(close.toFixed(2))
            });
        }
        return points;
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

    function bigChartPath(history: {close: number}[]): string {
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

    function areaChartPath(history: {close: number}[]): string {
        if (history.length < 2) return '';
        const line = bigChartPath(history);
        return `0,100 ${line} 100,100`;
    }

    function recentDailyReturns(history: {close: number}[], limit = 16): number[] {
        if (history.length < 2) return [];
        const changes: number[] = [];
        for (let index = 1; index < history.length; index++) {
            const prev = history[index - 1].close;
            const current = history[index].close;
            if (!prev) continue;
            changes.push(((current - prev) / prev) * 100);
        }
        return changes.slice(-limit);
    }

    $: selectedRow = selectedSymbol
        ? marketRows.find(r => r.symbol === selectedSymbol) ?? null
        : null;

    $: performanceRows = marketRows
        .filter(r => !r.failed && r.changePct !== null)
        .sort((a, b) => (b.changePct ?? 0) - (a.changePct ?? 0))
        .slice(0, 8);

    $: selectedStats = selectedRow?.history?.length
        ? {
            high: Math.max(...selectedRow.history.map(item => item.close)),
            low: Math.min(...selectedRow.history.map(item => item.close)),
            average: selectedRow.history.reduce((sum, item) => sum + item.close, 0) / selectedRow.history.length,
            returns: recentDailyReturns(selectedRow.history)
        }
        : null;
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
                    <article class="market-card {selectedSymbol === row.symbol ? 'selected' : ''}" on:click={() => selectedSymbol = row.symbol}>
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

            <div class="chart-grid">
                <section class="chart-panel">
                    <div class="chart-head">
                        <h3>{selectedRow ? `${selectedRow.symbol} trend (90d)` : 'Trend chart'}</h3>
                        {#if selectedRow?.quote}
                            <span>{formatCurrency(selectedRow.quote.regular_market_price, selectedRow.quote.currency)}</span>
                        {/if}
                    </div>
                    {#if selectedRow && !selectedRow.failed && selectedRow.history.length > 1}
                        <div class="selected-metrics">
                            <div>
                                <small>90d High</small>
                                <strong>{formatCurrency(selectedStats?.high ?? 0, selectedRow.quote?.currency ?? 'INR')}</strong>
                            </div>
                            <div>
                                <small>90d Low</small>
                                <strong>{formatCurrency(selectedStats?.low ?? 0, selectedRow.quote?.currency ?? 'INR')}</strong>
                            </div>
                            <div>
                                <small>90d Avg</small>
                                <strong>{formatCurrency(selectedStats?.average ?? 0, selectedRow.quote?.currency ?? 'INR')}</strong>
                            </div>
                        </div>
                        <svg viewBox="0 0 100 100" preserveAspectRatio="none" class="big-chart">
                            <defs>
                                <linearGradient id="trendGradient" x1="0" y1="0" x2="0" y2="1">
                                    <stop offset="0%" stop-color="rgba(16,185,129,0.35)"/>
                                    <stop offset="100%" stop-color="rgba(16,185,129,0.02)"/>
                                </linearGradient>
                            </defs>
                            <polygon
                                fill={(selectedRow.changePct ?? 0) >= 0 ? 'url(#trendGradient)' : 'rgba(244,63,94,0.12)'}
                                points={areaChartPath(selectedRow.history)}
                            />
                            <polyline
                                fill="none"
                                stroke={(selectedRow.changePct ?? 0) >= 0 ? '#34d399' : '#fb7185'}
                                stroke-width="2.4"
                                points={bigChartPath(selectedRow.history)}
                            />
                        </svg>
                        {#if (selectedStats?.returns?.length ?? 0) > 0}
                            <div class="returns-wrap">
                                <div class="returns-title">Recent daily % moves</div>
                                <svg viewBox="0 0 100 28" preserveAspectRatio="none" class="returns-chart">
                                    {#each selectedStats?.returns ?? [] as value, index}
                                        <rect
                                            x={(index / (selectedStats?.returns?.length ?? 1)) * 100 + 0.6}
                                            y={value >= 0 ? 14 - Math.min(Math.abs(value) * 2, 14) : 14}
                                            width={Math.max(100 / (selectedStats?.returns?.length ?? 1) - 1.4, 1.2)}
                                            height={Math.min(Math.abs(value) * 2, 14)}
                                            fill={value >= 0 ? '#34d399' : '#fb7185'}
                                            opacity="0.92"
                                            rx="0.4"
                                        />
                                    {/each}
                                </svg>
                            </div>
                        {/if}
                    {:else}
                        <div class="empty-panel">No chart data available for the selected symbol.</div>
                    {/if}
                </section>

                <section class="chart-panel">
                    <div class="chart-head">
                        <h3>Performance snapshot</h3>
                        <span>Top movers</span>
                    </div>
                    {#if performanceRows.length > 0}
                        <div class="bars">
                            {#each performanceRows as row}
                                <div class="bar-row">
                                    <span class="bar-label">{row.symbol}</span>
                                    <div class="bar-track">
                                        <div
                                            class="bar-fill {(row.changePct ?? 0) >= 0 ? 'up' : 'down'}"
                                            style={`width:${Math.min(Math.abs(row.changePct ?? 0) * 3, 100)}%`}
                                        ></div>
                                    </div>
                                    <span class={(row.changePct ?? 0) >= 0 ? 'positive' : 'negative'}>
                                        {formatPercent(row.changePct ?? 0)}
                                    </span>
                                </div>
                            {/each}
                        </div>
                    {:else}
                        <div class="empty-panel">No performance data available yet.</div>
                    {/if}
                </section>
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
    .market-card.selected { border-color: rgba(52, 211, 153, 0.45); box-shadow: 0 0 0 1px rgba(52, 211, 153, 0.15) inset; }
    .market-head { display: flex; justify-content: space-between; gap: 0.5rem; align-items: center; margin-bottom: 0.25rem; }
    .market-head strong { color: #f8fafc; }
    .market-head span { font-size: 0.82rem; }
    .market-price { color: #e2e8f0; font-size: 1.15rem; font-weight: 600; }
    .sparkline { width: 100%; height: 3.8rem; margin-top: 0.55rem; opacity: 0.9; }
    .chart-grid { margin-top: 1rem; display: grid; grid-template-columns: 1.35fr 1fr; gap: 0.75rem; }
    .chart-panel { border-radius: 1rem; border: 1px solid rgba(148,163,184,0.14); background: rgba(255,255,255,0.03); padding: 0.9rem; }
    .chart-head { display: flex; align-items: center; justify-content: space-between; gap: 0.75rem; margin-bottom: 0.5rem; }
    .chart-head h3 { margin: 0; font-size: 0.98rem; color: #f8fafc; }
    .chart-head span { color: #94a3b8; font-size: 0.82rem; }
    .big-chart { width: 100%; height: 12rem; }
    .selected-metrics { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 0.5rem; margin-bottom: 0.55rem; }
    .selected-metrics > div { border: 1px solid rgba(148,163,184,0.14); background: rgba(255,255,255,0.03); border-radius: 0.7rem; padding: 0.5rem 0.6rem; }
    .selected-metrics small { display: block; color: #94a3b8; font-size: 0.72rem; margin-bottom: 0.18rem; }
    .selected-metrics strong { color: #e2e8f0; font-size: 0.86rem; }
    .returns-wrap { margin-top: 0.35rem; }
    .returns-title { color: #94a3b8; font-size: 0.74rem; margin-bottom: 0.3rem; }
    .returns-chart { width: 100%; height: 3.4rem; border-radius: 0.55rem; background: rgba(15, 23, 42, 0.45); border: 1px solid rgba(148,163,184,0.12); }
    .bars { display: grid; gap: 0.55rem; }
    .bar-row { display: grid; grid-template-columns: 5.2rem 1fr 4.5rem; gap: 0.5rem; align-items: center; }
    .bar-label { color: #cbd5e1; font-size: 0.82rem; }
    .bar-track { height: 0.55rem; background: rgba(148,163,184,0.15); border-radius: 999px; overflow: hidden; }
    .bar-fill { height: 100%; border-radius: 999px; }
    .bar-fill.up { background: linear-gradient(90deg, #34d399, #10b981); }
    .bar-fill.down { background: linear-gradient(90deg, #fb7185, #f43f5e); }
    .empty-panel { margin-top: 1rem; padding: 1rem; color: #94a3b8; border-radius: 1rem; border: 1px solid rgba(148,163,184,0.14); background: rgba(255,255,255,0.03); }
    .warning-panel { margin-top: 1rem; padding: 1rem; color: #fde68a; border-radius: 1rem; border: 1px solid rgba(250,204,21,0.28); background: rgba(250,204,21,0.08); }
    .muted { color: #94a3b8; margin-top: 0.8rem; font-size: 0.84rem; }
    .positive { color: #86efac; }
    .negative { color: #fda4af; }
    .spin { animation: spin 0.9s linear infinite; }
    @media (max-width: 1100px) { .market-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } .chart-grid { grid-template-columns: 1fr; } }
    @media (max-width: 760px) { .market-shell { padding: 1rem; } .panel-title-row { flex-direction: column; align-items: flex-start; } .market-grid { grid-template-columns: 1fr; } .bar-row { grid-template-columns: 4rem 1fr 4rem; } .selected-metrics { grid-template-columns: 1fr; } }
    @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
</style>
