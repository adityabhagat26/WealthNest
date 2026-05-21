<script lang="ts">
    import {browser} from '$app/environment';
    import {onMount} from 'svelte';

    type CategoryItem = { category: string; total_expense: string };
    type StatementPreview = {
        bank_name: string;
        account_name: string;
        rows_processed: number;
        total_expense: string;
        total_income: string;
        net_change: string;
        current_balance?: string | null;
        categories: CategoryItem[];
    };
    type BankAccountContainer = {
        id: string;
        bank_name: string;
        account_name: string;
        latest_summary: StatementPreview | null;
        updated_at: string;
    };

    const bankOptions = ['HDFC', 'ICICI', 'SBI', 'Axis', 'Kotak', 'Other'];
    let bankName = bankOptions[0];
    let accountName = 'Primary Account';
    let accounts: BankAccountContainer[] = [];
    let selectedAccountId = '';
    let selectedFile: File | null = null;
    let loading = false;
    let errorMsg = '';

    const ACCOUNTS_KEY = 'wealthnest-banking-accounts-v1';

    const formatINR = (value: string | number) =>
        new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR' }).format(Number(value || 0));
    const formatDateTime = (value: string) => new Date(value).toLocaleString();

    $: selectedAccount = accounts.find((item) => item.id === selectedAccountId) ?? null;
    $: result = selectedAccount?.latest_summary ?? null;

    onMount(() => {
        if (!browser) return;
        const raw = localStorage.getItem(ACCOUNTS_KEY);
        if (!raw) return;
        try {
            const parsed = JSON.parse(raw) as BankAccountContainer[];
            accounts = Array.isArray(parsed) ? parsed : [];
            if (accounts.length > 0) {
                selectedAccountId = accounts[0].id;
            }
        } catch {
            accounts = [];
        }
    });

    function persistAccounts() {
        if (!browser) return;
        localStorage.setItem(ACCOUNTS_KEY, JSON.stringify(accounts));
    }

    function createAccountContainer() {
        errorMsg = '';
        const normalizedBank = bankName.trim();
        const normalizedAccount = accountName.trim();
        if (!normalizedBank || !normalizedAccount) {
            errorMsg = 'Please enter bank and account name.';
            return;
        }

        const existing = accounts.find(
            (item) =>
                item.bank_name.toLowerCase() === normalizedBank.toLowerCase() &&
                item.account_name.toLowerCase() === normalizedAccount.toLowerCase()
        );
        if (existing) {
            selectedAccountId = existing.id;
            return;
        }

        const container: BankAccountContainer = {
            id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
            bank_name: normalizedBank,
            account_name: normalizedAccount,
            latest_summary: null,
            updated_at: new Date().toISOString()
        };
        accounts = [container, ...accounts];
        selectedAccountId = container.id;
        persistAccounts();
    }

    function removeSelectedContainer() {
        if (!selectedAccountId) return;
        accounts = accounts.filter((item) => item.id !== selectedAccountId);
        selectedAccountId = accounts[0]?.id ?? '';
        persistAccounts();
    }

    function onFileChange(event: Event) {
        const input = event.target as HTMLInputElement;
        selectedFile = input.files?.[0] ?? null;
    }

    async function previewStatement() {
        if (!selectedAccountId) {
            errorMsg = 'Create and select an account container first.';
            return;
        }
        if (!selectedFile) {
            errorMsg = 'Please select a CSV file first.';
            return;
        }

        loading = true;
        errorMsg = '';
        try {
            const formData = new FormData();
            formData.append('file', selectedFile);
            formData.append('bank_name', selectedAccount?.bank_name ?? bankName);
            formData.append('account_name', selectedAccount?.account_name ?? accountName);

            const response = await fetch('/api/v1/banking/statements/preview', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                throw new Error(await response.text());
            }

            const summary = (await response.json()) as StatementPreview;
            accounts = accounts.map((item) =>
                item.id === selectedAccountId
                    ? {
                          ...item,
                          latest_summary: summary,
                          updated_at: new Date().toISOString()
                      }
                    : item
            );
            persistAccounts();
        } catch (error) {
            errorMsg = error instanceof Error ? error.message : 'Failed to parse statement';
        } finally {
            loading = false;
        }
    }
</script>

