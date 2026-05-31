// pages/result/result.js
var app = getApp();

Page({
  data: {
    originalImage: '',
    resultImage: '',
    processType: 'restore',
    isLoading: true,
    progress: 0,
    engine: 'volcengine',
    compareX: 0,
    wrapperLeft: 0,
    wrapperWidth: 0,
    evaluation: null,
    evalLoading: true,
    showEvalCard: true,
    restorePrompt: '',
    showPrivacyPopup: false
  },

  onLoad: function(options) {
    var that = this;
    console.log('[result] onLoad');
    try {
      var imagePath = '';
      if (options && options.image) {
        imagePath = decodeURIComponent(options.image);
      }
      if (!imagePath) {
        wx.showToast({ title: '缺少圖片', icon: 'error' });
        setTimeout(function(){ wx.navigateBack(); }, 1500);
        return;
      }
      var processType = (options && options.type) || 'restore';
      var restorePrompt = '';
      if (options && options.prompt) {
        restorePrompt = decodeURIComponent(options.prompt);
      }
      
      that.setData({
        originalImage: imagePath,
        processType: processType,
        restorePrompt: restorePrompt
      });
      
      // 確認文件存在
      var fs = wx.getFileSystemManager();
      try {
        fs.accessSync(imagePath);
        console.log('[result] file exists');
      } catch(e) {
        console.error('[result] file missing:', imagePath);
        wx.showToast({ title: '圖片丟失，請返回重選', icon: 'error' });
        setTimeout(function(){ wx.navigateBack(); }, 1500);
        return;
      }
      
      that._doEvaluate(imagePath);
      that._doProcess(imagePath, processType);
    } catch(e) {
      console.error('[result] onLoad error:', e);
      wx.showToast({ title: '載入失敗', icon: 'error' });
    }
  },

  onReady: function() {
    this._updateWrapperRect();
  },

  // 隐私授权回调
  handleAgreePrivacy: function() {
    this.setData({ showPrivacyPopup: false });
    app.handleAgreePrivacy();
  },
  handleOpenPrivacyContract: function() {
    app.openPrivacyContract();
  },
  showPrivacyPopup: function() {
    this.setData({ showPrivacyPopup: true });
  },

  _updateWrapperRect: function() {
    var that = this;
    wx.createSelectorQuery()
      .select('#compareWrapper')
      .boundingClientRect(function(rect) {
        if (rect) {
          that.setData({
            wrapperLeft: rect.left,
            wrapperWidth: rect.width,
            compareX: rect.width / 2
          });
        }
      }).exec();
  },

  _doEvaluate: function(imagePath) {
    var that = this;
    that.setData({ evalLoading: true, showEvalCard: true });
    
    console.log('[result] evaluate start');
    app.cloudUpload('/api/evaluate', imagePath)
      .then(function(res) {
        console.log('[result] evaluate success');
        var data = res.data;
        if (data && data.success) {
          that.setData({
            evaluation: {
              text: data.text || '',
              score: data.score || 85,
              tags: data.tags || [],
              quote: data.quote || '',
              location: data.location || '',
              fallback: data.fallback || false
            },
            evalLoading: false
          });
        } else {
          that._evalFallback();
        }
      })
      .catch(function(err) {
        console.error('[result] eval fail:', JSON.stringify(err));
        that._evalFallback();
      });
  },

  _evalFallback: function() {
    this.setData({
      evalLoading: false,
      evaluation: {
        text: '這是一張承載著珍貴記憶的照片，值得被好好保存。',
        score: 85,
        tags: ['📸 珍貴記憶'],
        quote: '每一張照片都值得被珍惜',
        fallback: true
      }
    });
  },

  _doProcess: function(imagePath, processType) {
    var that = this;
    that.setData({ isLoading: true, progress: 0 });
    
    console.log('[result] process start, API:', app.globalData.API_BASE);
    
    var doUpload = function() {
      var progressInterval = setInterval(function() {
        var p = that.data.progress;
        if (p < 90) {
          p = p + Math.random() * 12;
          that.setData({ progress: Math.min(90, Math.floor(p)) });
        }
      }, 200);
      
      app.cloudUpload('/api/process', imagePath, { function: processType, prompt: that.data.restorePrompt || '' })
        .then(function(res) {
          clearInterval(progressInterval);
          console.log('[result] process success, status:', res.statusCode);
          
          if (res.statusCode >= 400) {
            var msg = '服務器錯誤: ' + res.statusCode;
            try {
              var ed = JSON.parse(res.data);
              msg = ed.detail || ed.message || msg;
            } catch(e) {}
            wx.showToast({ title: msg, icon: 'error' });
            that.setData({ isLoading: false });
            return;
          }
          
          var data = res.data;
          try {
            if (data && data.success && data.result) {
              that.setData({ progress: 100 });
              setTimeout(function() {
                that.setData({
                  isLoading: false,
                  resultImage: data.result,
                  engine: data.engine || 'volcengine'
                });
                setTimeout(function(){ that._updateWrapperRect(); }, 200);
              }, 500);
            } else {
              throw new Error(data.message || data.detail || '处理失败');
            }
          } catch(e) {
            console.error('[result] process parse error:', e);
            wx.showToast({ title: e.message || '处理失败', icon: 'error' });
            that.setData({ isLoading: false });
          }
        })
        .catch(function(err) {
          clearInterval(progressInterval);
          console.error('[result] process fail:', JSON.stringify(err));
          wx.showModal({
            title: '網絡連接失敗',
            content: '請檢查網絡後重試\n(' + (err.errMsg || 'unknown') + ')',
            showCancel: false,
            confirmText: '知道了'
          });
          that.setData({ isLoading: false });
        });
    };
    
    // 可選登錄
    if (!app.globalData || !app.globalData.token) {
      try {
        wx.showLoading({ title: '連接中...', mask: true });
        app.login().then(function() {
          wx.hideLoading();
          doUpload();
        }).catch(function() {
          wx.hideLoading();
          // 登錄失敗不阻擋，繼續嘗試
          doUpload();
        });
      } catch(e) {
        wx.hideLoading();
        doUpload();
      }
    } else {
      doUpload();
    }
  },

  onTouchStart: function(e) {
    var x = e.touches[0].clientX - this.data.wrapperLeft;
    this.setData({ compareX: Math.max(10, Math.min(this.data.wrapperWidth, x)) });
  },
  onTouchMove: function(e) {
    var x = e.touches[0].clientX - this.data.wrapperLeft;
    this.setData({ compareX: Math.max(10, Math.min(this.data.wrapperWidth, x)) });
  },

  onSave: function() {
    if (!this.data.resultImage) return;
    var that = this;
    if (this.data.resultImage.indexOf('data:') === 0) {
      var fs = wx.getFileSystemManager();
      var savePath = wx.env.USER_DATA_PATH + '/save_' + Date.now() + '.jpg';
      var b64 = this.data.resultImage.replace(/^data:image\/\w+;base64,/, '');
      fs.writeFile({
        filePath: savePath, data: b64, encoding: 'base64',
        success: function() {
          wx.saveImageToPhotosAlbum({
            filePath: savePath,
            success: function(){ wx.showToast({ title: '已保存', icon: 'success' }); },
            fail: function(){ wx.showToast({ title: '请授权相册权限', icon: 'none' }); }
          });
        },
        fail: function(){ wx.showToast({ title: '保存失败', icon: 'error' }); }
      });
    } else {
      wx.saveImageToPhotosAlbum({
        filePath: this.data.resultImage,
        success: function(){ wx.showToast({ title: '已保存', icon: 'success' }); },
        fail: function(){ wx.showToast({ title: '请授权相册权限', icon: 'none' }); }
      });
    }
  },

  onRetry: function() {
    var that = this;
    app.requirePrivacy(function() {
      that._doRetry();
    });
  },

  _doRetry: function() {
    var that = this;
    wx.chooseMedia({
      count: 1, mediaType: ['image'], sourceType: ['album'], sizeType: ['compressed'],
      success: function(res) {
        var path = res.tempFiles[0].tempFilePath;
        that.setData({
          originalImage: path, resultImage: '', isLoading: true, progress: 0,
          evaluation: null, evalLoading: true, showEvalCard: true
        });
        that._doEvaluate(path);
        that._doProcess(path, that.data.processType);
      },
      fail: function(err) {
        console.log('[result] chooseMedia 失败:', JSON.stringify(err))
        if (err.errMsg && err.errMsg.indexOf('cancel') !== -1) return
        wx.showToast({ title: (err.errMsg || '操作失败').substring(0, 20), icon: 'none' })
      }
    });
  },

  onShareAppMessage: function() {
    return { title: '时光修复 - AI免费老照片修复', path: '/pages/index/index' };
  }
});
