import { api } from '../api.js';
import { ENUMS, liftTone } from '../config.js';
import {
  barList,
  emptyState,
  errorBox,
  errorMessage,
  esc,
  fmtLift,
  fmtMoney,
  fmtNum,
  fmtPct,
  statStrip,
  trendChart,
} from '../ui.js';

function segTiles(segments) {
  return `<div class="seg-grid" data-testid="segment-grid">${segments
    .map(
      (item) => `<button class="seg-tile" data-segment="${esc(item.code)}">
        <span class="t-name">${esc(item.name)}</span>
        <span class="t-count">${fmtNum(item.member_count)}</span>
        <span class="t-lift">${fmtPct(item.share, 1)} · lift <b>${fmtLift(item.lift)}</b></span>
      </button>`,
    )
    .join('')}</div>`;
}

export const overviewPage = {
  async render(view, ctx) {
    view.innerHTML = '<div class="empty"><div class="mark">正在对账会员与订单…</div></div>';
    let data;
    try {
      data = await api.get('/api/overview');
    } catch (err) {
      view.innerHTML = errorBox(errorMessage(err));
      view.querySelector('#retry-btn')?.addEventListener('click', () => overviewPage.render(view, ctx));
      return;
    }
    const latest = data.latest_audience;
    const snapshot = data.snapshot || {};
    const budget = data.budget_total || 0;
    const p0 = snapshot.global_purchase_rate || 0;
    view.innerHTML = `
      <section class="hero">
        <div class="hero-main">
          <div class="eyebrow">会员资产总览 · 快照 ${esc((data.as_of || '').slice(0, 10) || '—')}</div>
          <div class="big">${fmtNum(data.members_total)}<small>位会员</small></div>
          <div class="rule-chipline">
            <span class="rule-chip">订单 ${fmtNum(data.orders_total)} 单</span>
            <span class="rule-chip">累计 GMV ${fmtMoney(data.gmv_total, 0)}</span>
            <span class="rule-chip">近 30 天 ${fmtNum(data.orders_30d)} 单</span>
            <span class="rule-chip">大盘购买率 ${fmtPct(p0)}</span>
          </div>
          <div class="note">
            F/M 窗口 ${esc(snapshot.window_days || 365)} 天，权重
            ${(snapshot.weights || [0.3, 0.3, 0.4]).map((w) => Number(w).toFixed(1)).join(' / ')}；
            分位阈值 R ${esc(JSON.stringify(snapshot.thresholds?.r || []))}。阈值一改，分群人数与 lift 会整批重算。
          </div>
        </div>
        <div class="hero-side">
          <div class="seal-mark">牧野<br />会员</div>
          <div class="eyebrow">本季券预算 / 预计结果</div>
          <div class="kv" style="grid-template-columns:80px 1fr">
            <dt>活动数</dt><dd>${fmtNum(data.campaigns_total)} 个（${fmtNum(data.pending_audiences)} 份待确认名单）</dd>
            <dt>预算</dt><dd class="mono">${fmtMoney(budget)}</dd>
            <dt>名单人数</dt><dd class="mono">${latest ? fmtNum(latest.member_count) : '—'}</dd>
            <dt>预计增量</dt><dd class="mono">${latest ? `${fmtNum(latest.inc_orders)} 单 / ${fmtMoney(latest.inc_gmv, 0)}` : '—'}</dd>
            <dt>预计 ROI</dt><dd class="mono">${latest ? Number(latest.roi).toFixed(2) : '—'}</dd>
          </div>
          ${
            latest
              ? `<div class="note">最近名单 <b>${esc(latest.audience_no)}</b> · ${esc(latest.status_label)} ·
                  花费 ${fmtMoney(latest.spend)}</div>`
              : emptyState({ title: '还没有名单', hint: '去「名单与提升度」按预算生成一份。' })
          }
        </div>
      </section>

      ${statStrip([
        { label: '会员数', value: fmtNum(data.members_total), hint: '32 万会员的 1/40 抽样' },
        { label: '可投分群', value: data.segments.filter((item) => item.lift > 1 && item.member_count > 0).length, hint: 'lift > 1 且有人' },
        { label: '最高 lift', value: fmtLift(Math.max(...data.segments.map((item) => item.lift || 0))), hint: '分群购买率 / 大盘' },
        { label: '后台任务', value: data.worker_alive ? '在岗' : '心跳超时', hint: 'Celery 每日重算' },
      ])}

      <section class="panel">
        <div class="panel-head">
          <h2>八类 RFM 分群</h2>
          <span class="meta">点击分群查看规则与名单</span>
        </div>
        <div class="panel-body">${segTiles(data.segments)}</div>
      </section>

      <div class="grid-2">
        <section class="panel">
          <div class="panel-head"><h2>近 7 天订单</h2><span class="meta">orders / day</span></div>
          <div class="panel-body">${trendChart(
            data.trend.map((point) => ({ date: point.date, runs: point.orders })),
          )}</div>
        </section>
        <section class="panel">
          <div class="panel-head"><h2>会员卡等级</h2><span class="meta">tier</span></div>
          <div class="panel-body">${
            data.tiers.length
              ? barList(data.tiers.map((item) => ({ label: item.label, count: item.count })))
              : emptyState({ title: '还没有会员', hint: '先执行 seed。' })
          }</div>
        </section>
      </div>

      <section class="panel">
        <div class="panel-head">
          <h2>提升度一览</h2>
          <span class="meta">lift = 分群购买率 / 大盘购买率</span>
        </div>
        <div class="panel-body">
          <div class="table-wrap">
            <table class="data seg-table">
              <thead><tr><th>分群</th><th>人数</th><th>占比</th><th>购买率</th><th>lift</th><th>券面额</th></tr></thead>
              <tbody>
                ${data.segments
                  .map(
                    (item) => `<tr data-id="${esc(item.code)}">
                      <td><b>${esc(item.name)}</b></td>
                      <td class="num">${fmtNum(item.member_count)}</td>
                      <td class="num">${fmtPct(item.share, 1)}</td>
                      <td class="num">${fmtPct(item.purchase_rate)}</td>
                      <td class="num"><span class="lift-pill ${liftTone(item.lift)}">${fmtLift(item.lift)}</span></td>
                      <td class="num">${fmtMoney(item.coupon_face, 0)}</td>
                    </tr>`,
                  )
                  .join('')}
              </tbody>
            </table>
          </div>
        </div>
      </section>`;

    view.querySelectorAll('.seg-tile').forEach((tile) => {
      tile.addEventListener('click', () => {
        ctx.navigate(`#/members?segment=${tile.dataset.segment}`);
      });
    });
  },
};

export default overviewPage;
