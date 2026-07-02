const $ = id => document.getElementById(id);
const api = async (url, opts={}) => {
  const res = await fetch(url, {headers:{'Content-Type':'application/json'}, ...opts});
  if(!res.ok) throw new Error(await res.text());
  return await res.json();
};

let commChart, claimChart, statusPie, validationBar, riskBar, conflictLine;
let simTimer = null;
let nodeMap = new Map();
let lastState = null;
let runningFast = false;

const statusColor = {normal:'#9E9E9E', watch:'#F9A825', restricted:'#EF6C00', isolated:'#C62828', system:'#111'};
const esc = s => String(s ?? '').replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
const pretty = obj => JSON.stringify(obj, null, 2);

function initCharts(){
  commChart = echarts.init($('commChart'));
  claimChart = echarts.init($('claimChart'));
  statusPie = echarts.init($('statusPie'));
  validationBar = echarts.init($('validationBar'));
  riskBar = echarts.init($('riskBar'));
  conflictLine = echarts.init($('conflictLine'));
  window.addEventListener('resize', () => [commChart,claimChart,statusPie,validationBar,riskBar,conflictLine].forEach(c=>c.resize()));
  commChart.on('click', params => {
    if(params.dataType === 'node') showNodeDetail(params.data.raw || params.data);
  });
  claimChart.on('click', async params => {
    if(params.dataType === 'node' && params.data.type === 'claim'){
      const d = await api('/api/dynamic/claim/' + encodeURIComponent(params.data.claim_id || params.data.id));
      $('claimDetail').textContent = pretty(d);
    }
  });
}

function updateSummary(st){
  $('stNodes').textContent = st.counts?.nodes ?? st.nodes?.length ?? 0;
  $('stProcessed').textContent = st.counts?.processed ?? st.current_index ?? 0;
  $('stClaims').textContent = st.counts?.claims ?? 0;
  $('stConflicts').textContent = st.counts?.conflicts ?? 0;
  const pct = Math.round((st.progress || 0) * 10000) / 100;
  $('stProgress').textContent = pct + '%';
  $('progressBar').style.width = Math.min(100, pct) + '%';
}

function buildLineCoords(activeLinks){
  return (activeLinks || []).map(l => {
    const s = nodeMap.get(l.source), t = nodeMap.get(l.target);
    if(!s || !t) return null;
    return {
      coords: [[s.x, s.y], [t.x, t.y]],
      lineStyle: {color: l.passed ? '#111' : '#C62828', width: l.relation === 'claim_package' ? 3 : 2, opacity: .88},
      effect: {color: l.passed ? '#111' : '#C62828'},
      raw: l
    };
  }).filter(Boolean);
}

function renderCommunication(st){
  nodeMap = new Map((st.nodes || []).map(n => [n.node_id, n]));
  const nodes = (st.nodes || []).map(n => ({
    id: n.node_id,
    name: n.label || n.node_id,
    value: [n.x, n.y, n.bss || 0],
    x: n.x, y: n.y,
    raw: n,
    symbolSize: n.symbolSize || (n.node_type === 'system' ? 28 : 20),
    itemStyle: {color: n.color || statusColor[n.status] || '#999', borderColor:'#111', borderWidth: n.node_type === 'system' ? 2 : 1},
    label: {show: n.node_type === 'system' || (n.bss || 0) > .25, formatter: n.node_id, color:'#111', fontSize:10}
  }));
  const baseLinks = [];
  const activeLines = buildLineCoords(st.active_links || []);
  commChart.setOption({
    backgroundColor:'#FAFAFA',
    tooltip:{
      trigger:'item',
      formatter:p => {
        if(p.dataType === 'node'){
          const n=p.data.raw;
          return `<b>${esc(n.node_id)}</b><br/>role=${esc(n.role)}<br/>status=${esc(n.status)}<br/>BSS=${Number(n.bss||0).toFixed(3)}<br/>root=${esc(n.root_cause)}`;
        }
        return esc(p.name || 'link');
      }
    },
    xAxis:{min:0,max:1000,show:false}, yAxis:{min:0,max:660,show:false},
    series:[
      {name:'agents', type:'graph', coordinateSystem:'cartesian2d', layout:'none', roam:true,
       data:nodes, links:baseLinks, edgeSymbol:['none','arrow'], lineStyle:{color:'#c8c8c8',width:1,opacity:.25},
       emphasis:{focus:'adjacency', itemStyle:{borderWidth:3}}, categories:[]},
      {name:'active-packets', type:'lines', coordinateSystem:'cartesian2d', zlevel:3,
       data:activeLines, polyline:false, symbol:['none','arrow'], symbolSize:8,
       effect:{show:true, period:1.4, trailLength:.25, symbol:'circle', symbolSize:8},
       lineStyle:{curveness:.18}}
    ]
  }, true);
}

