/**
 * HR 分析图表 — 部门分布 / 相关性 / 相似性 / 回归 / 桑基图 / 性别 / 转岗 / 地图 / 留任
 */
import { initChart, COLORS, fmt } from '../utils.js';

// --- 部门饼图 ---
export function renderDeptPie(data, { searchText, onSearch }) {
    const c = initChart('c_dept_pie');
    if (!c) return;
    c.setOption({
        tooltip: { trigger: 'item', formatter: '{b}: {c}人 ({d}%)' },
        legend: { type: 'scroll', bottom: 0, textStyle: { color: '#a0aec0' } },
        series: [{
            type: 'pie', radius: ['35%', '65%'], center: ['50%', '42%'],
            data: data.map(d => ({ name: d.dept_name, value: d.emp_count })),
            itemStyle: { borderRadius: 6, borderColor: '#0b0f19', borderWidth: 2 },
            label: { color: '#a0aec0' }
        }]
    });
    c.on('click', (p) => {
        searchText.value = p.name;
        onSearch();
    });
}

// --- 部门柱线图 ---
export function renderDeptBar(data) {
    const c = initChart('c_dept_bar');
    if (!c) return;
    const sorted = [...data].sort((a, b) => b.avg_salary - a.avg_salary);
    c.setOption({
        tooltip: { trigger: 'axis' },
        legend: { data: ['人数', '平均薪资', '中位薪资'], textStyle: { color: '#e2e8f0' }, top: 5 },
        grid: { bottom: '22%', containLabel: true },
        xAxis: { type: 'category', data: sorted.map(d => d.dept_name), axisLabel: { rotate: 30, color: '#a0aec0', fontSize: 11 } },
        yAxis: [
            { type: 'value', name: '人数', axisLabel: { color: '#a0aec0' } },
            { type: 'value', name: '薪资($)', axisLabel: { color: '#a0aec0' }, splitLine: { show: false } }
        ],
        series: [
            { name: '人数', type: 'bar', data: sorted.map(d => d.emp_count), itemStyle: { color: '#00f2fe' }, barWidth: '40%' },
            { name: '平均薪资', type: 'line', yAxisIndex: 1, data: sorted.map(d => d.avg_salary), lineStyle: { color: '#f6e05e', width: 2.5 }, symbol: 'circle', symbolSize: 8 },
            { name: '中位薪资', type: 'line', yAxisIndex: 1, data: sorted.map(d => d.median_salary), lineStyle: { color: '#ff4757', width: 2, type: 'dashed' }, symbol: 'diamond', symbolSize: 6 }
        ]
    });
}

// --- 相关性热力图 (Req 6) ---
export function renderCorrelation(data, corrMethod) {
    const c = initChart('c_corr_heat');
    if (!c || !data) return;

    const method = corrMethod.value;
    const matrix = data[method];
    const labels = data.labels;
    const labelMap = { salary: '薪资', tenure: '司龄', age: '年龄' };
    const displayLabels = labels.map(l => labelMap[l] || l);

    const heatData = [];
    for (let i = 0; i < labels.length; i++)
        for (let j = 0; j < labels.length; j++)
            heatData.push([i, j, matrix[i][j]]);

    const titles = { pearson: 'Pearson 相关系数', spearman: 'Spearman 秩相关', partial: '偏相关系数 (控第三变量)', mutual_info: '互信息 (Mutual Info)' };
    const isMI = method === 'mutual_info';
    const flatVals = matrix.flat();
    const vMin = isMI ? 0 : -1;
    const vMax = isMI ? Math.ceil(Math.max(...flatVals)) : 1;

    c.setOption({
        title: { text: titles[method] || '', textStyle: { color: '#00f2fe', fontSize: 13 }, left: 'center', top: 5 },
        tooltip: { position: 'top', formatter: (p) => `${displayLabels[p.value[0]]} vs ${displayLabels[p.value[1]]}: ${p.value[2].toFixed(4)}` },
        grid: { left: '15%', right: '8%', bottom: '15%', top: '18%' },
        xAxis: { type: 'category', data: displayLabels, axisLabel: { color: '#a0aec0' }, splitArea: { show: true } },
        yAxis: { type: 'category', data: displayLabels, axisLabel: { color: '#a0aec0' }, splitArea: { show: true } },
        visualMap: { min: vMin, max: vMax, calculable: true, orient: 'horizontal', left: 'center', bottom: '2%',
                      inRange: { color: isMI ? ['#1f2937', '#00f2fe'] : ['#ff4757', '#1f2937', '#00f2fe'] }, textStyle: { color: '#a0aec0' } },
        series: [{ name: '相关性', type: 'heatmap', data: heatData,
                   label: { show: true, formatter: (p) => Number(p.value[2]).toFixed(3), color: '#e2e8f0', fontSize: 11 },
                   emphasis: { itemStyle: { shadowBlur: 8, shadowColor: 'rgba(0,242,254,0.3)' } } }]
    });
}

