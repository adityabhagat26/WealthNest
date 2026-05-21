<script lang="ts">
    import {onMount} from 'svelte';
    import {page} from '$app/stores';
    import AnimatedBackground from '$lib/components/ui/AnimatedBackground.svelte';
    import ThemeToggle from '$lib/components/ui/ThemeToggle.svelte';
    import LanguageSelector from '$lib/components/layout/LanguageSelector.svelte';
    import {axiosInstance} from '$lib/api';
    import {AlertCircle, Clock3, LockKeyhole, Mail, ShieldCheck} from 'lucide-svelte';
    import {isAxiosError} from 'axios';

    type ThresholdUnit = 'days' | 'hours' | 'minutes' | 'seconds';

    type NomineeAccessData = {
        account_holder_username: string;
        nominee_email: string;
        access_scope: 'read_only';
        expires_at: string;
        last_activity_at: string | null;
        nominee_threshold_days: number;
        nominee_threshold_unit: ThresholdUnit;
        broker_count: number;
        broker_names: string[];
        banking_details: {
            broker_id: number;
            broker_name: string;
            cash_balances: {
                currency: string;
                amount: string;
            }[];
        }[];
        account_cash_totals: {
            currency: string;
            amount: string;
        }[];
        asset_holdings: {
            broker_id: number;
            broker_name: string;
            asset_id: number;
            asset_name: string;
            quantity: string;
            asset_currency: string;
        }[];
    };

    let loading = true;
    let error: string | null = null;
    let data: NomineeAccessData | null = null;

    const copy = {
        title: 'Nominee Access',
        subtitle: 'This secure link provides limited read-only access for nominee review.',
        invalidLink: 'This nominee access link is invalid or has expired.',
        missingToken: 'This nominee access link is incomplete.',
        accountHolder: 'Account holder',
        nomineeEmail: 'Nominee email',
        accessScope: 'Access scope',
        expiry: 'Link expires',
        lastActivity: 'Last activity',
        configuredThreshold: 'Configured inactivity threshold',
        visibleBrokers: 'Visible brokers',
        bankingDetails: 'Banking details',
        assetHoldings: 'Asset holdings',
        noBanking: 'No banking balances are currently available.',
        allAccountCash: 'All accounts cash totals',
        noAssets: 'No asset holdings are currently available.',
        noActivity: 'Not available',
        readOnly: 'Read-only nominee access',
        backToLogin: 'Open main login'
    };

    onMount(async () => {
        const token = $page.url.searchParams.get('token');
        if (!token) {
            error = copy.missingToken;
            loading = false;
            return;
        }

        try {
            const response = await axiosInstance.get<NomineeAccessData>('/api/v1/nominee/access', {
                params: {token}
            });
            data = response.data;
        } catch (err) {
            if (isAxiosError(err) && err.response?.status === 401) {
                error = copy.invalidLink;
            } else {
                error = 'Unable to load nominee access right now.';
            }
        } finally {
            loading = false;
        }
    });

    function formatDateTime(value: string | null): string {
        if (!value) return copy.noActivity;
        return new Intl.DateTimeFormat(undefined, {
            dateStyle: 'medium',
            timeStyle: 'short'
        }).format(new Date(value));
    }

    function formatThreshold(value: number, unit: ThresholdUnit): string {
        if (value === 1 && unit.endsWith('s')) {
            return `${value} ${unit.slice(0, -1)}`;
        }
        return `${value} ${unit}`;
    }
</script>

<AnimatedBackground/>

