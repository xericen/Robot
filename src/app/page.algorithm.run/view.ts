import { OnInit, OnDestroy, Input, ViewChild, ElementRef } from '@angular/core';
import { DomSanitizer } from '@angular/platform-browser';
import { Service } from '@wiz/libs/portal/season/service';

export class Component implements OnInit, OnDestroy {
    @Input() embedded = false;
    public activeView = 'simulation';
    public parallelInitialView = '2d';
    public parallelActive = false;
    public parallelBusy = false;
    public parallelRuns:any[] = [];
    public crossingPatrol = true;
    private parallelTimer:any = null;
    private parallelEpoch = 0;
    private async parallelRpc(row:any, action:string, extra:any = {}) {
        const perform=async()=>{
            const response:any=await wiz.call('live_newton',{...row.config,algorithm:row.key,token:row.token||'',
                action,presented_frame:row.presented??-1,compact:'true',metadata_version:row.data?.metadata_version||'',render_3d:this.viewMode==='3d'?'true':'false',since:row.data?.frame_count ? row.data.frame_count-1 : -1,...extra});
            if(response.code!==200) throw new Error(response.data?.message||response.message||'동시 비교 제어 실패');
            return response.data;
        };
        const task=(row.queue||Promise.resolve()).then(perform);
        row.queue=task.catch(()=>{});return task;
    }
    private acceptParallel(row:any,data:any,fresh=false) {
        const frames=fresh?[]:(row.data?.frames||[]);
        if(fresh) {row.pathEnd=-1;row.pathText='';row.presented=-1;}
        row.token=data.token; row.data={...(fresh?{}:row.data),...data,frames:frames.concat(data.frames||[])};
        if(!row.url) row.url=this.sanitizer.bypassSecurityTrustResourceUrl(data.viewer_url);
    }
    public async closeParallel() {
        ++this.parallelEpoch; clearTimeout(this.parallelTimer);
        const rows=this.parallelRuns;
        this.parallelRuns=[];this.parallelActive=false;
        await Promise.allSettled(rows.filter(r=>r.token).map(r=>this.parallelRpc(r,'close')));
    }