function renderClaimGraph(graph){
  claimChart.setOption({
    backgroundColor:'#FAFAFA',
    tooltip:{trigger:'item', formatter:p => {
      if(p.dataType === 'node') return `<b>${esc(p.data.id)}</b><br/>type=${esc(p.data.type)}<br/>${esc(p.data.name)}`;
      return `${esc(p.data.source)} → ${esc(p.data.target)}<br/>${esc(p.data.name)}`;
    }},
    legend:[{data:(graph.categories||[]).map(c=>c.name), top:8, textStyle:{color:'#333'}}],
    series:[{
      type:'graph', layout:'force', roam:true, draggable:true,
      categories:graph.categories || [], data:graph.nodes || [], links:graph.links || [],
      force:{repulsion:170, edgeLength:[65,145], gravity:.08},
      label:{show:true, formatter:p => String(p.data.name || p.data.id).slice(0,22), fontSize:10, color:'#111'},
      edgeLabel:{show:false}, edgeSymbol:['none','arrow'], edgeSymbolSize:7,
      lineStyle:{color:'#999', opacity:.58, width:1.2, curveness:.12},
      emphasis:{focus:'adjacency', lineStyle:{width:3}}
    }]
  }, true);
}

function showNodeDetail(n){
  $('nodeDetail').textContent = pretty({
    node_id:n.node_id, label:n.label, role:n.role, node_type:n.node_type,
    ground_truth:n.ground_truth, status:n.status, root_cause:n.root_cause,
    bss:Number(n.bss||0).toFixed(6),
    metrics:{H:n.H,R:n.R,P:n.P,S:n.S,D:n.D,F:n.F,O:n.O,M:n.M},
    raw_counts:{H:n.H_count,R:n.R_count,P:n.P_count,S:n.S_count,D:n.D_count,F:n.F_count,O:n.O_count,M:n.M_count},
    sample_count:n.sample_count, updated_at:n.updated_at
  });
}

function updateFeeds(st){
  const claims = st.processed_batch?.map(x=>x.claim) || st.recent_claims || [];
  if(claims.length){
    const html = claims.slice(-12).reverse().map(c => `<div class="feed-item"><span class="tag">${esc(c.agent_id)}</span><span class="tag">${esc(c.label)}</span> ${esc(c.subject)} → ${esc(c.object)} ${c.validation_passed ? '<span class="ok">通过</span>' : '<span class="danger">拒绝</span>'}${c.conflict ? ' <span class="danger">冲突</span>' : ''}</div>`).join('');
    $('eventFeed').innerHTML = html + $('eventFeed').innerHTML;
    const first = claims[claims.length-1];
    if(first?.package) $('claimDetail').textContent = pretty({package:first.package, validation:first.validation});
  }
  const conflicts = st.batch_conflicts || st.recent_conflicts || [];
  if(conflicts.length){
    $('conflictList').classList.remove('empty');
    $('conflictList').innerHTML = conflicts.slice(-12).reverse().map(c => `<div class="feed-item"><b class="danger">冲突</b> step=${esc(c.step)} task=${esc(c.task_id)}<br/>${esc(c.subject)}：${esc(c.new_label || c.labels)} vs ${esc(c.opposing_label || '')}</div>`).join('') + $('conflictList').innerHTML;
  }
}

async function refreshClaimGraph(){
  const graph = await api('/api/dynamic/claim-graph?limit=180');
  renderClaimGraph(graph);
}

async function updateAll(st){
  lastState = st;
  updateSummary(st);
  renderCommunication(st);
  updateFeeds(st);
  await refreshClaimGraph();
  if(st.finished || (st.current_index || 0) % 50 === 0) await renderCharts();
}

