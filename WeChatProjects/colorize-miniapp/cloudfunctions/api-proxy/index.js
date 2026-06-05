// 云函数：api-proxy — HTTP 转发到云托管
const https = require('https');

exports.main = async (event) => {
  const { path, method = 'POST', data, headers } = event;
  return new Promise((resolve, reject) => {
    const body = method === 'GET' ? undefined : JSON.stringify(data);
    const req = https.request({
      hostname: 'yushu-264118-8-1438528191.sh.run.tcloudbase.com',
      port: 443,
      path: path,
      method: method,
      headers: headers || { 'content-type': 'application/json' },
      timeout: 120000
    }, res => {
      let raw = '';
      res.on('data', c => raw += c);
      res.on('end', () => {
        try {
          resolve({ statusCode: res.statusCode, data: JSON.parse(raw) });
        } catch (_) {
          resolve({ statusCode: res.statusCode, data: raw });
        }
      });
    });
    req.on('error', reject);
    if (body) req.write(body);
    req.end();
  });
};