    private async paintParallel() {
        await this.service.render();
        await new Promise<void>(resolve=>requestAnimationFrame(()=>requestAnimationFrame(()=>resolve())));
        const index=this.parallelFrameIndex;
        this.parallelRuns.forEach(row=>row.presented=Math.min(index,(row.data?.frame_count||1)-1));
    }
    private async waitParallelViewers() {
        const epoch=this.parallelEpoch,deadline=Date.now()+60000;
        await this.paintParallel();
        while(!this.destroyed&&epoch===this.parallelEpoch) {
            await Promise.all(this.parallelRuns.map(async row=>this.acceptParallel(row,await this.parallelRpc(row,'status'))));
            await this.paintParallel();
            if(this.viewMode!=='3d'||this.parallelRuns.every(row=>row.data?.viewer_ready)) return;
            this.message='3D 장면 준비 중 · '+this.parallelRuns.filter(row=>row.data?.viewer_ready).length+'/3 · 모두 준비될 때 시작합니다.';
            if(Date.now()>deadline) throw new Error('3D 화면 준비가 지연되어 세 로봇을 정지 상태로 유지합니다. 다시 시도하거나 2D 보기를 선택하세요.');
            await new Promise(resolve=>setTimeout(resolve,100));
        }
        throw new Error('화면 준비가 취소되었습니다.');
    }
    private presentedFrame = -1;
    private async paintSingle() {
        await this.service.render();
        await new Promise<void>(resolve=>requestAnimationFrame(()=>requestAnimationFrame(()=>resolve())));
        this.presentedFrame=this.frame;
    }
    private async waitSingleViewer() {
        const deadline=Date.now()+60000;
        await this.paintSingle();
        while(!this.destroyed) {
            this.accept(await this.rpc('status'));await this.paintSingle();
            if(this.viewMode!=='3d'||this.selected?.viewer_ready) return;
            if(Date.now()>deadline)throw new Error('3D 장면이 준비되지 않아 로봇을 정지 상태로 유지합니다.');
            await new Promise(resolve=>setTimeout(resolve,100));
        }
    }
    private pollParallel() {
        clearTimeout(this.parallelTimer);
        if(this.destroyed||!this.parallelActive||this.parallelBusy) return;
        const epoch=this.parallelEpoch;
        this.parallelTimer=setTimeout(async()=>{
            const settled=await Promise.allSettled(this.parallelRuns.map(async row=>{
                try {const data=await this.parallelRpc(row,'status');
                    if(epoch===this.parallelEpoch) this.acceptParallel(row,data);
                } catch(error:any) {row.error=error.message;}
            }));
            if(epoch!==this.parallelEpoch||this.destroyed) return;
            await this.paintParallel();this.pollParallel();
        },100);
    }
    public async startParallel(autoRun=true) {
        if(this.destroyed||this.busy||this.controlBusy||this.parallelBusy) return;
        if(!this.parallelActive) this.viewMode=this.parallelInitialView;
        this.controlBusy=true;this.parallelBusy=true;
        this.message='Naive · VO · ORCA의 동일 조건 Newton 환경 3개를 준비합니다.';
        await this.service.render();
        try {
            await this.closeParallel();
            clearTimeout(this.pollTimer);++this.generation;
            if(this.session) await this.rpc('close');
            this.session='';this.viewerUrl=null;this.selected=null;this.phase='idle';
            const config:any={...this.liveParams()};
            this.parallelRuns=this.algorithms.map(a=>({...a,config:{...config},token:'',data:null,url:null,error:''}));
            this.parallelActive=true;
            await this.service.render();
            const rows=this.parallelRuns;
            const epoch=this.parallelEpoch;
            const created=await Promise.allSettled(rows.map(async row=>{
                this.acceptParallel(row,await this.parallelRpc(row,'create'),true);
            }));
            if(this.destroyed||epoch!==this.parallelEpoch) {
                await Promise.allSettled(rows.filter(r=>r.token).map(r=>this.parallelRpc(r,'close')));
                return;
            }
            const failure:any=created.find(r=>r.status==='rejected');
            if(failure) throw failure.reason;
            const hashes=rows.map(r=>r.data.scene_hash);
            if(hashes.some(h=>!h)||new Set(hashes).size!==1) throw new Error('세 실행의 초기 조건이 일치하지 않습니다.');
            await this.waitParallelViewers();
            if(autoRun) {
                const startAt=(Date.now()/1000)+1;
                const resumed=await Promise.allSettled(rows.map(async row=>
                    this.acceptParallel(row,await this.parallelRpc(row,'resume',{start_at:startAt}))));
                const error:any=resumed.find(r=>r.status==='rejected');
                if(error) throw error.reason;
            }
            this.message=autoRun?'세 알고리즘 동시 실행 중 · 같은 초기 조건에서 로봇 3대의 이동을 비교합니다.'
                :'새 맵에 세 로봇을 준비했습니다. 함께 Resume으로 시작하세요.';
        } catch(error:any) {
            await this.closeParallel();this.message=error.message;
        } finally {
            this.controlBusy=false;this.parallelBusy=false;if(!this.destroyed){this.pollParallel();await this.service.render();}
        }
    }
    public async parallelCommand(action:string) {
        if(this.parallelBusy||!this.parallelRuns.length) return;
        this.parallelBusy=true;clearTimeout(this.parallelTimer);
        await this.service.render();
        const epoch=this.parallelEpoch;
        try {
            if(action==='resume') await this.waitParallelViewers();
            const startAt=Date.now()/1000+1;
            const settled=await Promise.allSettled(this.parallelRuns.map(async row=>{
                const data=await this.parallelRpc(row,action,{start_at:startAt,path:this.showPath,risk:this.showCollisions,render_3d:this.viewMode==='3d'?'true':'false'});
                if(epoch===this.parallelEpoch) {this.acceptParallel(row,data,action==='reset');row.error='';}
            }));
            const failure:any=settled.find(r=>r.status==='rejected');
            if(failure) {
                await Promise.allSettled(this.parallelRuns.map(row=>this.parallelRpc(row,'pause')));
                throw failure.reason;
            }
            this.message=action==='reset'?'세 로봇을 출발 상태로 초기화했습니다. 함께 Resume으로 시작하세요.':'세 알고리즘에 '+action+' 적용';
        } catch(error:any) {this.message=error.message;}
        finally {this.parallelBusy=false;this.pollParallel();await this.service.render();}
    }
    public async endParallel() {
        if(this.controlBusy||this.parallelBusy) return;
        this.parallelBusy=true;await this.service.render();
        try {await this.closeParallel();this.message='동시 비교를 종료했습니다.';}
        finally {this.parallelBusy=false;await this.service.render();}
    }
    public get parallelMeta() {return this.parallelRuns.find(r=>r.data)?.data;}
    public get parallelFrameIndex() {
        const rows=this.parallelRuns.filter(r=>r.data);
        const active=rows.filter(r=>!r.error&&!r.data.phase.startsWith('replay'));
        const histories=(active.length?active:rows).map(r=>r.data.frames.length-1);
        return histories.length?(active.length?Math.min(...histories):Math.max(...histories)):0;
    }
    public parallelCurrent(row:any) {return row.data?.frames?.[Math.min(this.parallelFrameIndex,(row.data?.frames?.length||1)-1)]||row.data?.current;}
    public parallelPath(row:any) {
        const end=Math.min(this.parallelFrameIndex,(row.data?.frames?.length||1)-1);
        if(row.pathEnd===end) return row.pathText||'';
        const frames=row.data?.frames||[],n=end+1,count=Math.min(n,256);
        row.pathText=Array.from({length:count},(_,i)=>frames[count<=1?0:Math.round(i*(n-1)/(count-1))]?.robot.join(',')||'').join(' ');
        row.pathEnd=end;return row.pathText;
    }
    public get parallelShelves() {return this.parallelMeta?.shelf_poses||[];}

