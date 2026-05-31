// pages/profile/profile.js
const app = getApp()

Page({
  data: {
    nickname: '时光用户',
    totalUsed: 0,
    quota: null
  },

  onShow() {
    this.loadUserInfo()
    this.fetchQuota()
  },

  loadUserInfo() {
    var that = this
    app.cloudGet('/api/user/info').then(function(res) {
      if (res.data && res.data.success && res.data.user) {
        that.setData({
          nickname: res.data.user.nickname || '时光用户',
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

  onShareAppMessage() {
    return {
      title: '时光修复 - AI 智能修复老照片',
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
