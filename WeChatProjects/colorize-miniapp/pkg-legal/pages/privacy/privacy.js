// pages/privacy/privacy.js
Page({
  data: { content: '' },

  onLoad() { this.loadPrivacyContent() },

  loadPrivacyContent() {
    const app = getApp()
    app.cloudGet('/api/privacy')
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
      content: '隐私保护政策\n\n最后更新日期：2026年5月30日\n\n一、引言\n「鱼数修照」非常重视您的隐私保护。\n\n二、我们收集的信息\n• 您上传的照片：仅用于本次AI处理，处理完成后立即删除\n• 微信账号信息（OpenID、昵称、头像）：用于登录识别\n• 设备信息：用于兼容性优化，保存30天\n\n三、信息保护\n• 所有数据存储在中国境内服务器，数据不出境\n• 所有数据传输采用HTTPS加密\n• 照片处理完成后立即删除，修复结果30天后自动删除\n• 不会将您的信息出售或分享给任何第三方\n\n四、AI服务商\n为实现AI功能，我们会将照片临时发送至以下国内服务商处理：\n• 火山引擎（seededit模型）\n• 豆包大模型\n所有数据处理在境内完成，处理完毕后不保留。\n\n五、您的权利\n• 查阅权、更正权、删除权、撤回同意权、注销账户权\n• 可通过小程序内客服或邮箱 yushutec@gmail.com 行使权利\n\n六、联系我们\n小程序内客服或邮箱：yushutec@gmail.com'
    })
  }
})
