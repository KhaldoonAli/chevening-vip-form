const ExcelJS = require('exceljs');

async function exportToExcel(results, keyword = 'architecture') {
  const workbook = new ExcelJS.Workbook();
  workbook.creator = 'PhD Scholarship Scraper';
  workbook.created = new Date();

  const sheet = workbook.addWorksheet('PhD Scholarships', {
    views: [{ state: 'frozen', ySplit: 1 }],
  });

  // --- Column definitions ---
  sheet.columns = [
    { header: '#',            key: 'num',         width: 5  },
    { header: 'Title',        key: 'title',       width: 55 },
    { header: 'University',   key: 'university',  width: 35 },
    { header: 'Department',   key: 'department',  width: 30 },
    { header: 'Supervisor',   key: 'supervisor',  width: 25 },
    { header: 'Funding',      key: 'funding',     width: 20 },
    { header: 'Deadline',     key: 'deadline',    width: 18 },
    { header: 'Location',     key: 'location',    width: 20 },
    { header: 'Description',  key: 'description', width: 60 },
    { header: 'Link',         key: 'link',        width: 50 },
  ];

  // --- Header styling ---
  const headerRow = sheet.getRow(1);
  headerRow.height = 22;
  headerRow.eachCell(cell => {
    cell.fill   = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FF1A3C5E' } };
    cell.font   = { bold: true, color: { argb: 'FFFFFFFF' }, size: 11 };
    cell.alignment = { vertical: 'middle', horizontal: 'center', wrapText: true };
    cell.border = {
      bottom: { style: 'medium', color: { argb: 'FF0D2137' } },
    };
  });

  // --- Data rows ---
  results.forEach((item, idx) => {
    const row = sheet.addRow({
      num:         idx + 1,
      title:       item.title       || '',
      university:  item.university  || '',
      department:  item.department  || '',
      supervisor:  item.supervisor  || '',
      funding:     item.funding     || '',
      deadline:    item.deadline    || '',
      location:    item.location    || '',
      description: item.description || '',
      link:        item.link        || '',
    });

    row.height = 18;

    // Zebra striping
    const bg = idx % 2 === 0 ? 'FFEAF1FB' : 'FFFFFFFF';
    row.eachCell({ includeEmpty: true }, cell => {
      cell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: bg } };
      cell.alignment = { vertical: 'middle', wrapText: true };
      cell.font = { size: 10 };
    });

    // Make link cell a hyperlink
    if (item.link) {
      const linkCell = row.getCell('link');
      linkCell.value = { text: 'View PhD', hyperlink: item.link };
      linkCell.font = { size: 10, color: { argb: 'FF1155CC' }, underline: true };
    }

    // Highlight funded rows
    const fundingCell = row.getCell('funding');
    const fundingText = (item.funding || '').toLowerCase();
    if (fundingText.includes('funded') || fundingText.includes('scholarship') || fundingText.includes('stipend')) {
      fundingCell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FFD4EDDA' } };
      fundingCell.font = { size: 10, bold: true, color: { argb: 'FF155724' } };
    }
  });

  // --- Auto-filter ---
  sheet.autoFilter = {
    from: { row: 1, column: 1 },
    to:   { row: 1, column: sheet.columns.length },
  };

  // --- Summary sheet ---
  const summary = workbook.addWorksheet('Summary');
  summary.getColumn(1).width = 30;
  summary.getColumn(2).width = 40;

  const summaryData = [
    ['Search Keyword',   keyword],
    ['Total Results',    results.length],
    ['Scraped On',       new Date().toLocaleString()],
    ['Source',          'https://www.findaphd.com'],
    ['', ''],
    ['Universities Found', [...new Set(results.map(r => r.university).filter(Boolean))].length],
  ];

  summaryData.forEach(([label, value]) => {
    const row = summary.addRow([label, value]);
    row.getCell(1).font = { bold: true };
  });

  const buffer = await workbook.xlsx.writeBuffer();
  return buffer;
}

module.exports = { exportToExcel };