<div class="min-h-screen flex items-center justify-center p-4" data-testid="nominee-access-page">
    <div class="fixed top-4 right-4 z-50 flex items-center space-x-2">
        <LanguageSelector/>
        <ThemeToggle/>
    </div>

    <div class="w-full max-w-4xl rounded-[32px] border border-slate-700 bg-slate-950/90 shadow-2xl backdrop-blur">
        <div class="border-b border-slate-800 px-6 py-6 sm:px-8">
            <div class="flex items-start gap-4">
                <div class="rounded-2xl bg-emerald-500/10 p-3 text-emerald-300">
                    <ShieldCheck size={28}/>
                </div>
                <div>
                    <h1 class="text-3xl font-semibold text-white">{copy.title}</h1>
                    <p class="mt-2 max-w-2xl text-sm leading-7 text-slate-300">{copy.subtitle}</p>
                </div>
            </div>
        </div>

        <div class="px-6 py-6 sm:px-8">
            {#if loading}
                <div class="rounded-2xl border border-slate-700 bg-slate-900 px-5 py-10 text-center text-slate-300">
                    Loading nominee access...
                </div>
            {:else if error}
                <div class="rounded-2xl border border-red-400/30 bg-red-500/10 px-5 py-6 text-red-100">
                    <div class="flex items-center gap-3 text-base font-medium">
                        <AlertCircle size={18}/>
                        {error}
                    </div>
                    <a href="/" class="mt-4 inline-flex items-center rounded-xl bg-white/10 px-4 py-2 text-sm font-medium text-white transition hover:bg-white/15">
                        {copy.backToLogin}
                    </a>
                </div>
            {:else if data}
                <div class="space-y-6">
                    <div class="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                        <div class="rounded-2xl border border-slate-700 bg-slate-900 px-4 py-4">
                            <div class="text-xs font-semibold uppercase tracking-wide text-slate-400">{copy.accountHolder}</div>
                            <div class="mt-2 text-lg font-semibold text-white">{data.account_holder_username}</div>
                        </div>

                        <div class="rounded-2xl border border-slate-700 bg-slate-900 px-4 py-4">
                            <div class="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
                                <Mail size={14}/>
                                {copy.nomineeEmail}
                            </div>
                            <div class="mt-2 break-all text-sm font-medium text-white">{data.nominee_email}</div>
                        </div>

                        <div class="rounded-2xl border border-slate-700 bg-slate-900 px-4 py-4">
                            <div class="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
                                <LockKeyhole size={14}/>
                                {copy.accessScope}
                            </div>
                            <div class="mt-2 text-sm font-medium text-white">{copy.readOnly}</div>
                        </div>

                        <div class="rounded-2xl border border-slate-700 bg-slate-900 px-4 py-4">
                            <div class="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
                                <Clock3 size={14}/>
                                {copy.expiry}
                            </div>
                            <div class="mt-2 text-sm font-medium text-white">{formatDateTime(data.expires_at)}</div>
                        </div>
                    </div>

                    <div class="grid gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
                        <div class="rounded-3xl border border-slate-700 bg-slate-900 p-5">
                            <h2 class="text-lg font-semibold text-white">Visible account summary</h2>
                            <div class="mt-4 grid gap-4 md:grid-cols-2">
                                <div class="rounded-2xl border border-slate-800 bg-slate-950 px-4 py-4">
                                    <div class="text-xs font-semibold uppercase tracking-wide text-slate-500">{copy.lastActivity}</div>
                                    <div class="mt-2 text-sm font-medium text-white">{formatDateTime(data.last_activity_at)}</div>
                                </div>

                                <div class="rounded-2xl border border-slate-800 bg-slate-950 px-4 py-4">
                                    <div class="text-xs font-semibold uppercase tracking-wide text-slate-500">{copy.configuredThreshold}</div>
                                    <div class="mt-2 text-sm font-medium text-white">
                                        {formatThreshold(data.nominee_threshold_days, data.nominee_threshold_unit)}
                                    </div>
                                </div>
                            </div>

                            <div class="mt-5 rounded-2xl border border-emerald-500/20 bg-emerald-500/10 px-4 py-4 text-sm leading-7 text-emerald-50">
                                This nominee view is intentionally limited. It does not allow changes to the account, settings, or portfolio data.
                            </div>
                        </div>

                        <div class="rounded-3xl border border-slate-700 bg-slate-900 p-5">
                            <h2 class="text-lg font-semibold text-white">{copy.visibleBrokers}</h2>
                            <div class="mt-2 text-sm text-slate-300">
                                {data.broker_count} broker{data.broker_count === 1 ? '' : 's'} available in this summary.
                            </div>

                            {#if data.broker_names.length > 0}
                                <div class="mt-4 flex flex-wrap gap-2">
                                    {#each data.broker_names as brokerName}
                                        <span class="rounded-full border border-slate-700 bg-slate-950 px-3 py-1 text-sm text-slate-100">
                                            {brokerName}
                                        </span>
                                    {/each}
                                </div>
                            {:else}
                                <div class="mt-4 rounded-2xl border border-dashed border-slate-700 px-4 py-5 text-sm text-slate-400">
                                    No broker summaries are currently available for this account.
                                </div>
                            {/if}
                        </div>
                    </div>

                    <div class="grid gap-4 lg:grid-cols-2">
                        <div class="rounded-3xl border border-slate-700 bg-slate-900 p-5">
                            <h2 class="text-lg font-semibold text-white">{copy.allAccountCash}</h2>
                            {#if data.account_cash_totals.length > 0}
                                <div class="mt-3 flex flex-wrap gap-2">
                                    {#each data.account_cash_totals as total}
                                        <span class="rounded-full border border-emerald-500/30 bg-emerald-500/10 px-3 py-1 text-xs text-emerald-100">
                                            {total.currency}: {total.amount}
                                        </span>
                                    {/each}
                                </div>
                            {/if}

                            <h2 class="text-lg font-semibold text-white">{copy.bankingDetails}</h2>
                            {#if data.banking_details.length > 0}
                                <div class="mt-4 space-y-3">
                                    {#each data.banking_details as bank}
                                        <div class="rounded-2xl border border-slate-800 bg-slate-950 px-4 py-3">
                                            <div class="text-sm font-semibold text-white">{bank.broker_name}</div>
                                            {#if bank.cash_balances.length > 0}
                                                <div class="mt-2 flex flex-wrap gap-2">
                                                    {#each bank.cash_balances as cash}
                                                        <span class="rounded-full border border-slate-700 bg-slate-900 px-3 py-1 text-xs text-slate-100">
                                                            {cash.currency}: {cash.amount}
                                                        </span>
                                                    {/each}
                                                </div>
                                            {:else}
                                                <div class="mt-2 text-sm text-slate-400">No cash balances</div>
                                            {/if}
                                        </div>
                                    {/each}
                                </div>
                            {:else}
                                <div class="mt-4 rounded-2xl border border-dashed border-slate-700 px-4 py-5 text-sm text-slate-400">
                                    {copy.noBanking}
                                </div>
                            {/if}
                        </div>

                        <div class="rounded-3xl border border-slate-700 bg-slate-900 p-5">
                            <h2 class="text-lg font-semibold text-white">{copy.assetHoldings}</h2>
                            {#if data.asset_holdings.length > 0}
                                <div class="mt-4 max-h-64 space-y-3 overflow-auto pr-1">
                                    {#each data.asset_holdings as holding}
                                        <div class="rounded-2xl border border-slate-800 bg-slate-950 px-4 py-3">
                                            <div class="text-sm font-semibold text-white">{holding.asset_name}</div>
                                            <div class="mt-1 text-xs text-slate-400">{holding.broker_name}</div>
                                            <div class="mt-2 text-sm text-slate-100">
                                                {holding.quantity} {holding.asset_currency}
                                            </div>
                                        </div>
                                    {/each}
                                </div>
                            {:else}
                                <div class="mt-4 rounded-2xl border border-dashed border-slate-700 px-4 py-5 text-sm text-slate-400">
                                    {copy.noAssets}
                                </div>
                            {/if}
                        </div>
                    </div>
                </div>
            {/if}
        </div>
    </div>
</div>
