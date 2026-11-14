import { api } from '../api.js';
import { ENUMS, can, liftTone, segmentTone } from '../config.js';
import {
  badge,
  drawer,
  errorBox,
  errorMessage,
  esc,
  field,
  fmtLift,
  fmtMoney,
  fmtNum,
  fmtPct,
  kv,
  table,
  toast,
} from '../ui.js';

const state = {
  weight_r: 0.3,
  weight_f: 0.3,
  weight_m: 0.4,
  window_days: 365,
  busy: false,
};

async function openSegment(view, ctx, segment) {
  const editable = can(ctx.user.role, 'segment:write');
  let members = { items: [] };
  try {
    members = await api.get('/api/members', { segment: segment.code, limit: 8 });
  } catch (err) {
    members = { items: [] };
  }
  const { root, close } = drawer({
    title: `${segment.name} · ${segment.code}`,
    subtitle: `规则 ${segment.rule_text} · ${fmtNum(segment.member_count)} 人（${fmtPct(segment.share, 1)}）`,
    body: `${kv([
      ['分群规则', esc(segment.rule_text)],
      ['人数 / 占比', `${fmtNum(segment.member_count)} / ${fmtPct(segment.share, 2)}`],
      ['平均 RFM', `<span class="mono">${Number(segment.avg_r_score).toFixed(2)} / ${Number(segment.avg_f_score).toFixed(2)} / ${Number(segment.avg_m_score).toFixed(2)}</span>`],
      ['平均 R 天数', `${Number(segment.avg_r_days || 0).toFixed(1)} 天`],
      ['人均窗口金额', fmtMoney(segment.avg_amount_window)],
      ['分群购买率', fmtPct(segment.purchase_rate)],
      ['提升度 lift', `<span class="lift-pill ${liftTone(segment.lift)}">${fmtLift(segment.lift)}</span>`],
      ['券面额', fmtMoney(segment.coupon_face, 0)],
      ['核心盘占比', fmtPct(segment.core_share, 0)],
      ['状态', segment.enabled ? '<span class="badge ok">参与分配</span>' : '<span class="badge">已停用</span>'],
    ])}
    <h3 style="margin:14px 0 8px;font-size:0.95rem">该群综合分最高会员（前 8 位）</h3>
    ${
      members.items.length
        ? `<div class="table-wrap"><table class="data" style="min-width:0">
            <thead><tr><th>会员</th><th>R/F/M</th><th>窗口金额</th><th>券响应率</th></tr></thead>
            <tbody>${members.items
              .map(
                (item) => `<tr><td>${esc(item.name)}<div class="mono muted">${esc(item.member_no)}</div></td>
                  <td class="mono">${item.r_score} / ${item.f_score} / ${item.m_score}</td>
                  <td class="num">${fmtMoney(item.amount_window, 0)}</td>
                  <td class="num">${fmtPct(item.purchase_rate)}</td></tr>`,
              )
              .join('')}</tbody></table></div>`
        : '<p class="muted">该分群暂无会员。</p>'
    }
    ${
      editable
        ? `<form id="coupon-form" class="filter-bar" style="margin-top:12px">
            ${field({ label: '券面额（元/张）', name: 'coupon_face', type: 'number', value: segment.coupon_face, attrs: 'step="0.5" min="0"' })}
            ${field({ label: '核心盘占比', name: 'core_share', type: 'number', value: segment.core_share, attrs: 'step="0.05" min="0.1" max="1"' })}
            <button class="btn sm accent" type="submit">保存券口径</button>
          </form>
          <div class="note">券面额只影响算法 B 的人均成本与 ROI，不改分群人数。</div>`
        : '<span class="mono muted">当前角色只能查看分群口径</span>'
    }`,
    footer: `<button class="btn ghost" data-members>看这 ${fmtNum(segment.member_count)} 人</button>`,
  });
  root.querySelector('[data-members]')?.addEventListener('click', () => {
    close();
    location.hash = `#/members?segment=${segment.code}`;
  });
  root.querySelector('#coupon-form')?.addEventListener('submit', async (event) => {
    event.preventDefault();
    const form = event.target;
    try {
      await api.patch(`/api/segments/${segment.id}`, {
        coupon_face: Number(form.coupon_face.value),
        core_share: Number(form.core_share.value),
      });
      toast('券口径已更新，去「名单与提升度」重新试算');
      close();
      await segmentsPage.render(view, ctx);
    } catch (err) {
      toast(errorMessage(err), 'err');
    }
  });
}

