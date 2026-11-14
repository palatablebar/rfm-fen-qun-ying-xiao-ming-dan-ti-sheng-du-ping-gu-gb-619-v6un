import { api } from '../api.js';
import { ENUMS, audienceTone, can, evaluationTone, liftTone } from '../config.js';
import {
  badge,
  budgetBar,
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
  statStrip,
  table,
  toast,
} from '../ui.js';

const state = {
  campaignId: '',
  budget: '',
  allocation: null,
  evaluations: { items: [], total: 0, published: 0, in_progress: 0 },
  loading: false,
};

async function loadAllocation(view, ctx, campaigns) {
  const campaign = campaigns.find((item) => String(item.id) === String(state.campaignId)) || campaigns[0];
  if (!campaign) return null;
  const budget = Number(state.budget || campaign.budget);
  try {
    const data = await api.get(`/api/campaigns/${campaign.id}/allocation`, { budget });
    state.campaignId = String(campaign.id);
    return data;
  } catch (err) {
    toast(errorMessage(err), 'err');
    return null;
  }
}

async function loadEvaluations(campaignId) {
  try {
    state.evaluations = await api.get('/api/evaluations', { campaign_id: Number(campaignId) });
  } catch (err) {
    state.evaluations = { items: [], total: 0, published: 0, in_progress: 0 };
  }
  return state.evaluations;
}

function allocationTable(allocation) {
  return `<div class="table-wrap"><table class="data allocation-table">
    <thead><tr>
      <th>优先级</th><th>分群</th><th>lift</th><th>券面额</th><th>人均成本</th><th>lift/成本</th>
      <th>投放人数</th><th>券预算</th><th>预计增量</th><th>增量 GMV</th><th>ROI</th><th>状态</th>
    </tr></thead>
    <tbody>
      ${allocation.segments
        .map(
          (row) => `<tr data-code="${esc(row.segment_code)}">
            <td class="num">${row.priority ?? '—'}</td>
            <td><b>${esc(row.segment_name)}</b>
              <div class="mini">${esc(row.status === 'allocated' ? row.reason : row.reason)}</div>
            </td>
            <td class="num"><span class="lift-pill ${liftTone(row.lift)}">${fmtLift(row.lift)}</span></td>
            <td class="num">${fmtMoney(row.coupon_face, 0)}</td>
            <td class="num">${fmtMoney(row.unit_cost)}</td>
            <td class="num">${Number(row.efficiency).toFixed(2)}</td>
            <td class="num">${fmtNum(row.allocated)}<div class="mini">核心 ${fmtNum(row.core_allocated)} / 溢出 ${fmtNum(row.tail_allocated)}</div></td>
            <td class="num">${fmtMoney(row.budget)}</td>
            <td class="num">${fmtNum(row.inc_orders)}</td>
            <td class="num">${fmtMoney(row.inc_gmv, 0)}</td>
            <td class="num">${Number(row.roi).toFixed(2)}</td>
            <td>${badge(row.status === 'allocated' ? 'ok' : row.status === 'deferred' ? 'warn' : '', ENUMS.allocationStatus[row.status])}</td>
          </tr>`,
        )
        .join('')}
    </tbody>
  </table></div>`;
}

function historyTable(audiences) {
  return table({
    rows: audiences,
    columns: [
      { key: 'audience_no', label: '名单号', className: 'mono' },
      { key: 'campaign_name', label: '活动' },
      { key: 'status', label: '名单状态', render: (row) => badge(audienceTone(row.status), row.status_label) },
      { key: 'member_count', label: '人数', className: 'num', render: (row) => fmtNum(row.member_count) },
      { key: 'budget', label: '预算', className: 'num', render: (row) => fmtMoney(row.budget) },
      { key: 'spend', label: '实花', className: 'num', render: (row) => fmtMoney(row.spend) },
      { key: 'inc_orders', label: '预估增量（投放前）', className: 'num', render: (row) => fmtNum(row.inc_orders) },
      { key: 'roi', label: '预估 ROI（投放前）', className: 'num', render: (row) => Number(row.roi).toFixed(2) },
      {
        key: 'evaluation',
        label: '结算评估（投放后）',
        render: (row) =>
          row.evaluation
            ? `${badge(evaluationTone(row.evaluation.status), row.evaluation.status_label)}
               <span class="mono muted">增量率 ${fmtPct(row.evaluation.incremental_rate)} · ROI ${Number(
                 row.evaluation.roi,
               ).toFixed(2)}</span>`
            : '<span class="muted">未确认</span>',
      },
      { key: 'operator_email', label: '生成人', render: (row) => `<span class="mono muted">${esc(row.operator_email)}</span>` },
    ],
    empty: { title: '还没有名单', hint: '选好活动与预算，点「生成名单」。' },
  });
}

