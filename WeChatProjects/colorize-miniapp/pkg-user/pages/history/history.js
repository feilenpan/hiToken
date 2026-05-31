// pages/history/history.js
const app = getApp()

Page({
  data: {
    records: [],
    loading: true,
    isEmpty: false,
    typeNames: {
      'colorize': 'AI上色',
      'restore': 'AI修复',
      'enhance': 'AI修复'
    },
    typeIcons: {
      'colorize': '🎨',
      'restore': '✨',
      'enhance': '✨'
    }
  },

  onShow() {
    this.loadRecords()
  },

  loadRecords() {
    if (!app.globalData.token) {
      this.setData({ loading: false, isEmpty: true })
      return
    }
    this.setData({ loading: true })

    app.cloudGet('/api/wechat/records')
      .then((res) => {
        if (res.data && res.data.records) {
          const records = res.data.records.map(r => ({
            ...r,
            result_url: r.result_url || '',
            timeStr: this.formatTime(r.created_at),
            typeName: this.data.typeNames[r.process_type] || 'AI处理',
            typeIcon: this.data.typeIcons[r.process_type] || '🎨'
          }))
          this.setData({ records: records, isEmpty: records.length === 0, loading: false })
        } else {
          this.setData({ loading: false, isEmpty: true })
        }
      })
      .catch(() => { this.setData({ loading: false, isEmpty: true }) })
  },

  formatTime(timestamp) {
    if (!timestamp) return ''
    const d = new Date(timestamp * 1000)
    return (d.getMonth()+1).toString().padStart(2,'0') + '-' +
           d.getDate().toString().padStart(2,'0') + ' ' +
           d.getHours().toString().padStart(2,'0') + ':' +
           d.getMinutes().toString().padStart(2,'0')
  },

  viewRecord(e) {
    const index = e.currentTarget.dataset.index
    const record = this.data.records[index]
    if (record && record.result_url) {
      wx.previewImage({ urls: [record.result_url], current: record.result_url })
    }
  },

  onPullDownRefresh() {
    this.loadRecords()
    wx.stopPullDownRefresh()
  },

  goHome() {
    wx.switchTab({ url: '/pages/index/index' })
  }
})