export const segmentsPage = {
  async render(view, ctx) {
    let data;
    try {
      data = await api.get('/api/segments');
    } catch (err) {
      view.innerHTML = errorBox(errorMessage(err));
      view.querySelector('#retry-btn')?.addEventListener('click', () => segmentsPage.render(view, ctx));
      return;
    }
    const snapshot = data.snapshot || {};
    if (snapshot.weights) {
      [state.weight_r, state.weight_f, state.weight_m] = snapshot.weights;
      state.window_days = snapshot.window_days || state.window_days;
    }
    const admin = can(ctx.user.role, 'segment:recompute');
    const top = data.items.reduce((best, item) => ((item.lift || 0) > (best.lift || 0) ? item : best), data.items[0] || {});
    view.innerHTML = `
      <section class="panel">
        <div class="panel-head">
          <h2>RFM 分群与分位阈值</h2>
          <span class="meta">快照 ${esc((data.as_of || '').slice(0, 10) || '—')} · 会员 ${fmtNum(data.members_total)} · 大盘购买率 ${fmtPct(data.global_purchase_rate)}</span>
        </div>
        <div class="panel-body" style="display:grid;gap:14px">
          <form id="recompute-form" class="filter-bar">
            <div class="weights" style="flex:1">
              ${field({ label: 'R 权重', name: 'weight_r', type: 'number', value: Number(state.weight_r).toFixed(1), attrs: 'step="0.1" min="0" max="1"' })}
              ${field({ label: 'F 权重', name: 'weight_f', type: 'number', value: Number(state.weight_f).toFixed(1), attrs: 'step="0.1" min="0" max="1"' })}
              ${field({ label: 'M 权重', name: 'weight_m', type: 'number', value: Number(state.weight_m).toFixed(1), attrs: 'step="0.1" min="0" max="1"' })}
            </div>
            ${field({
              label: 'F/M 统计窗口',
              name: 'window_days',
              value: String(state.window_days),
              options: ENUMS.windowDays.map((item) => ({ value: item.value, label: item.label })),
            })}
            <button class="btn accent" type="submit" ${admin ? '' : 'disabled'} data-testid="recompute">重算分群</button>
          </form>
          <div class="rule-chipline">
            ${['r', 'f', 'm']
              .map(
                (dim) =>
                  `<span class="rule-chip">${dim.toUpperCase()} 分位切点 ${esc(
                    JSON.stringify((data.thresholds || {})[dim] || []),
                  )}</span>`,
              )
              .join('')}
            <span class="rule-chip">同值同档：只与切点比较，不排名次</span>
            ${admin ? '' : '<span class="rule-chip">只读角色不能调阈值</span>'}
          </div>
          <div class="note">
            分群规则：${ENUMS.segmentOrder
              .map((code) => `${ENUMS.segment[code]}（${ENUMS.segmentRules[code]}）`)
              .join('；')}。按顺序首次命中，R 越小分越高。
          </div>
        </div>
        ${table({
          rows: data.items,
          columns: [
            {
              key: 'name',
              label: '分群',
              render: (row) => `<b>${esc(row.name)}</b><div class="mono muted">${esc(row.code)}</div>`,
            },
            { key: 'rule_text', label: '规则', render: (row) => `<span class="mono muted">${esc(row.rule_text)}</span>` },
            { key: 'member_count', label: '人数', className: 'num', render: (row) => fmtNum(row.member_count) },
            { key: 'share', label: '占比', className: 'num', render: (row) => fmtPct(row.share, 2) },
            {
              key: 'scores',
              label: '平均 RFM',
              className: 'num',
              render: (row) => `${Number(row.avg_r_score).toFixed(1)} / ${Number(row.avg_f_score).toFixed(1)} / ${Number(row.avg_m_score).toFixed(1)}`,
            },
            { key: 'purchase_rate', label: '购买率', className: 'num', render: (row) => fmtPct(row.purchase_rate) },
            {
              key: 'lift',
              label: '提升度',
              className: 'num',
              render: (row) => `<span class="lift-pill ${liftTone(row.lift)}">${fmtLift(row.lift)}</span>`,
            },
            { key: 'coupon_face', label: '券面额', className: 'num', render: (row) => fmtMoney(row.coupon_face, 0) },
            {
              key: 'enabled',
              label: '状态',
              render: (row) => (row.enabled ? badge('ok', '启用') : badge('', '停用')),
            },
          ],
          empty: { title: '还没有分群快照', hint: '管理员点一次「重算分群」。' },
        })}
      </section>

      <section class="panel">
        <div class="panel-head"><h2>怎么读这张表</h2><span class="meta">口径说明</span></div>
        <div class="panel-body note">
          当前提升度最高的分群是 <b>${esc(top.name || '—')}</b>（lift ${fmtLift(top.lift)}，${fmtNum(top.member_count)} 人）。
          把权重从 0.3/0.3/0.4 调成 0.6/0.2/0.2，综合分排序会变，但八类规则只依赖 R/F/M 各自的分档，
          所以人数变化只来自分位切点移动（窗口变了切点也变）。这正是「阈值拍脑袋 → 人数不可解释」的解法。
        </div>
      </section>`;

    view.querySelector('#recompute-form')?.addEventListener('submit', async (event) => {
      event.preventDefault();
      const form = event.target;
      const payload = {
        weight_r: Number(form.weight_r.value),
        weight_f: Number(form.weight_f.value),
        weight_m: Number(form.weight_m.value),
        window_days: Number(form.window_days.value),
      };
      const sum = payload.weight_r + payload.weight_f + payload.weight_m;
      if (Math.abs(sum - 1) > 0.001) {
        toast('三项权重之和必须等于 1.0', 'err');
        return;
      }
      const button = form.querySelector('button[type=submit]');
      button.disabled = true;
      button.textContent = '重算中…';
      try {
        const result = await api.post('/api/segments/recompute', payload);
        const topSegment = (result.segments || []).reduce(
          (best, item) => ((item.lift || 0) > (best.lift || 0) ? item : best),
          { lift: 0, name: '—' },
        );
        toast(`重算完成：${result.member_count} 人，最高 ${topSegment.name} lift ${Number(topSegment.lift).toFixed(2)}`);
        await segmentsPage.render(view, ctx);
      } catch (err) {
        toast(errorMessage(err), 'err');
        button.disabled = false;
        button.textContent = '重算分群';
      }
    });
    view.querySelectorAll('table.data tbody tr').forEach((row) => {
      row.addEventListener('click', () => {
        const item = data.items.find((entry) => String(entry.id) === row.dataset.id);
        if (item) openSegment(view, ctx, item);
      });
    });
  },
};

export default segmentsPage;