    public async selectResearchPanel(panel:string) {this.researchPanel=panel; await this.service.render();}
    public async refreshResearchView() {await this.service.render();}
    public research:any = null;
    public researchError = '';
    public researchPanel = 'algorithm';
    public researchScenario = 'Head-On';
    public researchPopulation = 'workers';
    public researchMap = 'map1';
    public researchCase = 0;
    public researchFrame = 0;
    public researchPanels = [{id:'algorithm',label:'알고리즘 종합'},{id:'scenario',label:'시나리오 분석'},
        {id:'scalability',label:'계산 비용'},{id:'orca',label:'ORCA 위반 분석'},{id:'layout',label:'창고 맵 분석'}];
    public researchScenarios = ['Head-On','Crossing','Narrow Passage','Dense Traffic'];
    public async loadResearch() {
        const requestedBatch=this.selectedBatchId;
        this.researchError = '';
        try {
            const response:any = await wiz.call('live_newton',{action:'research_status',research_id:this.selectedBatchId});
            if(response.code!==200) throw new Error(response.message || '연구 결과 조회 실패');
            if(requestedBatch!==this.selectedBatchId) return;
            this.research = response.data;
            if(this.research.scenario_options) this.researchScenario=this.research.scenario_options[0];
            if(this.research.population_options) this.researchPopulation=this.research.population_options[0];
        } catch(error:any) { this.researchError = error.message; }
        await this.service.render();
    }
    public researchAsset(name:string) { return '/warehouse-experiments/research/'+this.research.id+'/'+name; }
    public researchNumber(value:any, digits=3) {return value===null || value===undefined ? 'N/A' : Number(value).toFixed(digits);}
    public get researchScenarioRows() {return (this.research?.scenarios || []).filter((r:any)=>r.scenario_label===this.researchScenario);}
    public get researchScaleRows() {return (this.research?.scalability || []).filter((r:any)=>r.population===this.researchPopulation);}
    public get researchScenarioFigure() {
        const keys:any={'Head-On':'head_on','Crossing':'crossing','Narrow Passage':'narrow_passing','Dense Traffic':'dense_traffic'};
        return '03_'+keys[this.researchScenario]+'.png';
    }
    public get researchCurrentCase() {return this.research?.orca_cases?.[this.researchCase];}
    public get researchCurrentFrame() {
        const item=this.researchCurrentCase;
        return item?.samples?.[this.researchFrame] || item?.frames?.[this.researchFrame] || null;
    }

    public algorithm = 'orca';
    public agents = 4;
    public seed = 42;
    public safety = .35;
    public speed = 1.2;
    public scenario = 'medium';
    public frames = 5400;
    public mapId = 'map1';
    public planner = 'astar';
    public trafficMode = 'dynamic';
    public controlledStudy:any = null;
    public controlledBatch = '';
    private controlledTimer:any = null;
    public async refreshControlledStudy() {
        clearTimeout(this.controlledTimer);
        try {
            const response:any=await wiz.call('live_newton',{action:'controlled_status',batch_id:this.controlledBatch});
            if(response.code!==200) throw new Error(response.message||'통제 실험 조회 실패');
            this.controlledStudy=response.data;
            if(!this.controlledBatch && response.data.batch_id) this.controlledBatch=response.data.batch_id;
        } catch(error:any) {this.controlledStudy={phase:'error',error:error.message,rows:[],figures:[]};}
        if(!this.destroyed && (this.controlledStudy?.phase==='running' ||
            (this.controlledStudy?.phase==='complete' && !this.controlledStudy?.figures?.length)))
            this.controlledTimer=setTimeout(()=>this.refreshControlledStudy(),5000);
        await this.service.render();
    }
    public figureTitle(name:string) {
        const titles:any={'01':'도달 시간','02':'이동 거리','03':'충돌·안전거리 위반','04':'도달률',
            '05':'평균 회피 계산시간','06':'안전 도달률','07':'무충돌 도달률','08':'최소 이격거리','09':'계산량과 Runtime'};
        return titles[name.slice(0,2)]||name;
    }
    public studyGroup(group:string) {
        return group.replace('workers','작업자 전용').replace('mixed','혼합').replace('narrow_passing','좁은 교행').replace('head_on','정면 접근').replace('crossing','횡단');
    }
    public study:any = null;
    public studyMode = 'static';
    public studyPath:any = null;
    public studyBusy = false;
    public studyError = '';
    public plannerNames:any = {astar:'A*',dijkstra:'Dijkstra',rrt:'RRT'};
    private studyTimer:any = null;
    public maps: any[] = [];
    private generation = 0;
    public busy = false;
    public compareScope = 'all';
    public encounterMode = 'crossing';
    public populationMode = 'workers';
    public showHistory = false;
    public async setEncounter(value:string) {
        this.followBatch=false;this.comparisonBatchId='';
        this.encounterMode=value;
        this.crossingPatrol=value==='crossing';
        if(value==='baseline') {this.populationMode='legacy';const counts:any={easy:2,medium:4,hard:9,crowded:16};this.agents=counts[this.scenario]??this.agents;}
        if(value!=='baseline' && this.populationMode==='legacy') this.populationMode='workers';
        if(!['easy','medium','hard','crowded'].includes(this.scenario)) this.scenario='medium';
        if(value==='narrow_passing') {this.mapId='map1';this.compareScope='selected';}
        this.comparisonRuns=[];
        if(this.parallelActive) await this.startParallel(false);
        else if(this.session) await this.startLive(null,false);
        await this.service.render();
    }
    public async setPopulation(value:string) {
        this.followBatch=false;this.comparisonBatchId='';
        this.populationMode=value;
        if(value==='legacy') {const counts:any={easy:2,medium:4,hard:9,crowded:16};this.agents=counts[this.scenario]??this.agents;}
        if(!['easy','medium','hard','crowded'].includes(this.scenario)) this.scenario='medium';
        if(value!=='legacy' && this.encounterMode==='baseline') this.encounterMode='crossing';
        this.comparisonRuns=[];
        await this.service.render();
    }

