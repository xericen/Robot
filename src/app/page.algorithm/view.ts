import { HostListener, OnInit, OnDestroy, ViewChild } from '@angular/core';
import { Router, NavigationEnd } from '@angular/router';
import { Service } from '@wiz/libs/portal/season/service';

export class Component implements OnInit, OnDestroy {
    public sectionView = new URLSearchParams(location.search).get('section') === 'implementation' ? 'implementation' : 'description';
    @ViewChild('simulation') simulation: any;
    public async setSection(section: string, focus = false, event?: Event) {
        event?.preventDefault();
        if (section !== 'description' && section !== 'implementation') return;
        this.sectionView = section;
        if (section === 'description') this.simulation?.stop();
        await this.service.render();
        if (focus) document.getElementById('algorithm-tab-' + section)?.focus();
    }
    @HostListener('window:ku-algorithm-section', ['$event'])
    public onSectionChange(event: CustomEvent<string>) {
        void this.setSection(event.detail);
    }
    public newNote = '';
    public savedMessage = '';
    public storageKey = 'ku-algorithm-newton-project';
    public steps = [
        { title: 'Newton CPU 강체 시뮬레이션', detail: 'Newton 1.7.0 + Viser 2D/3D · 전역 탐색 A*/Dijkstra/RRT', done: false },
        { title: 'Naive · VO · ORCA 기반 방식 구현', detail: '동일한 초기 조건과 보행자 경로로 비교', done: false },
        { title: '예비 실험 및 평가 기준 조정', detail: '군중 수·이동 패턴·안전거리·세부 지표 확정', done: false },
        { title: '군중 규모별 반복 실험', detail: '사람 수를 점차 늘리며 주행 성능과 Runtime 측정', done: false },
        { title: '결과 시각화 및 복잡도 분석', detail: '실측 실행 시간과 이론적 시간 복잡도 비교', done: false }
    ];
    public methods = [
        { name: 'Naive', label: '기준 방식', detail: '현재 거리만으로 감속과 반발력을 계산합니다. 미래 위치는 예측하지 않습니다.' },
        { name: 'VO', label: 'Velocity Obstacle', detail: '상대 위치·속도로 기본 3초 내 충돌을 예측하고 74개 후보 속도를 평가합니다.' },
        { name: 'ORCA', label: 'Optimal Reciprocal Collision Avoidance', detail: '반평면 제약과 순차 2D 선형계획을 사용합니다. 현재 순찰 작업자는 비협조적이므로 R0이 회피 책임 전부를 부담합니다.' }
    ];
    public metrics = [
        { name: '목적지 도달 시간', unit: '초 (s)', detail: '출발부터 도착까지의 시뮬레이션 시간' },
        { name: '전체 이동 거리', unit: '미터 (m)', detail: '로봇이 이동한 경로의 누적 길이' },
        { name: '충돌 / 안전거리 위반', unit: '횟수', detail: '충돌과 안전거리 위반을 구분하여 기록' },
        { name: '목적지 도달 성공 여부', unit: '성공 / 실패', detail: '제한 시간 내 도달 여부와 반복 실험 성공률' },
        { name: '알고리즘 실행 시간', unit: '밀리초 (ms)', detail: '회피 함수만 계측: 프레임당 평균·최악(ms), 스텝 수. 전역 탐색·물리·렌더링 제외' },
        { name: '계산량 및 시간 복잡도', unit: '군중 수 n 기준', detail: '입력 크기에 따른 연산량과 실행 시간의 증가 추세' }
    ];
    public notes: any[] = [];
    private pageSubscription: any;
    private pageLocation = '';
    private defaults: any;
    private pageGeneration = 0;
    public pageState: any = null;
    public canEdit = false;
    public pageBusy = false;
    public pageError = '';
        private async pageRequest(action: string, data: any = {}) {
        const response: any = await wiz.app('component.page.share').call('handle', { action, data: JSON.stringify(data) });
        if (response.code !== 200) throw new Error(response.data?.message || response.message || '페이지를 불러오지 못했습니다.');
        return response.data;
    }

    constructor(public service: Service, private router: Router) { }
    public async ngOnInit() {
        await this.service.init();
        this.defaults = JSON.parse(JSON.stringify({steps: this.steps, notes: this.notes}));
        this.pageLocation = location.href;
        this.pageSubscription = this.router.events.subscribe(event => {
            if (event instanceof NavigationEnd && location.href !== this.pageLocation) {
                this.pageLocation = location.href;
                this.sectionView = new URLSearchParams(location.search).get('section') === 'implementation' ? 'implementation' : 'description';
                Object.assign(this, JSON.parse(JSON.stringify(this.defaults)));
                void this.loadPage().then(() => this.service.render());
            }
        });
        await this.loadPage();
        await this.service.render();
    }
    public async loadPage() {
        const generation = ++this.pageGeneration;
        this.canEdit = false;
        this.pageState = null;
        this.pageError = '';
        if (!this.service.auth.status) return;
        try {
            const state = await this.pageRequest('get', {path: '/algorithm', id: new URLSearchParams(location.search).get('share') || ''});
            if (generation !== this.pageGeneration) return;
            this.pageState = state;
            let data = this.pageState.content;
            if (this.pageState.role === 'owner' && this.pageState.version === 0) {
                try { data = JSON.parse(localStorage.getItem(this.storageKey) || 'null') || data; } catch {}
            }
            if (Array.isArray(data.done)) this.steps.forEach((step, i) => step.done = data.done[i] === true);
            if (Array.isArray(data.notes)) this.notes = data.notes.filter((n: any) => n && typeof n.text === 'string');
            this.canEdit = this.pageState.role !== 'viewer';
            if (this.pageState.role === 'owner' && this.pageState.version === 0) {
                await this.save();
                if (!this.pageError) localStorage.removeItem(this.storageKey);
            }
        } catch (error: any) { this.pageError = error.message; this.canEdit = false; }
    }
    public async save() {
        if (!this.canEdit || this.pageBusy) return;
        this.pageBusy = true;
        try {
            this.pageState = await this.pageRequest('save', {id: this.pageState.id, path: '/algorithm',
                version: this.pageState.version, content: {done: this.steps.map(s => s.done), notes: this.notes}});
            this.savedMessage = '페이지 기록을 서버에 저장했어요.';
            this.pageError = '';
        } catch (error: any) { this.pageError = error.message; this.canEdit = false; }
        finally { this.pageBusy = false; await this.service.render(); }
    }
    public async toggleStep(step: any) { if (!this.canEdit || this.pageBusy) return; step.done = !step.done; await this.save(); }
    public async addNote() {
        if (!this.canEdit || this.pageBusy || !this.newNote.trim()) return;
        this.notes.unshift({ text: this.newNote.trim(), date: new Date().toLocaleDateString('ko-KR') });
        this.newNote = '';
        await this.save();
    }
    public async removeNote(index: number) { if (!this.canEdit || this.pageBusy) return; this.notes.splice(index, 1); await this.save(); }
    public ngOnDestroy() { this.pageGeneration++; this.pageSubscription?.unsubscribe(); }
}
