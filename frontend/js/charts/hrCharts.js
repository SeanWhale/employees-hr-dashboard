// File: frontend/js/charts/hrCharts.js
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

    const heatData = [];
    for (let i = 0; i < labels.length; i++)
        for (let j = 0; j < labels.length; j++)
            heatData.push([i, j, matrix[i][j]]);

    const titles = { pearson: 'Pearson 相关系数', spearman: 'Spearman 秩相关', partial: '偏相关系数 (控其他变量)', mutual_info: '互信息 (Mutual Info)' };
    const isMI = method === 'mutual_info';
    const flatVals = matrix.flat();
    const vMin = isMI ? 0 : -1;
    const vMax = isMI ? Math.ceil(Math.max(...flatVals)) : 1;

    c.setOption({
        title: { text: titles[method] || '', textStyle: { color: '#00f2fe', fontSize: 13 }, left: 'center', top: 5 },
        tooltip: { position: 'top', formatter: (p) => `${labels[p.value[0]]} vs ${labels[p.value[1]]}: ${p.value[2].toFixed(4)}` },
        grid: { left: '16%', right: '8%', bottom: '30%', top: '18%' },
        xAxis: { type: 'category', data: labels, axisLabel: { rotate: 35, margin: 15, color: '#a0aec0', fontSize: 12 }, splitArea: { show: true } },
        yAxis: { type: 'category', data: labels, axisLabel: { color: '#a0aec0', fontSize: 12 }, splitArea: { show: true } },
        visualMap: { min: vMin, max: vMax, calculable: true, orient: 'horizontal', left: 'center', bottom: '1%',
                      inRange: { color: isMI ? ['#1f2937', '#00f2fe'] : ['#ff4757', '#1f2937', '#00f2fe'] }, textStyle: { color: '#a0aec0' } },
        series: [{ name: '相关性', type: 'heatmap', data: heatData,
                   label: { show: true, formatter: (p) => Number(p.value[2]).toFixed(3), color: '#e2e8f0', fontSize: 12 },
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
        grid: { left: '22%', right: '8%', bottom: '28%', top: '18%' },
        xAxis: { type: 'category', data: depts, axisLabel: { rotate: 35, margin: 15, color: '#a0aec0', fontSize: 10 }, splitArea: { show: true } },
        yAxis: { type: 'category', data: depts, axisLabel: { color: '#a0aec0', fontSize: 10 }, splitArea: { show: true } },
        visualMap: {
            min: isDist ? 0 : -1, max: isDist ? Math.max(...matrix.flat()) : 1,
            calculable: true, orient: 'horizontal', left: 'center', bottom: '1%',
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
            type: 'sankey', layoutIterations: 32, nodeAlign: 'left',
            data: data.nodes, links: data.links,
            left: '2%', right: '18%', top: '6%', bottom: '6%',
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

// --- 部门稳定性 100% 堆叠柱状图 ---
export function renderDeptStabilityChart(domId, data) {
    const c = initChart(domId);
    if (!c || !data?.departments?.length) return;

    const labels = ['已离职', '在职-稳定未调岗', '在职-内部流动/晋升'];
    const colors = ['#95a5a6', '#2ecc71', '#3498db'];

    // 将绝对人数转换为百分比
    const pctDatasets = {};
    const n = data.departments.length;
    for (const label of labels) {
        pctDatasets[label] = [];
        for (let i = 0; i < n; i++) {
            const total = labels.reduce((sum, l) => sum + (data.datasets[l]?.[i] || 0), 0);
            const val = data.datasets[label]?.[i] || 0;
            pctDatasets[label].push(total > 0 ? parseFloat((val / total * 100).toFixed(1)) : 0);
        }
    }

    c.setOption({
        tooltip: {
            trigger: 'axis',
            axisPointer: { type: 'shadow' },
            formatter: (params) => {
                let html = `<b>${params[0].axisValue}</b><br/>`;
                let sum = 0;
                params.forEach(p => { sum += p.value; });
                params.forEach(p => {
                    html += `${p.marker} ${p.seriesName}: ${p.value}%<br/>`;
                });
                html += `<hr style="margin:4px 0;border-color:rgba(255,255,255,0.1)"/>合计: <b>${sum.toFixed(1)}%</b>`;
                return html;
            }
        },
        legend: {
            data: labels,
            textStyle: { color: '#e2e8f0' },
            top: 5
        },
        grid: { left: '10%', right: '5%', bottom: '15%', top: '15%' },
        xAxis: {
            type: 'category',
            data: data.departments,
            axisLabel: { rotate: 30, color: 'rgba(255,255,255,0.7)', fontSize: 11 },
            axisLine: { lineStyle: { color: 'rgba(255,255,255,0.2)' } },
            axisTick: { lineStyle: { color: 'rgba(255,255,255,0.2)' } }
        },
        yAxis: {
            type: 'value',
            max: 100,
            name: '占比 (%)',
            nameTextStyle: { color: 'rgba(255,255,255,0.7)' },
            axisLabel: { color: 'rgba(255,255,255,0.7)', formatter: '{value}%' },
            splitLine: { lineStyle: { color: 'rgba(255,255,255,0.1)' } }
        },
        series: labels.map((label, i) => ({
            name: label,
            type: 'bar',
            stack: 'stability',
            data: pctDatasets[label],
            itemStyle: { color: colors[i], borderRadius: i === labels.length - 1 ? [6, 6, 0, 0] : 0 },
            barWidth: '50%',
            emphasis: { focus: 'series' },
            label: { show: false }
        }))
    });
}