<div class="space-y-6">
    <div>
        <h2 class="text-lg font-semibold text-gray-700">Bank Statement Analyzer</h2>
        <p class="text-sm text-gray-500">Create multiple bank account containers and upload statements for each.</p>
    </div>

    <div class="bg-white rounded-xl shadow-sm p-5 border border-gray-100 space-y-4">
        <div class="grid grid-cols-1 md:grid-cols-4 gap-3">
            <select class="border rounded-lg px-3 py-2" bind:value={bankName}>
                {#each bankOptions as bank}
                    <option value={bank}>{bank}</option>
                {/each}
            </select>
            <input class="border rounded-lg px-3 py-2" bind:value={accountName} placeholder="Account name"/>
            <button class="px-4 py-2 bg-gray-800 text-white rounded-lg hover:bg-gray-900" on:click={createAccountContainer}>
                Add Account Container
            </button>
            <button
                class="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50"
                on:click={removeSelectedContainer}
                disabled={!selectedAccountId}
            >
                Remove Selected
            </button>
        </div>

        {#if accounts.length === 0}
            <div class="text-sm text-gray-500">No bank account container added yet.</div>
        {:else}
            <div class="space-y-2">
                {#each accounts as account}
                    <button
                        class="w-full text-left border rounded-lg px-3 py-2 transition-colors {selectedAccountId === account.id ? 'bg-libre-green/10 border-libre-green' : 'hover:bg-gray-50'}"
                        on:click={() => (selectedAccountId = account.id)}
                    >
                        <div class="font-medium text-gray-700">{account.bank_name} • {account.account_name}</div>
                        <div class="text-xs text-gray-500">Last update: {formatDateTime(account.updated_at)}</div>
                    </button>
                {/each}
            </div>
        {/if}
    </div>

    <div class="bg-white rounded-xl shadow-sm p-5 border border-gray-100 space-y-4">
        <div class="text-sm text-gray-600">
            Upload for:
            <strong>{selectedAccount ? `${selectedAccount.bank_name} • ${selectedAccount.account_name}` : 'No account selected'}</strong>
        </div>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
            <input class="border rounded-lg px-3 py-2" type="file" accept=".csv,text/csv" on:change={onFileChange}/>
        </div>

        <button
            class="px-4 py-2 bg-libre-green text-white rounded-lg hover:bg-libre-green/90 disabled:opacity-50"
            on:click={previewStatement}
            disabled={loading}
        >
            {loading ? 'Processing...' : 'Upload & Analyze'}
        </button>

        {#if errorMsg}
            <div class="p-3 rounded-lg border border-red-200 bg-red-50 text-red-700 text-sm">{errorMsg}</div>
        {/if}
    </div>

    {#if result}
        <div class="bg-white rounded-xl shadow-sm p-5 border border-gray-100 space-y-3">
            <div class="text-sm text-gray-600">{result.bank_name} • {result.account_name}</div>
            <div class="grid grid-cols-1 md:grid-cols-4 gap-3 text-sm">
                <div class="p-3 rounded-lg bg-gray-50">Rows: <strong>{result.rows_processed}</strong></div>
                <div class="p-3 rounded-lg bg-gray-50">Expense: <strong>{formatINR(result.total_expense)}</strong></div>
                <div class="p-3 rounded-lg bg-gray-50">Income: <strong>{formatINR(result.total_income)}</strong></div>
                <div class="p-3 rounded-lg bg-gray-50">Balance: <strong>{result.current_balance ? formatINR(result.current_balance) : 'N/A'}</strong></div>
            </div>
            <div class="text-sm text-gray-700">
                Net change: <strong>{formatINR(result.net_change)}</strong>
            </div>
            <div>
                <h3 class="font-medium text-gray-700 mb-2">Expenses by category</h3>
                {#if result.categories.length === 0}
                    <div class="text-sm text-gray-500">No expense rows detected.</div>
                {:else}
                    <div class="space-y-2">
                        {#each result.categories as item}
                            <div class="flex items-center justify-between text-sm border rounded-lg px-3 py-2">
                                <span>{item.category}</span>
                                <strong>{formatINR(item.total_expense)}</strong>
                            </div>
                        {/each}
                    </div>
                {/if}
            </div>
        </div>
    {/if}
</div>
