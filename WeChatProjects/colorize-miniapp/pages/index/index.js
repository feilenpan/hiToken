// pages/index/index.js
const app = getApp()

Page({
  data: {
    showAgreementModal: false,
    agreementChecked: false,
    heroImage: '/static/images/demo/hero_compare.png',
    showPrivacyPopup: false
  },

  onLoad() {
    this.checkAgreement()
  },

  // 隐私授权回调
  handleAgreePrivacy: function() {
    this.setData({ showPrivacyPopup: false })
    app.handleAgreePrivacy()
  },
  handleOpenPrivacyContract: function() {
    app.openPrivacyContract()
  },
  showPrivacyPopup: function() {
    this.setData({ showPrivacyPopup: true })
  },

  onShow() {
    var pending = app.globalData.pendingRestore
    if (pending) {
      app.globalData.pendingRestore = null
      var that = this
      wx.showModal({
        title: 'AI 建议',
        content: '使用建议「' + pending.label + '」进行修复\n\n请选择照片开始',
        confirmText: '选择照片',
        cancelText: '稍后',
        success: function(res) {
          if (res.confirm) {
            app.globalData.pendingRestore = pending
            that.onChooseImage()
          }
        }
      })
    }
  },

  checkAgreement() {
    const agreed = wx.getStorageSync('agreementAgreed') || false
    if (!agreed) {
      this.setData({ showAgreementModal: true })
      return
    }
    this.tryLogin()
  },

  tryLogin() {
    if (!app.globalData.token) {
      app.login().catch(err => console.error('登录失败:', err))
    }
  },

  // === 服务协议弹窗 ===
  onAgreementCheckboxChange(e) {
    this.setData({ agreementChecked: e.detail.value.includes('agree') })
  },

  onAgreeAgreement() {
    if (!this.data.agreementChecked) {
      wx.showToast({ title: '请先阅读并同意用户服务协议', icon: 'none' })
      return
    }
    app.agreeAgreement().then(() => {
      this.setData({ showAgreementModal: false, agreementChecked: false })
      wx.showToast({ title: '欢迎使用时光修复！', icon: 'success' })
      this.tryLogin()
    })
  },

  onViewPrivacy() { wx.navigateTo({ url: '/pkg-legal/pages/privacy/privacy' }) },
  onViewAgreement() { wx.navigateTo({ url: '/pkg-legal/pages/agreement/agreement' }) },

  // === 选择照片 ===
  // 隐私授权由 app.js onNeedPrivacyAuthorization 自动处理
  // 只需检查服务协议即可
  onChooseImage() {
    var that = this
    const agreed = wx.getStorageSync('agreementAgreed') || false
    if (!agreed) {
      this.setData({ showAgreementModal: true })
      return
    }
    app.requirePrivacy(function() {
      that._chooseMedia()
    })
  },

  _chooseMedia() {
    var that = this

    var doChoose = function() {
      wx.chooseMedia({
        count: 1, mediaType: ['image'], sourceType: ['album', 'camera'], sizeType: ['compressed'],
        success: function(res) {
          var tempFilePath = res.tempFiles[0].tempFilePath
          var fs = wx.getFileSystemManager()
          var savedPath = wx.env.USER_DATA_PATH + '/preview_' + Date.now() + '.jpg'
          fs.saveFile({
            tempFilePath: tempFilePath,
            filePath: savedPath,
            success: function() {
              wx.navigateTo({
                url: '/pages/preview/preview?image=' + encodeURIComponent(savedPath) + '&type=restore'
              })
            },
            fail: function() {
              wx.navigateTo({
                url: '/pages/preview/preview?image=' + encodeURIComponent(tempFilePath) + '&type=restore'
              })
            }
          })
        },
        fail: function(err) {
          console.error('[index] chooseMedia 失败:', JSON.stringify(err))
          // 用户取消则静默
          if (err.errMsg && err.errMsg.indexOf('cancel') !== -1) return
          // 真正的错误
          var msg = (err.errMsg || '操作失败，请重试').substring(0, 30)
          wx.showToast({ title: msg, icon: 'none', duration: 2500 })
        }
      })
    }

    if (app.globalData.token) {
      doChoose()
    } else {
      wx.showLoading({ title: '登录中...', mask: true })
      app.login().then(function() {
        wx.hideLoading()
        doChoose()
      }).catch(function() {
        wx.hideLoading()
        wx.showModal({ title: '登录失败', content: '请检查网络连接后重试', showCancel: false })
      })
    }
  },

  onGoHistory() {
    wx.navigateTo({ url: '/pkg-user/pages/history/history' })
  },

  onShareAppMessage() {
    return {
      title: '时光修复 - AI 智能修复老照片',
      path: '/pages/index/index'
    }
  }
})
