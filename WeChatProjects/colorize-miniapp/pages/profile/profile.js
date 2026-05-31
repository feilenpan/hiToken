// pages/profile/profile.js
const app = getApp()

// 判断是否为后端自动生成的默认昵称（如 "用戶oNuo"）
function isDefaultNickname(name) {
  if (!name) return true
  return /^用戶[a-zA-Z0-9]{4}$/.test(name)
}

Page({
  data: {
    nickname: '',
    avatarUrl: '',
    totalUsed: 0,
    quota: null
  },

  onShow() {
    var that = this
    var loginPromise = app._loginReady || Promise.resolve()
    loginPromise.then(function() {
      that.loadUserInfo()
    })
    this.fetchQuota()
  },

  loadUserInfo() {
    var that = this
    var cached = app.globalData.userInfo
    if (cached && cached.nickname) {
      var nick = isDefaultNickname(cached.nickname) ? '' : cached.nickname
      that.setData({
        nickname: nick,
        avatarUrl: cached.avatar || '',
        totalUsed: cached.total_used || 0
      })
    }
    app.cloudGet('/api/user/info').then(function(res) {
      if (res.data && res.data.success && res.data.user) {
        var nick = res.data.user.nickname || ''
        if (isDefaultNickname(nick)) nick = ''
        that.setData({
          nickname: nick,
          avatarUrl: res.data.user.avatar || '',
          totalUsed: res.data.user.total_used || 0
        })
      }
    }).catch(function() {})
  },

  fetchQuota() {
    var that = this
    app.cloudGet('/api/user/usage').then(function(res) {
      if (res.data && res.data.success) {
        that.setData({ quota: res.data.quota })
      }
    }).catch(function() {})
  },

  onChooseAvatar(e) {
    var that = this
    var avatarPath = e.detail.avatarUrl
    if (!avatarPath) return
    that.setData({ avatarUrl: avatarPath })

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
              nickname: resp.data.user.nickname || ''
            })
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

  onNicknameBlur(e) {
    var nickname = (e.detail.value || '').trim()
    if (!nickname || nickname === this.data.nickname) return
    var that = this
    app.cloudPost('/api/user/profile', { nickname: nickname })
      .then(function(resp) {
        if (resp.data && resp.data.success) {
          wx.showToast({ title: '昵称已更新', icon: 'success' })
          if (resp.data.user) {
            app.globalData.userInfo = resp.data.user
            wx.setStorageSync('userInfo', resp.data.user)
          }
        }
      })
      .catch(function() {
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
