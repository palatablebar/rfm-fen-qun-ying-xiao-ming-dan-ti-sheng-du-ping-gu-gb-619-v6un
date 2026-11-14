import { api } from '../api.js';
import { session } from '../store.js';
import { BRAND } from '../config.js';
import { errorMessage, esc, toast } from '../ui.js';

export const loginPage = {
  async render(root, ctx) {
    root.className = 'login-host';
    root.innerHTML = `
      <div class="login">
        <section class="login-brief">
          <div class="eyebrow">${esc(BRAND.edition)}</div>
          <h1>${esc(BRAND.title)}<em>提升度评估</em></h1>
          <p class="tagline">${esc(BRAND.loginLead)}</p>
          <div class="member-card">
            <div class="card-top">
              <span class="card-brand">牧野茶饮</span>
              <span class="card-no">${esc(BRAND.cardNo)}</span>
            </div>
            <div class="card-tier">${esc(BRAND.cardTier)} · 会员运营组持卡</div>
            <div class="card-points">
              ${BRAND.cardPoints
                .map(([label, value]) => `<div><b>${esc(value)}</b>${esc(label)}</div>`)
                .join('')}
            </div>
            <div class="seal">牧野<br />会员</div>
          </div>
          <div class="brief-points">
            ${BRAND.loginPoints
              .map(([no, text]) => `<div class="brief-point"><i>${esc(no)}</i><span>${esc(text)}</span></div>`)
              .join('')}
          </div>
          <div class="eyebrow" style="margin-top:auto">${esc(BRAND.org)} · 内部工作台</div>
        </section>
        <section class="login-form-wrap">
          <form class="login-card" id="login-form" novalidate>
            <div>
              <div class="brand">持卡登录</div>
              <div class="sub">三个演示账号权限不同：管理员调阈值与发券、专员看 lift 与确认名单、门店只读且手机号脱敏。</div>
            </div>
            <div class="field">
              <label for="email">邮箱</label>
              <input id="email" name="email" type="email" autocomplete="username" value="admin@${esc(BRAND.short)}.io" required />
            </div>
            <div class="field">
              <label for="password">密码</label>
              <input id="password" name="password" type="password" autocomplete="current-password" value="Demo@2026" required />
            </div>
            <div class="form-error" id="login-error" role="alert"></div>
            <button class="btn accent" id="login-submit" type="submit">盖章进入</button>
            <div class="login-hint">
              演示账号（密码 <code>Demo@2026</code>）：<br />
              <code>admin@${esc(BRAND.short)}.io</code> 管理员 · <code>analyst@${esc(BRAND.short)}.io</code> 数据专员 ·
              <code>viewer@${esc(BRAND.short)}.io</code> 门店只读
            </div>
          </form>
        </section>
      </div>`;

    const form = root.querySelector('#login-form');
    const errorNode = root.querySelector('#login-error');
    const submit = root.querySelector('#login-submit');
    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      errorNode.textContent = '';
      submit.disabled = true;
      submit.textContent = '正在核对会员卡…';
      try {
        const result = await api.post('/api/auth/login', {
          email: form.email.value.trim(),
          password: form.password.value,
        });
        session.set(result.access_token, result.user);
        toast(`欢迎回来，${result.user.display_name}`);
        location.hash = '#/overview';
        await ctx.reload();
      } catch (err) {
        errorNode.textContent = err.code === 'AUTH_INVALID' ? '账号或密码不正确' : errorMessage(err);
      } finally {
        submit.disabled = false;
        submit.textContent = '盖章进入';
      }
    });
  },
};

export default loginPage;
