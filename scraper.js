const axios = require('axios');
const cheerio = require('cheerio');

const BASE_URL = 'https://www.findaphd.com';

const HEADERS = {
  'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
  'Accept': 'text/html,application/xhtml+xml,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
  'Accept-Language': 'en-GB,en;q=0.5',
  'Accept-Encoding': 'gzip, deflate, br',
  'Connection': 'keep-alive',
  'Upgrade-Insecure-Requests': '1',
};

async function fetchPage(url, retries = 3) {
  for (let attempt = 1; attempt <= retries; attempt++) {
    try {
      const response = await axios.get(url, {
        headers: HEADERS,
        timeout: 15000,
        maxRedirects: 5,
      });
      return response.data;
    } catch (err) {
      if (attempt === retries) throw err;
      await new Promise(r => setTimeout(r, attempt * 1500));
    }
  }
}

function parseListings(html) {
  const $ = cheerio.load(html);
  const results = [];

  // FindAPhD listing cards
  $('.phd-result--key-info, .ResultsRow, [class*="phd-result"]').each((_, el) => {
    const card = $(el);
    const titleEl = card.find('h3 a, h4 a, .title a, a[href*="/phds/"]').first();
    const title = titleEl.text().trim();
    const relHref = titleEl.attr('href') || '';
    const link = relHref.startsWith('http') ? relHref : BASE_URL + relHref;

    if (!title) return;

    const university = card.find('.phd-result__dept--university, [class*="university"], .institution').first().text().trim()
      || card.find('a[href*="/universities/"]').first().text().trim();

    const department = card.find('.phd-result__dept--department, [class*="department"]').first().text().trim();

    const supervisor = card.find('.phd-result__supervisor, [class*="supervisor"]').first().text().trim();

    const deadline = card.find('[class*="deadline"], .closing-date').first().text().trim().replace(/deadline:?/i, '').trim();

    const funding = card.find('[class*="funding"], .funded').first().text().trim();

    const location = card.find('[class*="location"], .country').first().text().trim();

    const description = card.find('.phd-result__description, [class*="description"], p').first().text().trim().slice(0, 300);

    results.push({ title, university, department, supervisor, deadline, funding, location, description, link });
  });

  return results;
}

function buildSearchUrl(keyword, page = 1) {
  const encoded = encodeURIComponent(keyword);
  // FindAPhD search URL structure
  return `${BASE_URL}/phds/?Keywords=${encoded}&PG=${page}`;
}

function getTotalPages($) {
  // Try to get total pages from pagination
  const paginationText = $('[class*="pagination"], .pager').text();
  const match = paginationText.match(/Page\s+\d+\s+of\s+(\d+)/i) || paginationText.match(/(\d+)\s*$/);
  if (match) return Math.min(parseInt(match[1]), 10); // cap at 10 pages

  // Count page links
  const pageLinks = $('[class*="pagination"] a, .pager a').length;
  return pageLinks > 0 ? Math.min(pageLinks, 10) : 1;
}

async function scrapePhDs(keyword = 'architecture', maxPages = 5, progressCallback = null) {
  const allResults = [];
  let page = 1;
  let totalPages = 1;

  do {
    const url = buildSearchUrl(keyword, page);
    if (progressCallback) progressCallback({ status: 'scraping', page, totalPages, found: allResults.length, url });

    let html;
    try {
      html = await fetchPage(url);
    } catch (err) {
      console.error(`Failed to fetch page ${page}: ${err.message}`);
      break;
    }

    const $ = cheerio.load(html);

    if (page === 1) {
      totalPages = Math.min(getTotalPages($), maxPages);
    }

    const listings = parseListings(html);

    // Fallback: try broader selectors if nothing matched
    if (listings.length === 0 && page === 1) {
      $('a[href*="/phds/"]').each((_, el) => {
        const a = $(el);
        const href = a.attr('href') || '';
        // Only actual PhD detail pages (not search/category pages)
        if (!href.match(/\/phds\/[^?]+\?/i) && !href.match(/\/phds\/\?/)) return;
        const title = a.text().trim();
        if (!title || title.length < 10) return;
        const link = href.startsWith('http') ? href : BASE_URL + href;
        const parent = a.closest('[class]');
        const university = parent.find('[class*="univ"], [class*="inst"]').first().text().trim();
        allResults.push({ title, university, department: '', supervisor: '', deadline: '', funding: '', location: '', description: '', link });
      });
    } else {
      allResults.push(...listings);
    }

    page++;
    if (page <= totalPages) await new Promise(r => setTimeout(r, 800)); // polite delay
  } while (page <= totalPages);

  return { results: allResults, totalPages, keyword };
}

module.exports = { scrapePhDs, buildSearchUrl };