// --- 相似性热力图 (Req 2) ---
export function renderSimilarity(data, simMetric) {
    const c = initChart('c_similarity');
    if (!c || !data) return;

    const depts = data.departments;
    const metric = simMetric.value;
    const matrix = metric === 'cosine' ? data.cosine_similarity : data.euclidean_distance;

    const hm = [];
    for (let i = 0; i < depts.length; i++)
        for (let j = 0; j < depts.length; j++)
            hm.push([i, j, matrix[i][j]]);

    const isDist = metric === 'euclidean';
    const title = isDist ? '部门特征欧氏距离 (标准化后)' : '部门特征余弦相似度';

    c.setOption({
        title: { text: title, textStyle: { color: '#f6e05e', fontSize: 13 }, left: 'center', top: 5 },
        tooltip: { position: 'top', formatter: (p) => `${depts[p.value[0]]} — ${depts[p.value[1]]}: ${p.value[2].toFixed(3)}` },
        grid: { left: '18%', right: '8%', bottom: '15%', top: '18%' },
        xAxis: { type: 'category', data: depts, axisLabel: { rotate: 30, color: '#a0aec0', fontSize: 10 }, splitArea: { show: true } },
        yAxis: { type: 'category', data: depts, axisLabel: { color: '#a0aec0', fontSize: 10 }, splitArea: { show: true } },
        visualMap: {
            min: isDist ? 0 : -1, max: isDist ? Math.max(...matrix.flat()) : 1,
            calculable: true, orient: 'horizontal', left: 'center', bottom: '2%',
            inRange: { color: isDist ? ['#00f2fe', '#1f2937', '#ff4757'] : ['#ff4757', '#1f2937', '#00f2fe'] },
            textStyle: { color: '#a0aec0' }
        },
        series: [{ name: '相似度', type: 'heatmap', data: hm,
                   label: { show: true, formatter: (p) => p.value[2].toFixed(2), color: '#e2e8f0', fontSize: 10 } }]
    });
}

// --- 回归散点 ---
export function renderRegression(reg) {
    const c = initChart('c_regression');
    if (!c || !reg) return;
    c.setOption({
        tooltip: { trigger: 'item', formatter: (p) => `司龄: ${p.data[0].toFixed(0)}<br/>薪资: $${fmt(p.data[1])}` },
        legend: { data: ['样本点', '回归线', '95%CI'], textStyle: { color: '#a0aec0' }, top: 5 },
        grid: { left: '8%', right: '5%', bottom: '10%', top: '15%' },
        xAxis: { name: '司龄 (年)', type: 'value', axisLabel: { color: '#a0aec0' }, splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } } },
        yAxis: { name: '薪资 ($)', type: 'value', axisLabel: { color: '#a0aec0' }, splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } } },
        series: [
            { name: '样本点', type: 'scatter', data: reg.points.map(p => [p.x, p.y]), symbolSize: 5,
              itemStyle: { color: 'rgba(0,242,254,0.5)' } },
            { name: '回归线', type: 'line', data: reg.line.map(p => [p.x, p.y]),
              showSymbol: false, lineStyle: { color: '#f6e05e', width: 3 } },
            { name: '95%CI', type: 'line', data: reg.ci.map(p => [p.x, p.y_high]),
              showSymbol: false, lineStyle: { color: 'rgba(246,224,94,0.3)', type: 'dashed' } },
            { name: '95%CI', type: 'line', data: reg.ci.map(p => [p.x, p.y_low]),
              showSymbol: false, lineStyle: { color: 'rgba(246,224,94,0.3)', type: 'dashed' } }
        ],
        graphic: [{ type: 'text', right: '8%', top: '5%',
                    style: { text: `斜率=${reg.slope} R²=${reg.r_squared}`, fill: '#f6e05e', font: '14px sans-serif' } }]
    });
}

