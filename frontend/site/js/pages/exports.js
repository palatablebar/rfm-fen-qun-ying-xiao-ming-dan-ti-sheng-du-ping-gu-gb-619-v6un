import { api } from '../api.js';
import { ENUMS, can } from '../config.js';
import {
  badge,
  emptyState,
  errorBox,
  errorMessage,
  esc,
  fmtLift,
  fmtMoney,
  fmtNum,
  fmtPct,
  fmtTime,
  table,
  toast,
} from '../ui.js';

const EXPORTS = [
  {
    id: 'members',
    path: '/api/exports/members.csv',
    filename: 'members.csv',
    title: '会员名单（含 RFM 得分与分群）',
    hint: '7 列以上：会员号 / 手机号 / 窗口单数与金额 / R-F-M 得分 / 综合分 / 分群 / 券响应率',
  },
  {
    id: 'segments',
    path: '/api/exports/segments.csv',
    filename: 'segments.csv',
    title: '分群表（含 lift 与券口径）',
    hint: '八类分群的人数、占比、平均 RFM、购买率、lift、券面额、核心盘占比',
  },
  {
    id: 'audiences',
    path: '/api/exports/audiences.csv',
    filename: 'audience.csv',
    title: '名单明细（推券平台用）',
    hint: '按名单的分群配额展开到会员级，带该群 lift / 预算 / 预计增量，便于回算',
  },
];

export const exportsPage = {
  async render(view, ctx) {
    const canExport = can(ctx.user.role, 'export:read');
    const canAudit = can(ctx.user.role, 'audit:read');
    let segments = { items: [] };
    let audit = null;
    try {
      segments = await api.get('/api/segments');
    } catch (err) {
      toast(errorMessage(err), 'err');
    }
    if (canAudit) {
      try {
        audit = await api.get('/api/audit', { limit: 60 });
      } catch (err) {
        audit = null;
      }
    }

    view.innerHTML = `
      <section class="panel">
        <div class="panel-head">
          <h2>导出中心</h2>
          <span class="meta">CSV · UTF-8 BOM · 导出一律记审计</span>
        </div>
        <div class="panel-body" style="display:grid;gap:12px">
          <div class="grid-3" style="gap:12px">
            ${EXPORTS.map(
              (item) => `<div class="panel" style="box-shadow:none">
                <div class="panel-head" style="padding:10px 14px"><h2 style="font-size:1rem">${esc(item.title)}</h2></div>
                <div class="panel-body" style="display:grid;gap:10px">
                  <p class="note" style="margin:0">${esc(item.hint)}</p>
                  <button class="btn ${canExport ? 'accent' : 'ghost'}" data-export="${item.id}"
                    data-path="${item.path}" data-filename="${item.filename}" ${canExport ? '' : 'disabled'}>
                    ${canExport ? '下载 CSV' : '无导出权限'}
                  </button>
                </div>
              </div>`,
            ).join('')}
          </div>
          ${
            canExport
              ? '<div class="note">导出走真实 403 校验：门店只读角色调用这些接口会被后端拒绝并留下被拒记录。</div>'
              : '<div class="note">当前角色是门店只读：可以查看分群与名单，但导出接口返回 403（服务器强制，不是按钮隐藏）。</div>'
          }
        </div>
      </section>

      <section class="panel">
        <div class="panel-head">
          <h2>分群口径（导出同源）</h2>
          <span class="meta">快照 ${esc((segments.as_of || '').slice(0, 10) || '—')} · 大盘购买率 ${fmtPct(segments.global_purchase_rate || 0)}</span>
        </div>
        ${table({
          rows: segments.items,
          columns: [
            { key: 'code', label: '编码', className: 'mono' },
            { key: 'name', label: '分群', render: (row) => `<b>${esc(row.name)}</b>` },
            { key: 'rule_text', label: '规则', render: (row) => `<span class="mono muted">${esc(row.rule_text)}</span>` },
            { key: 'member_count', label: '人数', className: 'num', render: (row) => fmtNum(row.member_count) },
            { key: 'purchase_rate', label: '购买率', className: 'num', render: (row) => fmtPct(row.purchase_rate) },
            { key: 'lift', label: 'lift', className: 'num', render: (row) => fmtLift(row.lift) },
            { key: 'coupon_face', label: '券面额', className: 'num', render: (row) => fmtMoney(row.coupon_face, 0) },
          ],
          empty: { title: '还没有分群快照', hint: '先执行 seed 或重算分群。' },
        })}
      </section>

      <section class="panel">
        <div class="panel-head">
          <h2>审计日志</h2>
          <span class="meta">${canAudit ? `${fmtNum(audit?.total || 0)} 条 · 最近 60 条` : '仅管理员可见'}</span>
        </div>
        ${
          !canAudit
            ? `<div class="panel-body"><div class="empty" data-testid="audit-denied">
                <div class="mark">审计日志需要管理员权限</div>
                <p>当前角色调用 <code>/api/audit</code> 会返回 403。登录、重算、生成名单、导出都会被记录。</p>
              </div></div>`
            : table({
                rows: audit?.items || [],
                empty: { title: '还没有审计记录', hint: '重算分群或导出一次就会写入。' },
                columns: [
                  { key: 'created_at', label: '时间', render: (row) => fmtTime(row.created_at) },
                  { key: 'actor_email', label: '操作人', className: 'mono' },
                  { key: 'actor_role', label: '角色' },
                  { key: 'action_label', label: '动作' },
                  { key: 'entity', label: '对象' },
                  { key: 'layer', label: '层', render: (row) => badge('', row.layer) },
                  {
                    key: 'detail',
                    label: '详情',
                    render: (row) => `<span class="mono muted">${esc(JSON.stringify(row.detail || {}).slice(0, 120))}</span>`,
                  },
                ],
              })
        }
      </section>

      <section class="panel">
        <div class="panel-head"><h2>角色与权限</h2><span class="meta">与后端 constants/roles.py 同步</span></div>
        <div class="panel-body note">
          管理员（admin@rfmseg.io）：调阈值权重、改券面额、生成名单、导出、看审计。<br />
          数据专员（analyst@rfmseg.io）：看分群与 lift、确认名单、导出；不能重算或改券口径。<br />
          门店只读（viewer@rfmseg.io）：只读会员/分群/名单，手机号脱敏；写、导出、审计一律 403。
        </div>
      </section>`;

    view.querySelectorAll('[data-export]').forEach((button) => {
      button.addEventListener('click', async () => {
        try {
          await api.download(button.dataset.path, button.dataset.filename);
          toast('已开始下载，审计日志同步写入');
        } catch (err) {
          toast(errorMessage(err), 'err');
        }
      });
    });
  },
};

export default exportsPage;
