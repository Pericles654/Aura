"""
Categorization Engine for Aura CashFlow.
Categorizes transactions using supplier rules, account rules, and keyword matching.
"""
import json
import os

GOLD_BUYERS = ['SARRE', 'SARREFI', 'AURAMED', 'AURA MED', 'SARREFINAMENTO']
TAX_KEYWORDS = ['TARIFA', 'PIXEL', 'ERR', 'TAR PIX', 'TAR TED', 'TAR DOC', 'TAXA', 'IOF']
TRANSFER_KEYWORDS = ['TRANSFERENCIA ENTRE CONTAS', 'CONTAMAX', 'RESGATE', 'APLICAÇÃO']
YIELD_KEYWORDS = ['RENDIMENTO', 'RENTABILIDADE', 'JUROS SOBRE']
FX_KEYWORDS = ['VARIAÇÃO CAMBIAL', 'REAVALIAÇÃO DA MOEDA', 'VARIACAO CAMBIAL']

FINANCING_CATEGORIES = [
    'Santander Capital',
    'Santander Interes',
    'GROY Interes',
    'Financiamento Veículos',
    'Rendimento de Aplicações',
    'Variação cambial - Itau',
]

FINANCING_KEYWORDS = [
    'SANTANDER CAPITAL', 'SANTANDER INTERES', 'GROY', 'FINANCIAMENTO',
]

CUSTOM_RULES_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'custom_rules.json')


def load_custom_rules():
    """Load user-defined custom categorization rules."""
    if os.path.exists(CUSTOM_RULES_FILE):
        with open(CUSTOM_RULES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_custom_rules(rules):
    """Save user-defined custom categorization rules."""
    os.makedirs(os.path.dirname(CUSTOM_RULES_FILE), exist_ok=True)
    with open(CUSTOM_RULES_FILE, 'w', encoding='utf-8') as f:
        json.dump(rules, f, ensure_ascii=False, indent=2)


def categorize_transaction(row, supplier_rules, account_rules, custom_rules=None):
    """
    Categorize a single transaction from the extrato.
    Priority: custom rules > existing classification > supplier rules > keyword matching > account rules.
    """
    if custom_rules is None:
        custom_rules = {}

    fornecedor = str(row.get('fornecedor', '') or '').strip().upper()
    texto = str(row.get('texto', '') or '').strip().upper()
    banco = str(row.get('banco', '') or '').strip().upper()
    existing = str(row.get('classificacao', '') or '').strip()
    entrada_saida = str(row.get('entrada_saida', '') or '').strip()
    valor = float(row.get('valor_brl', 0) or 0)

    # 1. Custom rules (user-defined overrides)
    for pattern, category in custom_rules.items():
        pattern_upper = pattern.upper()
        if pattern_upper in fornecedor or pattern_upper in texto:
            return category

    # 2. If already classified and not empty, keep it
    if existing and existing != 'nan' and existing != 'None':
        return existing

    # 3. Gold Sales detection
    for buyer in GOLD_BUYERS:
        if buyer in fornecedor or buyer in texto:
            return 'Gold Sales'

    # 4. Transfer between accounts
    for kw in TRANSFER_KEYWORDS:
        if kw in texto or kw in fornecedor:
            return 'Transferencia entre Contas'

    # 5. Tax/fee detection
    for kw in TAX_KEYWORDS:
        if kw in texto:
            return 'Taxas e Impostos'

    # 6. Yield/income detection
    for kw in YIELD_KEYWORDS:
        if kw in texto:
            return 'Rendimento de Aplicações'

    # 7. FX variation
    for kw in FX_KEYWORDS:
        if kw in texto:
            return 'Variação cambial - Itau'

    # 8. Financing detection
    for kw in FINANCING_KEYWORDS:
        if kw in fornecedor or kw in texto:
            return _match_financing(fornecedor, texto)

    # 9. Supplier rules (from Classificação sheet)
    if fornecedor and fornecedor in supplier_rules:
        return supplier_rules[fornecedor]

    # 10. Partial match on supplier rules
    for supplier_name, category in supplier_rules.items():
        if supplier_name in fornecedor or fornecedor in supplier_name:
            return category

    # 11. Default
    return 'Others'


def _match_financing(fornecedor, texto):
    """Match specific financing sub-categories."""
    combined = fornecedor + ' ' + texto
    if 'GROY' in combined:
        return 'GROY Interes'
    if 'SANTANDER' in combined and 'CAPITAL' in combined:
        return 'Santander Capital'
    if 'SANTANDER' in combined and ('INTERES' in combined or 'JUROS' in combined):
        return 'Santander Interes'
    if 'FINANCIAMENTO' in combined:
        return 'Financiamento Veículos'
    return 'Others'


def categorize_extrato(extrato_df, supplier_rules, account_rules, custom_rules=None):
    """Categorize all transactions in the extrato DataFrame."""
    if extrato_df is None or extrato_df.empty:
        return extrato_df

    if custom_rules is None:
        custom_rules = load_custom_rules()

    df = extrato_df.copy()
    df['categoria_auto'] = df.apply(
        lambda row: categorize_transaction(row, supplier_rules, account_rules, custom_rules),
        axis=1
    )

    return df


def get_category_summary(categorized_df):
    """Get summary of categorized transactions."""
    if categorized_df is None or categorized_df.empty:
        return []

    col = 'categoria_auto' if 'categoria_auto' in categorized_df.columns else 'classificacao'

    summary = categorized_df.groupby(col).agg(
        total_brl=('valor_brl', 'sum'),
        count=('valor_brl', 'count'),
    ).reset_index()
    summary.columns = ['categoria', 'total_brl', 'count']
    summary = summary.sort_values('total_brl')
    summary['total_brl'] = summary['total_brl'].round(2)

    return summary.to_dict('records')


def is_financing_category(category):
    """Check if a category belongs to the Financing section (below FCFF)."""
    financing_names = [
        'Santander Capital', 'Santander Interes', 'GROY Interes',
        'Financiamento Veículos', 'Rendimento de Aplicações',
        'Variação cambial - Itau', 'Intercompany', 'Deposit in Transit',
        'Dividendos',
    ]
    return category in financing_names
