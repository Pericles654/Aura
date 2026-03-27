"""
Excel Reader Engine for Aura CashFlow Reconciliation System.
Reads all relevant sheets from the BBR CashFlow Excel files.
"""
import warnings
import pandas as pd
import openpyxl
from datetime import datetime

warnings.filterwarnings('ignore')

BANK_ACCOUNTS = {
    '1000001': 'Banco Santander Ag. 2271 / CC 130127307',
    '1000002': 'Banco do Brasil Ag: 1229-7 / CC:131390-8',
    '1000006': 'Banco Itaú CC 183789-1',
    '1000007': 'Banco Bradesco Ag. 0465/ CC 0826019-2',
    '1000010': 'Banco Santander - Ag. 2271 CC 13166137',
    '1000011': 'Banco Bradesco - Ag. 895 CC 491977',
    '1000012': 'Banco do Nordeste AG: 100 CC: 45344-8',
    '1100003': 'Aplicação Santander - Renda Fixa',
    '1100008': 'Bradesco - Fundo Cascar Filial',
    '1100014': 'Bradesco Inest Facil - Ag: 0465 / CC 0826019-2',
    '1100015': 'Bradesco CDB - Ag: 0465 / CC 0826019-2',
    '1100016': 'Banco do Brasil - Ag 1229-7 CC 13190-8',
    '1100018': 'Aplicação Santander Conta Max OPEX - Ag. 2271 CC 13166137',
}

DE_PARA_CONTAS = {
    '1000001': 'SANT',
    '1000002': 'BB',
    '1000006': ' ITAÚ NASSAU',
    '1000007': 'BRADESCO C/C NOVA',
    '1000010': 'SANT',
    '1000011': 'BRADESCO TRIANON',
    '1100003': 'CONTAMAX SANTANDER',
    '1100014': 'BRADESCO INVESTFACIL',
    '1100015': 'BRADESCO CDB NOVO',
    '1100016': 'BB',
    '1100018': 'APLICAÇÃO CONTA OPEX',
}


def read_excel_file(filepath):
    """Read the full CashFlow Excel file and return all parsed data."""
    wb = openpyxl.load_workbook(filepath, data_only=True, read_only=True)
    sheet_names = wb.sheetnames
    wb.close()

    result = {
        'filepath': filepath,
        'sheet_names': sheet_names,
        'razao': None,
        'extrato': None,
        'month_realizado': None,
        'classificacao': None,
        'base_de_dados': None,
        'dimensao_cash': None,
        'check': None,
    }

    result['razao'] = read_razao_contabil(filepath)
    result['extrato'] = read_relatorio_analitico(filepath, sheet_names)
    result['month_realizado'] = read_month_realizado(filepath)
    result['classificacao'] = read_classificacao(filepath)
    result['base_de_dados'] = read_base_de_dados(filepath)
    result['dimensao_cash'] = read_dimensao_cash(filepath)
    result['check'] = read_check(filepath)

    # Merge classificacao with base_de_dados (base_de_dados is more complete)
    if result['base_de_dados'] and result['classificacao']:
        merged = dict(result['base_de_dados'])
        merged.update(result['classificacao'])
        result['classificacao'] = merged
    elif result['base_de_dados']:
        result['classificacao'] = result['base_de_dados']

    return result


def read_razao_contabil(filepath):
    """Read the Razão Contábil sheet - accounting ledger."""
    wb = openpyxl.load_workbook(filepath, data_only=True, read_only=True)
    ws = wb['Razão Contábil']

    rows = []
    headers = None
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i == 0:
            headers = list(row)
            continue
        rows.append(list(row))

    wb.close()

    if not rows:
        return pd.DataFrame()

    # Handle duplicate column names by making them unique
    seen = {}
    unique_headers = []
    for h in headers:
        if h in seen:
            seen[h] += 1
            unique_headers.append(f"{h}_{seen[h]}")
        else:
            seen[h] = 0
            unique_headers.append(h)

    df = pd.DataFrame(rows, columns=unique_headers)

    col_map = {
        'Conta': 'conta',
        'Descr Conta': 'descr_conta',
        'Valor Débito': 'debito',
        'Valor Crédito': 'credito',
        'Valor': 'valor',
        'Moeda': 'moeda',
        'Texto': 'texto',
        'Nº Lancto': 'num_lancto',
        'Nº Linha': 'num_linha',
        'Data Lancto': 'data_lancto',
    }

    rename = {k: v for k, v in col_map.items() if k in df.columns}
    df = df.rename(columns=rename)

    for col in ['debito', 'credito', 'valor']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    if 'data_lancto' in df.columns:
        df['data_lancto'] = pd.to_datetime(df['data_lancto'], errors='coerce')
        df['data'] = df['data_lancto'].dt.date

    if 'conta' in df.columns:
        df['conta'] = df['conta'].astype(str).str.strip()

    return df


def read_relatorio_analitico(filepath, sheet_names):
    """Read all Relatório Analítico IFS sheets (bank statements)."""
    analitico_sheets = [s for s in sheet_names if s.startswith('Relatório Analítico IFS')]

    all_dfs = []
    for sheet_name in analitico_sheets:
        df = _read_single_analitico(filepath, sheet_name)
        if df is not None and len(df) > 0:
            periodo_num = sheet_name.split()[-1]
            df['sheet_origem'] = sheet_name
            df['periodo_ref'] = periodo_num
            all_dfs.append(df)

    if not all_dfs:
        return pd.DataFrame()

    return pd.concat(all_dfs, ignore_index=True)