    public parameters:any = {orca_neighbor_dist_m:0,orca_max_neighbors:0,orca_horizon_s:3,
        time_step_s:1/30,vo_horizon_s:3,vo_candidates:74,naive_stop_margin_m:0,naive_influence_m:1.2};
    public parameterFields = [
        {key:'orca_neighbor_dist_m',label:'ORCA 이웃 거리(m), 0=전체'},
        {key:'orca_max_neighbors',label:'ORCA 최대 이웃 수, 0=전체'},
        {key:'orca_horizon_s',label:'ORCA 예측 시간(s)'},
        {key:'time_step_s',label:'공통 timeStep(s)'},
        {key:'vo_horizon_s',label:'VO 예측 시간(s)'},
        {key:'vo_candidates',label:'VO 후보 속도 K'},
        {key:'naive_stop_margin_m',label:'Naive 긴급 반응 반경 추가 여유(m)'},
        {key:'naive_influence_m',label:'Naive 반발 영향 거리(m)'}
    ];
    public savedMessage = '';
    private batchEpoch=0;
    public selectedBatchId = '';
    public unifiedBatch:any = null;
    public unifiedAvailable:string[] = [];
    public comparisonBatchId = '';
    public followBatch = true;
    public async selectUnifiedBatch(id='') {
        const epoch=++this.batchEpoch;
        const response:any=await wiz.call('live_newton',{action:'unified_status',batch_id:id});
        if(response.code!==200){this.savedMessage=response.message||'통일 배치 조회 실패';return;}
        if(epoch!==this.batchEpoch) return;
        this.unifiedAvailable=response.data.available||[];
        if(response.data.status!=='complete'){this.unifiedBatch=null;return;}
        this.unifiedBatch=response.data;this.selectedBatchId=response.data.id;this.followBatch=true;
        const c=this.unifiedBatch.config;
        this.scenario=c.scenario;this.agents=c.agent_count;this.encounterMode=c.encounter_mode;
        this.populationMode=c.population_mode;this.crossingPatrol=c.encounter_mode==='crossing';
        this.planner=c.planner;this.trafficMode=c.traffic_mode;this.frames=c.frames;
        this.safety=c.safety;this.speed=c.speed;this.parameters={...c.parameters};this.seed=c.seeds[0];
        this.compareScope='all';
        await this.loadSavedResults();await this.loadResearch();await this.service.render();
    }
    public async loadSavedResults() {
        const requestedBatch=this.followBatch?this.selectedBatchId:'';
        try {
            const response:any = await wiz.call('run_newton',{mode:'saved',history:'true',batch_id:this.followBatch?this.selectedBatchId:''});
            if(response.code !== 200) throw new Error(response.message || 'CSV 조회 실패');
            if(requestedBatch!==(this.followBatch?this.selectedBatchId:'')) return;
            const fromBatch=this.followBatch&&!!this.selectedBatchId;
            this.comparisonBatchId=fromBatch?this.selectedBatchId:'';
            let rows = fromBatch?response.data:response.data.filter((r:any) => r.scenario===this.scenario && r.seed===Number(this.seed)
                && r.planner===this.planner && r.traffic_mode===this.trafficMode
                && (r.encounter_mode || 'baseline')===this.encounterMode
                && (r.population_mode || 'legacy')===this.populationMode
                && (this.populationMode==='legacy' || r.agent_count===Number(this.agents))
                && r.frame_limit===Number(this.frames) && r.safety_distance_m===Number(this.safety)
                && r.max_speed_mps===Number(this.speed)
                && (this.compareScope==='all' ? r.common_traffic===(this.encounterMode==='baseline' && this.populationMode==='legacy' ? 1 : 0) : r.map===this.mapId)
                && this.parameterFields.every(f => Math.abs(r[f.key]-Number(this.parameters[f.key])) < 1e-12));
            if(!fromBatch&&!this.showHistory){
                const keys=new Set<string>();
                rows=rows.sort((a:any,b:any)=>{
                    const dated=(r:any)=>/^[0-9]{8}T/.test(String(r.run_id||''))?1:0;
                    return dated(b)-dated(a)||String(b.run_id||'').localeCompare(String(a.run_id||''));}).filter((r:any)=>{
                    const key=r.map+'|'+r.algorithm;if(keys.has(key))return false;keys.add(key);return true;});
            }
            this.comparisonRuns=rows.map((r:any)=>({...r,mapId:r.map,
                mapName:this.maps.find(m=>m.mapId===r.map)?.mapName||r.map,
                status:r.success===1?'success':'timeout',sim_time_s:r.observed_time_s,
                collisions:r.collision_count,safety_violations:r.safety_violation_count,
                parameters:Object.fromEntries(this.parameterFields.map(f=>[f.key,r[f.key]])),saved:true}));
            if(fromBatch) this.savedMessage='통일 배치 '+this.selectedBatchId+' · 전체5시드 '+rows.length+'건 · 결과·연구분석과 같은 원본';
            else this.savedMessage=(this.showHistory?'보존된 실행 이력 · ':'최신 결과 · ')+'현재 설정과 일치하는 CSV '+rows.length+'건 · 도달 실패는 N/A · 재생 데이터는 현재 세션 실행에만 포함됩니다.';
        } catch(error:any) {this.savedMessage=error.message;}
        await this.service.render();
    }
    public get arrivalChartMax() {
        return Math.max(1,...this.comparisonRows.filter(r=>r.status==='success').map(r=>r.arrival_time_s ?? r.sim_time_s));
    }
    public arrivalBar(run:any) {return run.status==='success' ? 100*(run.arrival_time_s ?? run.sim_time_s)/this.arrivalChartMax : 0;}
    public mapComparisonRows(id:string) {return this.comparisonRows.filter(r=>r.mapId===id);}

