const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const source=fs.readFileSync(path.resolve(__dirname,'../../src/app/page.algorithm.run/view.ts'),'utf8');
function body(signature){
 let at=source.indexOf(signature);assert(at>=0,signature);let begin=source.indexOf('{',at),end=begin+1,depth=1;
 for(;depth;end++){if(source[end]==='{')depth++;if(source[end]==='}')depth--;}
 return source.slice(begin+1,end-1).replace(/:any/g,'').split('new Set<string>()').join('new Set()');
}
const params=new Function(body('private params()')),live=new Function(body('private liveParams()'));
const AsyncFunction=Object.getPrototypeOf(async function(){}).constructor;
const compare=new AsyncFunction('mode','wiz',body("public async execute(mode:"));
(async()=>{
 for(const scope of ['all','selected']) for(const [encounter,population,common] of [['crossing','workers','false'],['baseline','legacy','true']]){
  const view={busy:false,controlBusy:false,session:'',compareScope:scope,scenario:'medium',agents:4,seed:42,
   safety:.35,speed:1.2,frames:5400,mapId:'map1',algorithm:'orca',planner:'astar',trafficMode:'dynamic',
   encounterMode:encounter,populationMode:population,parameters:{time_step_s:1/30},
   maps:Array.from({length:6},(_,i)=>({mapId:'map'+(i+1),mapName:'Map '+(i+1)})),comparisonRuns:[],runs:[],
   stop(){},service:{async render(){}}};
  view.params=params;view.liveParams=live;
  const canonical=view.liveParams();assert.equal(canonical.encounter_mode,encounter);assert.equal(canonical.population_mode,population);
  assert.equal(canonical.common_traffic,common);
  let requests=[];
  await compare.call(view,'compare',{async call(action,input){requests.push(input);return {code:200,data:[]};}});
  assert.equal(requests.length,scope==='all'?6:1);
  for(const r of requests)for(const key of ['encounter_mode','population_mode','planner','traffic_mode','seed','agents','safety','speed','frames','parameters','common_traffic'])
    assert.deepEqual(r[key],canonical[key],key);
 }
 const saved=new AsyncFunction('wiz',body('public async loadSavedResults()'));
 const view={followBatch:false,selectedBatchId:'',showHistory:false,scenario:'medium',seed:42,planner:'astar',
    trafficMode:'dynamic',encounterMode:'crossing',populationMode:'workers',agents:4,frames:5400,
    safety:.35,speed:1.2,compareScope:'all',parameterFields:[],parameters:{},maps:[{mapId:'map1',mapName:'Map1'}],service:{async render(){}}};
 const record={map:'map1',algorithm:'VO',scenario:'medium',seed:42,planner:'astar',traffic_mode:'dynamic',
    encounter_mode:'crossing',population_mode:'workers',agent_count:4,frame_limit:5400,safety_distance_m:.35,max_speed_mps:1.2,
    common_traffic:0,success:1};
 const latest={...record,run_id:'20261117T120000_abcdef012345'};
 await saved.call(view,{async call(action,args){assert.equal(args.history,'true');return {code:200,data:[{...record,run_id:'legacy_zzz'},latest]};}});
 assert.equal(view.comparisonRuns.length,1);assert.equal(view.comparisonRuns[0].run_id,latest.run_id);
 view.followBatch=true;view.selectedBatchId='batch';
 await saved.call(view,{async call(action,args){assert.equal(args.batch_id,'batch');return {code:200,data:[latest,{...latest,seed:43,run_id:'other'}]};}});
 assert.equal(view.comparisonRuns.length,2);assert.equal(view.comparisonBatchId,'batch');
 console.log('PASS: 4 live/compare condition combinations, newest archive priority and whole-batch multi-seed selection.');
})().catch(error=>{console.error(error);process.exitCode=1;});
