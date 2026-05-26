// File: frontend/js/charts/salaryCharts.js
/**
 * 薪资分析图表 — 历史演变 / 箱线图 / 趋势 / 基准 / 增长 / 预测
 */
import { initChart, COLORS, fmt } from '../utils.js';

// --- 时间轴动态演变 (Req 8) ---
export function renderTimeline(data) {
    const c = initChart('c_timeline');
    if (!c || !data?.length) return;
    const years = [...new Set(data.map(d => d.year))].sort();
    const depts = [...new Set(data.map(d => d.dept_name))];

    const options = years.map(yr => {
        const yrData = data.filter(d => d.year === yr);
        return {
            title: { text: `${yr} 年各部门平均薪资`, textStyle: { color: '#00f2fe', fontSize: 15 } },
            series: [{
                type: 'bar', data: depts.map(dept => {
                    const hit = yrData.find(d => d.dept_name === dept);
                    return hit ? hit.avg_salary : 0;
                }), itemStyle: { borderRadius: [4, 4, 0, 0] }
            }]
        };
    });

    c.setOption({
        baseOption: {
            timeline: { axisType: 'category', autoPlay: true, playInterval: 1500, data: years,
                        label: { color: '#a0aec0' },
                        controlStyle: { color: '#00f2fe', borderColor: '#00f2fe' } },
            tooltip: { trigger: 'axis' },
            grid: { bottom: '20%', top: '18%', left: '8%', right: '5%' },
            xAxis: { type: 'category', data: depts, axisLabel: { rotate: 30, color: '#a0aec0', fontSize: 10 } },
            yAxis: { type: 'value', name: '平均薪资($)', axisLabel: { color: '#a0aec0' }, splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } } },
            series: [{ type: 'bar', itemStyle: { color: '#4facfe' } }],
            color: ['#4facfe']
        },
        options: options
    });
}

// --- 箱线图 ---
export function renderBoxPlot(data) {
    const c = initChart('c_box');
    if (!c || !data?.departments) return;
    const depts = data.departments.map(d => d.dept_name);
    const boxData = data.departments.map(d => d.box);
    const outliers = [];
    data.departments.forEach((d, i) => {
        d.outliers_low.forEach(v => outliers.push([i, v]));
        d.outliers_high.forEach(v => outliers.push([i, v]));
    });
    c.setOption({
        tooltip: { trigger: 'item', formatter: (p) => {
            if (p.seriesType === 'boxplot') {
                const d = data.departments[p.dataIndex];
                return `<b>${d.dept_name}</b><br/>上限: $${fmt(d.stats.max)}<br/>Q3: $${fmt(d.stats.q3)}<br/>中位: $${fmt(d.stats.median)}<br/>Q1: $${fmt(d.stats.q1)}<br/>下限: $${fmt(d.stats.min)}<br/>均值: $${fmt(d.stats.mean)}<br/>离群值: ${d.stats.outliers_low + d.stats.outliers_high}个`;
            }
        }},
        grid: { left: '14%', right: '5%', bottom: '25%', top: '8%' },
        xAxis: { type: 'category', data: depts, axisLabel: { rotate: 35, color: '#a0aec0', fontSize: 10 } },
        yAxis: { type: 'value', name: '薪资($)', axisLabel: { color: '#a0aec0' }, splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } } },
        series: [
            { name: '薪资分布', type: 'boxplot', data: boxData, itemStyle: { color: '#00f2fe', borderColor: '#4facfe' } },
            { name: '离群值', type: 'scatter', data: outliers, symbolSize: 5, itemStyle: { color: '#ff4757' } }
        ]
    });
}

