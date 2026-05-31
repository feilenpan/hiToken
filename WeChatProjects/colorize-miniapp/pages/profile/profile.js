// pages/profile/profile.js
const app = getApp()

Page({
  data: {
    nickname: '时光用户',
    avatarUrl: '',
    totalUsed: 0,
    quota: null
  },

  onShow() {
    // 等待自动登录完成再加载用户信息
    var that = this
    var loginPromise = app._loginReady || Promise.resolve()
    loginPromise.then(function() {
      that.loadUserInfo()
    })
    this.fetchQuota()
  },

  loadUserInfo() {
    var that = this
    // 优先用缓存
    var cached = app.globalData.userInfo
    if (cached && cached.nickname) {
      that.setData({
        nickname: cached.nickname,
        avatarUrl: cached.avatar || '',
        totalUsed: cached.total_used || 0
      })
    }
    app.cloudGet('/api/user/info').then(function(res) {
      if (res.data && res.data.success && res.data.user) {
        that.setData({
          nickname: res.data.user.nickname || '时光用户',
          avatarUrl: res.data.user.avatar || '',
          totalUsed: res.data.user.total_used || 0
        })
      } else {
        that.setData({
          totalUsed: app.globalData.totalUsed || 0
        })
      }
    }).catch(function() {
      that.setData({
        totalUsed: app.globalData.totalUsed || 0
      })
    })
  },

  fetchQuota() {
    var that = this
    app.cloudGet('/api/user/usage').then(function(res) {
      if (res.data && res.data.success) {
        that.setData({ quota: res.data.quota })
      }
    }).catch(function() {})
  },

  // 用户选择头像
  onChooseAvatar(e) {
    var that = this
    var avatarPath = e.detail.avatarUrl
    if (!avatarPath) return

    // 先本地预览
    that.setData({ avatarUrl: avatarPath })

    // 上传到后端
    wx.getFileSystemManager().readFile({
      filePath: avatarPath,
      encoding: 'base64',
      success: function(readRes) {
        app.cloudPost('/api/user/profile', {
          avatar: readRes.data
        }).then(function(resp) {
          if (resp.data && resp.data.success && resp.data.user) {
            that.setData({
              avatarUrl: resp.data.user.avatar || avatarPath,
              nickname: resp.data.user.nickname || that.data.nickname
            })
            // 更新全局缓存
            app.globalData.userInfo = resp.data.user
            wx.setStorageSync('userInfo', resp.data.user)
            wx.showToast({ title: '头像已更新', icon: 'success' })
          }
        }).catch(function() {
          wx.showToast({ title: '上传失败，请重试', icon: 'none' })
        })
      },
      fail: function() {
        wx.showToast({ title: '读取头像失败', icon: 'none' })
      }
    })
  },

  // 用户修改昵称（失焦时保存）
  onNicknameBlur(e) {
    var nickname = (e.detail.value || '').trim()
    if (!nickname || nickname === this.data.nickname) return

    var that = this
    app.cloudPost('/api/user/profile', {
      nickname: nickname
    }).then(function(resp) {
      if (resp.data && resp.data.success) {
        wx.showToast({ title: '昵称已更新', icon: 'success' })
        // 更新全局缓存
        if (resp.data.user) {
          app.globalData.userInfo = resp.data.user
          wx.setStorageSync('userInfo', resp.data.user)
        }
      }
    }).catch(function() {
      // 失败时恢复旧昵称
      that.setData({ nickname: that.data.nickname })
      wx.showToast({ title: '保存失败', icon: 'none' })
    })
  },

  onShareAppMessage() {
    return {
      title: '时光修复 - AI 照片点评与修复',
      path: '/pages/score/score'
    }
  },

  goPrivacy() {
    wx.navigateTo({ url: '/pkg-legal/pages/privacy/privacy' })
  },

  goAgreement() {
    wx.navigateTo({ url: '/pkg-legal/pages/agreement/agreement' })
  },

  requestDataDeletion() {
    wx.showModal({
      title: '确认删除',
      content: '删除后您的所有数据将被清除，此操作不可恢复。',
      confirmColor: '#FF4D4F',
      success: (res) => {
        if (res.confirm) {
          app.requestDataDeletion().then(() => {
            wx.showToast({ title: '已提交申请', icon: 'success' })
          }).catch(() => {
            wx.showToast({ title: '提交失败', icon: 'error' })
          })
        }
      }
    })
  },

  contactSupport() {
    wx.showModal({
      title: '联系客服',
      content: '如有问题，请发送邮件至 yushutec@gmail.com',
      showCancel: false
    })
  }
})