    public comparisonRuns:any[] = [];
    public get comparisonRows(){return this.comparisonRuns;}
    public message = '설정을 확인한 뒤 Start를 눌러 실제 Newton CPU 시뮬레이션을 실행하세요.';
    public runs: any[] = [];
    public selected: any = null;
    public frame = 0;
    public timer: any = null;
    public showPath = true;
    public showCollisions = true;
    public algorithms = [
        {key:'naive', name:'Naive', detail:'현재 거리 기반 반응형 회피 · O(n)'},
        {key:'vo', name:'VO', detail:'상대속도와 미래 충돌 후보 평가 · O(Kn)'},
        {key:'orca', name:'ORCA', detail:'반평면 제약과 순차 선형계획 · 최악 O(n²)'}
    ];
    public scenarios = [
        {key:'easy', name:'easy · AMR 1대 / 작업자 2명'},
        {key:'medium', name:'medium · AMR 1대 / 작업자 4명'},
        {key:'hard', name:'hard · AMR 3대 / 작업자 7명'},
        {key:'crowded', name:'crowded · 다중 AMR / 다수 작업자'},
        {key:'basic', name:'이전 실험 · 기본 환경'},
        {key:'warehouse', name:'이전 실험 · 기존 창고'},
        {key:'crossing', name:'이전 실험 · 횡단'},
        {key:'multi_robot', name:'이전 실험 · 다중 로봇'}
    ];
    public get presetPopulation() { return this.populationMode==='legacy' && ['easy','medium','hard'].includes(this.scenario); }
    public async setScenario(value:string) {
        this.scenario = value;
        const counts:any = {easy:2,medium:4,hard:9,crowded:16};
        if (counts[value] !== undefined) this.agents = counts[value];
        await this.service.render();
    }
    public get mapScale() { return Math.min(900/(this.selected?.width || 24),600/(this.selected?.height || 16)); }
    public get mapWidth() { return (this.selected?.width || 24) * this.mapScale; }
    public get mapHeight() { return (this.selected?.height || 16) * this.mapScale; }
    public get mapViewBox() { return '0 0 '+this.mapWidth+' '+this.mapHeight; }
    public shelves = [
        {x:5,y:1.5,w:2.5,h:5},{x:5,y:9.5,w:2.5,h:5},
        {x:10.5,y:1.5,w:2.5,h:5},{x:10.5,y:9.5,w:2.5,h:5},
        {x:16,y:1.5,w:2.5,h:5},{x:16,y:9.5,w:2.5,h:5}
    ];

    @ViewChild('viewerPanel') viewerPanel?: ElementRef;
    public viewMode = '3d';
    public session = '';
    public viewerUrl: any = null;
    public phase = 'idle';
    public controlBusy = false;
    private pollTimer: any = null;
    private destroyed = false;
    private rpcQueue: Promise<any> = Promise.resolve();
    constructor(public service: Service, private sanitizer: DomSanitizer) {}

