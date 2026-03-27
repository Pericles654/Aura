"""
Reconciliation Engine for Aura CashFlow.
Compares Razão Contábil (accounting) vs Relatório Analítico (bank statements) day by day.
"""
import pandas as pd
from datetime import date


def reconcile(razao_df, extrato_df):
    """
    Main reconciliation: compare razão vs extrato day-by-day.
    Returns reconciliation summary with daily balances and discrepancies.
    """
    if razao_df is None or razao_df.empty or extrato_df is None or extrato_df.empty:
        return {
            'status': 'NO_DATA',
            'daily': [],
            'summary': {},
            'discrepancies': [],
        }

    razao_daily = _aggregate_razao_daily(razao_df)
    extrato_daily = _aggregate_extrato_daily(extrato_df)

    all_dates = sorted(set(razao_daily.keys()) | set(extrato_daily.keys()))

    daily_results = []
    discrepancies = []
    razao_cumulative = 0
    extrato_cumulative = 0

    for d in all_dates:
        razao_val = razao_daily.get(d, 0)
        extrato_val = extrato_daily.get(d, 0)
        diff = round(razao_val - extrato_val, 2)

        razao_cumulative += razao_val
        extrato_cumulative += extrato_val

        row = {
            'data': d,
            'razao_movimento': round(razao_val, 2),
            'extrato_movimento': round(extrato_val, 2),
            'diferenca': diff,
            'razao_acumulado': round(razao_cumulative, 2),
            'extrato_acumulado': round(extrato_cumulative, 2),
            'diferenca_acumulada': round(razao_cumulative - extrato_cumulative, 2),
            'conciliado': abs(diff) < 0.01,
        }
        daily_results.append(row)

        if abs(diff) >= 0.01:
            discrepancies.append(row)

    total_razao = round(razao_cumulative, 2)
    total_extrato = round(extrato_cumulative, 2)
    total_diff = round(total_razao - total_extrato, 2)

    summary = {
        'total_razao': total_razao,
        'total_extrato': total_extrato,
        'diferenca_total': total_diff,
        'conciliado': abs(total_diff) < 0.01,
        'dias_com_diferenca': len(discrepancies),
        'dias_total': len(daily_results),
        'percentual_conciliado': round(
            (len(daily_results) - len(discrepancies)) / max(len(daily_results), 1) * 100, 1
        ),
    }

    return {
        'status': 'CONCILIADO' if summary['conciliado'] else 'PENDENTE',
        'daily': daily_results,
        'summary': summary,
        'discrepancies': discrepancies,
    }


def reconcile_by_bank(razao_df, extrato_df, de_para_contas):
    """
    Reconcile by individual bank account.
    Maps razão accounts to extrato bank names using DE_PARA mapping.
    """
    results = {}

    if razao_df is None or razao_df.empty or extrato_df is None or extrato_df.empty:
        return results

    conta_to_banco = de_para_contas or {}

    for conta, banco_name in conta_to_banco.items():
        if not banco_name or not banco_name.strip():
            continue

        razao_bank = razao_df[razao_df['conta'] == str(conta)].copy()
        extrato_bank = extrato_df[extrato_df['banco'] == banco_name.strip()].copy()

        if razao_bank.empty and extrato_bank.empty:
            continue

        rec = reconcile(razao_bank, extrato_bank)
        rec['conta'] = conta
        rec['banco'] = banco_name.strip()

        results[banco_name.strip()] = rec

    return results


def _aggregate_razao_daily(df):
    """Aggregate razão entries by date, summing net values."""
    if 'data' not in df.columns or 'valor' not in df.columns:
        return {}

    daily = df.groupby('data')['valor'].sum()
    return {d: round(v, 2) for d, v in daily.items() if d is not None}


def _aggregate_extrato_daily(df):
    """Aggregate extrato entries by date, summing BRL values."""
    if 'data' not in df.columns or 'valor_brl' not in df.columns:
        return {}

    daily = df.groupby('data')['valor_brl'].sum()
    return {d: round(v, 2) for d, v in daily.items() if d is not None}


def find_reversal_pairs(extrato_df):
    """
    Find debit/credit reversal pairs in the extrato (IFS baixa errors).
    These are entries on the same date/bank with equal opposite values that cancel out.
    As Michelle explained, these don't need to be removed since they net to zero.
    """
    if extrato_df is None or extrato_df.empty:
        return []

    reversals = []
    if 'banco' not in extrato_df.columns or 'data' not in extrato_df.columns:
        return reversals

    for (banco, data_val), grp in extrato_df.groupby(['banco', 'data']):
        if data_val is None:
            continue
        values = grp['valor_brl'].tolist()
        textos = grp['texto'].tolist() if 'texto' in grp.columns else [''] * len(values)
        indices = grp.index.tolist()
        used = set()

        for i in range(len(values)):
            if i in used:
                continue
            for j in range(i + 1, len(values)):
                if j in used:
                    continue
                if abs(values[i] + values[j]) < 0.01 and values[i] != 0:
                    reversals.append({
                        'banco': banco,
                        'data': str(data_val),
                        'valor': round(values[i], 2),
                        'texto_debito': textos[i],
                        'texto_credito': textos[j],
                        'idx_a': indices[i],
                        'idx_b': indices[j],
                    })
                    used.add(i)
                    used.add(j)
                    break

    return reversals


def get_unmatched_entries(razao_df, extrato_df, target_date):
    """Get detailed entries for a specific date where there's a discrepancy."""
    razao_day = razao_df[razao_df['data'] == target_date] if 'data' in razao_df.columns else pd.DataFrame()
    extrato_day = extrato_df[extrato_df['data'] == target_date] if 'data' in extrato_df.columns else pd.DataFrame()

    razao_entries = []
    if not razao_day.empty:
        for _, row in razao_day.iterrows():
            razao_entries.append({
                'conta': row.get('conta', ''),
                'descr_conta': row.get('descr_conta', ''),
                'debito': row.get('debito', 0),
                'credito': row.get('credito', 0),
                'valor': row.get('valor', 0),
                'texto': row.get('texto', ''),
            })

    extrato_entries = []
    if not extrato_day.empty:
        for _, row in extrato_day.iterrows():
            extrato_entries.append({
                'banco': row.get('banco', ''),
                'fornecedor': row.get('fornecedor', ''),
                'valor_brl': row.get('valor_brl', 0),
                'entrada_saida': row.get('entrada_saida', ''),
                'classificacao': row.get('classificacao', ''),
                'texto': row.get('texto', ''),
            })

    return {
        'data': str(target_date),
        'razao_entries': razao_entries,
        'extrato_entries': extrato_entries,
        'razao_total': round(sum(e['valor'] for e in razao_entries), 2),
        'extrato_total': round(sum(e['valor_brl'] for e in extrato_entries), 2),
    }
