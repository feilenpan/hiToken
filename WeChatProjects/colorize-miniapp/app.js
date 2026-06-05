// app.js - 时光修复
// 通过 wx.cloud.callContainer 云调用直连云托管，免域名配置、体验版可直接使用

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
    pendingRestore: null
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
  // 模式：CALL_CONTAINER = callContainer（体验版）| DIRECT = wx.request（开发版，需开启不校验域名）
  // 当前：DIRECT（callContainer 网关 INVALID_PATH，暂时绕过）

  BASE_URL: 'https://yushu-264118-8-1438528191.sh.run.tcloudbase.com',

  // 安全解析响应
  _parseResponse(res) {
    var data = res.data
    if (typeof data === 'string') {
      try { data = JSON.parse(data) } catch(e) { data = {} }
    }
    return { statusCode: res.statusCode, data: data }
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
          } else {
            resolve({ data: res.data })
          }
        },
        fail: reject
      })
    })
  },

  // 文件上传 — 先上传云存储，再传 file_url 给后端
  cloudUpload(path, filePath, extraData, noAuth) {
    var that = this
    return new Promise((resolve, reject) => {
      var cloudPath = 'uploads/' + Date.now() + '_' + Math.random().toString(36).slice(2, 8) + '.jpg'
      wx.cloud.uploadFile({
        cloudPath: cloudPath,
        filePath: filePath,
        success: function(uploadRes) {
          wx.cloud.getTempFileURL({
            fileList: [uploadRes.fileID],
            success: function(urlRes) {
              var fileUrl = urlRes.fileList[0].tempFileURL
              var data = Object.assign({ file_url: fileUrl }, extraData || {})
              that.cloudPost(path, data, noAuth).then(resolve).catch(reject)
            },
            fail: reject
          })
        },
        fail: reject
      })
    })
  },

  _getCloudHeaders() {
    var headers = {
      'content-type': 'application/json'
    }
    if (this.globalData.token) {
      headers['X-Auth-Token'] = this.globalData.token
    }
    return headers
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
      this.cloudUpload('/api/process?process_type=' + processType, filePath)
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
