// app.js - 时光修复
// 正式版：wx.request/uploadFile 直连自定义域名 yushucolor.cn（ICP备案已完成）

wx.cloud.init({
  env: 'yushucolor-d6gd4kytb9000e446',
  traceUser: true
})

App({
  globalData: {
    envId: 'yushucolor-d6gd4kytb9000e446',
    userInfo: null,
    token: null,
    totalUsed: 0,
    agreementAgreed: false,
    pendingRestore: null,
    pendingScoreImage: null,
    quota: null   // 全局配额缓存，操作后立即更新
  },

  // 同步全局配额（每次 consume quota 后调用）
  syncQuota: function(newQuota) {
    if (newQuota) {
      this.globalData.quota = newQuota
    }
  },

  // 从后端拉取最新配额并更新全局缓存
  fetchAndSyncQuota: function() {
    var that = this
    return this.cloudGet('/api/user/usage').then(function(res) {
      if (res.data && res.data.success) {
        that.globalData.quota = res.data.quota
      }
      return that.globalData.quota
    }).catch(function() {
      return that.globalData.quota
    })
  },

  onLaunch() {
    const token = wx.getStorageSync('token') || ''
    const userInfo = wx.getStorageSync('userInfo') || {}
    if (token && userInfo) {
      this.globalData.token = token
      this.globalData.userInfo = userInfo
      this.globalData.totalUsed = userInfo.total_used || 0
      this.globalData.agreementAgreed = userInfo.agreement_agreed || false
    }

    // 自动登录，返回 Promise 供页面等待
    this._loginReady = this._autoLogin()

    // 隐私授权全局监听
    var that = this
    if (wx.onNeedPrivacyAuthorization) {
      wx.onNeedPrivacyAuthorization(function(resolve, eventInfo) {
        // 新版基础库：open-type="agreePrivacyAuthorization" 按钮会自动 resolve
        // 这里只负责显示弹窗，不再手动存 resolve
        that.globalData._showPrivacyPopup = true
        var pages = getCurrentPages()
        if (pages.length > 0) {
          var page = pages[pages.length - 1]
          if (page.setData) {
            page.setData({ showPrivacyPopup: true })
          }
        }
      })
    }
  },

  // 用户同意隐私协议（由 agreePrivacyAuthorization 按钮自动触发）
  handleAgreePrivacy() {
    this.globalData._showPrivacyPopup = false
  },

  // 打开隐私协议
  openPrivacyContract() {
    wx.openPrivacyContract({})
  },

  // 隐私授权检查（在调用隐私接口前调用）
  requirePrivacy(callback) {
    var that = this
    if (wx.requirePrivacyAuthorize) {
      wx.requirePrivacyAuthorize({
        success: function() { callback() },
        fail: function() { wx.showToast({ title: '需要同意隐私协议', icon: 'none' }) }
      })
    } else {
      callback()
    }
  },

  // === HTTP 请求封装 ===
  // 模式：wx.request/uploadFile 直连自定义域名 yushucolor.cn（备案已完成）
  // callContainer 网关 INVALID_PATH 已弃用

  BASE_URL: 'https://www.yushucolor.cn',

  // 安全解析响应
  _parseResponse(res) {
    var data = res.data
    if (typeof data === 'string') {
      try { data = JSON.parse(data) } catch(e) { data = {} }
    }
    return { statusCode: res.statusCode, data: data }
  },

  // 构建认证 header
  _getCloudHeaders() {
    var headers = { 'content-type': 'application/json' }
    if (this.globalData.token) {
      headers['X-Auth-Token'] = this.globalData.token
    }
    return headers
  },

  // GET 请求
  cloudGet(path, noAuth) {
    var that = this
    return new Promise((resolve, reject) => {
      wx.request({
        url: that.BASE_URL + path,
        method: 'GET',
        header: noAuth ? {} : that._getCloudHeaders(),
        success: (res) => resolve({ data: res.data }),
        fail: reject
      })
    })
  },

  // POST JSON 请求
  cloudPost(path, data, noAuth) {
    var that = this
    return new Promise((resolve, reject) => {
      wx.request({
        url: that.BASE_URL + path,
        method: 'POST',
        data: data,
        header: noAuth ? { 'content-type': 'application/json' } : that._getCloudHeaders(),
        timeout: 120000,
        success: (res) => {
          if (res.statusCode === 429) {
            wx.showToast({ title: (res.data && res.data.detail) || '今日次数已用完', icon: 'none', duration: 2500 })
            reject(new Error('QUOTA_EXCEEDED'))
          } else if (res.statusCode === 503) {
            wx.showToast({ title: '服务繁忙，请明天再来～', icon: 'none', duration: 2500 })
            reject(new Error('GLOBAL_LIMIT'))
          } else {
            resolve({ data: res.data })
          }
        },
        fail: reject
      })
    })
  },

  // 文件上传 — 直传后端 multipart/form-data，不经过云存储
  cloudUpload(path, filePath, extraData, noAuth) {
    var that = this
    return new Promise((resolve, reject) => {
      wx.uploadFile({
        url: that.BASE_URL + path,
        filePath: filePath,
        name: 'file',
        formData: extraData || {},
        header: noAuth ? {} : { 'X-Auth-Token': that.globalData.token || '' },
        timeout: 300000,
        success: function(res) {
          if (res.statusCode === 429) {
            var detail = ''
            try { detail = JSON.parse(res.data).detail || '' } catch(e) {}
            wx.showToast({ title: detail || '今日次数已用完', icon: 'none', duration: 2500 })
            reject(new Error('QUOTA_EXCEEDED'))
          } else if (res.statusCode === 503) {
            wx.showToast({ title: '服务繁忙，请明天再来～', icon: 'none', duration: 2500 })
            reject(new Error('GLOBAL_LIMIT'))
          } else {
            var data = res.data
            if (typeof data === 'string') {
              try { data = JSON.parse(data) } catch(e) { data = {} }
            }
            resolve({ data: data })
          }
        },
        fail: reject
      })
    })
  },

  // === 业务方法 ===

  login() {
    return new Promise((resolve, reject) => {
      wx.login({
        success: (res) => {
          if (res.code) {
            this.cloudPost('/api/wechat/login', { code: res.code })
              .then((response) => {
                if (response.data.success) {
                  const { token, user } = response.data
                  this.globalData.token = token
                  this.globalData.userInfo = user
                  this.globalData.totalUsed = user.total_used || 0
                  this.globalData.agreementAgreed = user.agreement_agreed || false
                  wx.setStorageSync('token', token)
                  wx.setStorageSync('userInfo', user)
                  resolve(user)
                } else {
                  reject(new Error(response.data.message || '登录失败'))
                }
              })
              .catch(reject)
          } else {
            reject(new Error('获取code失败'))
          }
        },
        fail: reject
      })
    })
  },

  // 静默自动登录，返回 Promise
  _autoLogin() {
    var that = this
    return this.login().then(function(user) {
      console.log('自动登录成功:', user.nickname)
      return user
    }).catch(function(err) {
      console.log('自动登录跳过:', err.message || err)
      return null
    })
  },

  agreeAgreement() {
    return new Promise((resolve) => {
      this.globalData.agreementAgreed = true
      wx.setStorageSync('agreementAgreed', true)
      this.cloudPost('/api/user/agree-agreement', {})
        .then(() => {
          const userInfo = wx.getStorageSync('userInfo') || {}
          userInfo.agreement_agreed = true
          wx.setStorageSync('userInfo', userInfo)
          resolve()
        })
        .catch(() => resolve())
    })
  },

  agreePrivacy() { return Promise.resolve() },
  checkAgreements() {
    return {
      agreement: this.globalData.agreementAgreed || wx.getStorageSync('agreementAgreed') || false
    }
  },

  processImage(filePath, processType) {
    return new Promise((resolve, reject) => {
      this.cloudUpload('/api/process', filePath, { function: processType })
        .then((response) => {
          if (response.data.success) {
            this.globalData.totalUsed++
            resolve(response.data)
          } else {
            reject(new Error(response.data.message || '处理失败'))
          }
        })
        .catch(reject)
    })
  },

  getUserInfo() {
    return new Promise((resolve, reject) => {
      this.cloudGet('/api/user/info')
        .then((res) => {
          if (res.data.success) {
            const user = res.data.user
            this.globalData.totalUsed = user.total_used || 0
            this.globalData.agreementAgreed = user.agreement_agreed || false
            wx.setStorageSync('userInfo', user)
            resolve(user)
          } else {
            reject(new Error('获取用户信息失败'))
          }
        })
        .catch(reject)
    })
  },

  requestDataDeletion() {
    return new Promise((resolve, reject) => {
      this.cloudPost('/api/user/request-deletion', {})
        .then((res) => {
          if (res.data.success) resolve(res.data)
          else reject(new Error(res.data.message || '申请失败'))
        })
        .catch(reject)
    })
  }
})