function parseSettlementCsv(text) {
  const rows = [];
  const lines = String(text || '')
    .replace(/^﻿/, '')
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
  if (!lines.length) return rows;
  const headers = lines[0].split(',').map((item) => item.trim().toLowerCase());
  const indexOf = (names) => headers.findIndex((item) => names.includes(item));
  const memberIndex = indexOf(['member_no', '会员号', 'member', 'mobile']);
  const redeemedIndex = indexOf(['redeemed', '核销', 'coupon_redeemed']);
  const ordersIndex = indexOf(['orders', '单量', 'order_count']);
  const gmvIndex = indexOf(['gmv', '金额', 'amount']);
  const asOfIndex = indexOf(['as_of', '日期', 'date']);
  if (memberIndex < 0) return rows;
  for (const line of lines.slice(1)) {
    const cells = line.split(',').map((item) => item.trim());
    if (!cells[memberIndex]) continue;
    const flag = redeemedIndex >= 0 ? cells[redeemedIndex] : '';
    rows.push({
      member_no: cells[memberIndex],
      redeemed: /^(1|true|y|yes|是|已核销|核销)$/i.test(flag),
      orders: ordersIndex >= 0 && cells[ordersIndex] !== '' ? Number(cells[ordersIndex]) : undefined,
      gmv: gmvIndex >= 0 && cells[gmvIndex] !== '' ? Number(cells[gmvIndex]) : undefined,
      as_of: asOfIndex >= 0 && cells[asOfIndex] ? cells[asOfIndex] : undefined,
    });
  }
  return rows;
}

function evaluationTable(evaluations) {
  return table({
    rows: evaluations.items,
    columns: [
      { key: 'audience_no', label: '名单号', className: 'mono' },
      { key: 'status', label: '评估状态', render: (row) => badge(evaluationTone(row.status), row.status_label) },
      { key: 'treated_count', label: '处理人数', className: 'num', render: (row) => fmtNum(row.treated_count) },
      {
        key: 'control_count',
        label: '对照人数',
        className: 'num',
        render: (row) => fmtNum(row.control_count),
      },
      {
        key: 'incremental_rate',
        label: '增量率',
        className: 'num',
        render: (row) => `<b>${fmtPct(row.incremental_rate)}</b>`,
      },
      { key: 'roi', label: 'ROI', className: 'num', render: (row) => Number(row.roi).toFixed(2) },
      { key: 'treated_rate', label: '处理组转化率', className: 'num', render: (row) => fmtPct(row.treated_rate) },
      { key: 'control_rate', label: '对照组自然转化率', className: 'num', render: (row) => fmtPct(row.control_rate) },
      {
        key: 'batch_no',
        label: '结算批次',
        render: (row) =>
          `<span class="mono muted">${esc(row.batch_no || '—')}${
            row.data_as_of ? ` · ${esc(row.data_as_of)}` : ''
          }</span>`,
      },
      {
        key: 'published_by',
        label: '发布',
        render: (row) =>
          row.published_at
            ? `<span class="mono muted">${esc((row.published_by || '').split('@')[0])} · ${esc(
                row.published_at.slice(0, 10),
              )}</span>`
            : '<span class="muted">—</span>',
      },
    ],
    empty: {
      title: '这个活动还没有结算评估',
      hint: '确认名单时会自动冻结同口径对照组；导入券平台核销批次后即可查看增量率。',
    },
  });
}

