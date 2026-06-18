// pages/score/score.js
var app = getApp();

var ANALYZE_TEXTS = [
  '正在仔细端详...',
  '嗯～这张有意思...',
  '让我想想怎么说...',
  '哎呀，越看越有感觉...',
  '快好了快好了～'
];

var _editId = 0;

Page({
  data: {
    imagePath: '',
    isUploading: false,
    showAnalyzing: false,
    analyzingText: '正在仔细端详...',
    analyzingReviewer: null,
    evaluation: null,
    shareCardPath: null,
    typedText: '',
    showCTA: false,
    quality: null,
    typingCursor: true,
    activeSuggestion: null,
    editResults: [],
    showPrivacyPopup: false,
    quota: null,
    // 点评师选择
    selectedReviewer: '',
    reviewers: [
      { id: 'li_bai', name: '李白', emoji: '🍶', title: '诗仙', shortTitle: '诗仙' },
      { id: 'su_shi', name: '苏轼', emoji: '🍖', title: '东坡居士', shortTitle: '东坡' },
      { id: 'li_qingzhao', name: '李清照', emoji: '🌸', title: '易安居士', shortTitle: '易安' },
      { id: 'tang_bohu', name: '唐伯虎', emoji: '🎨', title: '江南才子', shortTitle: '才子' },
      { id: 'lu_xun', name: '鲁迅', emoji: '🖊️', title: '周树人', shortTitle: '先生' },
      { id: 'bai_juyi', name: '白居易', emoji: '👴', title: '香山居士', shortTitle: '香山' }
    ]
  },

  onShow: function() {
    var that = this
    var loginPromise = app._loginReady || Promise.resolve()
    loginPromise.then(function() {
      that._refreshQuota()
    })
    // 从修复页跳转过来的：自动触发品鉴
    if (app.globalData.pendingScoreImage) {
      var imagePath = app.globalData.pendingScoreImage;
      app.globalData.pendingScoreImage = null;
      var that = this;
      // 等页面渲染完再触发
      setTimeout(function() {
        that.setData({ 
          imagePath: imagePath,
          evaluation: null,
          shareCardPath: null,
          typedText: '',
          showCTA: false,
          showAnalyzing: false,
          editResults: [],
          activeSuggestion: null
        });
        _editId = 0;
        that.setData({ isUploading: true, showAnalyzing: true });
        that._startAnalyzeAnim();
        that._callEvaluate(imagePath);
      }, 400);
    }
  },

  _twTimer: null,
  _txtTimer: null,

  onUnload: function() {
    if (this._twTimer) clearInterval(this._twTimer);
    if (this._txtTimer) clearInterval(this._txtTimer);
  },

  _refreshQuota: function() {
    // 优先读全局缓存，避免每次 onShow 都调 API
    var quota = app.globalData.quota
    if (quota) {
      this.setData({ quota: quota })
      return
    }
    // 冷启动：从后端拉取
    var that = this
    app.fetchAndSyncQuota().then(function(quota) {
      if (quota) that.setData({ quota: quota })
    })
  },

  // 隐私授权回调（按钮 open-type="agreePrivacyAuthorization" 自动 resolve）
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

  // 选择点评师
  onSelectReviewer: function(e) {
    var id = e.currentTarget.dataset.id;
    this.setData({ selectedReviewer: id === this.data.selectedReviewer ? '' : id });
  },

  onChooseImage: function() {
    var that = this;
    app.requirePrivacy(function() {
      that._doChooseImage();
    });
  },

  _doChooseImage: function() {
    var that = this;
    wx.chooseMedia({
      count: 1,
      mediaType: ['image'],
      sourceType: ['album', 'camera'],
      sizeType: ['compressed'],
      success: function(res) {
        if (!res || !res.tempFiles || !res.tempFiles[0]) return;
        var path = res.tempFiles[0].tempFilePath;
        that.setData({ 
          imagePath: path,
          evaluation: null,
          shareCardPath: null,
          quality: null,
          typedText: '',
          showCTA: false,
          showAnalyzing: false,
          editResults: [],
          activeSuggestion: null
        });
        _editId = 0;
        that.setData({ isUploading: true, showAnalyzing: true });
        that._startAnalyzeAnim();
        that._callEvaluate(path);
      },
      fail: function(err) {
        console.log('[score] chooseMedia 失败:', JSON.stringify(err))
        // 用户取消则静默
        if (err.errMsg && err.errMsg.indexOf('cancel') !== -1) return
        wx.showToast({ title: (err.errMsg || '操作失败').substring(0, 30), icon: 'none', duration: 2500 })
      }
    });
  },

  _startAnalyzeAnim: function() {
    var that = this;
    // 确定点评师：选中 → 展示；随机 → 从列表中随机取一个展示
    var reviewer = null;
    if (that.data.selectedReviewer) {
      for (var i = 0; i < that.data.reviewers.length; i++) {
        if (that.data.reviewers[i].id === that.data.selectedReviewer) {
          reviewer = that.data.reviewers[i]; break;
        }
      }
    }
    if (!reviewer) {
      reviewer = that.data.reviewers[Math.floor(Math.random() * that.data.reviewers.length)];
    }
    that.setData({ analyzingReviewer: reviewer });

    if (that._txtTimer) clearInterval(that._txtTimer);
    var idx = 0;
    that._txtTimer = setInterval(function() {
      idx = (idx + 1) % ANALYZE_TEXTS.length;
      that.setData({ analyzingText: ANALYZE_TEXTS[idx] });
    }, 1800);
  },

  _callEvaluate: function(path) {
    var that = this;

    console.log('[score] evaluate start');

    app.cloudUpload('/api/evaluate', path, { reviewer: that.data.selectedReviewer })
      .then(function(res) {
        if (that._txtTimer) clearInterval(that._txtTimer);
        that.setData({ isUploading: false, showAnalyzing: false });

        console.log('[score] evaluate success');
        console.log('[score] raw res.data type:', typeof res.data);
        console.log('[score] res.data keys:', res.data ? Object.keys(res.data).join(',') : 'NULL');
        console.log('[score] GATEWAY code:', res.data && res.data.code);
        console.log('[score] GATEWAY message:', res.data && res.data.message);
        console.log('[score] success:', res.data && res.data.success, '| text len:', res.data && res.data.text ? res.data.text.length : 0);

        var data = res.data;
        if (data && data.success && data.text) {
          that._showResult({
            text: data.text,
            score: data.score || 85,
            tags: data.tags || [],
            quote: data.quote || '',
            title: data.title || '珍贵印记',
            location: data.location || '',
            suggestions: data.suggestions || [],
            reviewer: data.reviewer || '时光点评师',
            fallback: data.fallback || false
          });
          if (data.quality) {
            that.setData({ quality: data.quality });
          }
          if (data.quota) {
            that.setData({ quota: data.quota });
            app.syncQuota(data.quota);
          }
        } else {
          that._showFallback();
        }
      })
      .catch(function(err) {
        if (that._txtTimer) clearInterval(that._txtTimer);
        that.setData({ isUploading: false, showAnalyzing: false });
        console.error('[score] fail:', JSON.stringify(err));
        that._showFallback();
      });
  },

  _showResult: function(ev) {
    var that = this;
    // WXML 不支持 .split()，预先拆成数组
    if (ev.poem && typeof ev.poem === 'string') {
      ev.poemLines = ev.poem.split('\n');
    }
    
    that.setData({ evaluation: ev });
    that._typewriter(ev.text || '');
    
    // 分数低 → 展示修复CTA（内部判断，不显示数字）
    if ((ev.score || 0) < 55) {
      setTimeout(function() { that.setData({ showCTA: true }); }, 2500);
    }
  },

  _showFallback: function() {
    var that = this;
    var ev = {
      text: '哎呀，网络有点调皮～不过没关系，这张照片一看就承载着满满的回忆呢！',
      score: 75,
      tags: ['📸 珍贵记忆'],
      quote: '每一张都值得被珍惜',
      title: '珍贵印记',
      location: '',
      location_story: '',
      suggestions: [],
      fallback: true,
      reviewer: '时光点评师'
    };
    that.setData({ evaluation: ev });
    that._typewriter(ev.text);
  },

  _typewriter: function(text) {
    var that = this;
    if (!text) { that.setData({ typingCursor: false }); return; }
    if (that._twTimer) clearInterval(that._twTimer);
    
    var chars = text.split('');
    var idx = 0;
    
    that._twTimer = setInterval(function() {
      if (idx >= chars.length) {
        clearInterval(that._twTimer);
        that._twTimer = null;
        setTimeout(function() {
          that.setData({ typingCursor: false });
        }, 400);
        return;
      }
      that.setData({ typedText: text.substring(0, idx + 1) });
      idx = idx + 1;
    }, 60);
  },

  onGoRestore: function() {
    wx.switchTab({ url: '/pages/index/index' });
  },

  // === 低分 CTA → 原地 AI 修复 ===
  onRepairNow: function() {
    var that = this;
    console.log('[score] onRepairNow CLICKED');
    var editId = ++_editId;
    var prompt = '修复这张老照片，去除噪点和划痕，增强人脸清晰度，还原肤色';
    var label = 'AI 修复';

    // 追加 loading 占位
    var results = that.data.editResults || [];
    results.push({
      id: editId,
      loading: true,
      prompt: prompt,
      label: label
    });
    that.setData({ editResults: results });

    console.log('[score] repair-now #' + editId, 'uploading...');

    app.cloudUpload('/api/suggest-edit', that.data.imagePath, { prompt: prompt })
      .then(function(res) {
        console.log('[score] repair-now #' + editId + ' GOT RESPONSE:', JSON.stringify(res.data).substring(0, 200));
        var data = res.data;
        if (data && data.quota) {
          that.setData({ quota: data.quota });
          app.syncQuota(data.quota);
        }
        var results = that.data.editResults || [];
        for (var i = 0; i < results.length; i++) {
          if (results[i].id === editId) {
            if (data && data.success && data.result) {
              results[i] = {
                id: editId, loading: false, success: true,
                result: data.result, prompt: prompt, label: label
              };
            } else {
              results[i] = {
                id: editId, loading: false, success: false,
                error: (data && data.detail) || '修复失败', prompt: prompt, label: label
              };
            }
            break;
          }
        }
        that.setData({ editResults: results });
        console.log('[score] repair-now #' + editId + ' DONE, success=' + (data && data.success));
      })
      .catch(function(err) {
        console.error('[score] repair-now #' + editId + ' FAIL:', JSON.stringify(err));
        var results = that.data.editResults || [];
        for (var i = 0; i < results.length; i++) {
          if (results[i].id === editId) {
            results[i] = {
              id: editId, loading: false, success: false,
              error: '网络连接失败', prompt: prompt, label: label
            };
            break;
          }
        }
        that.setData({ editResults: results });
      });
  },

  onRetry: function() {
    // 直接弹出照片选择器 — 成功时 _doChooseImage 会清除旧数据
    // 取消时保留当前结果，不跳回首屏
    this.onChooseImage();
  },

  // === 建议点击 → 原地编辑（多图叠加） ===
  onSuggestionTap: function(e) {
    var that = this;
    console.log('[score] onSuggestionTap CLICKED, dataset:', JSON.stringify(e.currentTarget.dataset));
    var item = e.currentTarget.dataset.suggestion;
    var index = e.currentTarget.dataset.index;
    if (!item || !item.prompt) {
      console.log('[score] onSuggestionTap SKIP: no item or prompt');
      return;
    }

    // 防重复：已点击或处理中不可再点
    if (item.clicked || item.loading) {
      console.log('[score] onSuggestionTap SKIP: already clicked/loading');
      return;
    }

    // 生成唯一 ID
    var editId = ++_editId;

    // 标记 chip loading + clicked
    var suggestions = that.data.evaluation.suggestions;
    suggestions[index].loading = true;
    suggestions[index].clicked = true;

    // 追加 loading 占位到结果列表
    var results = that.data.editResults || [];
    results.push({
      id: editId,
      loading: true,
      prompt: item.prompt,
      label: item.label
    });

    that.setData({ 
      activeSuggestion: item,
      'evaluation.suggestions': suggestions,
      editResults: results
    });

    console.log('[score] suggest-edit #' + editId, 'prompt:', item.prompt, 'uploading...');

    app.cloudUpload('/api/suggest-edit', that.data.imagePath, { prompt: item.prompt })
      .then(function(res) {
        console.log('[score] suggest-edit #' + editId + ' GOT RESPONSE:', JSON.stringify(res.data).substring(0, 200));
        suggestions[index].loading = false;
        that.setData({ 'evaluation.suggestions': suggestions });

        var data = res.data;
        if (data && data.quota) {
          that.setData({ quota: data.quota });
          app.syncQuota(data.quota);
        }
        var results = that.data.editResults || [];
        for (var i = 0; i < results.length; i++) {
          if (results[i].id === editId) {
            if (data && data.success && data.result) {
              results[i] = {
                id: editId, loading: false, success: true,
                result: data.result, prompt: item.prompt, label: item.label
              };
            } else {
              results[i] = {
                id: editId, loading: false, success: false,
                error: (data && data.detail) || '编辑失败', prompt: item.prompt, label: item.label
              };
            }
            break;
          }
        }
        that.setData({ editResults: results });
        console.log('[score] suggest-edit #' + editId + ' DONE, success=' + (data && data.success));
      })
      .catch(function(err) {
        console.error('[score] suggest-edit #' + editId + ' FAIL:', JSON.stringify(err));
        suggestions[index].loading = false;
        that.setData({ 'evaluation.suggestions': suggestions });

        var results = that.data.editResults || [];
        for (var i = 0; i < results.length; i++) {
          if (results[i].id === editId) {
            results[i] = {
              id: editId, loading: false, success: false,
              error: '网络连接失败', prompt: item.prompt, label: item.label
            };
            break;
          }
        }
        that.setData({ editResults: results });
      });
  },

  onShareAppMessage: function() {
    return {
      title: '时光修复 - AI 照片点评与修复',
      path: '/pages/score/score'
    };
  },

  // ===== 分享卡片：服务端 Pillow 生成（1080×1500）+ 缓存 =====
  onShareEvaluate: function() {
    var that = this;
    var ev = this.data.evaluation;
    var imagePath = this.data.imagePath;
    if (!ev || !imagePath) return;

    // 已有缓存 → 直接复用
    if (this.data.shareCardPath) {
      wx.showShareImageMenu({ path: this.data.shareCardPath });
      return;
    }

    wx.showLoading({ title: '生成分享图…', mask: true });

    var poemText = (ev.poemLines || []).join('\n');
    if (!poemText) poemText = ev.poem || '';

    var sendRequest = function(photoPayload) {
      var data = {
        poem: poemText,
        text: ev.text || '',
        quote: ev.quote || '',
        reviewer_name: ev.reviewer || '',
        reviewer_emoji: ev.reviewer_emoji || '',
        reviewer_stamp: ev.stamp || ''
      };
      Object.assign(data, photoPayload);

      wx.request({
        url: getApp().BASE_URL + '/api/share-card',
        method: 'POST',
        data: data,
        header: { 'content-type': 'application/json' },
        timeout: 30000,
        success: function(res) {
          wx.hideLoading();
          if (res.data && res.data.success && res.data.image) {
            var b64 = res.data.image.replace(/^data:image\/\w+;base64,/, '');
            var fp = wx.env.USER_DATA_PATH + '/share_card_' + Date.now() + '.png';
            that.setData({ shareCardPath: fp });
            var fs = wx.getFileSystemManager();
            fs.writeFile({
              filePath: fp, data: b64, encoding: 'base64',
              success: function() { wx.showShareImageMenu({ path: fp }); },
              fail: function() { wx.showToast({ title: '保存失败', icon: 'none' }); }
            });
          } else {
            wx.showToast({ title: '生成失败，请重试', icon: 'none' });
          }
        },
        fail: function() {
          wx.hideLoading();
          wx.showToast({ title: '网络错误，请重试', icon: 'none' });
        }
      });
    };

    var src = imagePath;
    if (src.indexOf('http') === 0 || src.indexOf('cloud://') === 0) {
      sendRequest({ file_url: src });
    } else if (src.indexOf('data:') === 0) {
      sendRequest({ file: src.replace(/^data:image\/\w+;base64,/, '') });
    } else {
      var fs = wx.getFileSystemManager();
      fs.readFile({
        filePath: src, encoding: 'base64',
        success: function(r) { sendRequest({ file: r.data }); },
        fail: function() { wx.hideLoading(); wx.showToast({ title: '图片读取失败', icon: 'none' }); }
      });
    }
  },

  _drawScoreShareCard: function(photoPath, imgInfo, ev, callback) {
    var that = this;
    var sys = wx.getSystemInfoSync();
    var dpr = sys.pixelRatio || 2;
    var W = 375;   // 逻辑宽度 (px)
    var H = 600;   // 逻辑高度

    var ctx = wx.createCanvasContext('shareCanvas');
    ctx.scale(dpr, dpr);

    // 背景渐变
    var bgGrad = ctx.createLinearGradient(0, 0, 0, H);
    bgGrad.addColorStop(0, '#FFFBF7');
    bgGrad.addColorStop(1, '#FFF5ED');
    ctx.setFillStyle(bgGrad);
    ctx.fillRect(0, 0, W, H);

    // 照片（等比缩放）
    var pw = W - 40;
    var ph = pw * (imgInfo.height / imgInfo.width);
    var maxH = 280;
    if (ph > maxH) { pw = maxH * (imgInfo.width / imgInfo.height); ph = maxH; }
    var px = (W - pw) / 2;
    var py = 24;

    // 照片白色边框 + 阴影
    ctx.setFillStyle('#FFFFFF');
    ctx.setShadow(0, 4, 16, 'rgba(0,0,0,0.1)');
    ctx.fillRect(px - 3, py - 3, pw + 6, ph + 6);
    ctx.setShadow(0, 0, 0, 'rgba(0,0,0,0)');
    ctx.drawImage(photoPath, px, py, pw, ph);

    // 点评师标题行
    var emoji = ev.reviewer_emoji || '🍶';
    var name = ev.reviewer || '时光点评师';
    var headerY = py + ph + 24 + 6;
    ctx.setFontSize(15);
    ctx.setFillStyle('#6B3A2A');
    ctx.setTextAlign('center');
    ctx.fillText(emoji + '  ' + name + '  品鉴', W / 2, headerY);

    // 分隔线
    var lineY = headerY + 15;
    ctx.setStrokeStyle('#E8D5C3');
    ctx.setLineWidth(0.5);
    ctx.beginPath();
    ctx.moveTo(50, lineY);
    ctx.lineTo(W - 50, lineY);
    ctx.stroke();

    // 诗词
    var poemY = lineY + 18;
    var lines = ev.poemLines || [];
    if (lines.length > 0) {
      ctx.setFontSize(16);
      ctx.setFillStyle('#333333');
      ctx.setTextAlign('center');
      var lineH = 26;
      for (var i = 0; i < lines.length && i < 6; i++) {
        var line = lines[i];
        if (line.length > 16) line = line.substring(0, 15) + '…';
        ctx.fillText(line, W / 2, poemY + i * lineH);
      }
      // 署名
      var authorY = poemY + Math.min(lines.length, 6) * lineH + 8;
      ctx.setFontSize(12);
      ctx.setFillStyle('#AAAAAA');
      ctx.fillText('—— ' + name, W / 2, authorY);
    }

    // 底部分隔线
    var bottomLineY = H - 58;
    ctx.setStrokeStyle('#E8D5C3');
    ctx.setLineWidth(0.5);
    ctx.beginPath();
    ctx.moveTo(50, bottomLineY);
    ctx.lineTo(W - 50, bottomLineY);
    ctx.stroke();

    // 底部品牌
    ctx.setFontSize(12);
    ctx.setFillStyle('#CC6B45');
    ctx.setTextAlign('center');
    ctx.fillText('时光修复 · AI 照片品鉴', W / 2, bottomLineY + 20);

    // 导出 → 写入持久化文件 → 回调
    ctx.draw(false, function() {
      setTimeout(function() {
        wx.canvasToTempFilePath({
          canvasId: 'shareCanvas',
          destWidth: W * dpr,
          destHeight: H * dpr,
          success: function(res) {
            var persistPath = wx.env.USER_DATA_PATH + '/share_card_' + Date.now() + '.png';
            var fs = wx.getFileSystemManager();
            fs.saveFile({
              tempFilePath: res.tempFilePath,
              filePath: persistPath,
              success: function() {
                callback && callback(persistPath);
              },
              fail: function() {
                // saveFile 失败则用 temp path
                callback && callback(res.tempFilePath);
              }
            });
          },
          fail: function(e) {
            wx.hideLoading();
            console.error('canvas export fail:', JSON.stringify(e));
            wx.showToast({ title: '生成失败，请重试', icon: 'none' });
          }
        });
      }, 400);
    });
  },

  _ensureLocalPath: function(src, cb) {
    if (!src) { cb(null); return; }
    if (src.indexOf('data:') === 0) {
      var b64 = src.replace(/^data:image\/\w+;base64,/, '');
      var fp = wx.env.USER_DATA_PATH + '/tmp_share_' + Date.now() + '.jpg';
      var fs = wx.getFileSystemManager();
      fs.writeFile({
        filePath: fp, data: b64, encoding: 'base64',
        success: function() { cb(fp); },
        fail: function() { cb(null); }
      });
    } else if (src.indexOf('http') === 0 || src.indexOf('cloud://') === 0) {
      wx.downloadFile({
        url: src,
        success: function(res) {
          if (res.statusCode === 200) cb(res.tempFilePath);
          else cb(null);
        },
        fail: function() { cb(null); }
      });
    } else {
      cb(src);
    }
  }
});
