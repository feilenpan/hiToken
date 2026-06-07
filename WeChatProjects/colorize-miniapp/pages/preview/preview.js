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
    quota: null,
    // 历史记录
    todayDate: '',
    todayWeekday: '',
    todayRecords: [],
    previousSections: []     // [{ dateKey, date, weekday, records }]
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
    var that = this
    var loginPromise = app._loginReady || Promise.resolve()
    loginPromise.then(function() {
      that._refreshQuota()
    })
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

  _refreshQuota() {
    var quota = app.globalData.quota
    if (quota) {
      this.setData({ quota: quota })
      return
    }
    var that = this
    app.fetchAndSyncQuota().then(function(quota) {
      if (quota) that.setData({ quota: quota })
    })
  },

  // === 默认态：点击选照片 ===
  onPickImage() {
    var that = this
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
          if (data.quota) {
            that.setData({ quota: data.quota })
            app.syncQuota(data.quota)
          }
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

  // === 跳转品鉴 ===
  onGoScore() {
    if (!this.data.repairResult) return
    var that = this
    var imageSource = this.data.repairResult

    function go(imagePath) {
      app.globalData.pendingScoreImage = imagePath
      wx.switchTab({ url: '/pages/score/score' })
    }

    // data URI → 写入临时文件
    if (imageSource.indexOf('data:') === 0) {
      var b64 = imageSource.replace(/^data:image\/\w+;base64,/, '')
      var savePath = wx.env.USER_DATA_PATH + '/score_' + Date.now() + '.jpg'
      var fs = wx.getFileSystemManager()
      fs.writeFile({
        filePath: savePath, data: b64, encoding: 'base64',
        success: function() { go(savePath) },
        fail: function() { wx.showToast({ title: '图片处理失败', icon: 'none' }) }
      })
      return
    }

    // HTTP URL → 下载
    if (imageSource.indexOf('http') === 0) {
      wx.downloadFile({
        url: imageSource,
        success: function(res) {
          if (res.statusCode === 200) go(res.tempFilePath)
          else wx.showToast({ title: '图片下载失败', icon: 'none' })
        },
        fail: function() { wx.showToast({ title: '图片下载失败', icon: 'none' }) }
      })
      return
    }

    // 本地路径 → 直接使用
    go(imageSource)
  },

  onBackHome() {
    this.setData({
      imagePath: '',
      repairResult: null,
      repairError: null,
      isRepairing: false
    })
    this.loadHistory()
  },

  // ========== 📜 历史记录 ==========

  loadHistory() {
    var records = wx.getStorageSync('history_records') || []
    var weekdays = ['星期日', '星期一', '星期二', '星期三', '星期四', '星期五', '星期六']
    var now = new Date()

    // 今天
    var m = now.getMonth() + 1, d = now.getDate()
    var todayKey = now.getFullYear() + '-' + (m < 10 ? '0' + m : m) + '-' + (d < 10 ? '0' + d : d)

    this.setData({
      todayDate: m + '月' + d + '日',
      todayWeekday: weekdays[now.getDay()]
    })

    // 按日期分组
    var groups = {}  // dateKey -> { date, weekday, records: [] }
    records.forEach(function(r) {
      var ts = r.time || 0
      var dt = new Date(ts)
      var key = dt.getFullYear() + '-' + ('0' + (dt.getMonth() + 1)).slice(-2) + '-' + ('0' + dt.getDate()).slice(-2)
      if (!groups[key]) {
        groups[key] = {
          dateKey: key,
          date: (dt.getMonth() + 1) + '月' + dt.getDate() + '日',
          weekday: weekdays[dt.getDay()],
          records: []
        }
      }
      groups[key].records.push({ taskId: r.taskId, localPath: r.localPath })
    })

    // 分离今天 vs 之前
    var todayRecords = groups[todayKey] ? groups[todayKey].records : []
    var previousSections = []
    var keys = Object.keys(groups).sort().reverse() // 最新在前
    for (var i = 0; i < keys.length; i++) {
      if (keys[i] !== todayKey) {
        previousSections.push(groups[keys[i]])
      }
    }

    this.setData({
      todayRecords: todayRecords,
      previousSections: previousSections
    })
  },

  _saveToHistory(imageSource) {
    if (!imageSource) return
    var that = this
    var taskId = 'r_' + Date.now()
    var now = Date.now()

    function persist(localPath) {
      var records = wx.getStorageSync('history_records') || []
      records.unshift({ taskId: taskId, type: 'restore', time: now, localPath: localPath })
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
    var date = e.currentTarget.dataset.date
    var idx = e.currentTarget.dataset.index
    var list = this.data.todayRecords
    this._openHistoryPreview(list, idx)
  },

  onPreviewHistoryByDate(e) {
    var dateKey = e.currentTarget.dataset.date
    var idx = e.currentTarget.dataset.index
    var sections = this.data.previousSections
    for (var i = 0; i < sections.length; i++) {
      if (sections[i].dateKey === dateKey) {
        this._openHistoryPreview(sections[i].records, idx)
        return
      }
    }
  },

  _openHistoryPreview(list, idx) {
    if (!list || idx === undefined || idx === null) return
    var r = list[idx]
    if (r && r.localPath) wx.previewImage({ urls: [r.localPath] })
  },

  onViewAllHistory() {
    wx.navigateTo({ url: '/pkg-user/pages/history/history' })
  }
})
