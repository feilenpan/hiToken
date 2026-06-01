// app.js - 时光修复
// 通过微信云调用直连云托管，不走公网域名

wx.cloud.init({
  env: 'yushu-264118-8'
})

App({
  globalData: {
    envId: 'yushu-264118-8',
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

  // GET 请求
  cloudGet(path) {
    var that = this
    return new Promise((resolve, reject) => {
      wx.cloud.callContainer({
        path: path,
        method: 'GET',
        header: that._getHeaders(),
        success: (res) => resolve({ data: res.data }),
        fail: reject
      })
    })
  },

  // POST JSON 请求
  cloudPost(path, data) {
    var that = this
    return new Promise((resolve, reject) => {
      wx.cloud.callContainer({
        path: path,
        method: 'POST',
        header: that._getHeaders(),
        data: data,
        timeout: 120000,
        success: (res) => {
          if (res.statusCode === 429) {
            wx.showToast({ title: res.data.detail || '今日次数已用完', icon: 'none', duration: 2500 })
            reject(new Error('QUOTA_EXCEEDED'))
          } else {
            resolve({ data: res.data })
          }
        },
        fail: reject
      })
    })
  },

  // 文件上传（base64 方式）
  cloudUpload(path, filePath, extraData) {
    var that = this
    return new Promise((resolve, reject) => {
      var fs = wx.getFileSystemManager()
      try {
        var base64 = fs.readFileSync(filePath, 'base64')
        var data = Object.assign({ file: base64 }, extraData || {})
        that.cloudPost(path, data).then(resolve).catch(reject)
      } catch(e) {
        reject(new Error('文件读取失败: ' + (e.message || e)))
      }
    })
  },

  _getHeaders() {
    var headers = { 'content-type': 'application/json' }
    if (this.globalData.token) {
      headers['Authorization'] = 'Bearer ' + this.globalData.token
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