// --- 桑基图 ---
export function renderSankey(data) {
    const c = initChart('c_sankey');
    if (!c || !data?.nodes?.length) return;
    c.setOption({
        tooltip: { trigger: 'item', formatter: (p) => p.dataType === 'edge' ? `${p.data.source} → ${p.data.target}: ${fmt(p.data.value)}人` : p.name },
        series: [{
            type: 'sankey', layoutIterations: 32, nodeAlign: 'justify',
            data: data.nodes, links: data.links,
            left: '2%', right: '2%', top: '6%', bottom: '6%',
            nodeWidth: 16, nodeGap: 12,
            emphasis: { focus: 'adjacency' },
            lineStyle: { color: 'gradient', curveness: 0.5, opacity: 0.5 },
            label: { color: '#e2e8f0', fontSize: 11 }
        }]
    });
}

// --- 性别比例 ---
export function renderGenderRatio(data) {
    const c = initChart('c_gender_ratio');
    if (!c || !data?.dept_ratio) return;
    const depts = data.dept_ratio.map(d => d.dept_name);
    c.setOption({
        tooltip: { trigger: 'axis', formatter: (p) => {
            const d = data.dept_ratio[p[0].dataIndex];
            return `<b>${d.dept_name}</b><br/>M: ${d.M} (${d.M_pct}%)<br/>F: ${d.F} (${d.F_pct}%)`;
        }},
        legend: { data: ['M', 'F'], textStyle: { color: '#a0aec0' }, top: 3 },
        grid: { left: '12%', right: '5%', bottom: '22%', top: '15%' },
        xAxis: { type: 'category', data: depts, axisLabel: { rotate: 30, color: '#a0aec0', fontSize: 10 } },
        yAxis: { type: 'value', name: '人数', axisLabel: { color: '#a0aec0' }, splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } } },
        series: [
            { name: 'M', type: 'bar', data: data.dept_ratio.map(d => d.M), itemStyle: { color: '#4facfe' }, stack: 'g' },
            { name: 'F', type: 'bar', data: data.dept_ratio.map(d => d.F), itemStyle: { color: '#ff6b81' }, stack: 'g' }
        ]
    });
}

// --- 性别薪资 ---
export function renderGenderPay(data) {
    const c = initChart('c_gender_pay');
    if (!c || !data?.dept_salary) return;
    const depts = [...new Set(data.dept_salary.map(d => d.dept_name))];
    const mData = depts.map(dept => { const r = data.dept_salary.find(d => d.dept_name === dept && d.gender === 'M'); return r ? r.avg_salary : null; });
    const fData = depts.map(dept => { const r = data.dept_salary.find(d => d.dept_name === dept && d.gender === 'F'); return r ? r.avg_salary : null; });
    c.setOption({
        tooltip: { trigger: 'axis' },
        legend: { data: ['M均薪', 'F均薪'], textStyle: { color: '#a0aec0' }, top: 3 },
        grid: { left: '12%', right: '5%', bottom: '22%', top: '15%' },
        xAxis: { type: 'category', data: depts, axisLabel: { rotate: 30, color: '#a0aec0', fontSize: 10 } },
        yAxis: { type: 'value', name: '薪资($)', axisLabel: { color: '#a0aec0' }, splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } } },
        series: [
            { name: 'M均薪', type: 'line', data: mData, lineStyle: { color: '#4facfe', width: 2.5 }, symbol: 'circle', symbolSize: 7 },
            { name: 'F均薪', type: 'line', data: fData, lineStyle: { color: '#ff6b81', width: 2.5 }, symbol: 'diamond', symbolSize: 7 }
        ]
    });
}