// --- 薪资演变 ---
export function renderEvolution(data) {
    const c = initChart('c_evolution');
    if (!c || !data?.yearly) return;
    const stats = data.yearly;
    c.setOption({
        tooltip: { trigger: 'axis' },
        legend: { data: ['中位数', '均值', 'Q1', 'Q3', 'P10', 'P90'], textStyle: { color: '#a0aec0' }, top: 5 },
        grid: { left: '8%', right: '5%', bottom: '12%', top: '18%' },
        xAxis: { type: 'category', data: stats.map(d => d.year), axisLabel: { color: '#a0aec0' }, splitLine: { show: false } },
        yAxis: { type: 'value', name: '薪资($)', axisLabel: { color: '#a0aec0' }, splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } } },
        series: [
            { name: 'P10', type: 'line', data: stats.map(d => d.p10), lineStyle: { color: 'rgba(0,242,254,0.3)', type: 'dashed', width: 1 }, symbol: 'none' },
            { name: 'P90', type: 'line', data: stats.map(d => d.p90), lineStyle: { color: 'rgba(0,242,254,0.3)', type: 'dashed', width: 1 }, symbol: 'none',
              areaStyle: { color: 'rgba(0,242,254,0.04)' }, z: 0 },
            { name: 'Q1', type: 'line', data: stats.map(d => d.q1), lineStyle: { color: 'rgba(0,242,254,0.5)', type: 'dotted', width: 1 }, symbol: 'none' },
            { name: 'Q3', type: 'line', data: stats.map(d => d.q3), lineStyle: { color: 'rgba(0,242,254,0.5)', type: 'dotted', width: 1 }, symbol: 'none',
              areaStyle: { color: 'rgba(0,242,254,0.08)' }, z: 1 },
            { name: '中位数', type: 'line', data: stats.map(d => d.median), lineStyle: { color: '#00f2fe', width: 2.5 }, symbol: 'none', z: 10 },
            { name: '均值', type: 'line', data: stats.map(d => d.mean), lineStyle: { color: '#f6e05e', width: 2, type: 'dashed' }, symbol: 'none', z: 10 }
        ]
    });
}

// --- 外部基准联动 (Req 10) ---
export function renderBenchmark(data) {
    const c = initChart('c_benchmark');
    if (!c || !data?.dept_comparison) return;
    const sorted = data.dept_comparison;
    c.setOption({
        tooltip: { trigger: 'axis', formatter: (p) => {
            const d = sorted[p[0].dataIndex];
            return `<b>${d.dept_name}</b> (${d.function})<br/>内部均薪: $${fmt(d.internal_avg)}<br/>行业基准: $${fmt(d.industry_avg)}<br/>差异: ${d.diff_pct > 0 ? '+' : ''}${d.diff_pct}%`;
        }},
        legend: { data: ['内部均薪', '行业基准', '差异%'], textStyle: { color: '#a0aec0' }, top: 5 },
        grid: { left: '8%', right: '8%', bottom: '15%', top: '18%' },
        xAxis: { type: 'category', data: sorted.map(d => d.dept_name), axisLabel: { rotate: 30, color: '#a0aec0', fontSize: 11 } },
        yAxis: [
            { type: 'value', name: '薪资($)', axisLabel: { color: '#a0aec0' }, splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } } },
            { type: 'value', name: '差异%', axisLabel: { color: '#a0aec0', formatter: '{v}%' }, splitLine: { show: false } }
        ],
        series: [
            { name: '内部均薪', type: 'bar', data: sorted.map(d => d.internal_avg), itemStyle: { color: '#00f2fe' }, barWidth: '40%' },
            { name: '行业基准', type: 'bar', data: sorted.map(d => d.industry_avg), itemStyle: { color: 'rgba(246,224,94,0.5)', borderColor: '#f6e05e', borderWidth: 2, borderRadius: 0 }, barWidth: '40%', barGap: '-100%', z: 2 },
            { name: '差异%', type: 'line', yAxisIndex: 1, data: sorted.map(d => d.diff_pct), lineStyle: { color: '#ff4757', width: 2.5 }, symbol: 'triangle', symbolSize: 10, itemStyle: { color: (p) => p.value >= 0 ? '#2ed573' : '#ff4757' } }
        ]
    });
}

