// pages/preview/preview.js - 默认态 + 选图即修
const app = getApp()

const RESTORE_PROMPT = '修复这张老照片，去除噪点和划痕，增强人脸清晰度，还原肤色'

Page({
  data: {
    imagePath: '',
    processType: 'restore',
    isRepairing: false,
    repairResult: null,
    repairError: null,
    // 历史记录
    historyRecords: [],
    hasHistory: false
  },

  onLoad(options) {
    if (options && options.image) {
      this.setData({ imagePath: decodeURIComponent(options.image) })
    }
    if (options && options.type) {
      this.setData({ processType: options.type })
    }
  },

  onShow() {
    this.loadHistory()
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
            that.onPickImage()
          }
        }
      })
    }
  },

  // === 默认态：点击选照片 ===
  onPickImage() {
    var that = this
    var agreed = wx.getStorageSync('agreementAgreed') || false
    if (!agreed) {
      wx.showToast({ title: '请先同意用户服务协议', icon: 'none' })
      return
    }
    app.requirePrivacy(function() {
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
          if (err.errMsg && err.errMsg.indexOf('cancel') !== -1) return
          wx.showToast({ title: (err.errMsg || '操作失败').substring(0, 20), icon: 'none' })
        }
      })
    })
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
          that._saveToHistory(data.result)
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
  },

  // ========== 📜 历史记录 ==========

  loadHistory() {
    var records = wx.getStorageSync('history_records') || []
    var that = this
    var display = records.slice(0, 10).map(function(r) {
      return {
        taskId: r.taskId,
        localPath: r.localPath,
        timeStr: r.timeStr || that._formatHistoryTime(r.time)
      }
    })
    this.setData({
      historyRecords: display,
      hasHistory: records.length > 0
    })
  },

  _saveToHistory(imageSource) {
    if (!imageSource) return
    var that = this
    var taskId = 'r_' + Date.now()
    var now = Date.now()

    function persist(localPath) {
      var records = wx.getStorageSync('history_records') || []
      records.unshift({ taskId: taskId, type: 'restore', time: now, localPath: localPath, timeStr: that._formatHistoryTime(now) })
      while (records.length > 50) records.pop()
      wx.setStorageSync('history_records', records)
      that.loadHistory()
    }

    // base64 data URI
    if (imageSource.indexOf('data:') === 0) {
      var b64 = imageSource.replace(/^data:image\/\w+;base64,/, '')
      var sp = wx.env.USER_DATA_PATH + '/history/' + taskId + '.jpg'
      try {
        var fs = wx.getFileSystemManager()
        try { fs.accessSync(wx.env.USER_DATA_PATH + '/history') } catch (e) { fs.mkdirSync(wx.env.USER_DATA_PATH + '/history') }
        fs.writeFileSync(sp, b64, 'base64')
        persist(sp)
      } catch (e) { console.error('[preview] 保存历史失败:', e) }
      return
    }

    // HTTP URL
    if (imageSource.indexOf('http') === 0) {
      wx.downloadFile({
        url: imageSource,
        success: function(res) {
          if (res.statusCode === 200) {
            var sp = wx.env.USER_DATA_PATH + '/history/' + taskId + '.jpg'
            try {
              var fs = wx.getFileSystemManager()
              try { fs.accessSync(wx.env.USER_DATA_PATH + '/history') } catch (e) { fs.mkdirSync(wx.env.USER_DATA_PATH + '/history') }
              fs.saveFileSync(res.tempFilePath, sp)
              persist(sp)
            } catch (e) { console.error('[preview] 保存历史失败:', e) }
          }
        }
      })
      return
    }

    persist(imageSource)
  },

  _formatHistoryTime(ts) {
    if (!ts) return ''
    var d = new Date(ts)
    var m = (d.getMonth() + 1).toString(), day = d.getDate().toString()
    if (m.length < 2) m = '0' + m
    if (day.length < 2) day = '0' + day
    return m + '-' + day
  },

  onPreviewHistory(e) {
    var r = this.data.historyRecords[e.currentTarget.dataset.index]
    if (r && r.localPath) wx.previewImage({ urls: [r.localPath] })
  },

  onViewAllHistory() {
    wx.navigateTo({ url: '/pkg-user/pages/history/history' })
  }
})
