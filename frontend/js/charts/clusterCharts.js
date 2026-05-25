/**
 * 聚类分析图表 — PCA 散点 / 雷达图 / 轮廓系数 / 聚类对比 / DBSCAN
 */
import { initChart, COLORS, fmt } from '../utils.js';

// --- PCA 降维散点 (Req 2) ---
export function renderPCA(data, { selectedEmp, showModal }) {
    const c = initChart('c_pca');
    if (!c || !data.pca) return;
    const { x, y, cluster, cluster_name, salary, dept } = data.pca;
    const groups = {};
    x.forEach((_, i) => {
        const cn = cluster_name[i];
        if (!groups[cn]) groups[cn] = [];
        groups[cn].push([x[i], y[i], salary[i], dept[i], cluster[i]]);
    });
    c.setOption({
        color: COLORS,
        tooltip: {
            trigger: 'item',
            formatter: (p) => {
                const d = p.data;
                return `<b>${data.pca.cluster_name[data.pca.cluster.indexOf(d[4])] || ''}</b><br/>
                    薪资: $${fmt(d[2])}<br/>部门: ${d[3]}<br/>PCA1: ${d[0].toFixed(1)} PCA2: ${d[1].toFixed(1)}`;
            }
        },
        legend: { data: Object.keys(groups), textStyle: { color: '#a0aec0' }, top: 5 },
        grid: { left: '8%', right: '5%', bottom: '10%', top: '15%' },
        xAxis: { name: `PC1 (${(data.pca.explained_variance[0]*100).toFixed(0)}%)`, axisLabel: { color: '#a0aec0' }, splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } } },
        yAxis: { name: `PC2 (${(data.pca.explained_variance[1]*100).toFixed(0)}%)`, axisLabel: { color: '#a0aec0' }, splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } } },
        series: Object.entries(groups).map(([name, pts]) => ({
            name, type: 'scatter', data: pts, symbolSize: 7,
            emphasis: { scale: 2 }
        }))
    });
    c.on('click', (p) => {
        if (p.data && p.data.length >= 5) {
            selectedEmp.value = {
                emp_no: '—',
                dept_name: p.data[3],
                title: '—',
                salary: p.data[2],
                tenure: '—',
                age: '—',
                cluster_name: data.pca.cluster_name[data.pca.cluster.indexOf(p.data[4])] || ''
            };
            showModal.value = true;
        }
    });
}

// --- 雷达图 ---
export function renderRadar(data) {
    const c = initChart('c_radar');
    if (!c || !data.radar) return;
    c.setOption({
        color: COLORS,
        legend: { bottom: 0, textStyle: { color: '#a0aec0', fontSize: 10 }, itemWidth: 8 },
        radar: {
            indicator: [
                { name: '薪资($)', max: Math.max(...data.radar.map(d => d.salary)) * 1.1 },
                { name: '司龄(年)', max: Math.max(...data.radar.map(d => d.tenure)) * 1.2 },
                { name: '年龄(岁)', max: Math.max(...data.radar.map(d => d.age)) * 1.05 }
            ],
            center: ['50%', '45%'], radius: '55%'
        },
        series: [{ type: 'radar', data: data.radar.map(d => ({ value: [d.salary, d.tenure, d.age], name: d.cluster_name })) }]
    });
}

// --- 轮廓系数 (Req 2) ---
export function renderSilhouette(data) {
    const c = initChart('c_silhouette');
    if (!c || !data.silhouette) return;
    const ks = data.silhouette.map(d => d.k);
    const vals = data.silhouette.map(d => d.silhouette);
    c.setOption({
        tooltip: { trigger: 'axis', formatter: 'K={b}<br/>轮廓系数: {c}' },
        grid: { left: '10%', right: '5%', top: '10%', bottom: '15%' },
        xAxis: { type: 'category', data: ks, name: 'K', axisLabel: { color: '#a0aec0' } },
        yAxis: { type: 'value', name: 'Silhouette', min: 0, axisLabel: { color: '#a0aec0' }, splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } } },
        series: [{
            type: 'bar', data: vals,
            itemStyle: { color: (p) => p.dataIndex === ks.indexOf(data.best_k) ? '#f6e05e' : '#4facfe' },
            label: { show: true, position: 'top', color: '#e2e8f0', formatter: '{c}' },
            markLine: { silent: true, data: [{ xAxis: data.best_k, label: { formatter: `最优K=${data.best_k}`, color: '#f6e05e' }, lineStyle: { color: '#f6e05e', type: 'dashed' } }] }
        }]
    });
}

// --- 聚类对比 ---
export function renderClusterCmp(data) {
    const c = initChart('c_cluster_cmp');
    if (!c || !data.comparison) return;
    const names = data.comparison.map(d => d.cluster_name);
    c.setOption({
        tooltip: { trigger: 'axis' },
        legend: { data: ['均薪($)', '均司龄', '均年龄', '人数'], textStyle: { color: '#a0aec0' }, top: 3 },
        grid: { left: '15%', right: '5%', bottom: '15%', top: '15%' },
        xAxis: { type: 'category', data: names, axisLabel: { color: '#a0aec0', fontSize: 10, rotate: 15 } },
        yAxis: [
            { type: 'value', name: '$', axisLabel: { color: '#a0aec0' }, splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } } },
            { type: 'value', name: '年/人', axisLabel: { color: '#a0aec0' }, splitLine: { show: false } }
        ],
        series: [
            { name: '均薪($)', type: 'bar', data: data.comparison.map(d => d.avg_salary), itemStyle: { color: '#00f2fe' }, barWidth: '35%' },
            { name: '均司龄', type: 'bar', yAxisIndex: 1, data: data.comparison.map(d => d.avg_tenure), itemStyle: { color: '#f6e05e' }, barWidth: '35%' },
            { name: '均年龄', type: 'bar', yAxisIndex: 1, data: data.comparison.map(d => d.avg_age), itemStyle: { color: '#ff4757' }, barWidth: '35%' },
            { name: '人数', type: 'line', data: data.comparison.map(d => d.count), lineStyle: { color: '#2ed573', width: 2 }, symbol: 'circle' }
        ]
    });
}

// --- DBSCAN ---
export function renderDBSCAN(data) {
    const c = initChart('c_dbscan');
    if (!c || !data.dbscan) return;
    const { labels, salary, tenure } = data.dbscan;
    const groups = {};
    labels.forEach((l, i) => {
        const key = l === -1 ? '噪声点' : `簇 ${l + 1}`;
        if (!groups[key]) groups[key] = [];
        groups[key].push([tenure[i], salary[i]]);
    });
    const colors = { '噪声点': '#ff4757' };
    Object.keys(groups).filter(k => k !== '噪声点').forEach((k, i) => { colors[k] = COLORS[i + 1]; });
    c.setOption({
        tooltip: { trigger: 'item', formatter: (p) => `司龄: ${p.data[0]}<br/>薪资: $${fmt(p.data[1])}` },
        legend: { data: Object.keys(groups), textStyle: { color: '#a0aec0', fontSize: 10 }, top: 3 },
        grid: { left: '10%', right: '5%', bottom: '10%', top: '15%' },
        xAxis: { name: '司龄', axisLabel: { color: '#a0aec0' }, splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } } },
        yAxis: { name: '薪资($)', axisLabel: { color: '#a0aec0' }, splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } } },
        series: Object.entries(groups).map(([name, pts]) => ({
            name, type: 'scatter', data: pts, symbolSize: 6,
            itemStyle: { color: colors[name] || '#a0aec0' }
        }))
    });
}
