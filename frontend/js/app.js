/**
 * Enterprise HR Insights 360 — 全局指挥舱
 * 覆盖 Req 2-10: 聚类/预测/相关性/相似性/大屏/动态/交互/外部数据
 */
const { createApp, ref, onMounted, onUnmounted, watch, nextTick } = Vue;

const COLORS = ['#00f2fe', '#f6e05e', '#ff4757', '#2ed573', '#4facfe', '#ff6b81', '#a29bfe', '#fd79a8', '#e17055'];
const API = window.location.port === '8000' 
    ? '/api' 
    : `${window.location.protocol}//${window.location.hostname}:8000/api`;

// ============ 工具函数 ============
const fmt = (n) => n ? Number(n).toLocaleString() : '0';
const $ = (id) => document.getElementById(id);
const resizeHandlers = [];
const initChart = (domId) => {
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

createApp({
    setup() {
        // ---- 状态 ----
        const kpi = ref({ total: 0, avg_s: 0, max_s: 0, min_s: 0, std_s: 0 });
        const currentTime = ref('');
        const showModal = ref(false);
        const selectedEmp = ref(null);
        const searchText = ref('');
        const corrMethod = ref('pearson');
        const simMetric = ref('cosine');
        const forecastModel = ref('all');
        const growthView = ref('dept');
        const deptForecastSel = ref('all');
        const deptForecastList = ref([]);

        // 缓存数据
        let cache = {};
        let chinaGeoJSON = null;
        let timer = null;

        const updateTime = () => { currentTime.value = new Date().toLocaleString('zh-CN', { hour12: false }); };

        // ============ 搜索过滤 ============
        const onSearch = () => {
            const q = searchText.value.toLowerCase().trim();
            const c = echarts.getInstanceByDom($('c_pca'));
            const pca = cache.cluster?.pca;
            if (!c || !pca) return;

            // 恢复所有系列
            c.dispatchAction({ type: 'downplay' });

            if (!q || q.length < 2) return;

            // 收集所有匹配查询的聚类名称（按 cluster_name / dept / title 匹配）
            const matchedClusters = new Set();
            const { cluster_name, dept, title } = pca;
            // 注: PCA 数据里没有 title 数组，从 cluster.scatter 取
            const titles = cache.cluster?.scatter?.map(d => d.title) || [];

            for (let i = 0; i < cluster_name.length; i++) {
                if (cluster_name[i]?.toLowerCase().includes(q) ||
                    dept[i]?.toLowerCase().includes(q) ||
                    (titles[i] && titles[i].toLowerCase().includes(q))) {
                    matchedClusters.add(cluster_name[i]);
                }
            }

            // 高亮匹配的系列
            const option = c.getOption();
            if (option?.series) {
                option.series.forEach((s) => {
                    if (matchedClusters.has(s.name)) {
                        c.dispatchAction({ type: 'highlight', seriesName: s.name });
                    }
                });
            }
        };

        // ============ 全屏 ============
        const toggleFullscreen = () => {
            if (document.fullscreenElement) {
                document.exitFullscreen();
            } else {
                document.documentElement.requestFullscreen();
            }
        };

        // ============ 数据加载 ============
        const fetchAll = async () => {
            // 加载地图 GeoJSON
            try {
                const g = await axios.get('data/china_geo.json');// 读取本地相对路径
                chinaGeoJSON = g.data;
            } catch (e) { 
                console.error('本地地图数据加载失败，请检查文件路径', e); 
            }

            const api = (path) => axios.get(`${API}${path}`).then(r => r.data).catch(e => { console.error(path, e); return null; });

            // 并行请求
        const [kpiD, deptD, clusterD, historyD, forecastD, corrD, simD, sankeyD,
            distD, genderD, transD, evolD, benchD, mapD, retD, deptFcD, growthD] =
            await Promise.all([
                api('/v1/overview/kpi'), 
                api('/v1/overview/dept_distribution'), 
                api('/v1/advanced/clustering'), 
                api('/v1/salary/history'),
                api('/v1/advanced/forecast'), 
                api('/v1/advanced/correlation'), 
                api('/v1/advanced/similarity'), 
                api('/v1/advanced/title_sankey'),
                api('/v1/salary/distribution'), 
                api('/v1/advanced/gender_analysis'), 
                api('/v1/advanced/title_transition'),
                api('/v1/salary/evolution'), 
                api('/v1/salary/external_benchmark'), 
                api('/v1/overview/office_map'),
                api('/v1/advanced/retention'), 
                api('/v1/advanced/dept_forecast'), 
                api('/v1/salary/growth')
            ]);

            // 缓存
            cache = { dept: deptD, cluster: clusterD, history: historyD, forecast: forecastD,
                      corr: corrD, sim: simD, sankey: sankeyD, dist: distD, gender: genderD,
                      trans: transD, evol: evolD, bench: benchD, map: mapD, ret: retD,
                      deptFc: deptFcD, growth: growthD };

            const safeRender = (name, fn, ...args) => {
                try { fn(...args); } catch (e) { console.error(`[${name}] 渲染失败:`, e); }
            };

            if (kpiD) kpi.value = kpiD;
            if (deptD) { safeRender('deptPie', renderDeptPie, deptD); safeRender('deptBar', renderDeptBar, deptD); }
            if (clusterD) { safeRender('PCA', renderPCA, clusterD); safeRender('Radar', renderRadar, clusterD); safeRender('Silhouette', renderSilhouette, clusterD);
                             safeRender('ClusterCmp', renderClusterCmp, clusterD); safeRender('DBSCAN', renderDBSCAN, clusterD); }
            if (historyD) safeRender('Timeline', renderTimeline, historyD);
            if (forecastD) safeRender('Forecast', renderForecast);
            if (corrD) safeRender('Correlation', renderCorrelation);
            if (simD) safeRender('Similarity', renderSimilarity);
            if (corrD?.regression) safeRender('Regression', renderRegression, corrD.regression);
            if (sankeyD) safeRender('Sankey', renderSankey, sankeyD);
            if (distD) safeRender('BoxPlot', renderBoxPlot, distD);
            if (genderD) { safeRender('GenderRatio', renderGenderRatio, genderD); safeRender('GenderPay', renderGenderPay, genderD); }
            if (transD) safeRender('Transition', renderTransition, transD);
            if (evolD) safeRender('Evolution', renderEvolution, evolD);
            if (benchD) safeRender('Benchmark', renderBenchmark, benchD);
            if (mapD && chinaGeoJSON) safeRender('Map', renderMap, mapD);
            if (retD) safeRender('Retention', renderRetention, retD);
            if (deptFcD) { deptForecastList.value = deptFcD.comparison?.map(d => d.dept_name) || []; safeRender('DeptForecast', renderDeptForecast); }
            if (growthD) safeRender('Growth', renderGrowth);
        };

        // ============ 图表渲染 ============

        // --- 部门饼图 ---
        const renderDeptPie = (data) => {
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
            // Req 9: 点击联动
            c.on('click', (p) => {
                searchText.value = p.name;
                onSearch();
            });
        };

        // --- 部门柱线图 ---
        const renderDeptBar = (data) => {
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
        };

        // --- PCA 降维散点 (Req 2) ---
        const renderPCA = (data) => {
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
        };

        // --- 雷达图 ---
        const renderRadar = (data) => {
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
        };

        // --- 轮廓系数 (Req 2) ---
        const renderSilhouette = (data) => {
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
        };

        // --- 聚类对比 ---
        const renderClusterCmp = (data) => {
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
        };

        // --- DBSCAN ---
        const renderDBSCAN = (data) => {
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
        };

        // --- 时间轴动态演变 (Req 8) ---
        const renderTimeline = (data) => {
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
        };

        // --- 多模型预测 (Req 4) ---
        const renderForecast = () => {
            const c = initChart('c_forecast');
            const data = cache.forecast;
            if (!c || !data) return;

            const { years, actuals, models, comparison } = data;
            const trainEnd = 1996;
            const filt = forecastModel.value;

            const series = [];
            if (filt === 'all') {
                // 历史线
                series.push({
                    name: '历史实际', type: 'line',
                    data: actuals.map((v, i) => years[i] <= trainEnd ? v : null),
                    lineStyle: { width: 4, color: '#00f2fe' }, symbol: 'circle', symbolSize: 7, z: 10
                });
                // 验证线
                series.push({
                    name: '验证实际 (1997-2002)', type: 'line',
                    data: actuals.map((v, i) => years[i] >= trainEnd ? v : null),
                    lineStyle: { width: 3, color: '#ff4757', type: 'dashed' }, symbol: 'diamond', symbolSize: 9, z: 9
                });
                // 各模型预测线
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

            // 模型指标对比表格
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
        };

        // --- 相关性热力图 (Req 6) ---
        const renderCorrelation = () => {
            const c = initChart('c_corr_heat');
            const data = cache.corr;
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
        };

        // --- 相似性热力图 (Req 2) ---
        const renderSimilarity = () => {
            const c = initChart('c_similarity');
            const data = cache.sim;
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
        };

        // --- 回归散点 ---
        const renderRegression = (reg) => {
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
        };

        // --- 桑基图 ---
        const renderSankey = (data) => {
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
        };

        // --- 箱线图 ---
        const renderBoxPlot = (data) => {
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
        };

        // --- 性别比例 ---
        const renderGenderRatio = (data) => {
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
        };

        // --- 性别薪资 ---
        const renderGenderPay = (data) => {
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
        };

        // --- 转岗耗时 ---
        const renderTransition = (data) => {
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
        };

        // --- 薪资演变 ---
        const renderEvolution = (data) => {
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
        };

        // --- 外部基准联动 (Req 10) ---
        const renderBenchmark = (data) => {
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
        };

        // --- 中国地图 (Req 7) ---
        const renderMap = (data) => {
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
        };

        // --- 留任分析 ---
        const renderRetention = (data) => {
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
        };

        // --- 分部门预测 ---
        const renderDeptForecast = () => {
            const c = initChart('c_dept_fc');
            if (!c || !cache.deptFc?.departments) return;
            const sel = deptForecastSel.value;
            const all = cache.deptFc.departments;
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
        };

        // --- 薪资增长曲线 ---
        const renderGrowth = () => {
            const c = initChart('c_growth');
            if (!c || !cache.growth) return;
            const view = growthView.value;
            const data = cache.growth;

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
        };

        // ============ Watch ============
        watch(corrMethod, () => renderCorrelation());
        watch(simMetric, () => renderSimilarity());
        watch(forecastModel, () => renderForecast());
        watch(growthView, () => renderGrowth());
        watch(deptForecastSel, () => renderDeptForecast());

        // ============ 键盘快捷键 (Req 9) ============
        const onKeydown = (e) => {
            if (e.key === 'f' || e.key === 'F') {
                if (!e.target.closest('input')) toggleFullscreen();
            }
            if (e.key === 'Escape') showModal.value = false;
        };

        // ============ 生命周期 ============
        onMounted(() => {
            updateTime();
            timer = setInterval(updateTime, 1000);
            document.addEventListener('keydown', onKeydown);
            fetchAll();
        });

        onUnmounted(() => {
            clearInterval(timer);
            document.removeEventListener('keydown', onKeydown);
            resizeHandlers.forEach(h => window.removeEventListener('resize', h));
            resizeHandlers.length = 0;
        });

        return {
            kpi, currentTime, showModal, selectedEmp, searchText,
            corrMethod, simMetric, forecastModel, growthView,
            deptForecastSel, deptForecastList,
            fmt, onSearch, toggleFullscreen,
            renderForecast, renderCorrelation, renderSimilarity,
            renderDeptForecast, renderGrowth
        };
    }
}).mount('#app');