// --- 薪资增长曲线 ---
export function renderGrowth(data, growthView) {
    const c = initChart('c_growth');
    if (!c || !data) return;
    const view = growthView.value;

    if (view === 'dept' && data.dept?.length) {
        const sorted = [...data.dept].sort((a, b) => b.median - a.median);
        c.setOption({
            tooltip: { trigger: 'axis' },
            legend: { data: ['中位数年增长', '平均年增长'], textStyle: { color: '#a0aec0' }, top: 3 },
            grid: { left: '12%', right: '5%', bottom: '22%', top: '15%' },
            xAxis: { type: 'category', data: sorted.map(d => d.dept_name), axisLabel: { rotate: 30, color: '#a0aec0', fontSize: 10 } },
            yAxis: { type: 'value', name: '$/年', axisLabel: { color: '#a0aec0' }, splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } } },
            series: [
                { name: '中位数年增长', type: 'bar', data: sorted.map(d => d.median), itemStyle: { color: '#00f2fe' } },
                { name: '平均年增长', type: 'bar', data: sorted.map(d => d.avg), itemStyle: { color: '#f6e05e' } }
            ]
        });
    } else if (view === 'title' && data.title?.length) {
        const sorted = [...data.title].sort((a, b) => b.median - a.median);
        c.setOption({
            tooltip: { trigger: 'axis' },
            legend: { data: ['中位数年增长', '平均年增长'], textStyle: { color: '#a0aec0' }, top: 3 },
            grid: { left: '12%', right: '5%', bottom: '22%', top: '15%' },
            xAxis: { type: 'category', data: sorted.map(d => d.title), axisLabel: { rotate: 30, color: '#a0aec0', fontSize: 10 } },
            yAxis: { type: 'value', name: '$/年', axisLabel: { color: '#a0aec0' }, splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } } },
            series: [
                { name: '中位数年增长', type: 'bar', data: sorted.map(d => d.median), itemStyle: { color: '#00f2fe' } },
                { name: '平均年增长', type: 'bar', data: sorted.map(d => d.avg), itemStyle: { color: '#f6e05e' } }
            ]
        });
    } else if (view === 'curves' && data.curves?.length) {
        const curves = data.curves.slice(0, 6);
        c.setOption({
            color: COLORS,
            tooltip: { trigger: 'axis' },
            legend: { type: 'scroll', bottom: 0, textStyle: { color: '#a0aec0', fontSize: 10 } },
            grid: { left: '8%', right: '5%', bottom: '22%', top: '8%' },
            xAxis: { type: 'value', name: '入职年数', axisLabel: { color: '#a0aec0' }, splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } } },
            yAxis: { type: 'value', name: '薪资($)', axisLabel: { color: '#a0aec0' }, splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } } },
            series: curves.map((crv, i) => ({
                name: `#${crv.emp_no} ${crv.dept}`, type: 'line',
                data: crv.actual.map(p => [p.x, p.y]),
                lineStyle: { width: 2 }, symbol: 'circle', symbolSize: 5
            }))
        });
    }
}