function importDrawer(view, ctx, campaigns) {
  const campaignId =
    state.evaluations.campaign?.id || campaigns.find((item) => String(item.id) === String(state.campaignId))?.id;
  if (!campaignId) {
    toast('先选择一个活动', 'err');
    return;
  }
  const { root, close } = drawer({
    title: '导入结算批次',
    subtitle: '券平台核销 / 订单回流 CSV · 同批次重试不会重复累计',
    body: `<form id="settlement-form" style="display:grid;gap:12px">
      ${field({ label: '批次号', name: 'batch_no', value: `B${new Date().toISOString().slice(0, 10).replace(/-/g, '')}`, attrs: 'maxlength="64"' })}
      ${field({ label: '数据截止', name: 'as_of', type: 'date', value: new Date().toISOString().slice(0, 10) })}
      <div class="field">
        <label for="settlement-file">结算 CSV（member_no, redeemed, orders, gmv, as_of）</label>
        <input id="settlement-file" type="file" accept=".csv,text/csv" />
      </div>
      <div class="note">
        核销和订单会分批晚到：同一会员以「数据截止」更新的记录为准；已发布评估的数字会锁定，晚到批次只计跳过。
      </div>
      <div class="rule-chipline">
        <button class="btn accent" type="submit">导入并重算</button>
      </div>
    </form>`,
  });
  root.querySelector('#settlement-form')?.addEventListener('submit', async (event) => {
    event.preventDefault();
    const form = event.target;
    const file = form.querySelector('#settlement-file')?.files?.[0];
    if (!file) {
      toast('请选择结算 CSV', 'err');
      return;
    }
    const text = await file.text();
    const rows = parseSettlementCsv(text);
    if (!rows.length) {
      toast('CSV 里没有解析到会员行（需要 member_no 列）', 'err');
      return;
    }
    const button = form.querySelector('button[type=submit]');
    button.disabled = true;
    button.textContent = '导入中…';
    try {
      const result = await api.post('/api/evaluations/import', {
        campaign_id: Number(campaignId),
        batch_no: form.batch_no.value.trim(),
        as_of: form.as_of.value || undefined,
        rows,
      });
      toast(
        result.duplicate
          ? `批次 ${form.batch_no.value} 已导入过，未重复累计`
          : `批次已导入：应用 ${fmtNum(result.applied)} 行，跳过 ${fmtNum(result.skipped)} 行`,
      );
      close();
      await audiencesPage.render(view, ctx);
    } catch (err) {
      toast(errorMessage(err), 'err');
      button.disabled = false;
      button.textContent = '导入并重算';
    }
  });
}

