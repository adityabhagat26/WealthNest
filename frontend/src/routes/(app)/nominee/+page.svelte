<script lang="ts">
    import {onMount} from 'svelte';
    import {_} from '$lib/i18n';
    import {zodiosApi} from '$lib/api';
    import {userSettings} from '$lib/stores/settings';
    import {
        AlertCircle,
        BellRing,
        CheckCircle2,
        Clock3,
        Mail,
        Save,
        Sparkles
    } from 'lucide-svelte';
    import type {UserSettings} from '$lib/types';

    type ThresholdUnit = 'days' | 'hours' | 'minutes' | 'seconds';

    const nomineeDefaults = {
        nominee_email: '',
        nominee_enabled: false,
        nominee_threshold_days: 30,
        nominee_threshold_unit: 'days' as ThresholdUnit,
        last_activity_at: null as string | null,
        nominee_last_notified_at: null as string | null
    };

    const unitOptions: Array<{value: ThresholdUnit; labelKey: string}> = [
        {value: 'days', labelKey: 'nominee.unitDays'},
        {value: 'hours', labelKey: 'nominee.unitHours'},
        {value: 'minutes', labelKey: 'nominee.unitMinutes'},
        {value: 'seconds', labelKey: 'nominee.unitSeconds'}
    ];

    const pageCopy = {
        title: 'Nominee',
        subtitle: 'Choose who should receive an automated WealthNest email if your account stays inactive for too long.',
        livePreview: 'Live trigger preview',
        notAvailable: 'Not available yet',
        lastActivityHint: 'The last time this account had authenticated activity.',
        currentStatus: 'Current status',
        alertsEnabled: 'Alerts enabled',
        alertsPaused: 'Alerts paused',
        contactTitle: 'Nominee contact',
        contactHint: 'Enter the email address that should receive an inactivity alert.',
        automationTitle: 'Automation',
        automationHint: 'Turn nominee alerts on when you want the backend to monitor inactivity and send mail automatically.',
        monitorState: 'Monitor state',
        activeState: 'Active and ready to send real alerts',
        inactiveState: 'Disabled until you switch it on',
        destination: 'Email destination',
        noEmail: 'No nominee email entered yet',
        timerTitle: 'Inactivity timer',
        timerHint: 'Choose how long WealthNest should wait before notifying your nominee.',
        thresholdValue: 'Threshold value',
        timeUnit: 'Time unit',
        triggerPreview: 'Trigger preview',
        saveFooter: 'Review the nominee email, enable the automation switch, and save to apply the real backend alert settings.'
    };

    let loading = true;
    let saving = false;
    let error: string | null = null;
    let success = false;
    let original = {...nomineeDefaults};
    let form = {...nomineeDefaults};

    onMount(async () => {
        await loadNomineeSettings();
    });

    function normalizeNullableString(value: unknown): string | null {
        return typeof value === 'string' && value.length > 0 ? value : null;
    }

    function hydrateNominee(settings: UserSettings) {
        original = {
            nominee_email: normalizeNullableString(settings.nominee_email) ?? '',
            nominee_enabled: settings.nominee_enabled ?? false,
            nominee_threshold_days: settings.nominee_threshold_days ?? 30,
            nominee_threshold_unit: settings.nominee_threshold_unit ?? 'days',
            last_activity_at: normalizeNullableString(settings.last_activity_at),
            nominee_last_notified_at: normalizeNullableString(settings.nominee_last_notified_at)
        };
        form = {...original};
    }

    async function loadNomineeSettings() {
        loading = true;
        error = null;

        try {
            const settings = await zodiosApi.get_user_settings_endpoint_api_v1_settings_user_get();
            hydrateNominee(settings);
        } catch (e) {
            console.error('Failed to load nominee settings:', e);
            error = 'Failed to load nominee settings';
        } finally {
            loading = false;
        }
    }

    function formatDateTime(value: string | null): string {
        if (!value) return pageCopy.notAvailable;

        return new Intl.DateTimeFormat(undefined, {
            dateStyle: 'medium',
            timeStyle: 'short'
        }).format(new Date(value));
    }

    function normalizeThresholdInput(event: Event) {
        const target = event.target as HTMLInputElement;
        const nextValue = Number.parseInt(target.value, 10);
        form.nominee_threshold_days = Number.isFinite(nextValue) && nextValue > 0 ? nextValue : 1;
    }

    function getUnitLabel(unit: ThresholdUnit): string {
        const option = unitOptions.find(item => item.value === unit);
        return option ? $_(option.labelKey) : unit;
    }

    function setThresholdUnit(unit: ThresholdUnit) {
        form.nominee_threshold_unit = unit;
    }

    $: modified =
        form.nominee_email !== original.nominee_email ||
        form.nominee_enabled !== original.nominee_enabled ||
        form.nominee_threshold_days !== original.nominee_threshold_days ||
        form.nominee_threshold_unit !== original.nominee_threshold_unit;

    $: canSave =
        modified &&
        (!form.nominee_enabled || form.nominee_email.trim().length > 0) &&
        form.nominee_threshold_days >= 1;

    $: thresholdPreview = `${form.nominee_threshold_days} ${getUnitLabel(form.nominee_threshold_unit).toLowerCase()}`;

    async function saveNomineeSettings() {
        saving = true;
        error = null;
        success = false;

        try {
            const updatedSettings = await zodiosApi.update_user_settings_endpoint_api_v1_settings_user_put({
                nominee_email: form.nominee_email.trim() || null,
                nominee_enabled: form.nominee_enabled,
                nominee_threshold_days: form.nominee_threshold_days,
                nominee_threshold_unit: form.nominee_threshold_unit
            });

            hydrateNominee(updatedSettings);
            userSettings.setDirect(updatedSettings);
            success = true;
            setTimeout(() => {
                success = false;
            }, 3000);
        } catch (e) {
            console.error('Failed to save nominee settings:', e);
            error = 'Failed to save nominee settings';
        } finally {
            saving = false;
        }
    }
