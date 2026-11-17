"""Browser regression for selected map -> batch compare -> 3D replay/reset."""
import os,json
from playwright.sync_api import sync_playwright,expect
with sync_playwright() as p:
 b=p.chromium.launch(headless=True,**({'executable_path':os.environ['WAREHOUSE_CHROMIUM']} if os.getenv('WAREHOUSE_CHROMIUM') else {}),args=['--no-sandbox','--enable-unsafe-swiftshader']);c=b.new_context();c.add_cookies([{'name':'season-wiz-devmode','value':'true','domain':'localhost','path':'/'}]);page=c.new_page();errors=[];tokens=set();latest={}
 page.on('pageerror',lambda e:errors.append(str(e)))
 def capture(r):
  if 'live_newton' in r.url:
   try:
    data=r.json()['data']
    if isinstance(data,dict) and 'current' in data:latest.clear();latest.update(data);tokens.add(data['token'])
   except:pass
 page.on('response',capture)
 try:
  page.goto('http://localhost:3000/algorithm?section=implementation&public=1');page.get_by_role('button',name='Map 6: Asymmetric',exact=True).click();expect(page.locator('.mode-badge')).to_have_text('실시간 물리 정지',timeout=30000)
  page.get_by_role('button',name='환경 설정',exact=True).click();page.get_by_label('실험 최대 실행 프레임 (30fps)').fill('30');page.get_by_role('button',name='알고리즘 비교',exact=True).click()
  with page.expect_response(lambda r:'run_newton' in r.url,timeout=120000) as response:
   page.get_by_label('비교 범위',exact=True).select_option('selected');page.get_by_role('button',name='선택 맵 · 세 알고리즘 실행',exact=True).click()
  rows=response.value.json()['data'];assert len(rows)==3 and {r['mapId'] for r in rows}=={'map6'};assert len({json.dumps(r['shelves']) for r in rows})==1
  expect(page.locator('button.link')).to_have_count(3,timeout=20000);page.locator('button.link').filter(has_text='VO').click();expect(page.locator('.mode-badge')).to_have_text('저장 기록 정지',timeout=30000);expect(page.locator('.section-head h2').first).to_have_text('VO · Map 6: Asymmetric')
  assert latest['shelf_poses']==rows[1]['shelf_poses'];assert latest['astar_path']==rows[1]['astar_path']
  page.locator('.control-card').get_by_role('button',name='Reset',exact=True).click();expect(page.locator('.mode-badge')).to_have_text('실시간 물리 정지',timeout=30000);assert latest['current']['t']==0 and latest['mapId']=='map6'
  assert not errors;json.dump({'passed':True,'mapIds':[r['mapId'] for r in rows],'algorithms':[r['algorithm'] for r in rows],'replay':'VO','reset':'map6 paused t=0','errors':errors},open('/tmp/shelf-map-comparison-browser-results.json','w'),indent=2);print('Map6 comparison, replay geometry/path and reset verified')
 finally:
  for token in tokens:
   c.request.post('http://localhost:3000/wiz/api/page.algorithm.run/live_newton',form={'action':'close','token':token})
  b.close()
