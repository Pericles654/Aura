"""
Aura CashFlow Reconciliation System
Flask web application for financial reconciliation and cash flow analysis.
"""
import os
import json
import glob
from flask import Flask, render_template, request, jsonify, redirect, url_for
from werkzeug.utils import secure_filename
from engine.excel_reader import read_excel_file, get_period_from_filename, DE_PARA_CONTAS
from engine.reconciliation import reconcile, reconcile_by_bank, get_unmatched_entries
from engine.categorizer import (
    categorize_extrato, get_category_summary,
    load_custom_rules, save_custom_rules
)
from engine.mamf_generator import generate_mamf, compare_with_original

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(__file__), 'data')
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB

# In-memory cache for loaded data
_cache = {}


def get_excel_files():
    """Find all Excel files in the project directory and data folder."""
    files = []
    for pattern in ['*.xlsx', 'data/*.xlsx']:
        files.extend(glob.glob(os.path.join(os.path.dirname(__file__), pattern)))
    return sorted(files)


def load_data(filepath):
    """Load and cache Excel data."""
    if filepath in _cache:
        return _cache[filepath]
    data = read_excel_file(filepath)
    _cache[filepath] = data
    return data


@app.route('/')
def dashboard():
    """Main dashboard page."""
    files = get_excel_files()
    file_info = []
    for f in files:
        period = get_period_from_filename(f)
        file_info.append({
            'path': f,
            'name': os.path.basename(f),
            'period': period,
        })
    return render_template('dashboard.html', files=file_info)


