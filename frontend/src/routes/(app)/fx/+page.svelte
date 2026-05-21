<script lang="ts">
    import {onMount} from 'svelte';
    import {_} from '$lib/i18n';
    import {Coins, RefreshCw} from 'lucide-svelte';
    import type {Broker, BrokerSummary} from '$lib/types';
    import {parseCurrencyAmount, safeCurrency} from '$lib/types';

    type FxProvider = {
        code: string;
        name: string;
    };

    type AssetConversionResult = {
        brokerName: string;
        assetName: string;
        originalCode: string;
        originalAmount: string;
        convertedCode: string;
        convertedAmount: string;
    };

    let providers: FxProvider[] = [];
    let loadingProviders = false;
    let syncing = false;
    let convertingAssets = false;
    let errorMsg: string | null = null;
    let successMsg: string | null = null;

    let syncProvider = 'ECB';
    let syncCurrencies = 'USD,EUR,GBP,INR';
    let syncStart = new Date(Date.now() - 7 * 86400000).toISOString().slice(0, 10);
    let syncEnd = new Date().toISOString().slice(0, 10);

    let targetCurrency = 'INR';
    let conversionDate = new Date().toISOString().slice(0, 10);
    let assetConversionResults: AssetConversionResult[] = [];
    let noAssetsMessage = false;

    onMount(async () => {
        await loadProviders();
    });

    async function loadProviders() {
        loadingProviders = true;
        errorMsg = null;
        try {
            const res = await fetch('/api/v1/fx/providers');
            if (!res.ok) throw new Error(await res.text());
            providers = (await res.json()) as FxProvider[];
            if (providers.length > 0 && !providers.find((p) => p.code === syncProvider)) {
                syncProvider = providers[0].code;
            }
        } catch (e) {
            errorMsg = e instanceof Error ? e.message : 'Failed to load FX providers';
        } finally {
            loadingProviders = false;
        }
    }

    async function syncRates() {
        syncing = true;
        errorMsg = null;
        successMsg = null;
        try {
            const query = new URLSearchParams({
                start: syncStart,
                end: syncEnd,
                currencies: syncCurrencies,
                provider: syncProvider
            });
            const res = await fetch(`/api/v1/fx/currencies/sync?${query.toString()}`);
            if (!res.ok) throw new Error(await res.text());
            const data = await res.json();
            successMsg = `Synced ${data.synced ?? 0} FX rows for ${syncCurrencies} (${syncStart} → ${syncEnd}).`;
        } catch (e) {
            errorMsg = e instanceof Error ? e.message : 'FX sync failed';
        } finally {
            syncing = false;
        }
    }

    async function convertAssetsNow() {
        convertingAssets = true;
        errorMsg = null;
        successMsg = null;
        noAssetsMessage = false;
        assetConversionResults = [];
        try {
            const brokersRes = await fetch('/api/v1/brokers');
            if (!brokersRes.ok) throw new Error(await brokersRes.text());
            const brokers = (await brokersRes.json()) as Broker[];

            const summaries = (await Promise.all(
                brokers.map(async (broker) => {
                    try {
                        const res = await fetch(`/api/v1/brokers/${broker.id}/summary`);
                        if (!res.ok) return null;
                        return (await res.json()) as BrokerSummary;
                    } catch {
                        return null;
                    }
                })
            )).filter((item): item is BrokerSummary => item !== null);

            const assetsToConvert: Array<{ brokerName: string; assetName: string; code: string; amount: string }> = [];
            for (const summary of summaries) {
                for (const holding of summary.holdings ?? []) {
                    const currentValue = safeCurrency(holding.current_value);
                    const fallbackCost = safeCurrency(holding.total_cost);
                    const sourceValue = currentValue ?? fallbackCost;
                    if (!sourceValue) continue;
                    assetsToConvert.push({
                        brokerName: summary.name,
                        assetName: holding.asset_name,
                        code: sourceValue.code,
                        amount: String(sourceValue.amount)
                    });
                }
            }

            if (assetsToConvert.length === 0) {
                noAssetsMessage = true;
                return;
            }

            const body = assetsToConvert.map((item) => ({
                from_amount: { code: item.code, amount: item.amount },
                to_currency: targetCurrency.trim().toUpperCase(),
                date_range: { start: conversionDate }
            }));

            const res = await fetch('/api/v1/fx/currencies/convert', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            });
            if (!res.ok) throw new Error(await res.text());
            const data = await res.json();
            const results = data.results ?? [];

            if (results.length === 0) {
                errorMsg = 'No conversion result returned. Sync FX rates first.';
                return;
            }

            assetConversionResults = results.map((row: any, idx: number) => ({
                brokerName: assetsToConvert[idx]?.brokerName ?? '-',
                assetName: assetsToConvert[idx]?.assetName ?? '-',
                originalCode: row.from_amount?.code ?? assetsToConvert[idx]?.code ?? '-',
                originalAmount: String(row.from_amount?.amount ?? assetsToConvert[idx]?.amount ?? '0'),
                convertedCode: row.to_amount?.code ?? targetCurrency.toUpperCase(),
                convertedAmount: String(row.to_amount?.amount ?? '0')
            }));
        } catch (e) {
            errorMsg = e instanceof Error ? e.message : 'Asset conversion failed';
        } finally {
            convertingAssets = false;
        }
    }
