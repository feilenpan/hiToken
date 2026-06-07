// pages/score/score.js
var app = getApp();

// 印章评级（不显示数字，只用印章文字）
var STAMP_LEVELS = [
  { min: 90, stamp: '神品', hint: '妙手偶得' },
  { min: 80, stamp: '妙品', hint: '意趣天成' },
  { min: 70, stamp: '佳作', hint: '赏心悦目' },
  { min: 55, stamp: '可觀', hint: '别有风味' },
  { min: 0,  stamp: '待琢', hint: '修后更妙' }
];

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
    typedText: '',
    showScore: false,
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
          typedText: '',
          showScore: false,
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
          quality: null,
          typedText: '',
          showScore: false,
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
    var stamp = STAMP_LEVELS[4];
    for (var i = 0; i < STAMP_LEVELS.length; i++) {
      if ((ev.score || 0) >= STAMP_LEVELS[i].min) { stamp = STAMP_LEVELS[i]; break; }
    }
    ev.stampLevel = stamp.stamp;
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
      reviewer: '时光点评师',
      stampLevel: '佳作'
    };
    that.setData({ evaluation: ev });
    that._typewriter(ev.text);
  },

  _typewriter: function(text) {
    var that = this;
    if (!text) { that.setData({ showScore: true, typingCursor: false }); return; }
    if (that._twTimer) clearInterval(that._twTimer);
    
    var chars = text.split('');
    var idx = 0;
    
    that._twTimer = setInterval(function() {
      if (idx >= chars.length) {
        clearInterval(that._twTimer);
        that._twTimer = null;
        setTimeout(function() {
          that.setData({ showScore: true, typingCursor: false });
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

    app.cloudUpload('/api/suggest-edit', that.data.imagePath, { prompt: prompt }, true)
      .then(function(res) {
        console.log('[score] repair-now #' + editId + ' GOT RESPONSE:', JSON.stringify(res.data).substring(0, 200));
        var data = res.data;
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
    this.setData({
      imagePath: '',
      evaluation: null,
      quality: null,
      typedText: '',
      showScore: false,
      showCTA: false,
      editResults: [],
      activeSuggestion: null
    });
    _editId = 0;
    // 直接弹出照片选择器，一步到位
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

    app.cloudUpload('/api/suggest-edit', that.data.imagePath, { prompt: item.prompt }, true)
      .then(function(res) {
        console.log('[score] suggest-edit #' + editId + ' GOT RESPONSE:', JSON.stringify(res.data).substring(0, 200));
        suggestions[index].loading = false;
        that.setData({ 'evaluation.suggestions': suggestions });

        var data = res.data;
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
  }
});