    private liveParams() { return this.params(); }
    public parallelPlanned(row:any) {return (row.data?.astar_path||[]).map((p:any)=>p.join(',')).join(' ');}
    private params() {
        return {algorithm:this.algorithm, agents:this.agents, seed:this.seed,
            safety:this.safety, speed:this.speed, scenario:this.scenario, frames:this.frames, map_id:this.mapId, planner:this.planner, traffic_mode:this.trafficMode,encounter_mode:this.encounterMode,population_mode:this.populationMode,parameters:JSON.stringify(this.parameters),common_traffic:this.encounterMode==='baseline'&&this.populationMode==='legacy'?'true':'false'};
    }
    private rpc(action:string, extra:any = {}) {
        const request = async () => {
            const response:any = await wiz.call('live_newton', {
                ...this.params(), token:this.session, action,presented_frame:this.presentedFrame,compact:'true',metadata_version:this.selected?.metadata_version||'',render_3d:this.viewMode==='3d'?'true':'false',
                since:(this.selected?.frames?.length || 0)-1, ...extra
            });
            if (response.code !== 200) throw new Error(response.data?.message || response.message || 'Newton 제어 실패');
            return response.data;
        };
        const task = this.rpcQueue.then(request);
        this.rpcQueue = task.catch(() => {});
        return task;
    }
    private accept(data:any, fresh = false) {
        if(fresh) this.presentedFrame=-1;
        const previousPhase = this.phase;
        const history = fresh ? [] : (this.selected?.frames || []);
        this.selected = {...(fresh ? {} : this.selected), ...data, frames:history.concat(data.frames || [])};
        this.session = data.token;
        this.phase = data.phase;
        if (data.mapId) this.mapId = data.mapId;
        if (fresh && data.planner) this.planner = data.planner;
        this.frame = data.frame_index;
        if (previousPhase === 'running' && data.phase === 'replay_paused') {
            this.message = data.status === 'success'
                ? '목표 도달 완료 · 로봇이 목표에서 정지했습니다. 기록을 재생할 수 있습니다.'
                : '실행 시간 한도에 도달했습니다. 목표 미도달이며 완료가 아닙니다. 실행 프레임을 늘려 다시 실행하세요.';
        }
        if (data.phase.startsWith("replay") && data.sim_time_s) {
            this.runs = this.runs.filter((run:any) => !(run.algorithm === data.algorithm && run.mapId === data.mapId && run.scenario === data.scenario && run.seed === data.seed && run.planner === data.planner && run.traffic_mode === data.traffic_mode)).concat([this.selected]);
        }
        const url = data.viewer_url;
        if (url && (!this.viewerUrl || fresh)) this.viewerUrl = this.sanitizer.bypassSecurityTrustResourceUrl(url);
        this.shelves = data.shelf_poses ? data.shelf_poses.map((s:any) => ({x:s.position[0]-s.size[0]/2,y:s.position[1]-s.size[1]/2,w:s.size[0],h:s.size[1],rotation:s.rotation,cx:s.position[0],cy:s.position[1]})) : (data.shelves || []).map((s:any) => ({x:s[0],y:s[1],w:s[2],h:s[3],rotation:0,cx:s[0]+s[2]/2,cy:s[1]+s[3]/2}));
    }
    private schedulePoll() {
        clearTimeout(this.pollTimer);
        if (this.destroyed || !this.session || this.controlBusy) return;
        const epoch = this.generation;
        this.pollTimer = setTimeout(async () => {
            try {
                const data = await this.rpc('status');
                if (epoch !== this.generation) return;
                this.accept(data);
                await this.paintSingle();
                this.schedulePoll();
            } catch (error:any) {
                this.phase = 'error'; this.message = error.message;
                await this.service.render();
            }
        }, 140);
    }
    public async startLive(record:any = null, autoRun = true) {
        if (this.busy || this.controlBusy) return;
        await this.closeParallel();
        this.controlBusy = true;
        this.generation++;
        clearTimeout(this.pollTimer);
        this.message = record ? '저장된 Newton 강체 기록을 3D 뷰어로 여는 중입니다.' : 'Newton CPU와 ViewerViser를 초기화합니다.';
        await this.service.render();
        try {
            if (this.session) {
                if (this.phase === 'running' || this.phase === 'replay') await this.rpc('pause');
                this.viewerUrl = null;
                await this.service.render();
                await this.rpc('close');
            }
            this.session = ''; this.viewerUrl = null;
            this.selected = null; this.frame = 0; this.shelves = []; this.phase = 'idle';
            await this.service.render();
            if (record) {
                this.mapId = record.mapId || 'map1';
                this.planner = record.planner || 'astar'; this.trafficMode = record.traffic_mode || 'dynamic';
                this.algorithm = record.algorithm.toLowerCase();
                this.scenario = record.scenario; this.agents = record.agent_count;
                this.seed = record.seed; this.safety = record.safety_distance_m; this.speed = record.robot_speed_mps;
            }
            this.accept(await this.rpc(record ? 'load' : 'create', record ? {record:JSON.stringify(record)} : this.liveParams()), true);
            this.accept(await this.rpc('display', {path:this.showPath, risk:this.showCollisions}));
            await this.waitSingleViewer();
            if (!record && autoRun) this.accept(await this.rpc('resume'));
            this.message = record ? '저장 기록 재생 모드 · 새로운 물리 계산은 수행하지 않습니다.'
                : this.selected.frame_budget_extended
                    ? '목표 주행에 부족한 실행 한도를 '+(this.selected.frame_limit / 30).toFixed(1)+'초로 자동 보정했습니다. 목표 도달 시 종료합니다.'
                    : '실시간 Newton CPU 실행 · 목표 도달 시 종료합니다. Pause는 물리 계산을 정지합니다.';
            if (!record && !autoRun) this.message = this.selected.mapName+' 적용 완료 · 경로를 재계산했습니다. Start 또는 Resume으로 주행하세요.';
        } catch (error:any) { this.message = error.message; this.phase = 'error'; }
        finally { this.controlBusy = false; this.schedulePoll(); await this.service.render(); }
    }
    public async control(action:string, extra:any = {}) {
        if (!this.session || this.controlBusy) return;
        this.controlBusy = true; clearTimeout(this.pollTimer);
        if (action === 'reset') this.generation++;
        await this.service.render();
        try {
            if(action==='resume') await this.waitSingleViewer();
            if (action === 'resume' && this.phase.startsWith('replay') && this.frame >= this.selected.frames.length-1) {
                this.accept(await this.rpc('seek', {frame:0}));
            }
            this.accept(await this.rpc(action, extra), action === 'reset');
            this.message = action === 'reset' ? 'Newton 강체를 출발 상태로 재생성했습니다. Resume으로 실행하세요.' : '모드: '+this.modeLabel;
        } catch (error:any) { this.message = error.message; }
        finally { this.controlBusy = false; this.schedulePoll(); await this.service.render(); }
    }
    public async seek() { await this.control('seek', {frame:this.frame}); }
    public async switchViewer(mode:string) {
        if(this.parallelBusy||this.controlBusy||mode===this.viewMode) return;
        const wasRunning=this.parallelActive?this.parallelRuns.some(r=>r.data?.phase==='running'):this.phase==='running';
        try {
            if(this.parallelActive) {
                this.controlBusy=true;
                await this.parallelCommand('pause');
                this.viewMode=mode;
                await this.parallelCommand('display');
                await this.waitParallelViewers();
                if(wasRunning) await this.parallelCommand('resume');
            } else {
                if(this.session&&wasRunning) await this.control('pause');
                this.viewMode=mode;
                if(this.session) {
                    await this.control('display',{path:this.showPath,risk:this.showCollisions,render_3d:mode==='3d'?'true':'false'});
                    await this.waitSingleViewer();
                    if(wasRunning) await this.control('resume');
                }
            }
        } catch(error:any) {this.message=error.message;}
        finally {this.controlBusy=false;await this.service.render();}
    }
    public async fullscreen() {
        try {
            if (document.fullscreenElement) await document.exitFullscreen();
            else await this.viewerPanel?.nativeElement.requestFullscreen();
        } catch (error:any) { this.message = '전체화면을 열 수 없습니다: '+error.message; await this.service.render(); }
    }
    public get modeLabel() {
        return ({idle:'실행 대기',running:'실시간 물리 실행',paused:'실시간 물리 정지',
            replay:'저장 기록 재생',replay_paused:'저장 기록 정지',error:'연결 오류'} as any)[this.phase] || this.phase;
    }