function openEvaluation(view, ctx, evaluation) {
  const canPublish = can(ctx.user.role, 'evaluation:publish');
  const canExport = can(ctx.user.role, 'export:read');
  const downloadButton = canExport
    ? '<button class="btn sm ghost" data-download>导出结算评估</button>'
    : '';
  const rows = evaluation.fact_rows || [];
  const treatedRows = rows.filter((row) => row.group === 'treated');
  const controlRows = rows.filter((row) => row.group === 'control');
  const { root, close } = drawer({
    title: `结算评估 · ${evaluation.audience_no}`,
    subtitle: `${evaluation.campaign_name || ''} · ${evaluation.status_label} · 批次 ${evaluation.batch_no || '—'}`,
    body: `${statStrip([
      { label: '处理人数', value: fmtNum(evaluation.treated_count), hint: '已投放名单' },
      { label: '对照人数', value: fmtNum(evaluation.control_count), hint: `同口径 ${fmtPct(evaluation.control_ratio, 0)}` },
      { label: '增量率', value: fmtPct(evaluation.incremental_rate), hint: '处理组 − 对照组' },
      { label: 'ROI', value: Number(evaluation.roi).toFixed(2), hint: `增量 GMV ${fmtMoney(evaluation.inc_gmv, 0)}` },
    ])}
    <h3 style="margin:14px 0 6px;font-size:0.95rem">自然复购剥离</h3>
    ${kv([
      ['处理组转化率', `${fmtPct(evaluation.treated_rate)}（${fmtNum(evaluation.treated_converters)} / ${fmtNum(evaluation.treated_count)}）`],
      ['对照组自然转化率', `${fmtPct(evaluation.control_rate)}（${fmtNum(evaluation.control_converters)} / ${fmtNum(evaluation.control_count)}）`],
      ['处理组券核销', `${fmtNum(evaluation.treated_redeemers)} 人`],
      ['有效触达', `${fmtNum(evaluation.treated_reached)} / ${fmtNum(evaluation.treated_count)} 人（投递失败的已剔除分母）`],
      ['增量率', `<b>${fmtPct(evaluation.incremental_rate)}</b> = 处理组 − 对照组`],
      ['增量人数', fmtNum(Math.round(evaluation.inc_converters))],
      ['增量单量', fmtNum(evaluation.inc_orders)],
      ['增量 GMV', fmtMoney(evaluation.inc_gmv)],
      ['名单实花', fmtMoney(evaluation.spend)],
      ['已回流', `处理组 ${fmtNum(evaluation.treated_observed)} 人 · 对照组 ${fmtNum(evaluation.control_observed)} 人`],
      ['发布人 / 时间', evaluation.published_at ? `${esc(evaluation.published_by || '')} · ${esc(evaluation.published_at.slice(0, 16).replace('T', ' '))}` : '未发布'],
    ])}
    <h3 style="margin:14px 0 6px;font-size:0.95rem">两组会员回流明细（前 20 行）</h3>
    <div class="table-wrap"><table class="data" style="min-width:0">
      <thead><tr><th>组</th><th>会员 ID</th><th>触达</th><th>核销</th><th>单量</th><th>GMV</th><th>数据截止</th></tr></thead>
      <tbody>${[...treatedRows, ...controlRows]
        .filter((row) => row.redeemed || row.orders || !row.reached)
        .slice(0, 20)
        .map(
          (row) => `<tr><td>${esc(ENUMS.evaluationGroups[row.group] || row.group)}</td>
            <td class="mono">#${row.member_id}</td>
            <td>${row.reached ? badge('ok', '已送达') : badge('warn', '未送达')}</td>
            <td>${row.redeemed ? badge('ok', '已核销') : badge('', '未核销')}</td>
            <td class="num">${fmtNum(row.orders)}</td>
            <td class="num">${fmtMoney(row.gmv)}</td>
            <td class="mono muted">${esc(row.fact_as_of || '—')}</td></tr>`,
        )
        .join('')}</tbody></table></div>
    <div class="note" style="margin-top:10px">
      对照组在确认名单时按同分群结构冻结，之后不再重抽。结算后发布，数字锁定，晚到核销不再改动这份评估。
    </div>`,
    footer: canPublish
      ? `<div class="rule-chipline">
          ${
            evaluation.status === 'published'
              ? '<span class="mono muted">评估已发布，数字已锁定</span>'
              : '<button class="btn accent" data-publish="1">结算并发布</button>'
          }
          ${downloadButton}
        </div>`
      : `<div class="rule-chipline"><span class="mono muted">只读角色可以看评估，发布与导入需要管理员</span>${downloadButton}</div>`,
  });

  root.querySelector('[data-publish]')?.addEventListener('click', async () => {
    try {
      await api.post(`/api/evaluations/${evaluation.id}/publish`, {});
      toast('评估已发布，处理人数 / 对照人数 / 增量率 / ROI 已锁定');
      close();
      await audiencesPage.render(view, ctx);
    } catch (err) {
      toast(errorMessage(err), 'err');
    }
  });
  root.querySelector('[data-download]')?.addEventListener('click', async () => {
    try {
      await api.download(`/api/exports/evaluations.csv?campaign_id=${evaluation.campaign_id}`, 'evaluations.csv');
      toast('已开始下载结算评估');
    } catch (err) {
      toast(errorMessage(err), 'err');
    }
  });
}

