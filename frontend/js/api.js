// File: frontend/js/api.js
/**
 * Enterprise HR Insights — API 层
 * 集中管理后端接口地址与 axios 请求封装
 */

export const API = window.location.port === '8000'
    ? '/api'
    : `${window.location.protocol}//${window.location.hostname}:8000/api`;

const api = (path) => axios.get(`${API}${path}`).then(r => r.data).catch(e => { console.error(path, e); return null; });

// ---- 总览看板 ----
export async function fetchKPI()              { return api('/v1/overview/kpi'); }
export async function fetchDeptDistribution() { return api('/v1/overview/dept_distribution'); }

// ---- 薪资分析 ----
export async function fetchSalaryHistory()      { return api('/v1/salary/history'); }
export async function fetchSalaryDistribution() { return api('/v1/salary/distribution'); }
export async function fetchSalaryEvolution()    { return api('/v1/salary/evolution'); }
export async function fetchSalaryGrowth()       { return api('/v1/salary/growth'); }
export async function fetchExternalBenchmark()  { return api('/v1/salary/external_benchmark'); }

// ---- 高级分析 ----
export async function fetchClustering()       { return api('/v1/advanced/clustering'); }
export async function fetchForecast()         { return api('/v1/advanced/forecast'); }
export async function fetchCorrelation()      { return api('/v1/advanced/correlation'); }
export async function fetchSimilarity()       { return api('/v1/advanced/similarity'); }
export async function fetchTitleSankey()      { return api('/v1/advanced/title_sankey'); }
export async function fetchGenderAnalysis()   { return api('/v1/advanced/gender_analysis'); }
export async function fetchTitleTransition()  { return api('/v1/advanced/title_transition'); }
export async function fetchDeptStability()  { return api('/v1/advanced/department-stability'); }
export async function fetchDeptForecast()     { return api('/v1/advanced/dept_forecast'); }