    public async ngOnInit() {
        await this.service.init();
        try {
            const response:any = await wiz.call('live_newton', {action:'maps'});
            if (response.code !== 200) throw new Error('맵 설정을 불러오지 못했습니다.');
            this.maps = response.data;
        } catch (error:any) { this.message = error.message; }
        await this.selectUnifiedBatch();
        if(!this.selectedBatchId) await this.loadSavedResults();
        await this.refreshControlledStudy();
        await this.refreshStudy();
        await this.service.render();
    }
    public async changeMap(value:string) {
        if(this.encounterMode==='narrow_passing' && value!=='map1') {this.message='좁은 교행 통제 실험은 Map1 전용입니다. 다른 만남 조건을 선택하면 모든 맵을 사용할 수 있습니다.';await this.service.render();return;}
        if (this.busy || this.controlBusy) return;
        this.mapId = value;
        if (!['easy','medium','hard','crowded'].includes(this.scenario)) {
            this.scenario = 'medium'; this.agents = 4;
        }
        if(this.parallelActive) await this.startParallel(false);
        else await this.startLive(null, false);
    }
    public async refreshStudy() {
        clearTimeout(this.studyTimer);
        try {
            const response:any = await wiz.call('live_newton',{action:'study_status'});
            if (response.code !== 200) throw new Error(response.message || '실험 결과 조회 실패');
            this.study = response.data;
            this.studyBusy = ['starting','running'].includes(this.study.phase);
            if (this.study.phase === 'error') this.studyError = this.study.error || '실험 실패';
        } catch(error:any) {this.studyError=error.message;this.studyBusy=false;}
        if (this.studyBusy && !this.destroyed) this.studyTimer=setTimeout(()=>this.refreshStudy(),1500);
        await this.service.render();
    }
    public async runStudy() {
        if(this.studyBusy) return;
        this.studyBusy=true;this.studyError='';
        try {
            const response:any=await wiz.call('live_newton',{action:'study_start'});
            if(response.code!==200) throw new Error(response.message || '실험 시작 실패');
            this.study=response.data;await this.refreshStudy();
        } catch(error:any){this.studyError=error.message;this.studyBusy=false;await this.service.render();}
    }
    public get studyRows(){return (this.study?.summary || []).filter((r:any)=>r.traffic_mode===this.studyMode);}
    public chartBars(metric:string){
        const rows=this.studyRows;
        const maximum=metric==='success_rate'?100:Math.max(1,...rows.map((r:any)=>r[metric]||0));
        return rows.map((r:any,i:number)=>({...r,x:35+Math.floor(i/3)*100+(i%3)*24,
            y:170-140*(r[metric]||0)/maximum,height:140*(r[metric]||0)/maximum,
            color:({astar:'#0f766e',dijkstra:'#2563eb',rrt:'#d97706'} as any)[r.planner],
            label:r[metric]===null?'N/A':Number(r[metric]).toFixed(2)}));
    }
    public chooseStudyPath(row:any){
        this.studyPath=(this.study?.rows||[]).find((r:any)=>r.traffic_mode===row.traffic_mode&&r.mapId===row.mapId&&r.planner===row.planner&&r.path);
    }
    public points(path:any){return (path||[]).map((p:any)=>p.join(',')).join(' ');}
    public metric(value:any){return value===null||value===undefined?'N/A':Number(value).toFixed(2);}
    public get mapDescription() { return this.maps.find((map:any) => map.mapId === this.mapId)?.description || ''; }
    public ngOnDestroy() { void this.closeParallel(); clearTimeout(this.controlledTimer); clearTimeout(this.studyTimer); this.destroyed = true; this.stop(); clearTimeout(this.pollTimer); if (this.session) void this.rpc("close").catch(() => {}); }
    public stop() { if (this.timer) clearInterval(this.timer); this.timer = null; }
    public async setView(view: string) { this.stop(); this.activeView = view; if(view==='research') await this.loadResearch(); if(view==='comparison' && !this.busy && !this.comparisonRuns.length) await this.loadSavedResults(); await this.service.render(); }
    public async setAlgorithm(value: string) { if (this.busy || this.controlBusy || value === this.algorithm) return; this.algorithm = value; if (this.session) await this.startLive(); await this.service.render(); }
    public async execute(mode: 'single'|'compare') {
        if (this.busy || this.controlBusy) return;
        if (mode === 'single') { await this.startLive(); return; }
        this.followBatch=false;this.comparisonBatchId='';
        if (this.session && (this.phase === 'running' || this.phase === 'replay')) await this.control('pause');
        const allMaps = this.compareScope === 'all';
        if (allMaps && !['easy','medium','hard','crowded'].includes(this.scenario)) {
            this.scenario='medium';this.agents=4;
        }
        const targets = allMaps ? this.maps.filter(m=>this.encounterMode!=='narrow_passing' || m.mapId==='map1') : [{mapId:this.mapId,mapName:this.maps.find((m:any)=>m.mapId===this.mapId)?.mapName||this.mapId}];
        if (!targets.length) {this.message='맵 목록을 불러온 뒤 다시 실행하세요.';await this.service.render();return;}
        this.stop(); this.busy = true; this.comparisonRuns=[];
        const params={algorithm:this.algorithm,agents:this.agents,seed:this.seed,safety:this.safety,
            speed:this.speed,scenario:this.scenario,frames:this.frames,planner:this.planner,
            traffic_mode:this.trafficMode,encounter_mode:this.encounterMode,population_mode:this.populationMode,parameters:JSON.stringify(this.parameters),common_traffic:this.encounterMode==='baseline' && this.populationMode==='legacy'?'true':'false'};
        let currentMap='';
        try {
            for(let i=0;i<targets.length;i++){
                const map=targets[i];currentMap=map.mapName;
                this.message='6개 맵 기준 비교 · '+(i+1)+'/'+targets.length+' '+currentMap+
                    ' · Naive/VO/ORCA 실행 중 ('+this.comparisonRuns.length+'/'+(targets.length*3)+'건 완료)';
                if(!allMaps) this.message=currentMap+' · Naive/VO/ORCA 실행 중';
                await this.service.render();
                const response:any=await wiz.call('run_newton',{...params,mode:'compare',map_id:map.mapId});
                if(response.code!==200) throw new Error(response.data?.message||response.message||'Newton 비교 실패');
                this.comparisonRuns=this.comparisonRuns.concat(response.data);
                this.runs=this.runs.concat(response.data);
                await this.service.render();
            }
            this.message=(allMaps?'6개 맵 × 3알고리즘':'선택 맵 × 3알고리즘')+' 비교 완료 · '+
                this.comparisonRuns.length+'건. success/timeout은 각 결과에 표시합니다. 알고리즘을 누르면 해당 맵의 3D·2D 기록을 재생합니다.';
        } catch(error:any) {
            this.message=currentMap+' 비교 중 오류 · '+this.comparisonRuns.length+'/'+(targets.length*3)+
                '건 반환됨. 이전 결과는 유지했습니다. '+error.message;
        } finally {this.busy=false;await this.service.render();}
    }
    public async selectRun(run:any) { if(run.saved) return; await this.startLive(run); }
    public async play() { await this.control(this.phase === 'running' || this.phase === 'replay' ? 'pause' : 'resume'); }
    public async reset() { await this.control('reset'); }
    public async togglePath() { this.showPath = !this.showPath; await this.control('display', {path:this.showPath, risk:this.showCollisions}); await this.service.render(); }
    public async toggleCollisions() { this.showCollisions = !this.showCollisions; await this.control('display', {path:this.showPath, risk:this.showCollisions}); await this.service.render(); }
    public get current() { return this.selected?.frames?.[this.frame] || this.selected?.current || null; }
    public get trajectory() { return this.selected?.frames?.slice(0, this.frame + 1).map((item:any) => (item.robot[0]*this.mapScale)+','+(this.mapHeight-item.robot[1]*this.mapScale)).join(' ') || ''; }
    public get plannedPath() { return this.selected?.astar_path?.map((point:any) => (point[0]*this.mapScale)+','+(this.mapHeight-point[1]*this.mapScale)).join(' ') || ''; }
    public methodColor(name:string) { return ({Naive:'#d97706',VO:'#2563eb',ORCA:'#0f766e'} as any)[name] || '#0f766e'; }
    public async render() { await this.service.render(); }
}
