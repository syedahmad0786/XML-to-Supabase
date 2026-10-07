const axios = require('axios');
const cheerio = require('cheerio');

(async () => {
  const tests = [
    { name: 'ProductHunt AI', url: 'https://www.producthunt.com/topics/artificial-intelligence' },
    { name: 'BuiltIn AI', url: 'https://builtin.com/artificial-intelligence' },
    { name: 'TopAI.tools', url: 'https://topai.tools/' },
    { name: 'Futurepedia', url: 'https://www.futurepedia.io/' },
    { name: 'There is an AI', url: 'https://theresanaiforthat.com/' },
    { name: 'AlternativeTo', url: 'https://alternativeto.net/category/business-and-commerce/artificial-intelligence/' },
    { name: 'SaaSHub AI', url: 'https://www.saashub.com/best-artificial-intelligence-software' },
    { name: 'GitHub AI topic', url: 'https://github.com/topics/artificial-intelligence' },
  ];

  for (const t of tests) {
    try {
      const r = await axios.get(t.url, {
        timeout: 10000,
        headers: { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36' },
        maxRedirects: 5,
      });
      const $ = cheerio.load(r.data);
      console.log(t.name + ': ' + r.status + ' (' + r.data.length + ' bytes)');
      const title = $('title').text().trim().slice(0, 80);
      console.log('  Title: ' + title);

      // Count links and headings
      const links = $('a[href]').length;
      const headings = $('h2, h3').length;
      console.log('  Links: ' + links + ' | Headings: ' + headings);

      // Show first few meaningful headings
      $('h2, h3').slice(0, 5).each((_, el) => {
        const text = $(el).text().trim().slice(0, 70);
        if (text) console.log('  H: ' + text);
      });
      console.log();
    } catch (err) {
      console.log(t.name + ': ERROR - ' + (err.response?.status || err.message?.slice(0, 60)));
      console.log();
    }
  }
})();
