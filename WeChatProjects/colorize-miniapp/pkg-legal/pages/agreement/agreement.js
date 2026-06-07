// pages/agreement/agreement.js
Page({
  data: { content: '' },

  onLoad() { this.loadAgreementContent() },

  loadAgreementContent() {
    const app = getApp()
    app.cloudGet('/api/agreement')
      .then((res) => {
        if (res.data && res.data.success) {
          this.setData({ content: res.data.content })
        } else {
          this.loadDefaultContent()
        }
      })
      .catch(() => { this.loadDefaultContent() })
  },

  loadDefaultContent() {
    this.setData({
      content: '用户服务协议\n\n最后更新日期：2026年5月30日\n\n一、服务条款\n欢迎使用「鱼数修照」。使用本服务即表示您同意本协议。\n\n二、服务内容\n本服务提供AI照片品鉴和AI照片修复功能，每日有限次免费使用。\n\n三、使用规范\n• 请遵守中华人民共和国法律法规\n• 请勿上传违法违规内容或侵犯他人权益的内容\n• 请勿对服务进行反向工程或攻击\n\n四、数据处理\n• 您上传的照片知识产权归您所有\n• 照片处理完成后立即从服务器删除\n• 所有数据存储在中国境内，数据不出境\n\n五、免责声明\n• AI评分和修复结果由AI自动生成，仅供参考\n• 不对AI处理结果的准确性做保证\n\n六、联系我们\n小程序内客服或邮箱：yushutec@gmail.com'
    })
  }
})