async function loadDataset(reset=false){
  $('eventFeed').innerHTML=''; $('conflictList').innerHTML='暂无冲突'; $('conflictList').classList.add('empty');
  $('nodeDetail').textContent='默认数据集已加载进 SQLite：nodes 表先创建节点，claims 表将在发包后动态写入。';
  $('claimDetail').textContent='等待发包生成声明包。';
  const st = await api('/api/dynamic/load', {method:'POST', body:JSON.stringify({reset})});
  await updateAll(st);
  await renderCharts();
}

async function startSimulation(){
  await api('/api/dynamic/start', {method:'POST', body:'{}'});
  if(simTimer) clearInterval(simTimer);
  simTimer = setInterval(async () => {
    try{
      const st = await api('/api/dynamic/step', {method:'POST', body:JSON.stringify({batch:3})});
      await updateAll(st);
      if(st.finished){ clearInterval(simTimer); simTimer=null; await renderCharts(); }
    }catch(e){ console.error(e); clearInterval(simTimer); simTimer=null; alert('发包失败：'+e.message); }
  }, 350);
}

async function pauseSimulation(){
  if(simTimer){ clearInterval(simTimer); simTimer=null; }
  const st = await api('/api/dynamic/pause', {method:'POST', body:'{}'});
  await updateAll(st);
}

async function runAll(){
  runningFast = true;
  if(simTimer){ clearInterval(simTimer); simTimer=null; }
  await api('/api/dynamic/start', {method:'POST', body:'{}'});
  let st;
  for(let i=0;i<2000;i++){
    st = await api('/api/dynamic/step', {method:'POST', body:JSON.stringify({batch:30})});
    if(i % 2 === 0 || st.finished) await updateAll(st);
    if(st.finished) break;
  }
  runningFast = false;
  await renderCharts();
}

async function renderCharts(){
  const ch = await api('/api/dynamic/charts');
  statusPie.setOption({title:{text:'节点风险状态',left:'center',textStyle:{fontSize:14}},tooltip:{trigger:'item'},series:[{type:'pie',radius:['35%','65%'],data:ch.status||[],itemStyle:{borderColor:'#fff',borderWidth:2}}]});
  validationBar.setOption({title:{text:'七项校验失败累计',left:'center',textStyle:{fontSize:14}},tooltip:{},xAxis:{type:'category',data:(ch.validation_failures||[]).map(x=>x.name),axisLabel:{rotate:30}},yAxis:{type:'value'},series:[{type:'bar',data:(ch.validation_failures||[]).map(x=>x.value),itemStyle:{color:'#111'}}],grid:{left:40,right:20,bottom:70,top:50}});
  riskBar.setOption({title:{text:'Top BSS 节点',left:'center',textStyle:{fontSize:14}},tooltip:{},xAxis:{type:'category',data:(ch.top_risk||[]).map(x=>x.node_id),axisLabel:{rotate:45}},yAxis:{type:'value',max:1},series:[{type:'bar',data:(ch.top_risk||[]).map(x=>Number(x.bss||0).toFixed(3)),itemStyle:{color:p=>statusColor[(ch.top_risk||[])[p.dataIndex]?.status]||'#555'}}],grid:{left:40,right:20,bottom:90,top:50}});
  conflictLine.setOption({title:{text:'冲突声明出现过程',left:'center',textStyle:{fontSize:14}},tooltip:{trigger:'axis'},xAxis:{type:'value',name:'step'},yAxis:{type:'value',name:'count'},series:[{type:'line',smooth:true,data:(ch.conflicts||[]),symbolSize:5,lineStyle:{color:'#C62828',width:2},itemStyle:{color:'#C62828'},areaStyle:{color:'rgba(198,40,40,.12)'}}],grid:{left:45,right:25,bottom:45,top:55}});
}

$('btnReset').onclick = () => loadDataset(true);
$('btnStart').onclick = startSimulation;
$('btnPause').onclick = pauseSimulation;
$('btnRunAll').onclick = runAll;

// Dataset switching
$('dsSelect').onchange = async () => {
  const mode = $('dsSelect').value;
  const res = await api('/api/dataset/switch', {method:'POST', body:JSON.stringify({mode})});
  console.log('Switched to', res.label);
  await loadDataset(true);
};

// Init dataset list from server
(async () => {
  try {
    const ds = await api('/api/dataset/list');
    $('dsSelect').value = ds.current;
  } catch(e) { /* ignore if endpoint not available */ }
})();

initCharts();
loadDataset(false).catch(e => alert('默认数据集加载失败：'+e.message));