</script>

<div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
        <div>
            <h2 class="text-lg font-semibold text-gray-700">{$_('fx.title')}</h2>
            <p class="text-gray-500 text-sm">{$_('fx.subtitle')}</p>
        </div>
        <button
                class="flex items-center space-x-2 px-4 py-2 bg-libre-green text-white rounded-lg hover:bg-libre-green/90 transition-all disabled:opacity-50"
                on:click={loadProviders}
                disabled={loadingProviders}
        >
            <RefreshCw size={18}/>
            <span>{loadingProviders ? 'Loading...' : 'Reload Providers'}</span>
        </button>
    </div>

    {#if errorMsg}
        <div class="p-3 rounded-lg border border-red-200 bg-red-50 text-red-700 text-sm">{errorMsg}</div>
    {/if}
    {#if successMsg}
        <div class="p-3 rounded-lg border border-emerald-200 bg-emerald-50 text-emerald-700 text-sm">{successMsg}</div>
    {/if}

    <!-- FX Sync -->
    <div class="bg-white rounded-xl shadow-sm p-5 border border-gray-100">
        <div class="flex items-center gap-2 mb-4">
            <Coins class="text-amber-600" size={20}/>
            <h3 class="font-semibold text-gray-700">FX Rate Sync</h3>
        </div>
        <div class="grid grid-cols-1 md:grid-cols-4 gap-3">
            <input class="border rounded-lg px-3 py-2" bind:value={syncStart} type="date"/>
            <input class="border rounded-lg px-3 py-2" bind:value={syncEnd} type="date"/>
            <input class="border rounded-lg px-3 py-2" bind:value={syncCurrencies} placeholder="USD,EUR,GBP,INR"/>
            <select class="border rounded-lg px-3 py-2" bind:value={syncProvider}>
                {#each providers as p}
                    <option value={p.code}>{p.code} - {p.name}</option>
                {/each}
            </select>
        </div>
        <div class="mt-4">
            <button
                    class="px-4 py-2 bg-libre-green text-white rounded-lg hover:bg-libre-green/90 disabled:opacity-50"
                    on:click={syncRates}
                    disabled={syncing}
            >
                {syncing ? 'Syncing...' : 'Sync FX Rates'}
            </button>
        </div>
    </div>

    <!-- Asset FX Conversion -->
    <div class="bg-white rounded-xl shadow-sm p-5 border border-gray-100">
        <div class="flex items-center gap-2 mb-4">
            <Coins class="text-libre-green" size={20}/>
            <h3 class="font-semibold text-gray-700">Convert My Assets</h3>
        </div>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
            <input class="border rounded-lg px-3 py-2" bind:value={targetCurrency} placeholder="Target currency (INR)"/>
            <input class="border rounded-lg px-3 py-2" bind:value={conversionDate} type="date"/>
        </div>
        <div class="mt-4">
            <button
                    class="px-4 py-2 bg-gray-800 text-white rounded-lg hover:bg-gray-900 disabled:opacity-50"
                    on:click={convertAssetsNow}
                    disabled={convertingAssets}
            >
                {convertingAssets ? 'Converting...' : 'Convert Asset Values'}
            </button>
        </div>

        {#if noAssetsMessage}
            <div class="mt-4 p-3 rounded-lg bg-gray-50 border border-gray-200 text-sm text-gray-600">
                No asset added.
            </div>
        {/if}

        {#if assetConversionResults.length > 0}
            <div class="mt-4 p-3 rounded-lg bg-gray-50 border border-gray-200 text-sm">
                {#each assetConversionResults as row}
                    <div class="text-gray-700 mb-2">
                        <strong>{row.assetName}</strong> ({row.brokerName}) :
                        {new Intl.NumberFormat(undefined, { style: 'currency', currency: row.originalCode }).format(parseCurrencyAmount(row.originalAmount))}
                        →
                        <strong>
                            {new Intl.NumberFormat(undefined, { style: 'currency', currency: row.convertedCode }).format(parseCurrencyAmount(row.convertedAmount))}
                        </strong>
                    </div>
                {/each}
            </div>
        {/if}
    </div>
</div>

