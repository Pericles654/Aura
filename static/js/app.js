// Aura CashFlow - Frontend JS

document.addEventListener('DOMContentLoaded', function() {
    // Highlight current nav link
    const path = window.location.pathname;
    document.querySelectorAll('.nav-links a').forEach(function(link) {
        if (link.getAttribute('href') === path) {
            link.style.background = 'rgba(255,255,255,0.2)';
            link.style.color = 'white';
        }
    });

    // Add sorting to tables
    document.querySelectorAll('.data-table th').forEach(function(th) {
        th.style.cursor = 'pointer';
        th.addEventListener('click', function() {
            sortTable(this);
        });
    });
});

function sortTable(header) {
    var table = header.closest('table');
    var tbody = table.querySelector('tbody');
    if (!tbody) return;

    var rows = Array.from(tbody.querySelectorAll('tr'));
    var colIndex = Array.from(header.parentElement.children).indexOf(header);
    var ascending = header.dataset.sort !== 'asc';

    rows.sort(function(a, b) {
        var aCell = a.cells[colIndex];
        var bCell = b.cells[colIndex];
        if (!aCell || !bCell) return 0;

        var aVal = aCell.textContent.trim().replace(/[R$\s.]/g, '').replace(',', '.');
        var bVal = bCell.textContent.trim().replace(/[R$\s.]/g, '').replace(',', '.');

        var aNum = parseFloat(aVal);
        var bNum = parseFloat(bVal);

        if (!isNaN(aNum) && !isNaN(bNum)) {
            return ascending ? aNum - bNum : bNum - aNum;
        }
        return ascending
            ? aVal.localeCompare(bVal, 'pt-BR')
            : bVal.localeCompare(aVal, 'pt-BR');
    });

    // Reset all sort indicators
    header.parentElement.querySelectorAll('th').forEach(function(th) {
        delete th.dataset.sort;
    });
    header.dataset.sort = ascending ? 'asc' : 'desc';

    rows.forEach(function(row) { tbody.appendChild(row); });
}

function formatBRL(value) {
    if (value === null || value === undefined) return 'R$ 0,00';
    var neg = value < 0;
    var v = Math.abs(value);
    var formatted = v.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    return (neg ? '-R$ ' : 'R$ ') + formatted;
}
