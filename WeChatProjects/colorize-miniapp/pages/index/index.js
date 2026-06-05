// pages/index/index.js
const app = getApp()

const RESTORE_PROMPT = '修复这张老照片，去除噪点和划痕，增强人脸清晰度，还原肤色'

Page({
  data: {
    showAgreementModal: false,
    agreementChecked: false,
    heroImage: '/static/images/demo/hero_compare.png',
    showPrivacyPopup: false,
    // 修复状态
    originalImage: '',
    isRepairing: false,
    repairResult: '',
    repairError: '',
    progress: 0,
    // 历史记录
    historyRecords: [],
    hasHistory: false
  },

  onLoad() {
    this.checkAgreement()
    // 协议已签 → 首次进入直接弹出选照片
    var agreed = wx.getStorageSync('agreementAgreed') || false
    if (agreed && app.globalData.token) {
      var that = this
      setTimeout(function() { that.onChooseImage() }, 300)
    }
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
            that._chooseMedia()
          }
        }
      })
    }
  },

  checkAgreement() {
    var agreed = wx.getStorageSync('agreementAgreed') || false
    if (!agreed) {
      this.setData({ showAgreementModal: true })
      return
    }
    this.tryLogin()
  },

  tryLogin() {
    if (!app.globalData.token) {
      app.login().catch(function(err) { console.error('登录失败:', err) })
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
    var that = this
    app.agreeAgreement().then(function() {
      that.setData({ showAgreementModal: false, agreementChecked: false })
      wx.showToast({ title: '欢迎使用时光修复！', icon: 'success' })
      that.tryLogin()
      // 同意后自动弹出选照片
      setTimeout(function() { that.onChooseImage() }, 1600)
    })
  },

  onViewPrivacy() { wx.navigateTo({ url: '/pkg-legal/pages/privacy/privacy' }) },
  onViewAgreement() { wx.navigateTo({ url: '/pkg-legal/pages/agreement/agreement' }) },

  // === 选择照片（入口） ===
  onChooseImage() {
    var that = this
    var agreed = wx.getStorageSync('agreementAgreed') || false
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
          var savedPath = wx.env.USER_DATA_PATH + '/repair_' + Date.now() + '.jpg'
          fs.saveFile({
            tempFilePath: tempFilePath,
            filePath: savedPath,
            success: function() {
              that.setData({ originalImage: savedPath, repairResult: '', repairError: '' })
              that._startRepair(savedPath)
            },
            fail: function() {
              that.setData({ originalImage: tempFilePath, repairResult: '', repairError: '' })
              that._startRepair(tempFilePath)
            }
          })
        },
        fail: function(err) {
          console.error('[index] chooseMedia 失败:', JSON.stringify(err))
          if (err.errMsg && err.errMsg.indexOf('cancel') !== -1) return
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

  // === 开始修复 ===
  _startRepair: function(imagePath) {
    var that = this
    if (that.data.isRepairing) return

    that.setData({ isRepairing: true, repairResult: '', repairError: '', progress: 0 })

    // 进度模拟
    var progressTimer = setInterval(function() {
      var p = that.data.progress
      if (p < 90) {
        p = p + Math.floor(Math.random() * 10 + 3)
        that.setData({ progress: Math.min(90, p) })
      }
    }, 300)

    var pendingPrompt = ''
    if (app.globalData.pendingRestore) {
      pendingPrompt = app.globalData.pendingRestore.prompt || ''
      app.globalData.pendingRestore = null
    }
    var prompt = pendingPrompt || RESTORE_PROMPT
    console.log('[index] repair start, prompt:', prompt.substring(0, 30))

    app.cloudUpload('/api/suggest-edit', imagePath, { prompt: prompt }, true)
      .then(function(res) {
        clearInterval(progressTimer)
        console.log('[index] repair done, status:', res.statusCode)
        var data = res.data
        if (data && data.success && data.result) {
          that.setData({ isRepairing: false, progress: 100, repairResult: data.result, repairError: '' })
          that._saveToHistory(data.result)
        } else {
          var msg = (data && data.detail) || '修复失败，请稍后重试'
          that.setData({ isRepairing: false, progress: 0, repairResult: '', repairError: msg })
        }
      })
      .catch(function(err) {
        clearInterval(progressTimer)
        console.error('[index] repair fail:', JSON.stringify(err))
        that.setData({ isRepairing: false, progress: 0, repairResult: '', repairError: '网络连接失败，请检查网络后重试' })
      })
  },

  // === 换一张 ===
  onChangeImage: function() {
    var that = this
    app.requirePrivacy(function() {
      wx.chooseMedia({
        count: 1, mediaType: ['image'], sourceType: ['album', 'camera'], sizeType: ['compressed'],
        success: function(res) {
          var path = res.tempFiles[0].tempFilePath
          that.setData({ originalImage: path, repairResult: '', repairError: '', progress: 0 })
          that._startRepair(path)
        },
        fail: function(err) {
          console.log('[index] chooseMedia 失败:', JSON.stringify(err))
          if (err.errMsg && err.errMsg.indexOf('cancel') !== -1) return
          wx.showToast({ title: (err.errMsg || '操作失败').substring(0, 20), icon: 'none' })
        }
      })
    })
  },

  // === 重新修复 ===
  onRetryRepair: function() {
    if (this.data.originalImage) {
      this._startRepair(this.data.originalImage)
    } else {
      this.onChooseImage()
    }
  },

  // === 保存到相册 ===
  onSaveResult: function() {
    if (!this.data.repairResult) return
    var that = this
    var imageUrl = this.data.repairResult
    if (imageUrl.indexOf('data:') === 0) {
      var fs = wx.getFileSystemManager()
      var savePath = wx.env.USER_DATA_PATH + '/save_' + Date.now() + '.jpg'
      var b64 = imageUrl.replace(/^data:image\/\w+;base64,/, '')
      fs.writeFile({
        filePath: savePath, data: b64, encoding: 'base64',
        success: function() {
          wx.saveImageToPhotosAlbum({
            filePath: savePath,
            success: function() { wx.showToast({ title: '已保存', icon: 'success' }) },
            fail: function() { wx.showToast({ title: '请授权相册权限', icon: 'none' }) }
          })
        },
        fail: function() { wx.showToast({ title: '保存失败', icon: 'error' }) }
      })
    } else {
      wx.saveImageToPhotosAlbum({
        filePath: imageUrl,
        success: function() { wx.showToast({ title: '已保存', icon: 'success' }) },
        fail: function() { wx.showToast({ title: '请授权相册权限', icon: 'none' }) }
      })
    }
  },

  // === 回到初始状态 ===
  onResetHome: function() {
    this.setData({
      originalImage: '', repairResult: '', repairError: '',
      isRepairing: false, progress: 0
    })
  },

  onGoHistory() {
    wx.navigateTo({ url: '/pkg-user/pages/history/history' })
  },

  // ========== 📜 历史记录 ==========

  /** 从本地加载历史记录 */
  loadHistory() {
    var records = wx.getStorageSync('history_records') || []
    var display = records.slice(0, 10).map(function(r) {
      return {
        taskId: r.taskId,
        localPath: r.localPath,
        timeStr: r.timeStr || this._formatHistoryTime(r.time)
      }
    }.bind(this))
    this.setData({
      historyRecords: display,
      hasHistory: records.length > 0
    })
  },

  /** 修复成功后保存到本地历史 */
  _saveToHistory(imageSource) {
    if (!imageSource) return
    var that = this
    var taskId = 'r_' + Date.now()
    var now = Date.now()

    function persistRecord(localPath) {
      var records = wx.getStorageSync('history_records') || []
      records.unshift({
        taskId: taskId,
        type: 'restore',
        time: now,
        localPath: localPath,
        timeStr: that._formatHistoryTime(now)
      })
      // 保留最近 50 条
      while (records.length > 50) records.pop()
      wx.setStorageSync('history_records', records)
      that.loadHistory()
    }

    // base64 data URI
    if (imageSource.indexOf('data:') === 0) {
      var b64 = imageSource.replace(/^data:image\/\w+;base64,/, '')
      var savePath = wx.env.USER_DATA_PATH + '/history/' + taskId + '.jpg'
      try {
        var fs = wx.getFileSystemManager()
        // ensure directory
        try { fs.accessSync(wx.env.USER_DATA_PATH + '/history') } catch (e) {
          fs.mkdirSync(wx.env.USER_DATA_PATH + '/history')
        }
        fs.writeFileSync(savePath, b64, 'base64')
        persistRecord(savePath)
      } catch (e) {
        console.error('[index] 保存历史失败(base64):', e)
      }
      return
    }

    // HTTP URL — 下载后保存
    if (imageSource.indexOf('http') === 0) {
      wx.downloadFile({
        url: imageSource,
        success: function(res) {
          if (res.statusCode === 200) {
            var savePath = wx.env.USER_DATA_PATH + '/history/' + taskId + '.jpg'
            try {
              var fs = wx.getFileSystemManager()
              try { fs.accessSync(wx.env.USER_DATA_PATH + '/history') } catch (e) {
                fs.mkdirSync(wx.env.USER_DATA_PATH + '/history')
              }
              fs.saveFileSync(res.tempFilePath, savePath)
              persistRecord(savePath)
            } catch (e) {
              console.error('[index] 保存历史失败(http):', e)
            }
          }
        },
        fail: function(err) {
          console.error('[index] 下载历史图片失败:', err)
        }
      })
      return
    }

    // 本地文件路径 — 直接复制
    persistRecord(imageSource)
  },

  /** 格式化时间戳 */
  _formatHistoryTime(timestamp) {
    if (!timestamp) return ''
    var d = new Date(timestamp)
    var m = (d.getMonth() + 1).toString()
    var day = d.getDate().toString()
    if (m.length < 2) m = '0' + m
    if (day.length < 2) day = '0' + day
    return m + '-' + day
  },

  /** 点击缩略图预览 */
  onPreviewHistory(e) {
    var index = e.currentTarget.dataset.index
    var record = this.data.historyRecords[index]
    if (record && record.localPath) {
      wx.previewImage({
        urls: [record.localPath],
        current: record.localPath
      })
    }
  },

  /** 查看全部历史 */
  onViewAllHistory() {
    wx.navigateTo({ url: '/pkg-user/pages/history/history' })
  },

  onShareAppMessage() {
    return {
      title: '时光修复 - AI 智能修复老照片',
      path: '/pages/index/index'
    }
  }
})
