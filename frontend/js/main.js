/**
 * Enterprise HR Insights 360 — 全局指挥舱入口
 * 组件化重构：Vue 状态管理 + API 层 + 图表渲染模块
 */
import { fmt, $, resizeHandlers, initChart, COLORS } from './utils.js';
import {
    fetchKPI, fetchDeptDistribution, fetchOfficeMap,
    fetchSalaryHistory, fetchSalaryDistribution, fetchSalaryEvolution,
    fetchSalaryGrowth, fetchExternalBenchmark,
    fetchClustering, fetchForecast, fetchCorrelation, fetchSimilarity,
    fetchTitleSankey, fetchGenderAnalysis, fetchTitleTransition,
    fetchRetention, fetchDeptForecast, fetchGeoJSON
} from './api.js';

import { renderPCA, renderRadar, renderSilhouette, renderClusterCmp, renderCluster3D } from './charts/clusterCharts.js';
import {
    renderForecast as _renderForecast,
    renderDeptForecast as _renderDeptForecast,
    renderGrowth as _renderGrowth,
    renderTimeline, renderBoxPlot, renderEvolution, renderBenchmark
} from './charts/salaryCharts.js';
import {
    renderCorrelation as _renderCorrelation,
    renderSimilarity as _renderSimilarity,
    renderDeptPie, renderDeptBar, renderRegression, renderSankey,
    renderGenderRatio, renderGenderPay, renderTransition, renderMap, renderRetention
} from './charts/hrCharts.js';

const { createApp, ref, onMounted, onUnmounted, watch } = Vue;

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

        let cache = {};
        let chinaGeoJSON = null;
        let timer = null;

        const updateTime = () => { currentTime.value = new Date().toLocaleString('zh-CN', { hour12: false }); };

        // ---- 搜索过滤 ----
        const onSearch = () => {
            const q = searchText.value.toLowerCase().trim();
            const c = echarts.getInstanceByDom($('c_pca'));
            const pca = cache.cluster?.pca;
            if (!c || !pca) return;

            c.dispatchAction({ type: 'downplay' });

            if (!q || q.length < 2) return;

            const matchedClusters = new Set();
            const { cluster_name, dept } = pca;
            const titles = cache.cluster?.scatter?.map(d => d.title) || [];

            for (let i = 0; i < cluster_name.length; i++) {
                if (cluster_name[i]?.toLowerCase().includes(q) ||
                    dept[i]?.toLowerCase().includes(q) ||
                    (titles[i] && titles[i].toLowerCase().includes(q))) {
                    matchedClusters.add(cluster_name[i]);
                }
            }

            const option = c.getOption();
            if (option?.series) {
                option.series.forEach((s) => {
                    if (matchedClusters.has(s.name)) {
                        c.dispatchAction({ type: 'highlight', seriesName: s.name });
                    }
                });
            }
        };

        // ---- 全屏 ----
        const toggleFullscreen = () => {
            if (document.fullscreenElement) {
                document.exitFullscreen();
            } else {
                document.documentElement.requestFullscreen();
            }
        };

        // ---- 数据加载 ----
        const fetchAll = async () => {
            chinaGeoJSON = await fetchGeoJSON();

            const [kpiD, deptD, clusterD, historyD, forecastD, corrD, simD, sankeyD,
                distD, genderD, transD, evolD, benchD, mapD, retD, deptFcD, growthD] =
                await Promise.all([
                    fetchKPI(), fetchDeptDistribution(), fetchClustering(),
                    fetchSalaryHistory(), fetchForecast(), fetchCorrelation(),
                    fetchSimilarity(), fetchTitleSankey(), fetchSalaryDistribution(),
                    fetchGenderAnalysis(), fetchTitleTransition(), fetchSalaryEvolution(),
                    fetchExternalBenchmark(), fetchOfficeMap(), fetchRetention(),
                    fetchDeptForecast(), fetchSalaryGrowth()
                ]);

            cache = { dept: deptD, cluster: clusterD, history: historyD, forecast: forecastD,
                      corr: corrD, sim: simD, sankey: sankeyD, dist: distD, gender: genderD,
                      trans: transD, evol: evolD, bench: benchD, map: mapD, ret: retD,
                      deptFc: deptFcD, growth: growthD };

            const safeRender = (name, fn, ...args) => {
                try { fn(...args); } catch (e) { console.error(`[${name}] 渲染失败:`, e); }
            };

            if (kpiD) kpi.value = kpiD;
            if (deptD) { safeRender('deptPie', renderDeptPie, deptD, { searchText, onSearch }); safeRender('deptBar', renderDeptBar, deptD); }
            if (clusterD) { safeRender('PCA', renderPCA, clusterD, { selectedEmp, showModal }); safeRender('Radar', renderRadar, clusterD); safeRender('Silhouette', renderSilhouette, clusterD);
                             safeRender('ClusterCmp', renderClusterCmp, clusterD); safeRender('Cluster3D', renderCluster3D, 'c_cluster_3d', clusterD); }
            if (historyD) safeRender('Timeline', renderTimeline, historyD);
            if (forecastD) safeRender('Forecast', _renderForecast, forecastD, forecastModel);
            if (corrD) safeRender('Correlation', _renderCorrelation, corrD, corrMethod);
            if (simD) safeRender('Similarity', _renderSimilarity, simD, simMetric);
            if (corrD?.regression) safeRender('Regression', renderRegression, corrD.regression);
            if (sankeyD) safeRender('Sankey', renderSankey, sankeyD);
            if (distD) safeRender('BoxPlot', renderBoxPlot, distD);
            if (genderD) { safeRender('GenderRatio', renderGenderRatio, genderD); safeRender('GenderPay', renderGenderPay, genderD); }
            if (transD) safeRender('Transition', renderTransition, transD);
            if (evolD) safeRender('Evolution', renderEvolution, evolD);
            if (benchD) safeRender('Benchmark', renderBenchmark, benchD);
            if (mapD && chinaGeoJSON) safeRender('Map', renderMap, mapD, chinaGeoJSON);
            if (retD) safeRender('Retention', renderRetention, retD);
            if (deptFcD) { deptForecastList.value = deptFcD.comparison?.map(d => d.dept_name) || []; safeRender('DeptForecast', _renderDeptForecast, deptFcD, deptForecastSel); }
            if (growthD) safeRender('Growth', _renderGrowth, growthD, growthView);
        };

        // ---- 模板事件适配器：将带参的渲染函数包装为无参版本 ----
        const renderForecast = () => { if (cache.forecast) _renderForecast(cache.forecast, forecastModel); };
        const renderCorrelation = () => { if (cache.corr) _renderCorrelation(cache.corr, corrMethod); };
        const renderSimilarity = () => { if (cache.sim) _renderSimilarity(cache.sim, simMetric); };
        const renderDeptForecast = () => { if (cache.deptFc) _renderDeptForecast(cache.deptFc, deptForecastSel); };
        const renderGrowth = () => { if (cache.growth) _renderGrowth(cache.growth, growthView); };

        // ---- Watch ----
        watch(corrMethod, renderCorrelation);
        watch(simMetric, renderSimilarity);
        watch(forecastModel, renderForecast);
        watch(growthView, renderGrowth);
        watch(deptForecastSel, renderDeptForecast);

        // ---- 键盘快捷键 (Req 9) ----
        const onKeydown = (e) => {
            if (e.key === 'f' || e.key === 'F') {
                if (!e.target.closest('input')) toggleFullscreen();
            }
            if (e.key === 'Escape') showModal.value = false;
        };

        // ---- 生命周期 ----
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
