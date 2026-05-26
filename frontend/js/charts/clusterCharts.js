// File: frontend/js/charts/clusterCharts.js
/**
 * 聚类分析图表 — PCA 散点 / 雷达图 / 轮廓系数 / 聚类对比 / DBSCAN
 */
import { initChart, COLORS, fmt } from '../utils.js';

// --- PCA 降维散点 (Req 2) ---
export function renderPCA(data, { selectedEmp, showModal }) {
    const c = initChart('c_pca');
    if (!c || !data.pca) return;
    const { x, y, cluster, cluster_name, salary, dept, tenure, age } = data.pca;
    const groups = {};
    x.forEach((_, i) => {
        const cn = cluster_name[i];
        if (!groups[cn]) groups[cn] = [];
        groups[cn].push([x[i], y[i], salary[i], dept[i], cluster[i], tenure[i], age[i], cluster_name[i]]);
    });
    c.setOption({
        color: COLORS,
        tooltip: {
            trigger: 'item',
            formatter: (p) => {
                const d = p.data;
                return `<div style="background:rgba(16,30,54,0.95);padding:10px 14px;border:1px solid #00f2fe;border-radius:6px;">
                    <b style="color:#00f2fe;font-size:14px;">${d[7]}</b><br/>
                    <span style="color:#a0aec0;">薪资:</span> <b style="color:#f6e05e;">$${fmt(d[2])}</b><br/>
                    <span style="color:#a0aec0;">部门:</span> <b style="color:#e2e8f0;">${d[3]}</b><br/>
                    <span style="color:#a0aec0;">工龄:</span> <b style="color:#e2e8f0;">${d[5].toFixed(1)} 年</b><br/>
                    <span style="color:#a0aec0;">年龄:</span> <b style="color:#e2e8f0;">${d[6].toFixed(0)} 岁</b>
                </div>`;
            }
        },
        legend: { data: Object.keys(groups), textStyle: { color: '#a0aec0' }, top: 5 },
        grid: { left: '10%', right: '5%', bottom: '12%', top: '15%' },
        xAxis: { name: `综合业务维度 (薪资/职位) - PC1 (${(data.pca.explained_variance[0]*100).toFixed(0)}%)`, nameLocation: 'center', nameGap: 28, axisLabel: { color: '#a0aec0' }, splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } } },
        yAxis: { name: `综合人口维度 (年龄/工龄) - PC2 (${(data.pca.explained_variance[1]*100).toFixed(0)}%)`, nameLocation: 'center', nameGap: 45, axisLabel: { color: '#a0aec0' }, splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } } },
        series: Object.entries(groups).map(([name, pts]) => ({
            name, type: 'scatter', data: pts, symbolSize: 7,
            emphasis: { scale: 2 }
        }))
    });
    c.on('click', (p) => {
        if (p.data && p.data.length >= 8) {
            selectedEmp.value = {
                emp_no: '—',
                dept_name: p.data[3],
                title: '—',
                salary: p.data[2],
                tenure: p.data[5].toFixed(1) + ' 年',
                age: Math.round(p.data[6]) + ' 岁',
                cluster_name: p.data[7] || ''
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
            markLine: { silent: true, data: [{ xAxis: data.best_k.toString(), label: { formatter: `最优K=${data.best_k}`, color: '#f6e05e' }, lineStyle: { color: '#f6e05e', type: 'dashed' } }] }
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
        legend: { data: ['均薪($)', '均司龄', '均年龄'], textStyle: { color: '#a0aec0' }, top: 3 },
        grid: { left: '15%', right: '5%', bottom: '15%', top: '15%' },
        xAxis: { type: 'category', data: names, axisLabel: { color: '#a0aec0', fontSize: 10, rotate: 15 } },
        yAxis: [
            { type: 'value', name: '$', axisLabel: { color: '#a0aec0' }, splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } } },
            { type: 'value', name: '年/岁', axisLabel: { color: '#a0aec0' }, splitLine: { show: false } }
        ],
        series: [
            { name: '均薪($)', type: 'bar', yAxisIndex: 0, data: data.comparison.map(d => d.avg_salary), itemStyle: { color: '#00f2fe' }, barWidth: '35%' },
            { name: '均司龄', type: 'line', yAxisIndex: 1, data: data.comparison.map(d => d.avg_tenure), lineStyle: { color: '#f6e05e', width: 2 }, smooth: true, symbol: 'circle', itemStyle: { color: '#f6e05e' } },
            { name: '均年龄', type: 'line', yAxisIndex: 1, data: data.comparison.map(d => d.avg_age), lineStyle: { color: '#ff4757', width: 2 }, smooth: true, symbol: 'diamond', itemStyle: { color: '#ff4757' } }
        ]
    });
}

