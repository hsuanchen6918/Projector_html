const express = require('express');
const axios = require('axios');
const cheerio = require('cheerio');
const cors = require('cors');

const app = express();
app.use(cors());

// 模擬真實瀏覽器標頭，避免被封鎖
const headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
};

// 搜尋 API
app.get('/api/search', async (req, res) => {
    const { q } = req.query; // 搜尋關鍵字
    const searchUrl = `https://www.projectorcentral.com/projectors.cfm?g=2&q=${encodeURIComponent(q)}`;

    try {
        const response = await axios.get(searchUrl, { headers });
        const $ = cheerio.load(response.data);
        const projectors = [];

        // 解析 ProjectorCentral 的搜尋結果列表 (需根據該站實際 HTML 結構調整)
        $('tr').each((i, el) => {
            const name = $(el).find('h3').text().trim();
            const link = $(el).find('a').attr('href');
            const specs = $(el).find('.specs').text().trim(); // 假設規格在此 class

            if (name) {
                projectors.push({
                    name,
                    url: `https://www.projectorcentral.com${link}`,
                    specs: specs
                });
            }
        });

        res.json(projectors);
    } catch (error) {
        res.status(500).json({ error: '無法抓取資料', details: error.message });
    }
});

app.listen(3000, () => console.log('後端伺服器運行在 http://localhost:3000'));