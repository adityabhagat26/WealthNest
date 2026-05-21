import {zodiosApi} from '$lib/api';
import {notifyPortfolioImport} from '$lib/stores/importRefresh';
import type {AssetCreateItem, AssetInfo, BrimAssetMapping, BrimParseResponse, TransactionCreateItem} from '$lib/types';
import {safeCurrency, safeNumber, safeString} from '$lib/types';

export interface BrimImportSummary {
    importedCount: number;
    createdAssets: number;
    skippedDuplicates: number;
    warnings: number;
}

function getResolvedAssetIdMap(parseResult: BrimParseResponse): Map<number, number> {
    const resolved = new Map<number, number>();

    for (const mapping of parseResult.asset_mappings || []) {
        const fakeAssetId = safeNumber(mapping.fake_asset_id);
        const selectedAssetId = safeNumber(mapping.selected_asset_id);
        if (!fakeAssetId) continue;

        if (selectedAssetId) {
            resolved.set(fakeAssetId, selectedAssetId);
            continue;
        }

        if (mapping.candidates?.length === 1) {
            const candidateId = safeNumber(mapping.candidates[0].asset_id);
            if (candidateId) {
                resolved.set(fakeAssetId, candidateId);
            }
        }
    }

    return resolved;
}

function inferAssetCurrency(parseResult: BrimParseResponse, fakeAssetId: number): string {
    const matchingTx = (parseResult.transactions || []).find(
        (tx) => tx.asset_id === fakeAssetId && safeCurrency(tx.cash)?.code
    );
    return safeCurrency(matchingTx?.cash)?.code || 'USD';
}

function buildMissingAssetPayload(parseResult: BrimParseResponse, mapping: BrimAssetMapping): AssetCreateItem {
    const fakeAssetId = safeNumber(mapping.fake_asset_id) ?? -1;
    const symbol = safeString(mapping.extracted_symbol)?.trim().toUpperCase();
    const displayName =
        safeString(mapping.extracted_name)?.trim() ||
        (symbol ? `${symbol} (Crypto)` : `Imported Crypto ${fakeAssetId}`);

    return {
        display_name: displayName,
        currency: inferAssetCurrency(parseResult, fakeAssetId),
        asset_type: 'CRYPTO',
        identifier_ticker: symbol || undefined,
        icon_url: null,
        classification_params: null,
        identifier_isin: undefined,
        identifier_cusip: undefined,
        identifier_sedol: undefined,
        identifier_figi: undefined,
        identifier_uuid: undefined,
        identifier_other: undefined
    };
}

async function createMissingAssetsFromParse(
    parseResult: BrimParseResponse,
    resolvedAssetIds: Map<number, number>
): Promise<Map<number, number>> {
    const unresolvedMappings = (parseResult.asset_mappings || []).filter(
        (mapping) => {
            const fakeAssetId = safeNumber(mapping.fake_asset_id);
            return fakeAssetId ? !resolvedAssetIds.has(fakeAssetId) : false;
        }
    );
    if (unresolvedMappings.length === 0) {
        return resolvedAssetIds;
    }

    const createPayload = unresolvedMappings.map((mapping) =>
        buildMissingAssetPayload(parseResult, mapping)
    );
    const createResponse = await zodiosApi.create_assets_bulk_api_v1_assets_post(createPayload);

    unresolvedMappings.forEach((mapping, index) => {
        const result = createResponse.results?.[index];
        const fakeAssetId = safeNumber(mapping.fake_asset_id);
        const createdAssetId = safeNumber(result?.asset_id);
        if (fakeAssetId && result?.success && createdAssetId) {
            resolvedAssetIds.set(fakeAssetId, createdAssetId);
        }
    });

    const stillMissing = unresolvedMappings.filter(
        (mapping) => {
            const fakeAssetId = safeNumber(mapping.fake_asset_id);
            return fakeAssetId ? !resolvedAssetIds.has(fakeAssetId) : false;
        }
    );
    if (stillMissing.length > 0) {
        const allAssets = (await zodiosApi.get_all_assets_api_v1_assets_all_get()) as AssetInfo[];
        for (const mapping of stillMissing) {
            const fakeAssetId = safeNumber(mapping.fake_asset_id);
            const symbol = safeString(mapping.extracted_symbol)?.trim().toUpperCase();
            const name = safeString(mapping.extracted_name)?.trim();
            const matchedAsset = allAssets.find(
                (asset) =>
                    (symbol && safeString(asset.identifier_ticker)?.toUpperCase() === symbol) ||
                    (name && asset.display_name === name) ||
                    (symbol && asset.display_name === `${symbol} (Crypto)`)
            );
            if (fakeAssetId && matchedAsset) {
                resolvedAssetIds.set(fakeAssetId, matchedAsset.id);
            }
        }
    }

    return resolvedAssetIds;
}