function openAudience(view, ctx, audience, campaigns) {
  const rows = audience.allocation || [];
  const canConfirm = can(ctx.user.role, 'audience:confirm');
  const evaluation = audience.evaluation;
  const { root, close } = drawer({
    title: `名单 ${audience.audience_no}`,
    subtitle: `${audience.campaign_name || ''} · ${audience.status_label}`,
    body: `${kv([
      ['活动', esc(audience.campaign_name || '—')],
      ['名单人数', fmtNum(audience.member_count)],
      ['预算 / 实花', `${fmtMoney(audience.budget)} / ${fmtMoney(audience.spend)}`],
      ['预计增量单量', fmtNum(audience.inc_orders)],
      ['增量 GMV', fmtMoney(audience.inc_gmv)],
      ['整体 ROI', `<b>${Number(audience.roi).toFixed(2)}</b>`],
      ['大盘购买率', fmtPct(audience.global_rate)],
      ['生成人 / 时间', `${esc(audience.operator_email)} · ${esc((audience.created_at || '').slice(0, 16).replace('T', ' '))}`],
      ['确认人', esc(audience.confirmed_by || '—')],
    ])}
    <h3 style="margin:14px 0 6px;font-size:0.95rem">分群预算分配</h3>
    <div class="table-wrap"><table class="data" style="min-width:0">
      <thead><tr><th>分群</th><th>lift</th><th>人数</th><th>预算</th><th>增量</th><th>ROI</th></tr></thead>
      <tbody>${rows
        .filter((row) => row.status === 'allocated')
        .map(
          (row) => `<tr><td>${esc(row.segment_name)}</td><td class="mono">${fmtLift(row.lift)}</td>
            <td class="num">${fmtNum(row.allocated)}</td><td class="num">${fmtMoney(row.budget)}</td>
            <td class="num">${fmtNum(row.inc_orders)}</td><td class="num">${Number(row.roi).toFixed(2)}</td></tr>`,
        )
        .join('')}</tbody></table></div>
    ${
      evaluation
        ? `<h3 style="margin:14px 0 6px;font-size:0.95rem">结算评估（同口径对照组）</h3>
          ${statStrip([
            { label: '处理人数', value: fmtNum(evaluation.treated_count), hint: evaluation.status_label },
            { label: '对照人数', value: fmtNum(evaluation.control_count), hint: `比例 ${fmtPct(evaluation.control_ratio, 0)}` },
            { label: '增量率', value: fmtPct(evaluation.incremental_rate), hint: '已扣自然复购' },
            { label: 'ROI', value: Number(evaluation.roi).toFixed(2), hint: fmtMoney(evaluation.inc_gmv, 0) },
          ])}
          <div class="rule-chipline" style="margin-top:8px">
            <button class="btn sm ghost" data-open-evaluation="${evaluation.id}">查看结算明细</button>
          </div>`
        : '<div class="note">确认名单后会冻结同口径对照组，导入结算批次后这里出现增量率与 ROI。</div>'
    }
    <div class="note" style="margin-top:10px">${esc(audience.note || '')}</div>`,
    footer: canConfirm
      ? `<div class="rule-chipline">
          <button class="btn accent" data-confirm="confirmed">确认名单（冻结对照组）</button>
          <button class="btn ghost" data-confirm="pushed">标记已推送券平台</button>
          <button class="btn sm ghost" data-download>导出名单明细</button>
        </div>`
      : '<span class="mono muted">只读角色可以查看名单，但不能确认或导出</span>',
  });

  root.querySelectorAll('[data-confirm]').forEach((node) => {
    node.addEventListener('click', async () => {
      try {
        const result = await api.patch(`/api/audiences/${audience.id}/review`, { status: node.dataset.confirm });
        toast(
          result.evaluation
            ? `名单状态已更新，已冻结对照组：处理 ${fmtNum(result.evaluation.treated_count)} / 对照 ${fmtNum(
                result.evaluation.control_count,
              )} 人`
            : '名单状态已更新',
        );
        close();
        await audiencesPage.render(view, ctx);
      } catch (err) {
        toast(errorMessage(err), 'err');
      }
    });
  });
  root.querySelector('[data-download]')?.addEventListener('click', async () => {
    try {
      await api.download(`/api/exports/audiences.csv?audience_id=${audience.id}`, `${audience.audience_no}.csv`);
      toast('已开始下载名单明细');
    } catch (err) {
      toast(errorMessage(err), 'err');
    }
  });
  root.querySelector('[data-open-evaluation]')?.addEventListener('click', async () => {
    const evaluationId = root.querySelector('[data-open-evaluation]').dataset.openEvaluation;
    close();
    try {
      const detail = await api.get(`/api/evaluations/${evaluationId}`);
      openEvaluation(view, ctx, detail);
    } catch (err) {
      toast(errorMessage(err), 'err');
    }
  });
  void campaigns;
}

