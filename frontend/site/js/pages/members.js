import { api } from '../api.js';
import { ENUMS, segmentTone } from '../config.js';
import {
  badge,
  drawer,
  errorBox,
  errorMessage,
  esc,
  field,
  fmtMoney,
  fmtNum,
  fmtPct,
  fmtTime,
  kv,
  scoreBar,
  table,
} from '../ui.js';

const state = { q: '', segment: '', tier: '', min_amount: '' };

async function openMember(view, ctx, member) {
  let detail;
  try {
    detail = await api.get(`/api/members/${member.id}`);
  } catch (err) {
    return;
  }
  const orders = detail.orders || [];
  const { root, close } = drawer({
    title: `${detail.name} · ${detail.member_no}`,
    subtitle: `${detail.tier_label} · ${detail.city} · ${detail.phone}${detail.phone_masked ? '（已脱敏）' : ''}`,
    body: `${kv([
      ['最近下单', fmtTime(detail.last_order_at)],
      ['R（距今天数）', `${detail.r_days ?? '—'} 天`],
      ['窗口内单数', fmtNum(detail.orders_window)],
      ['窗口内金额', fmtMoney(detail.amount_window)],
      ['RFM 得分', scoreBar(detail.r_score, detail.f_score, detail.m_score)],
      ['综合分', `<span class="mono">${Number(detail.composite_score || 0).toFixed(2)}</span>`],
      ['所属分群', badge(segmentTone(detail.segment_code), detail.segment_label || '未评分')],
      ['历史券响应率', fmtPct(detail.purchase_rate)],
      ['平均客单价', fmtMoney(detail.avg_ticket)],
      ['入会日期', esc(detail.joined_on)],
    ])}
    <h3 style="margin:14px 0 8px;font-size:0.95rem">订单（最近 ${orders.length} / 共 ${fmtNum(detail.orders_total)} 笔）</h3>
    ${
      orders.length
        ? `<div class="table-wrap"><table class="data" style="min-width:0">
            <thead><tr><th>订单号</th><th>门店</th><th>渠道</th><th>金额</th><th>用券</th><th>时间</th></tr></thead>
            <tbody>${orders
              .map(
                (order) => `<tr><td class="mono">${esc(order.order_no)}</td><td>${esc(order.store_code)}</td>
                  <td>${esc(order.channel_label)}</td><td class="num">${fmtMoney(order.amount)}</td>
                  <td>${order.coupon_used ? '是' : '—'}</td><td class="mono">${fmtTime(order.paid_at)}</td></tr>`,
              )
              .join('')}</tbody></table></div>`
        : '<p class="muted">这位会员还没有订单记录。</p>'
    }`,
    footer: `<span class="mono muted">数据口径：F/M 为 ${esc(ctx.windowDays || 365)} 天窗口内的订单事实</span>`,
  });
  root.querySelectorAll('[data-close]').forEach((node) => node.addEventListener('click', close));
}

export const membersPage = {
  async render(view, ctx) {
    if (ctx.query.segment) state.segment = ctx.query.segment;
    if (ctx.query.tier) state.tier = ctx.query.tier;
    let data;
    try {
      data = await api.get('/api/members', {
        q: state.q,
        segment: state.segment,
        tier: state.tier,
        min_amount: state.min_amount,
        limit: 40,
      });
    } catch (err) {
      view.innerHTML = errorBox(errorMessage(err));
      view.querySelector('#retry-btn')?.addEventListener('click', () => membersPage.render(view, ctx));
      return;
    }
    view.innerHTML = `
      <section class="panel">
        <div class="panel-head">
          <h2>会员与订单</h2>
          <span class="meta">${fmtNum(data.total)} 位会员 · 按综合分倒序</span>
        </div>
        <div class="panel-body">
          <div class="filter-bar" id="member-filters">
            ${field({ label: '搜索', name: 'q', value: state.q, placeholder: '会员号 / 姓名 / 手机号' })}
            ${field({
              label: '分群',
              name: 'segment',
              value: state.segment,
              options: [
                { value: '', label: '全部分群' },
                ...ENUMS.segmentOrder.map((code) => ({ value: code, label: ENUMS.segment[code] })),
              ],
            })}
            ${field({
              label: '卡等级',
              name: 'tier',
              value: state.tier,
              options: [
                { value: '', label: '全部等级' },
                ...Object.entries(ENUMS.tier).map(([value, label]) => ({ value, label })),
              ],
            })}
            ${field({ label: '窗口内金额 ≥', name: 'min_amount', type: 'number', value: state.min_amount, placeholder: '0' })}
            <div class="spacer"></div>
            <span class="note">${
              ctx.user.role === 'viewer' ? '只读角色：手机号自动脱敏' : '管理员 / 专员可见完整手机号'
            }</span>
          </div>
        </div>
        ${table({
          rows: data.items,
          columns: [
            {
              key: 'member_no',
              label: '会员',
              render: (row) => `<b>${esc(row.name)}</b><div class="mono muted">${esc(row.member_no)} · ${esc(row.phone)}</div>`,
            },
            { key: 'tier_label', label: '卡等级' },
            {
              key: 'segment_code',
              label: '分群',
              render: (row) => (row.segment_code ? badge(segmentTone(row.segment_code), row.segment_label) : '<span class="muted">未评分</span>'),
            },
            { key: 'r_score', label: 'RFM', render: (row) => scoreBar(row.r_score, row.f_score, row.m_score) },
            { key: 'r_days', label: 'R(天)', className: 'num', render: (row) => row.r_days ?? '—' },
            { key: 'orders_window', label: '单数', className: 'num', render: (row) => fmtNum(row.orders_window) },
            { key: 'amount_window', label: '金额', className: 'num', render: (row) => fmtMoney(row.amount_window, 0) },
            { key: 'purchase_rate', label: '券响应率', className: 'num', render: (row) => fmtPct(row.purchase_rate) },
            { key: 'composite_score', label: '综合分', className: 'num', render: (row) => Number(row.composite_score || 0).toFixed(2) },
          ],
          empty: { title: '没有匹配的会员', hint: '换个分群或清空搜索词再试。' },
        })}
      </section>`;

    const filters = view.querySelector('#member-filters');
    const apply = () => {
      state.q = filters.querySelector('[name=q]').value.trim();
      state.segment = filters.querySelector('[name=segment]').value;
      state.tier = filters.querySelector('[name=tier]').value;
      state.min_amount = filters.querySelector('[name=min_amount]').value;
      membersPage.render(view, ctx);
    };
    filters?.addEventListener('change', apply);
    filters?.querySelector('[name=q]')?.addEventListener('keydown', (event) => {
      if (event.key === 'Enter') apply();
    });
    view.querySelectorAll('table.data tbody tr').forEach((row) => {
      row.addEventListener('click', () => {
        const item = data.items.find((entry) => String(entry.id) === row.dataset.id);
        if (item) openMember(view, ctx, item);
      });
    });
  },
};

export default membersPage;