function buildImportTransactions(
    parseResult: BrimParseResponse,
    resolvedAssetIds: Map<number, number>
): TransactionCreateItem[] {
    const duplicates = parseResult.duplicates && !Array.isArray(parseResult.duplicates)
        ? parseResult.duplicates
        : null;
    const duplicateIndexes = new Set<number>([
        ...((duplicates?.tx_possible_duplicates || []).map((item) => item.tx_row_index)),
        ...((duplicates?.tx_likely_duplicates || []).map((item) => item.tx_row_index))
    ]);

    const importable: TransactionCreateItem[] = [];

    (parseResult.transactions || []).forEach((tx, index) => {
        if (duplicateIndexes.has(index)) return;

        const rawAssetId = safeNumber(tx.asset_id);
        const cash = safeCurrency(tx.cash);
        const nextAssetId =
            rawAssetId && resolvedAssetIds.has(rawAssetId)
                ? resolvedAssetIds.get(rawAssetId) ?? null
                : rawAssetId ?? null;

        if (rawAssetId && !nextAssetId) {
            return;
        }

        importable.push({
            broker_id: tx.broker_id,
            asset_id: nextAssetId,
            type: tx.type,
            date: tx.date,
            quantity: tx.quantity,
            cash: cash
                ? {
                      code: cash.code,
                      amount: cash.amount
                  }
                : null,
            link_uuid: tx.link_uuid ?? null,
            tags: tx.tags ?? null,
            description: tx.description ?? null,
            cost_basis_override: tx.cost_basis_override ?? null
        });
    });

    return importable;
}

export async function autoImportBrimFile(fileId: string, brokerId: number): Promise<BrimImportSummary> {
    const parseResult = (await zodiosApi.parse_file_api_v1_brokers_import_files__file_id__parse_post(
        {plugin_code: 'auto', broker_id: brokerId},
        {params: {file_id: fileId}}
    )) as BrimParseResponse;

    const resolvedAssetIds = await createMissingAssetsFromParse(
        parseResult,
        getResolvedAssetIdMap(parseResult)
    );

    const importTransactions = buildImportTransactions(parseResult, resolvedAssetIds);
    if (importTransactions.length > 0) {
        await zodiosApi.create_transactions_api_v1_transactions_post(importTransactions);
    }

    notifyPortfolioImport();

    const duplicates = parseResult.duplicates && !Array.isArray(parseResult.duplicates)
        ? parseResult.duplicates
        : null;

    return {
        importedCount: importTransactions.length,
        createdAssets: (parseResult.asset_mappings || []).filter((mapping) => {
            const selected =
                safeNumber(mapping.selected_asset_id) ||
                (mapping.candidates?.length === 1 ? safeNumber(mapping.candidates[0].asset_id) : null);
            const fakeAssetId = safeNumber(mapping.fake_asset_id);
            return !selected && !!fakeAssetId && resolvedAssetIds.has(fakeAssetId);
        }).length,
        skippedDuplicates:
            (duplicates?.tx_possible_duplicates?.length || 0) +
            (duplicates?.tx_likely_duplicates?.length || 0),
        warnings: parseResult.warnings?.length || 0
    };
}
