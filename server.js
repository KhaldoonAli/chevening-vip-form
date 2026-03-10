const express = require('express');
const cors = require('cors');
const path = require('path');
const { scrapePhDs } = require('./scraper');
const { exportToExcel } = require('./exporter');

const app = express();
const PORT = process.env.PORT || 3000;

app.use(cors());
app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

// Store active scrape sessions (in-memory, keyed by sessionId)
const sessions = new Map();

// --- SSE progress endpoint ---
app.get('/api/scrape/progress/:sessionId', (req, res) => {
  const { sessionId } = req.params;
  res.setHeader('Content-Type', 'text/event-stream');
  res.setHeader('Cache-Control', 'no-cache');
  res.setHeader('Connection', 'keep-alive');

  const send = (data) => res.write(`data: ${JSON.stringify(data)}\n\n`);

  // If session already has results (completed), send immediately
  const session = sessions.get(sessionId);
  if (session?.status === 'done') {
    send({ status: 'done', found: session.results.length, sessionId });
    return res.end();
  }

  // Register listener
  sessions.set(sessionId, { ...(sessions.get(sessionId) || {}), listener: send, res });

  req.on('close', () => {
    const s = sessions.get(sessionId);
    if (s) { s.listener = null; s.res = null; }
  });
});

// --- Start scrape endpoint ---
app.post('/api/scrape', async (req, res) => {
  const { keyword = 'architecture', maxPages = 5 } = req.body;
  const sessionId = Date.now().toString(36) + Math.random().toString(36).slice(2);

  // Init session
  sessions.set(sessionId, { status: 'running', results: [], keyword });
  res.json({ sessionId });

  // Run scrape asynchronously
  (async () => {
    try {
      const { results } = await scrapePhDs(keyword, Math.min(parseInt(maxPages) || 5, 10), (progress) => {
        const s = sessions.get(sessionId);
        if (s?.listener) s.listener({ ...progress, sessionId });
      });

      sessions.set(sessionId, { status: 'done', results, keyword });
      const s = sessions.get(sessionId);
      if (s?.listener) s.listener({ status: 'done', found: results.length, sessionId });
    } catch (err) {
      sessions.set(sessionId, { status: 'error', error: err.message, results: [] });
      const s = sessions.get(sessionId);
      if (s?.listener) s.listener({ status: 'error', message: err.message, sessionId });
    }
  })();
});

// --- Get results ---
app.get('/api/results/:sessionId', (req, res) => {
  const session = sessions.get(req.params.sessionId);
  if (!session) return res.status(404).json({ error: 'Session not found' });
  if (session.status !== 'done') return res.status(202).json({ status: session.status });
  res.json({ results: session.results, total: session.results.length });
});

// --- Download Excel ---
app.get('/api/download/:sessionId', async (req, res) => {
  const session = sessions.get(req.params.sessionId);
  if (!session || session.status !== 'done') {
    return res.status(404).json({ error: 'Results not ready' });
  }

  try {
    const buffer = await exportToExcel(session.results, session.keyword);
    const filename = `phd-${session.keyword.replace(/\s+/g, '-')}-${new Date().toISOString().slice(0, 10)}.xlsx`;
    res.setHeader('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
    res.setHeader('Content-Disposition', `attachment; filename="${filename}"`);
    res.send(buffer);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.listen(PORT, () => {
  console.log(`PhD Scraper running at http://localhost:${PORT}`);
});
