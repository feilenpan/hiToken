// pages/score/score.js
var app = getApp();

var LEVELS = [
  { min: 95, emoji: '🏆', title: '时光宝藏', desc: '无可替代的回忆' },
  { min: 90, emoji: '💎', title: '岁月珍品', desc: '历久弥新的感动' },
  { min: 85, emoji: '🌟', title: '温暖瞬间', desc: '触动心弦的画面' },
  { min: 80, emoji: '✨', title: '美好时刻', desc: '值得珍藏的记忆' },
  { min: 70, emoji: '📸', title: '珍贵印记', desc: '生活中的小确幸' },
  { min: 55, emoji: '📷', title: '朴实记录', desc: '平凡也值得被记住' },
  { min: 0,  emoji: '💝', title: '随手拍', desc: '每一刻都有它的意义' }
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
    evaluation: null,
    typedText: '',
    showScore: false,
    showCTA: false,
    quality: null,
    typingCursor: true,
    activeSuggestion: null,
    editResults: [],
    showPrivacyPopup: false,
    quota: null
  },

  onShow: function() {
    this._fetchQuota();
  },

  _twTimer: null,
  _txtTimer: null,

  onUnload: function() {
    if (this._twTimer) clearInterval(this._twTimer);
    if (this._txtTimer) clearInterval(this._txtTimer);
  },

  _fetchQuota: function() {
    if (!app.globalData.token) return;
    var that = this;
    app.cloudGet('/api/user/usage').then(function(res) {
      if (res.data && res.data.success) {
        that.setData({ quota: res.data.quota });
      }
    }).catch(function() {});
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

    app.cloudUpload('/api/evaluate', path)
      .then(function(res) {
        if (that._txtTimer) clearInterval(that._txtTimer);
        that.setData({ isUploading: false, showAnalyzing: false });

        console.log('[score] evaluate success');

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
    var level = LEVELS[5];
    for (var i = 0; i < LEVELS.length; i++) {
      if (ev.score >= LEVELS[i].min) { level = LEVELS[i]; break; }
    }
    ev.level = level;
    
    that.setData({ evaluation: ev });
    that._typewriter(ev.text || '');
    
    if (ev.score < 55) {
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
      suggestions: [],
      fallback: true,
      reviewer: '时光点评师',
      level: LEVELS[3]
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

    console.log('[score] repair-now #' + editId);

    app.cloudUpload('/api/suggest-edit', that.data.imagePath, { prompt: prompt })
      .then(function(res) {
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
      })
      .catch(function(err) {
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
    var item = e.currentTarget.dataset.suggestion;
    var index = e.currentTarget.dataset.index;
    if (!item || !item.prompt) return;

    // 防重复：已点击或处理中不可再点
    if (item.clicked || item.loading) return;

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

    console.log('[score] suggest-edit #' + editId, 'prompt:', item.prompt);

    app.cloudUpload('/api/suggest-edit', that.data.imagePath, { prompt: item.prompt })
      .then(function(res) {
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
      })
      .catch(function(err) {
        suggestions[index].loading = false;
        that.setData({ 'evaluation.suggestions': suggestions });

        console.error('[score] suggest-edit #' + editId + ' fail:', JSON.stringify(err));

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
      title: '时光修复 - AI照片打分',
      path: '/pages/score/score'
    };
  }
});
