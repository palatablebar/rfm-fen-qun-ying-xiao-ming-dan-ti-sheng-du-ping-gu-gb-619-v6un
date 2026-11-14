/**
 * 项目品牌、导航、角色权限与枚举文案（前端唯一定义处）。
 * 后端对应：backend/src/constants/{roles,enums}.py；README 列出全部出现位置。
 */
export const BRAND = {
  short: 'rfmseg',
  title: 'RFM 分群与营销名单',
  full: '牧野茶饮 · RFM 分群与营销名单提升度评估',
  org: '牧野茶饮 · 会员运营组',
  edition: 'MEMBERSHIP DESK · 2026 Q4',
  subtitle: 'POS 订单 → RFM 分位评分 → 八类分群 → 名单与预算 → 提升度与 ROI',
  loginLead:
    '全员群发核销率 3%、季度预算 40 万：先把「谁值得发」算出来，再决定「先发谁、发多少」。',
  loginPoints: [
    ['01', 'RFM 按分位切 5 档，权重可调；同值同档，阈值重算后人数变化可解释。'],
    ['02', 'lift = 分群购买率 / 大盘购买率，按 lift/成本 贪心分配预算，超出核心盘按 0.6 折减。'],
    ['03', '名单可确认、可导出到券平台；手机号对只读角色脱敏，全程审计。'],
  ],
  cardNo: 'MY-8800 1942 0721',
  cardTier: '黑金卡会员',
  cardPoints: [
    ['积分', '12,480'],
    ['近一年到店', '37 次'],
  ],
};

export const NAV = [
  { to: '#/overview', no: '01', label: '总览', permission: 'overview:read' },
  { to: '#/members', no: '02', label: '会员与订单', permission: 'member:read' },
  { to: '#/segments', no: '03', label: 'RFM 分群', permission: 'segment:read' },
  { to: '#/audiences', no: '04', label: '名单与提升度', permission: 'audience:read' },
  { to: '#/exports', no: '05', label: '导出与审计', permission: 'member:read' },
];

export const ROLE_LABELS = {
  admin: '会员运营管理员',
  analyst: '会员数据专员',
  viewer: '门店业务只读',
};

export const PERMISSIONS = {
  admin: [
    'overview:read', 'member:read', 'order:read', 'segment:read', 'segment:recompute', 'segment:write',
    'campaign:read', 'campaign:write', 'audience:read', 'audience:generate', 'audience:confirm',
    'export:read', 'audit:read',
  ],
  analyst: [
    'overview:read', 'member:read', 'order:read', 'segment:read', 'campaign:read',
    'audience:read', 'audience:confirm', 'export:read',
  ],
  viewer: ['overview:read', 'member:read', 'order:read', 'segment:read', 'campaign:read', 'audience:read'],
};

export const ENUMS = {
  segment: {
    champion: '重要价值',
    loyal: '重要保持',
    potential: '重要发展',
    at_risk: '重要挽留',
    new: '新客养成',
    churn_warn: '流失预警',
    ordinary: '一般价值',
    hibernating: '沉睡会员',
  },
  segmentOrder: [
    'champion', 'loyal', 'potential', 'at_risk', 'new', 'churn_warn', 'ordinary', 'hibernating',
  ],
  segmentRules: {
    champion: 'R≥4 且 F≥4 且 M≥4',
    loyal: 'R≥3 且 F≥4 且 M≥3',
    potential: 'R≥4 且 F≥3 且 M≥4',
    at_risk: 'R≤2 且 F≥4 且 M≥4',
    new: 'R≥4 且 F≤2',
    churn_warn: 'R≤2 且 F≥2 且 M≥2',
    ordinary: 'R≥3 且 M≤3',
    hibernating: '其余',
  },
  tier: {
    normal: '普通会员',
    silver: '银卡',
    gold: '金卡',
    black: '黑金卡',
  },
  channel: {
    miniapp: '小程序自提',
    store: '门店收银',
    delivery: '外卖平台',
  },
  campaignStatus: {
    draft: '草稿',
    active: '进行中',
    closed: '已结束',
  },
  audienceStatus: {
    pending: '待确认',
    confirmed: '已确认',
    pushed: '已推送券平台',
  },
  allocationStatus: {
    allocated: '已分配',
    deferred: '预算不足',
    ineligible: 'lift≤1 不投',
  },
  windowDays: [
    { value: 90, label: '近 90 天' },
    { value: 180, label: '近 180 天' },
    { value: 365, label: '近 365 天（默认）' },
    { value: 730, label: '近 730 天' },
  ],
};

export function can(role, permission) {
  return (PERMISSIONS[role] || []).includes(permission);
}

export function segmentTone(code) {
  return {
    champion: 'ok',
    loyal: 'ok',
    potential: 'info',
    at_risk: 'warn',
    new: 'info',
    churn_warn: 'warn',
    ordinary: 'low',
    hibernating: 'danger',
  }[code] || 'info';
}

export function audienceTone(status) {
  return { pending: 'pending warn', confirmed: 'ok', pushed: 'info' }[status] || 'info';
}

export function liftTone(lift) {
  if (lift >= 1.5) return 'hot';
  if (lift > 1) return '';
  return 'cold';
}