export const audiencesPage = {
  async render(view, ctx) {
    let campaigns;
    let history;
    try {
      [campaigns, history] = await Promise.all([
        api.get('/api/campaigns'),
        api.get('/api/audiences', { limit: 20 }),
      ]);
    } catch (err) {
      view.innerHTML = errorBox(errorMessage(err));
      view.querySelector('#retry-btn')?.addEventListener('click', () => audiencesPage.render(view, ctx));
      return;
    }
    if (!campaigns.items.length) {
      view.innerHTML = errorBox('还没有活动，请先执行 seed 或由管理员创建活动。');
      return;
    }
    if (!state.campaignId) state.campaignId = String(campaigns.items[0].id);
    const allocation = await loadAllocation(view, ctx, campaigns.items);
    const evaluations = await loadEvaluations(state.campaignId);
    const campaign = campaigns.items.find((item) => String(item.id) === String(state.campaignId)) || campaigns.items[0];
    const admin = can(ctx.user.role, 'audience:generate');
    const canImport = can(ctx.user.role, 'evaluation:import');
    const totals = allocation ? allocation.totals : null;

    view.innerHTML = `
      <section class="panel">
        <div class="panel-head">
          <h2>名单与提升度</h2>
          <span class="meta">${campaign.name} · ${campaign.status_label} · 券口径 ${campaign.channel}</span>
        </div>
        <div class="panel-body" style="display:grid;gap:12px">
          <div class="filter-bar">
            ${field({
              label: '活动',
              name: 'campaign_id',
              value: state.campaignId,
              options: campaigns.items.map((item) => ({
                value: item.id,
                label: `${item.name}（预算 ${fmtMoney(item.budget, 0)}）`,
              })),
            })}
            ${field({
              label: '本次预算（元）',
              name: 'budget',
              type: 'number',
              value: state.budget || campaign.budget,
              attrs: 'step="100" min="1"',
            })}
            <button class="btn ghost" data-testid="preview" id="preview">重新试算</button>
            ${admin ? '<button class="btn accent" id="generate" data-testid="generate">生成名单</button>' : '<span class="note">只读 / 专员角色只能试算与确认，不能生成</span>'}
          </div>
          ${
            allocation
              ? `<div class="note">
                  算法 B：lift = 分群购买率 / 大盘购买率（${fmtPct(allocation.global_rate)}）；人均成本 = 触达 ${fmtMoney(
                    allocation.basis.reach_cost,
                  )} + 购买率 × 券面额；按 lift/成本 贪心排序；人均增量单量 ${allocation.basis.orders_per_converter}；
                  超出核心盘部分 ×${allocation.basis.tail_factor} 折减。${esc(allocation.log)}
                </div>`
              : ''
          }
        </div>
        ${
          allocation
            ? `<div class="panel-body" style="padding-top:0">${budgetBar(
                totals.spend,
                allocation.budget,
              )}</div>${allocationTable(allocation)}`
            : '<div class="panel-body"><div class="empty"><div class="mark">没有可投分群</div><p>提高预算或先重算分群。</p></div></div>'
        }
      </section>

      ${
        totals
          ? statStrip([
              { label: '名单人数', value: fmtNum(totals.audience), hint: `覆盖 ${totals.segments_allocated} 个分群` },
              { label: '券预算花费', value: fmtMoney(totals.spend), hint: `剩余 ${fmtMoney(totals.budget_remaining)}` },
              { label: '预计增量单量', value: fmtNum(totals.inc_orders), hint: '核心盘全效 + 溢出折减' },
              { label: '预计 ROI', value: Number(totals.roi).toFixed(2), hint: `增量 GMV ${fmtMoney(totals.inc_gmv, 0)}` },
            ])
          : ''
      }

      <section class="panel">
        <div class="panel-head">
          <h2>结算评估（同口径对照组）</h2>
          <span class="meta">${fmtNum(evaluations.total)} 份 · 已发布 ${fmtNum(evaluations.published)} · 进行中 ${fmtNum(
            evaluations.in_progress,
          )}</span>
        </div>
        <div class="panel-body" style="display:grid;gap:10px;padding-bottom:0">
          <div class="note">
            确认名单即冻结同口径对照组（同分群、同人数结构、不投放），用处理组 − 对照组剥离自然复购；
            核销 / 订单按批次回流，晚到批次会更新「进行中」评估，发布后数字锁定。页面与导出共用处理人数、对照人数、增量率、ROI。
          </div>
          ${
            canImport
              ? '<div class="rule-chipline"><button class="btn ghost" id="import-settlement">导入结算批次</button><button class="btn sm ghost" id="export-evaluation">导出评估表</button></div>'
              : '<span class="note">导入结算批次需要管理员权限；只读角色可以查看已发布评估。</span>'
          }
        </div>
        <div id="evaluation-table">${evaluationTable(evaluations)}</div>
      </section>

      <section class="panel">
        <div class="panel-head">
          <h2>历史名单</h2>
          <span class="meta">${fmtNum(history.total)} 份 · 点击查看分群分配</span>
        </div>
        <div id="audience-history">${historyTable(history.items)}</div>
      </section>`;

    const campaignField = view.querySelector('[name=campaign_id]');
    const budgetField = view.querySelector('[name=budget]');
    campaignField?.addEventListener('change', () => {
      state.campaignId = campaignField.value;
      state.budget = '';
      audiencesPage.render(view, ctx);
    });
    view.querySelector('#preview')?.addEventListener('click', () => {
      state.budget = budgetField.value;
      audiencesPage.render(view, ctx);
    });
    view.querySelector('#generate')?.addEventListener('click', async (event) => {
      const button = event.currentTarget;
      button.disabled = true;
      button.textContent = '生成中…';
      try {
        const audience = await api.post('/api/audiences', {
          campaign_id: Number(state.campaignId),
          budget: Number(budgetField.value || campaign.budget),
        });
        toast(`名单 ${audience.audience_no} 已生成：${audience.member_count} 人，ROI ${Number(audience.roi).toFixed(2)}`);
        state.budget = '';
        await audiencesPage.render(view, ctx);
      } catch (err) {
        toast(errorMessage(err), 'err');
        button.disabled = false;
        button.textContent = '生成名单';
      }
    });
    view.querySelector('#import-settlement')?.addEventListener('click', () => importDrawer(view, ctx, campaigns.items));
    view.querySelector('#export-evaluation')?.addEventListener('click', async () => {
      try {
        await api.download(`/api/exports/evaluations.csv?campaign_id=${state.campaignId}`, 'evaluations.csv');
        toast('已开始下载结算评估');
      } catch (err) {
        toast(errorMessage(err), 'err');
      }
    });

    view.querySelectorAll('#evaluation-table table.data tbody tr').forEach((row) => {
      const evaluation = evaluations.items.find((item) => String(item.id) === String(row.dataset.id));
      if (evaluation) {
        row.addEventListener('click', async () => {
          try {
            const detail = await api.get(`/api/evaluations/${evaluation.id}`);
            openEvaluation(view, ctx, detail);
          } catch (err) {
            toast(errorMessage(err), 'err');
          }
        });
      }
    });
    view.querySelectorAll('#audience-history table.data tbody tr').forEach((row) => {
      const audience = history.items.find((item) => String(item.id) === row.dataset.id);
      if (audience) {
        row.addEventListener('click', () => openAudience(view, ctx, audience, campaigns.items));
      }
    });
  },
};

export default audiencesPage;