</script>

<div class="space-y-6" data-testid="nominee-page">
    <div class="space-y-3">
        <div class="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
            <div class="max-w-3xl">
                <h1 class="flex items-center gap-3 text-3xl font-semibold text-white">
                    <BellRing size={26} class="text-emerald-400"/>
                    <span>{$_['nominee.title'] || pageCopy.title}</span>
                </h1>
                <p class="mt-2 text-sm leading-7 text-slate-300">
                    {$_['nominee.subtitle'] || pageCopy.subtitle}
                </p>
            </div>
            <div class="rounded-2xl border border-slate-700 bg-slate-900/80 px-4 py-3 text-sm text-slate-200 shadow-lg">
                <div class="text-xs font-semibold uppercase tracking-wide text-slate-400">{pageCopy.livePreview}</div>
                <div class="mt-1 flex items-center gap-2 text-lg font-semibold text-white">
                    <Sparkles size={18} class="text-emerald-400"/>
                    {thresholdPreview}
                </div>
            </div>
        </div>
    </div>

    <section class="rounded-3xl border border-slate-700 bg-gradient-to-br from-slate-900 via-slate-850 to-slate-900 shadow-2xl">
        <div class="grid gap-4 border-b border-slate-700 px-6 py-6 md:grid-cols-3">
            <div class="rounded-2xl border border-slate-700 bg-slate-800/80 px-4 py-4">
                <div class="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
                    <Clock3 size={14}/>
                    {$_['nominee.lastActivity']}
                </div>
                <div class="mt-2 text-lg font-semibold text-white">{formatDateTime(form.last_activity_at)}</div>
                <p class="mt-1 text-sm text-slate-300">{pageCopy.lastActivityHint}</p>
            </div>

            <div class="rounded-2xl border border-slate-700 bg-slate-800/80 px-4 py-4">
                <div class="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
                    <Mail size={14}/>
                    {$_['nominee.lastEmail']}
                </div>
                <div class="mt-2 text-lg font-semibold text-white">{formatDateTime(form.nominee_last_notified_at)}</div>
            </div>

            <div class="rounded-2xl border border-slate-700 bg-slate-800/80 px-4 py-4">
                <div class="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
                    <CheckCircle2 size={14}/>
                    {pageCopy.currentStatus}
                </div>
                <div class="mt-2 text-lg font-semibold text-white">
                    {form.nominee_enabled ? pageCopy.alertsEnabled : pageCopy.alertsPaused}
                </div>
                <p class="mt-1 text-sm text-slate-300">
                    {form.nominee_enabled
                        ? `Your nominee will be notified after ${thresholdPreview} of inactivity.`
                        : 'Enable the switch below when you are ready to send real alerts.'}
                </p>
            </div>
        </div>

        <div class="space-y-6 px-6 py-6">
            {#if loading}
                <div class="rounded-2xl border border-dashed border-slate-600 bg-slate-800 px-5 py-8 text-sm text-slate-300">
                    {$_['nominee.loading']}
                </div>
            {:else}
                <div class="grid gap-6 xl:grid-cols-[minmax(0,1.25fr)_minmax(320px,0.85fr)]">
                    <div class="space-y-6">
                        <div class="rounded-2xl border border-slate-700 bg-slate-800/90 p-5 shadow-lg">
                            <div class="mb-4">
                                <h2 class="text-lg font-semibold text-white">{pageCopy.contactTitle}</h2>
                                <p class="mt-1 text-sm text-slate-300">
                                    {pageCopy.contactHint}
                                </p>
                            </div>

                            <label class="block">
                                <span class="mb-2 flex items-center gap-2 text-sm font-medium text-slate-100">
                                    <Mail size={16} class="text-emerald-400"/>
                                    {$_['nominee.emailLabel']}
                                </span>
                                <input
                                    bind:value={form.nominee_email}
                                    type="email"
                                    placeholder="nominee@gmail.com"
                                    class="w-full rounded-xl border border-slate-600 bg-slate-900 px-4 py-3 text-sm text-white shadow-sm outline-none transition placeholder:text-slate-400 focus:border-emerald-500 focus:ring-2 focus:ring-emerald-300"
                                />
                            </label>
                        </div>

                        <div class="rounded-2xl border border-slate-700 bg-slate-800/90 p-5 shadow-lg">
                            <div class="flex items-start justify-between gap-4">
                                <div>
                                    <h2 class="text-lg font-semibold text-white">{pageCopy.automationTitle}</h2>
                                    <p class="mt-1 text-sm text-slate-300">
                                        {pageCopy.automationHint}
                                    </p>
                                </div>
                                <label class="relative inline-flex cursor-pointer items-center self-center">
                                    <input bind:checked={form.nominee_enabled} class="peer sr-only" type="checkbox"/>
                                    <div class="peer h-8 w-14 rounded-full bg-slate-600 transition after:absolute after:left-[4px] after:top-[4px] after:h-6 after:w-6 after:rounded-full after:bg-white after:transition-all after:content-[''] peer-checked:bg-emerald-500 peer-checked:after:translate-x-6"></div>
                                </label>
                            </div>

                            <div class="mt-4 grid gap-3 sm:grid-cols-2">
                                <div class="rounded-xl border border-slate-700 bg-slate-900 px-4 py-3">
                                    <div class="text-xs font-semibold uppercase tracking-wide text-slate-400">{pageCopy.monitorState}</div>
                                    <div class="mt-1 text-sm font-medium text-white">
                                        {form.nominee_enabled ? pageCopy.activeState : pageCopy.inactiveState}
                                    </div>
                                </div>
                                <div class="rounded-xl border border-slate-700 bg-slate-900 px-4 py-3">
                                    <div class="text-xs font-semibold uppercase tracking-wide text-slate-400">{pageCopy.destination}</div>
                                    <div class="mt-1 truncate text-sm font-medium text-white">
                                        {form.nominee_email || pageCopy.noEmail}
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <div class="space-y-6">
                        <div class="rounded-2xl border border-slate-700 bg-slate-800/90 p-5 shadow-lg">
                            <div class="mb-4">
                                <h2 class="text-lg font-semibold text-white">{pageCopy.timerTitle}</h2>
                                <p class="mt-1 text-sm text-slate-300">
                                    {pageCopy.timerHint}
                                </p>
                            </div>

                            <label class="block">
                                <span class="mb-2 block text-sm font-medium text-slate-100">{pageCopy.thresholdValue}</span>
                                <input
                                    min="1"
                                    on:input={normalizeThresholdInput}
                                    step="1"
                                    type="number"
                                    value={form.nominee_threshold_days}
                                    class="w-full rounded-xl border border-slate-600 bg-slate-900 px-4 py-3 text-sm text-white outline-none transition placeholder:text-slate-400 focus:border-emerald-500 focus:ring-2 focus:ring-emerald-300"
                                />
                            </label>

                            <div class="mt-4">
                                <div class="mb-2 text-sm font-medium text-slate-100">{pageCopy.timeUnit}</div>
                                <div class="grid grid-cols-2 gap-2">
                                    {#each unitOptions as option}
                                        <button
                                            type="button"
                                            class={`rounded-xl border px-4 py-3 text-sm font-medium transition ${form.nominee_threshold_unit === option.value
                                                ? 'border-emerald-400 bg-emerald-500/20 text-white shadow-[0_0_0_1px_rgba(52,211,153,0.25)]'
                                                : 'border-slate-600 bg-slate-900 text-slate-200 hover:border-slate-500 hover:bg-slate-800'}`}
                                            on:click={() => setThresholdUnit(option.value)}
                                        >
                                            {$_(option.labelKey)}
                                        </button>
                                    {/each}
                                </div>
                            </div>

                            <div class="mt-4 rounded-2xl border border-emerald-500/20 bg-emerald-500/10 px-4 py-4 text-sm text-emerald-50">
                                <div class="text-xs font-semibold uppercase tracking-wide text-emerald-300">{pageCopy.triggerPreview}</div>
                                <div class="mt-2 text-xl font-semibold text-white">{thresholdPreview}</div>
                                <p class="mt-2 leading-6 text-emerald-100/90">
                                    {$_['nominee.thresholdHint', {values: {value: form.nominee_threshold_days, unit: getUnitLabel(form.nominee_threshold_unit).toLowerCase()}}]}
                                </p>
                            </div>
                        </div>
                    </div>
                </div>

                {#if error}
                    <div class="flex items-center gap-2 rounded-2xl border border-red-400/30 bg-red-500/10 px-4 py-3 text-sm text-red-200">
                        <AlertCircle size={16}/>
                        <span>{error}</span>
                    </div>
                {/if}

                {#if success}
                    <div class="rounded-2xl border border-emerald-400/30 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-100">
                        {$_['nominee.saveSuccess']}
                    </div>
                {/if}

                <div class="flex flex-col gap-3 border-t border-slate-700 pt-5 sm:flex-row sm:items-center sm:justify-between">
                    <p class="text-sm text-slate-300">
                        {pageCopy.saveFooter}
                    </p>
                    <button
                        class="inline-flex items-center justify-center gap-2 rounded-xl bg-emerald-500 px-5 py-3 text-sm font-semibold text-white shadow-lg transition hover:bg-emerald-400 disabled:cursor-not-allowed disabled:opacity-50"
                        disabled={!canSave || saving}
                        on:click={saveNomineeSettings}
                    >
                        <Save size={16}/>
                        {saving ? $_('nominee.saving') : $_('nominee.saveButton')}
                    </button>
                </div>
            {/if}
        </div>
    </section>
</div>