// --- 转岗耗时 ---
export function renderTransition(data) {
    const c = initChart('c_transition');
    if (!c || !data?.box_data?.length) return;
    const limited = data.box_data.slice(0, 20);
    c.setOption({
        tooltip: { trigger: 'item', formatter: (p) => {
            const d = limited[p.dataIndex];
            return `<b>${d.name}</b><br/>最短: ${d.data[0]}年<br/>Q1: ${d.data[1]}年<br/>中位: ${d.data[2]}年<br/>Q3: ${d.data[3]}年<br/>最长: ${d.data[4]}年`;
        }},
        grid: { left: '28%', right: '5%', bottom: '25%', top: '8%' },
        xAxis: { type: 'category', data: limited.map(d => d.name), axisLabel: { rotate: 45, color: '#a0aec0', fontSize: 9 } },
        yAxis: { type: 'value', name: '年数', axisLabel: { color: '#a0aec0' }, splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } } },
        series: [{ type: 'boxplot', data: limited.map(d => d.data), itemStyle: { color: '#f6e05e', borderColor: '#f6e05e' } }]
    });
}

// --- 中国地图 (Req 7) ---
export function renderMap(data, chinaGeoJSON) {
    const c = initChart('c_map');
    if (!c || !chinaGeoJSON) return;
    echarts.registerMap('china', chinaGeoJSON);
    c.setOption({
        tooltip: {
            trigger: 'item',
            formatter: (p) => {
                const v = p.value;
                if (!v || v.length < 4) return p.name;
                return `<div style="background:rgba(16,30,54,0.9);padding:10px;border:1px solid #00f2fe;border-radius:4px;">
                    <b style="color:#00f2fe;font-size:15px;">${p.name}</b><br/>
                    人数: <b style="color:#fff;">${fmt(v[3])}</b> 人<br/>
                    均薪: <b style="color:#f6e05e;">$${fmt(v[2])}</b></div>`;
            },
            backgroundColor: 'transparent', borderWidth: 0, padding: 0
        },
        geo: {
            map: 'china', roam: true,
            itemStyle: { areaColor: '#101e36', borderColor: '#00f2fe', borderWidth: 1 },
            emphasis: { areaColor: '#1a2a44', label: { show: true, color: '#fff' } }
        },
        series: [{
            type: 'effectScatter', coordinateSystem: 'geo',
            data: data,
            symbolSize: (v) => Math.max(12, v[3] / 4500),
            rippleEffect: { brushType: 'stroke', scale: 3 },
            itemStyle: {
                color: (p) => p.value[2] > 80000 ? '#f6e05e' : '#00f2fe',
                shadowBlur: 12, shadowColor: '#00f2fe'
            }
        }]
    });
}

// --- 留任分析 ---
export function renderRetention(data) {
    const c = initChart('c_retention');
    if (!c || !data?.employees) return;
    const groups = { 'stable': [], 'moderate': [], 'frequent': [] };
    data.employees.forEach(e => { if (groups[e.category]) groups[e.category].push([e.total_changes, e.salary, e]); });
    c.setOption({
        color: ['#2ed573', '#f6e05e', '#ff4757'],
        tooltip: { trigger: 'item', formatter: (p) => {
            const e = p.data[2];
            return `<b>#${e.emp_no}</b> — ${e.dept}<br/>部变: ${e.dept_changes} 职变: ${e.title_changes}<br/>薪资: $${fmt(e.salary)}`;
        }},
        legend: { data: data.summary?.map(s => s.label) || [], textStyle: { color: '#a0aec0', fontSize: 10 }, top: 3 },
        grid: { left: '10%', right: '5%', bottom: '10%', top: '15%' },
        xAxis: { name: '总变动次数', type: 'value', axisLabel: { color: '#a0aec0' }, splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } } },
        yAxis: { name: '薪资($)', type: 'value', axisLabel: { color: '#a0aec0' }, splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } } },
        series: Object.entries(groups).map(([cat, pts]) => ({
            name: data.labels?.[cat] || cat, type: 'scatter', data: pts, symbolSize: 6
        }))
    });
}