@app.route('/upload', methods=['POST'])
def upload_file():
    """Upload a new Excel file."""
    if 'file' not in request.files:
        return jsonify({'error': 'Nenhum arquivo enviado'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Nenhum arquivo selecionado'}), 400

    if not file.filename.endswith('.xlsx'):
        return jsonify({'error': 'Apenas arquivos .xlsx são aceitos'}), 400

    filename = secure_filename(file.filename)
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

    return redirect(url_for('dashboard'))


@app.route('/analyze/<path:filename>')
def analyze(filename):
    """Analyze a specific Excel file - main analysis page."""
    filepath = _find_file(filename)
    if not filepath:
        return "Arquivo não encontrado", 404

    data = load_data(filepath)
    period = get_period_from_filename(filepath)

    # Categorize extrato
    categorized = categorize_extrato(
        data['extrato'],
        data['classificacao'] or {},
        data['dimensao_cash'] or {},
    )

    # Generate MAMF
    mamf = generate_mamf(categorized, period)

    # Compare with original
    month_col = 3  # Janeiro = col D (index 3)
    if period.get('month'):
        month_col = period['month'] + 2  # Dec=col C(2), Jan=col D(3), Feb=col E(4)
    comparison = compare_with_original(mamf, data['month_realizado'], month_col)

    # Reconciliation
    rec = reconcile(data['razao'], data['extrato'])
    rec_by_bank = reconcile_by_bank(data['razao'], data['extrato'], DE_PARA_CONTAS)

    return render_template('analysis.html',
        filename=filename,
        period=period,
        mamf=mamf,
        comparison=comparison,
        reconciliation=rec,
        rec_by_bank=rec_by_bank,
        categories=get_category_summary(categorized),
        extrato_count=len(data['extrato']) if data['extrato'] is not None else 0,
        razao_count=len(data['razao']) if data['razao'] is not None else 0,
    )


@app.route('/reconciliation/<path:filename>')
def reconciliation_detail(filename):
    """Detailed reconciliation view."""
    filepath = _find_file(filename)
    if not filepath:
        return "Arquivo não encontrado", 404

    data = load_data(filepath)
    rec = reconcile(data['razao'], data['extrato'])
    rec_by_bank = reconcile_by_bank(data['razao'], data['extrato'], DE_PARA_CONTAS)
    period = get_period_from_filename(filepath)

    return render_template('reconciliation.html',
        filename=filename,
        period=period,
        reconciliation=rec,
        rec_by_bank=rec_by_bank,
    )


@app.route('/categorization/<path:filename>')
def categorization_detail(filename):
    """Categorization management view."""
    filepath = _find_file(filename)
    if not filepath:
        return "Arquivo não encontrado", 404

    data = load_data(filepath)
    custom_rules = load_custom_rules()

    categorized = categorize_extrato(
        data['extrato'],
        data['classificacao'] or {},
        data['dimensao_cash'] or {},
        custom_rules,
    )

    categories = get_category_summary(categorized)

    # Get uncategorized or "Others" entries for review
    others = []
    if categorized is not None and not categorized.empty:
        cat_col = 'categoria_auto' if 'categoria_auto' in categorized.columns else 'classificacao'
        others_df = categorized[categorized[cat_col] == 'Others'].head(50)
        others = others_df[['banco', 'fornecedor', 'texto', 'valor_brl', 'entrada_saida']].to_dict('records')

    return render_template('categorization.html',
        filename=filename,
        period=get_period_from_filename(filepath),
        categories=categories,
        custom_rules=custom_rules,
        others=others,
    )


@app.route('/mamf/<path:filename>')
def mamf_detail(filename):
    """MAMF report detail view."""
    filepath = _find_file(filename)
    if not filepath:
        return "Arquivo não encontrado", 404

    data = load_data(filepath)
    period = get_period_from_filename(filepath)

    categorized = categorize_extrato(
        data['extrato'],
        data['classificacao'] or {},
        data['dimensao_cash'] or {},
    )

    mamf = generate_mamf(categorized, period)

    month_col = 3
    if period.get('month'):
        month_col = period['month'] + 2
    comparison = compare_with_original(mamf, data['month_realizado'], month_col)

    return render_template('mamf.html',
        filename=filename,
        period=period,
        mamf=mamf,
        comparison=comparison,
    )


@app.route('/api/custom-rules', methods=['GET', 'POST', 'DELETE'])
def api_custom_rules():
    """API for managing custom categorization rules."""
    if request.method == 'GET':
        return jsonify(load_custom_rules())

    if request.method == 'POST':
        data = request.get_json()
        pattern = data.get('pattern', '').strip()
        category = data.get('category', '').strip()
        if not pattern or not category:
            return jsonify({'error': 'Pattern e category são obrigatórios'}), 400

        rules = load_custom_rules()
        rules[pattern] = category
        save_custom_rules(rules)

        # Clear cache to force re-categorization
        _cache.clear()
        return jsonify({'success': True, 'rules': rules})

    if request.method == 'DELETE':
        data = request.get_json()
        pattern = data.get('pattern', '').strip()
        rules = load_custom_rules()
        if pattern in rules:
            del rules[pattern]
            save_custom_rules(rules)
            _cache.clear()
        return jsonify({'success': True, 'rules': rules})


@app.route('/api/reconciliation-detail/<path:filename>/<date>')
def api_reconciliation_detail(filename, date):
    """API to get detailed entries for a specific date."""
    from datetime import date as date_type
    filepath = _find_file(filename)
    if not filepath:
        return jsonify({'error': 'File not found'}), 404

    data = load_data(filepath)
    parts = date.split('-')
    target_date = date_type(int(parts[0]), int(parts[1]), int(parts[2]))
    detail = get_unmatched_entries(data['razao'], data['extrato'], target_date)
    return jsonify(detail)


def _find_file(filename):
    """Find the full path of a file by its basename."""
    for f in get_excel_files():
        if os.path.basename(f) == filename:
            return f
    base = os.path.dirname(__file__)
    full = os.path.join(base, filename)
    if os.path.exists(full):
        return full
    return None


def format_brl(value):
    """Format a number as BRL currency."""
    if value is None:
        return 'R$ 0,00'
    try:
        v = float(value)
        neg = v < 0
        v = abs(v)
        formatted = f"{v:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
        return f"-R$ {formatted}" if neg else f"R$ {formatted}"
    except (ValueError, TypeError):
        return 'R$ 0,00'


app.jinja_env.filters['brl'] = format_brl
app.jinja_env.filters['abs'] = abs


if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    app.run(debug=True, host='0.0.0.0', port=5000)
