// pages/preview/preview.js - 选图即修，结果内联
const app = getApp()

const RESTORE_PROMPT = '修复这张老照片，去除噪点和划痕，增强人脸清晰度，还原肤色'

Page({
  data: {
    imagePath: '',
    processType: 'restore',
    isRepairing: false,
    repairResult: null,
    repairError: null
  },

  onLoad(options) {
    if (options.image) {
      this.setData({ imagePath: decodeURIComponent(options.image) })
    }
    if (options.type) {
      this.setData({ processType: options.type })
    }
  },

  _startRepair() {
    var that = this
    if (that.data.isRepairing) return

    that.setData({ isRepairing: true, repairResult: null, repairError: null })

    var pendingPrompt = ''
    if (app.globalData.pendingRestore) {
      pendingPrompt = app.globalData.pendingRestore.prompt || ''
      app.globalData.pendingRestore = null
    }

    var prompt = pendingPrompt || RESTORE_PROMPT
    console.log('[preview] repair start, prompt:', prompt.substring(0, 30))

    app.cloudUpload('/api/suggest-edit', that.data.imagePath, { prompt: prompt })
      .then(function(res) {
        console.log('[preview] repair done')
        var data = res.data
        if (data && data.success && data.result) {
          that.setData({ isRepairing: false, repairResult: data.result, repairError: null })
        } else {
          that.setData({ isRepairing: false, repairResult: null, repairError: (data && data.detail) || '修复失败，请稍后重试' })
        }
      })
      .catch(function(err) {
        console.error('[preview] repair fail:', JSON.stringify(err))
        that.setData({ isRepairing: false, repairResult: null, repairError: '网络连接失败，请检查网络后重试' })
      })
  },

  onChangeImage() {
    var that = this
    wx.chooseMedia({
      count: 1, mediaType: ['image'], sourceType: ['album', 'camera'], sizeType: ['compressed'],
      success: function(res) {
        that.setData({
          imagePath: res.tempFiles[0].tempFilePath,
          repairResult: null,
          repairError: null
        })
      },
      fail: function(err) {
        console.log('[preview] chooseMedia 失败:', JSON.stringify(err))
        if (err.errMsg && err.errMsg.indexOf('cancel') !== -1) return
        wx.showToast({ title: (err.errMsg || '操作失败').substring(0, 20), icon: 'none' })
      }
    })
  },

  onRetryRepair() {
    this._startRepair()
  }
})
