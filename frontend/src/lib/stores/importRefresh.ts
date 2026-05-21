import {writable} from 'svelte/store';

export const portfolioImportVersion = writable(0);

export function notifyPortfolioImport(): void {
    portfolioImportVersion.update((value) => value + 1);
}