// --- 3D 人才聚类散点 (工龄-薪资-部门) ---
export function renderCluster3D(domId, data) {
    const dom = document.getElementById(domId);
    if (!dom) { console.error('[Cluster3D] DOM not found:', domId); return; }

    const existing = echarts.getInstanceByDom(dom);
    if (existing) existing.dispose();
    const c = echarts.init(dom);
    if (!c) { console.error('[Cluster3D] init failed'); return; }

    const handler = () => c.resize();
    window.addEventListener('resize', handler);

    if (!data.points_3d || !data.points_3d.length) {
        console.warn('[Cluster3D] No points_3d data');
        return;
    }

    const deptLabels = ["Development", "Sales", "Marketing", "Finance",
        "Human Resources", "Production", "Quality Management",
        "Research", "Customer Service"];

    const groups = {};
    data.points_3d.forEach(([tenure, salary, deptIdx, deptName, clusterName]) => {
        const key = clusterName || '未分类';
        if (!groups[key]) groups[key] = [];
        groups[key].push({
            value: [tenure, salary, deptName],
            deptName: deptName,
            clusterName: clusterName
        });
    });

    const clusterNames = Object.keys(groups);

    c.setOption({
        tooltip: {
            formatter: (p) => {
                const d = p.data;
                return `<b>${d.deptName}</b><br/>
                    工龄: ${d.value[0].toFixed(1)} 年<br/>
                    薪资: $${fmt(d.value[1])}<br/>
                    聚类: ${d.clusterName}`;
            }
        },
        legend: {
            data: clusterNames,
            textStyle: { color: '#a0aec0', fontSize: 11 },
            top: 5
        },
        grid3D: {
            boxWidth: 100,
            boxHeight: 80,
            boxDepth: 100,
            viewControl: {
                autoRotate: true,
                autoRotateSpeed: 10,
                distance: 180
            },
            light: {
                main: { intensity: 1.2, shadow: true },
                ambient: { intensity: 0.6 }
            }
        },
        xAxis3D: {
            name: '工龄 (年)',
            type: 'value',
            nameTextStyle: { color: '#a0aec0' },
            axisLine: { lineStyle: { color: '#4facfe' } },
            splitLine: { lineStyle: { color: 'rgba(255,255,255,0.06)' } }
        },
        yAxis3D: {
            name: '薪资 (美元)',
            type: 'value',
            nameTextStyle: { color: '#a0aec0' },
            axisLine: { lineStyle: { color: '#f6e05e' } },
            splitLine: { lineStyle: { color: 'rgba(255,255,255,0.06)' } },
            axisLabel: { formatter: (v) => '$' + fmt(v) }
        },
        zAxis3D: {
            name: '部门',
            type: 'category',
            data: deptLabels,
            nameTextStyle: { color: '#a0aec0' },
            axisLine: { lineStyle: { color: '#00f2fe' } }
        },
        series: clusterNames.map((name, i) => ({
            name,
            type: 'scatter3D',
            data: groups[name],
            symbolSize: 6,
            itemStyle: { color: COLORS[i % COLORS.length] },
            emphasis: { itemStyle: { color: COLORS[i % COLORS.length] }, scale: 1.5 }
        }))
    });
}