def _read_single_analitico(filepath, sheet_name):
    """Read a single Relatório Analítico IFS sheet."""
    wb = openpyxl.load_workbook(filepath, data_only=True, read_only=True)
    ws = wb[sheet_name]

    rows = []
    headers = None
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i == 0:
            headers = list(row)
            continue
        rows.append(list(row))

    wb.close()

    if not rows or not headers:
        return None

    df = pd.DataFrame(rows, columns=headers)

    # Filter out total/summary rows (SHORT_NAME contains 'Total' or is empty with no COMPANY)
    if 'COMPANY' in df.columns:
        df = df[df['COMPANY'].notna() & (df['COMPANY'] != '')].copy()

    col_map = {
        'SHORT_NAME': 'banco',
        'NAME': 'fornecedor',
        'TEXT': 'texto',
        'VOUCHER_DATE': 'data_voucher',
        'Valor Pago BRL': 'valor_brl',
        'Valor Pago USD': 'valor_usd',
        'Entrada/Saída': 'entrada_saida',
        'Classificação': 'classificacao',
        'OPEX/CAPEX': 'opex_capex',
        'Período': 'periodo',
        'Status': 'status',
        'IDENTITY': 'identity',
        'PARTY_TYPE': 'party_type',
        'VOUCHER_NO': 'voucher_no',
        'PAYMENT_ID': 'payment_id',
    }

    rename = {k: v for k, v in col_map.items() if k in df.columns}
    df = df.rename(columns=rename)

    for col in ['valor_brl', 'valor_usd']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    if 'data_voucher' in df.columns:
        df['data_voucher'] = pd.to_datetime(df['data_voucher'], errors='coerce')
        df['data'] = df['data_voucher'].dt.date

    if 'banco' in df.columns:
        df['banco'] = df['banco'].astype(str).str.strip()

    return df


def read_month_realizado(filepath):
    """Read the Month Realizado sheet - MAMF cash flow summary."""
    wb = openpyxl.load_workbook(filepath, data_only=True, read_only=True)
    ws = wb['Month Realizado']

    rows = []
    for row in ws.iter_rows(values_only=True):
        rows.append(list(row))

    wb.close()

    return rows


def read_classificacao(filepath):
    """Read the Classificação sheet - supplier classification rules."""
    wb = openpyxl.load_workbook(filepath, data_only=True, read_only=True)
    ws = wb['Classificação']

    rules = {}
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i == 0:
            continue
        fornecedor = str(row[0]).strip() if row[0] else None
        classificacao = str(row[1]).strip() if row[1] else None
        if fornecedor and classificacao:
            rules[fornecedor.upper()] = classificacao

    wb.close()
    return rules


def read_base_de_dados(filepath):
    """Read the Base de Dados sheet - master supplier classification (789 suppliers)."""
    wb = openpyxl.load_workbook(filepath, data_only=True, read_only=True)
    try:
        ws = wb['Base de Dados']
    except KeyError:
        wb.close()
        return {}

    rules = {}
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i == 0:
            continue
        fornecedor = str(row[0]).strip() if row[0] else None
        classificacao = str(row[1]).strip() if row[1] else None
        if fornecedor and classificacao:
            rules[fornecedor.upper()] = classificacao

    wb.close()
    return rules


def read_dimensao_cash(filepath):
    """Read the DimensaoCash sheet - account-based classification rules."""
    wb = openpyxl.load_workbook(filepath, data_only=True, read_only=True)
    ws = wb['DimensaoCash']

    rules = {}
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i == 0:
            continue
        conta = str(row[0]).strip() if row[0] else None
        classificacao = str(row[3]).strip() if len(row) > 3 and row[3] else None
        if conta and classificacao:
            rules[conta] = classificacao

    wb.close()
    return rules


def read_check(filepath):
    """Read the Check sheet - reconciliation status."""
    wb = openpyxl.load_workbook(filepath, data_only=True, read_only=True)
    ws = wb['Check']

    rows = []
    headers = None
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i == 0:
            headers = list(row)
            continue
        rows.append(list(row))

    wb.close()

    if not rows:
        return pd.DataFrame()

    return pd.DataFrame(rows, columns=headers)


def get_period_from_filename(filepath):
    """Extract the period (month/year) from the filename."""
    name = filepath.lower()
    months_pt = {
        'janeiro': 1, 'fevereiro': 2, 'março': 3, 'marco': 3,
        'abril': 4, 'maio': 5, 'junho': 6, 'julho': 7,
        'agosto': 8, 'setembro': 9, 'outubro': 10,
        'novembro': 11, 'dezembro': 12
    }
    for month_name, month_num in months_pt.items():
        if month_name in name:
            for year in range(2024, 2028):
                if str(year) in name:
                    return {'month': month_num, 'year': year, 'month_name': month_name.capitalize()}
    return {'month': None, 'year': None, 'month_name': 'Desconhecido'}