// --- 多模型预测 (Req 4) ---
export function renderForecast(data, forecastModel) {
    const c = initChart('c_forecast');
    if (!c || !data) return;

    const { years, actuals, models, comparison } = data;
    const trainEnd = 1996;
    const filt = forecastModel.value;

    const series = [];
    if (filt === 'all') {
        series.push({
            name: '历史实际', type: 'line',
            data: actuals.map((v, i) => years[i] <= trainEnd ? v : null),
            lineStyle: { width: 4, color: '#00f2fe' }, symbol: 'circle', symbolSize: 7, z: 10
        });
        series.push({
            name: '验证实际 (1997-2002)', type: 'line',
            data: actuals.map((v, i) => years[i] >= trainEnd ? v : null),
            lineStyle: { width: 3, color: '#ff4757', type: 'dashed' }, symbol: 'diamond', symbolSize: 9, z: 9
        });
        const styles = [{ color: '#f6e05e', type: 'dotted' }, { color: '#2ed573', type: 'dotted' }, { color: '#a29bfe', type: 'dotted' }];
        models.forEach((m, i) => {
            series.push({
                name: `${m.name} (MAE=${m.metrics.mae})`, type: 'line',
                data: m.predictions,
                lineStyle: { width: 1.5, color: styles[i].color, type: styles[i].type },
                symbol: 'none'
            });
        });
    } else {
        const m = models.find(x => x.name === filt);
        if (!m) return;
        series.push({
            name: '历史实际', type: 'line',
            data: actuals.map((v, i) => years[i] <= trainEnd ? v : null),
            lineStyle: { width: 4, color: '#00f2fe' }, symbol: 'circle', symbolSize: 7
        });
        series.push({
            name: '验证实际', type: 'line',
            data: actuals.map((v, i) => years[i] >= trainEnd ? v : null),
            lineStyle: { width: 3, color: '#ff4757', type: 'dashed' }, symbol: 'diamond', symbolSize: 9
        });
        series.push({
            name: `${m.name} 预测 (MAE=${m.metrics.mae})`, type: 'line',
            data: m.predictions,
            lineStyle: { width: 2, color: '#f6e05e' }, areaStyle: { color: 'rgba(246,224,94,0.1)' }, symbol: 'none'
        });
    }

    const cmpText = comparison.map(x => `${x.name}: MAE=${x.mae} RMSE=${x.rmse} MAPE=${x.mape}%`).join('  |  ');

    c.setOption({
        tooltip: { trigger: 'axis' },
        legend: { type: 'scroll', bottom: 0, textStyle: { color: '#a0aec0', fontSize: 10 } },
        grid: { left: '6%', right: '5%', bottom: '18%', top: '12%' },
        xAxis: { type: 'category', data: years, axisLabel: { color: '#a0aec0' }, splitLine: { show: false } },
        yAxis: { type: 'value', name: '平均薪资($)', axisLabel: { color: '#a0aec0' }, splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } } },
        series: series,
        graphic: [
            { type: 'text', left: '48%', top: '5%', style: { text: '← 训练期 | 验证期 →', fill: '#f6e05e', font: '13px sans-serif' } },
            { type: 'text', left: 'center', top: '2%', style: { text: cmpText, fill: '#a0aec0', font: '11px sans-serif' } }
        ]
    });
}

// --- 分部门预测 ---
export function renderDeptForecast(data, deptForecastSel) {
    const c = initChart('c_dept_fc');
    if (!c || !data?.departments) return;
    const sel = deptForecastSel.value;
    const all = data.departments;
    let depts = sel === 'all' ? all.slice(0, 6) : all.filter(d => d.dept_name === sel);

    const series = [];
    depts.forEach((dept, i) => {
        const color = COLORS[i % COLORS.length];
        const yrs = dept.data.map(d => d.year);
        series.push({
            name: `${dept.dept_name} 实际`, type: 'line',
            data: dept.data.map(d => d.actual),
            lineStyle: { color, width: 2 }, symbol: 'circle', symbolSize: 5
        });
        series.push({
            name: `${dept.dept_name} 预测`, type: 'line',
            data: dept.data.map(d => d.prediction),
            lineStyle: { color, width: 1.5, type: 'dashed' }, symbol: 'none'
        });
    });

    c.setOption({
        tooltip: { trigger: 'axis' },
        legend: { type: 'scroll', bottom: 0, textStyle: { color: '#a0aec0', fontSize: 10 } },
        grid: { left: '8%', right: '5%', bottom: '20%', top: '8%' },
        xAxis: { type: 'category', data: depts[0]?.data.map(d => d.year) || [], axisLabel: { color: '#a0aec0' }, splitLine: { show: false } },
        yAxis: { type: 'value', name: '平均薪资($)', axisLabel: { color: '#a0aec0' }, splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } } },
        series: series
    });
}
