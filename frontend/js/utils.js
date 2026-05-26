/**
 * Enterprise HR Insights — 工具函数
 * 共用的格式化、DOM 操作、图表初始化及 resize 管理
 */

/** 图表统一色板 */
export const COLORS = ['#00f2fe', '#f6e05e', '#ff4757', '#2ed573', '#4facfe', '#ff6b81', '#a29bfe', '#fd79a8', '#e17055'];

/** 数字千分位格式化 */
export const fmt = (n) => n ? Number(n).toLocaleString() : '0';

/** document.getElementById 简写 */
export const $ = (id) => document.getElementById(id);

/** 全局 resize 回调列表，生命周期钩子负责注册/注销 */
export const resizeHandlers = [];

/**
 * 初始化 ECharts 实例并注册自适应监听。
 * 若 dom 上已有实例则先销毁再重建，防止重复初始化导致的内存泄漏。
 */
export const initChart = (domId) => {
    const dom = $(domId);
    if (!dom) return null;
    const existing = echarts.getInstanceByDom(dom);
    if (existing) existing.dispose();
    const c = echarts.init(dom);
    const handler = () => c.resize();
    resizeHandlers.push(handler);
    window.addEventListener('resize', handler);
    return c;
};
