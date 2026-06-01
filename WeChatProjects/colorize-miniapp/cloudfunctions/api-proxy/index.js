// 云函数：api-proxy — HTTP 转发到云托管
const API_BASE = 'https://yushu-264118-8-1438528191.sh.run.tcloudbase.com'
const got = require('got')

exports.main = async (event) => {
  const { path, method = 'POST', data, headers } = event

  const resp = await got(API_BASE + path, {
    method,
    headers: headers || { 'content-type': 'application/json' },
    json: method === 'GET' ? undefined : data,
    searchParams: method === 'GET' ? data : undefined,
    timeout: { request: 120000 },
    responseType: 'json',
    throwHttpErrors: false
  })

  return { statusCode: resp.statusCode, data: resp.body }
}
