import { OnInit, OnDestroy, Input, ViewChild, ElementRef } from '@angular/core';
import { DomSanitizer } from '@angular/platform-browser';
import { Service } from '@wiz/libs/portal/season/service';

export class Component implements OnInit, OnDestroy {
    @Input() embedded = false;
    public activeView = 'simulation';
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
    public async loadSavedResults() {
        try {
            const response:any = await wiz.call('run_newton',{mode:'saved'});
            if(response.code !== 200) throw new Error(response.message || 'CSV 조회 실패');
            const rows = response.data.filter((r:any) => r.scenario===this.scenario && r.seed===Number(this.seed)
                && r.planner===this.planner && r.traffic_mode===this.trafficMode
                && r.frame_limit===Number(this.frames) && r.safety_distance_m===Number(this.safety)
                && r.max_speed_mps===Number(this.speed)
                && (this.compareScope==='all' ? r.common_traffic===1 : r.map===this.mapId)
                && this.parameterFields.every(f => Math.abs(r[f.key]-Number(this.parameters[f.key])) < 1e-12));
            this.comparisonRuns=rows.map((r:any)=>({...r,mapId:r.map,
                mapName:this.maps.find(m=>m.mapId===r.map)?.mapName||r.map,
                status:r.success===1?'success':'timeout',sim_time_s:r.observed_time_s,
                collisions:r.collision_count,safety_violations:r.safety_violation_count,
                parameters:Object.fromEntries(this.parameterFields.map(f=>[f.key,r[f.key]])),saved:true}));
            this.savedMessage='현재 설정과 일치하는 CSV '+rows.length+'건 · 도달 실패는 N/A · 재생 데이터는 현재 세션 실행에만 포함됩니다.';
        } catch(error:any) {this.savedMessage=error.message;}
        await this.service.render();
    }
    public get arrivalChartMax() {
        return Math.max(1,...this.comparisonRows.filter(r=>r.status==='success').map(r=>r.arrival_time_s ?? r.sim_time_s));
    }
    public arrivalBar(run:any) {return run.status==='success' ? 100*(run.arrival_time_s ?? run.sim_time_s)/this.arrivalChartMax : 0;}
    public mapComparisonRows(id:string) {return this.comparisonRows.filter(r=>r.mapId===id);}

    public comparisonRuns:any[] = [];
    public get comparisonRows(){return this.comparisonRuns.length ? this.comparisonRuns : this.runs;}
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
    public get presetPopulation() { return ['easy','medium','hard'].includes(this.scenario); }
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

    private params() {
        return {algorithm:this.algorithm, agents:this.agents, seed:this.seed,
            safety:this.safety, speed:this.speed, scenario:this.scenario, frames:this.frames, map_id:this.mapId, planner:this.planner, traffic_mode:this.trafficMode,parameters:JSON.stringify(this.parameters)};
    }
    private rpc(action:string, extra:any = {}) {
        const request = async () => {
            const response:any = await wiz.call('live_newton', {
                ...this.params(), token:this.session, action,
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
                await this.service.render();
                this.schedulePoll();
            } catch (error:any) {
                this.phase = 'error'; this.message = error.message;
                await this.service.render();
            }
        }, 140);
    }
    public async startLive(record:any = null, autoRun = true) {
        if (this.busy || this.controlBusy) return;
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
            this.accept(await this.rpc(record ? 'load' : 'create', record ? {record:JSON.stringify(record)} : {}), true);
            this.accept(await this.rpc('display', {path:this.showPath, risk:this.showCollisions}));
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
            if (action === 'resume' && this.phase.startsWith('replay') && this.frame >= this.selected.frames.length-1) {
                this.accept(await this.rpc('seek', {frame:0}));
            }
            this.accept(await this.rpc(action, extra), action === 'reset');
            this.message = action === 'reset' ? 'Newton 강체를 출발 상태로 재생성했습니다. Resume으로 실행하세요.' : '모드: '+this.modeLabel;
        } catch (error:any) { this.message = error.message; }
        finally { this.controlBusy = false; this.schedulePoll(); await this.service.render(); }
    }
    public async seek() { await this.control('seek', {frame:this.frame}); }
    public async switchViewer(mode:string) { this.viewMode = mode; await this.service.render(); }
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
        await this.loadSavedResults();
        await this.refreshStudy();
        await this.service.render();
    }
    public async changeMap(value:string) {
        if (this.busy || this.controlBusy) return;
        this.mapId = value;
        if (!['easy','medium','hard','crowded'].includes(this.scenario)) {
            this.scenario = 'medium'; this.agents = 4;
        }
        await this.startLive(null, false);
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
    public ngOnDestroy() { clearTimeout(this.studyTimer); this.destroyed = true; this.stop(); clearTimeout(this.pollTimer); if (this.session) void this.rpc("close").catch(() => {}); }
    public stop() { if (this.timer) clearInterval(this.timer); this.timer = null; }
    public async setView(view: string) { this.stop(); this.activeView = view; if(view==='comparison' && !this.busy && !this.comparisonRuns.length) await this.loadSavedResults(); await this.service.render(); }
    public async setAlgorithm(value: string) { if (this.busy || this.controlBusy || value === this.algorithm) return; this.algorithm = value; if (this.session) await this.startLive(); await this.service.render(); }
    public async execute(mode: 'single'|'compare') {
        if (this.busy || this.controlBusy) return;
        if (mode === 'single') { await this.startLive(); return; }
        if (this.session && (this.phase === 'running' || this.phase === 'replay')) await this.control('pause');
        const allMaps = this.compareScope === 'all';
        if (allMaps && !['easy','medium','hard','crowded'].includes(this.scenario)) {
            this.scenario='medium';this.agents=4;
        }
        const targets = allMaps ? this.maps : [{mapId:this.mapId,mapName:this.maps.find((m:any)=>m.mapId===this.mapId)?.mapName||this.mapId}];
        if (!targets.length) {this.message='맵 목록을 불러온 뒤 다시 실행하세요.';await this.service.render();return;}
        this.stop(); this.busy = true; this.comparisonRuns=[];
        const params={algorithm:this.algorithm,agents:this.agents,seed:this.seed,safety:this.safety,
            speed:this.speed,scenario:this.scenario,frames:this.frames,planner:this.planner,
            traffic_mode:this.trafficMode,parameters:JSON.stringify(this.parameters),common_traffic:allMaps?'true':'false'};
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
