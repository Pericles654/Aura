"""
MAMF Generator for Aura CashFlow.
Generates the Month Actual cash flow report (MAMF Realizada)
with proper separation of FCFF and Financing sections.
"""
from .categorizer import is_financing_category

# Categories that are internal movements and should be excluded from MAMF
# (they inflate both inflows and outflows but net to ~zero)
EXCLUDED_FROM_MAMF = {
    'Transferencia entre Contas',
    'Deposit in Transit',
    'Intercompany',
}


def generate_mamf(categorized_df, period_info=None):
    """
    Generate the MAMF (Month Actual) report from categorized extrato data.
    Separates into: Cash Inflows, OPEX, CAPEX, FCFF, Financing.
    Excludes internal transfers that inflate both sides.
    """
    if categorized_df is None or categorized_df.empty:
        return _empty_mamf()

    cat_col = 'categoria_auto' if 'categoria_auto' in categorized_df.columns else 'classificacao'
    df = categorized_df.copy()

    # Exclude internal transfer categories from main MAMF calculation
    # but track their net value for transparency
    excluded_mask = df[cat_col].isin(EXCLUDED_FROM_MAMF)
    excluded_df = df[excluded_mask]
    df_filtered = df[~excluded_mask]

    excluded_net = round(excluded_df['valor_brl'].sum(), 2) if len(excluded_df) > 0 else 0

    # Separate inflows and outflows (excluding internal transfers)
    inflows_df = df_filtered[df_filtered['valor_brl'] > 0].copy()
    outflows_df = df_filtered[df_filtered['valor_brl'] < 0].copy()

    # Cash Inflows
    inflow_categories = _group_by_category(inflows_df, cat_col)

    # Separate Gold Sales from other inflows
    gold_sales = inflow_categories.pop('Gold Sales', 0)

    # Remove financing categories from inflows (they go to financing section)
    financing_inflow_items = {}
    other_inflows = {}
    for cat, val in inflow_categories.items():
        if is_financing_category(cat):
            financing_inflow_items[cat] = val
        else:
            other_inflows[cat] = val

    # Cash Outflows - separate OPEX, CAPEX, and Financing
    opex_items = {}
    capex_items = {}
    financing_items = dict(financing_inflow_items)

    opex_capex_col = 'opex_capex' if 'opex_capex' in df_filtered.columns else None

    for _, row in outflows_df.iterrows():
        category = row.get(cat_col, 'Others')
        valor = row.get('valor_brl', 0)
        is_capex = opex_capex_col and str(row.get(opex_capex_col, '')).strip().upper() == 'CAPEX'

        if is_financing_category(category):
            financing_items[category] = financing_items.get(category, 0) + valor
        elif is_capex:
            capex_items[category] = capex_items.get(category, 0) + valor
        else:
            opex_items[category] = opex_items.get(category, 0) + valor

    # Totals
    total_inflows = round(gold_sales + sum(other_inflows.values()), 2)
    total_opex = round(sum(opex_items.values()), 2)
    total_capex = round(sum(capex_items.values()), 2)
    total_outflows = round(total_opex + total_capex, 2)
    fcff = round(total_inflows + total_outflows, 2)
    total_financing = round(sum(financing_items.values()), 2)

    # Sort items by absolute value
    opex_items = dict(sorted(opex_items.items(), key=lambda x: x[1]))
    capex_items = dict(sorted(capex_items.items(), key=lambda x: x[1]))

    mamf = {
        'period': period_info or {},
        'inflows': {
            'gold_sales': round(gold_sales, 2),
            'other_detail': {k: round(v, 2) for k, v in other_inflows.items()},
            'total': total_inflows,
        },
        'opex': {
            'detail': {k: round(v, 2) for k, v in opex_items.items()},
            'total': total_opex,
        },
        'capex': {
            'detail': {k: round(v, 2) for k, v in capex_items.items()},
            'total': total_capex,
        },
        'total_outflows': total_outflows,
        'fcff': fcff,
        'financing': {
            'detail': {k: round(v, 2) for k, v in financing_items.items()},
            'total': total_financing,
        },
        'net_cash_flow': round(fcff + total_financing, 2),
        'excluded_transfers': {
            'net': excluded_net,
            'count': len(excluded_df),
        },
    }

    return mamf


def compare_with_original(mamf, original_month_realizado, month_col_index=3):
    """
    Compare generated MAMF with the original Month Realizado sheet.
    month_col_index: column index for the target month (3=Jan, 4=Feb, etc.)
    """
    if not original_month_realizado:
        return {'match': False, 'details': 'No original data to compare'}

    comparisons = []

    # Find key values from original
    original_values = {}
    for row in original_month_realizado:
        if row and row[1]:
            label = str(row[1]).strip()
            val = None
            if len(row) > month_col_index and row[month_col_index] is not None:
                try:
                    val = float(row[month_col_index])
                except (ValueError, TypeError):
                    val = None
            original_values[label] = val

    # Key comparisons
    checks = [
        ('(a) Total cash inflows', mamf['inflows']['total']),
        ('(b) Total Opex', mamf['opex']['total']),
        ('(d) Total Capex', mamf['capex']['total']),
        ('(e) Free cash flow to firm (a + b + c + d)', mamf['fcff']),
        ('(f) Financing (financial institutions & suppliers)', mamf['financing']['total']),
    ]

    for label, generated_val in checks:
        original_val = original_values.get(label)
        if original_val is not None:
            diff = round(generated_val - original_val, 2)
            # Match threshold: within 0.1% of original value or less than R$100
            threshold = max(abs(original_val) * 0.001, 100)
            comparisons.append({
                'label': label,
                'original': original_val,
                'generated': generated_val,
                'difference': diff,
                'match': abs(diff) < threshold,
                'pct_diff': round(abs(diff) / max(abs(original_val), 1) * 100, 2),
            })

    all_match = all(c['match'] for c in comparisons) if comparisons else False

    return {
        'match': all_match,
        'comparisons': comparisons,
    }


def _group_by_category(df, cat_col):
    """Group DataFrame by category and sum values."""
    if df.empty:
        return {}
    grouped = df.groupby(cat_col)['valor_brl'].sum()
    return {k: round(v, 2) for k, v in grouped.items()}


def _empty_mamf():
    return {
        'period': {},
        'inflows': {'gold_sales': 0, 'other_detail': {}, 'total': 0},
        'opex': {'detail': {}, 'total': 0},
        'capex': {'detail': {}, 'total': 0},
        'total_outflows': 0,
        'fcff': 0,
        'financing': {'detail': {}, 'total': 0},
        'net_cash_flow': 0,
    }
