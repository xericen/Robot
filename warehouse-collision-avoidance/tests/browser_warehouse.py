"""Local WIZ browser regression. Requires Playwright and a running localhost:3000.

Run test_newton_viewer.py first to create the real collision recording.
Set WAREHOUSE_CHROMIUM to an existing Chromium executable when necessary.
Uses only the public algorithm page and per-test Newton sessions.
"""
import os,json,time,glob
from playwright.sync_api import sync_playwright,expect
with sync_playwright() as p:
 b=p.chromium.launch(headless=True,**({'executable_path':os.environ['WAREHOUSE_CHROMIUM']} if os.getenv('WAREHOUSE_CHROMIUM') else {}),args=['--no-sandbox','--enable-unsafe-swiftshader'])
 c=b.new_context(viewport={'width':1600,'height':1100});c.add_cookies([{'name':'season-wiz-project','value':'main','domain':'localhost','path':'/'},{'name':'season-wiz-devmode','value':'true','domain':'localhost','path':'/'}])
 page=c.new_page(); errors=[]; evidence={}; sessions=set();latest={}
 page.on('pageerror',lambda e:errors.append(str(e)));page.on('console',lambda m:errors.append(m.text) if m.type=='error' else None)
 def capture(response):
  if '/live_newton' in response.url:
   try:
    data=response.json()
    if data['code']==200 and 'current' in data['data']:
     latest.clear();latest.update(data['data']); sessions.add(data['data']['token'])
   except:pass
 page.on('response',capture)
 def api(action,**params):
  result=c.request.post('http://localhost:3000/wiz/api/page.algorithm.run/live_newton',form={'action':action,**params}).json();assert result['code']==200,result;return result['data']
 try:
  page.goto('http://localhost:3000/algorithm?section=implementation&public=1')
  page.get_by_role('button',name='환경 설정',exact=True).click();page.get_by_label('실행 프레임',exact=False).fill('30')
  page.get_by_role('button',name='시뮬레이션',exact=True).click();page.get_by_role('button',name='Start',exact=True).click()
  expect(page.locator('.mode-badge')).to_have_text('저장 기록 정지',timeout=120000)
  page.frame_locator('iframe[title="Newton ViewerViser 3D Warehouse"]').locator('canvas[data-engine]').wait_for(timeout=30000)
  page.wait_for_timeout(1800)
  evidence['3d_canvas']=True
  canvas=page.frame_locator('iframe[title="Newton ViewerViser 3D Warehouse"]').locator('canvas[data-engine]')
  before=canvas.screenshot();box=canvas.bounding_box()
  page.mouse.move(box['x']+box['width']*.6,box['y']+box['height']*.65)
  page.mouse.down();page.mouse.move(box['x']+box['width']*.6+90,box['y']+box['height']*.65+40,steps=8);page.mouse.up();page.mouse.wheel(0,-180)
  page.wait_for_timeout(350);assert canvas.screenshot()!=before;evidence['camera_orbit_zoom']=True
  # Current 2D SVG location must exactly match Newton body_q from the same paused frame.
  page.get_by_role('button',name='2D Top View',exact=True).click();page.wait_for_timeout(300)
  point=latest['current']['body_q'][0]
  transform=page.locator('.primary-robot').get_attribute('transform')
  import re
  xy=list(map(float,re.findall(r'[-+]?\d*\.?\d+(?:e[-+]?\d+)?',transform)))
  scale=min(900/latest['width'],600/latest['height'])
  assert abs(xy[0]-point[0]*scale)<1e-6 and abs(xy[1]-(latest['height']-point[1])*scale)<1e-6
  evidence['2d_matches_body_q']=True
  slider=page.locator('.playback input');slider.fill('0');slider.dispatch_event('change');page.wait_for_timeout(400)
  assert page.locator('.viewer-card .badge').inner_text()=='0s'
  page.locator('.control-card').get_by_role('button',name='Resume',exact=True).click();page.wait_for_timeout(300)
  page.locator('.control-card').get_by_role('button',name='Pause',exact=True).click();page.wait_for_timeout(200)
  assert latest['current']['t']>0;evidence['replay_seek_resume_pause']=True
  page.get_by_role('button',name='3D View',exact=True).click()
  page.get_by_role('button',name='전체화면',exact=True).click();page.wait_for_timeout(200)
  assert page.evaluate('!!document.fullscreenElement');page.evaluate('document.exitFullscreen()');evidence['fullscreen']=True
  for method in ['Naive','VO','ORCA']:
   if method!='ORCA' or latest.get('algorithm')!='ORCA':
    page.locator('.algorithm-buttons').get_by_role('button',name=method,exact=True).click()
    expect(page.locator('.section-head h2').first).to_contain_text(method,timeout=20000)
    expect(page.locator('.mode-badge')).to_have_text('저장 기록 정지',timeout=120000)
   assert latest['algorithm']==method
   assert any(abs(v)>0 for v in latest['current']['target_velocity'])
   evidence['algorithm_'+method]=True
  page.get_by_role('button',name='이동 경로 ON',exact=True).click();expect(page.get_by_role('button',name='이동 경로 OFF',exact=True)).to_be_visible();evidence['path_toggle']=True
  page.get_by_role('button',name='알고리즘 비교',exact=True).click();page.get_by_label('비교 범위',exact=True).select_option('selected');page.get_by_role('button',name='선택 맵 · 세 알고리즘 실행',exact=True).click()
  expect(page.locator('.unified-dashboard .table-scroll tbody tr')).to_have_count(3,timeout=30000)
  expect(page.get_by_role('button',name='선택 맵 · 세 알고리즘 실행',exact=True)).to_be_enabled(timeout=30000)
  page.locator('.unified-dashboard .table-scroll').get_by_role('button',name='VO',exact=True).click()
  expect(page.locator('.mode-badge')).to_have_text('저장 기록 정지',timeout=20000)
  expect(page.locator('.section-head h2').first).to_contain_text('VO',timeout=20000);evidence['compare_and_load']=True
  expect(page.frame_locator('iframe[title="Newton ViewerViser 3D Warehouse"]').get_by_text('Newton CPU · Warehouse',exact=True)).to_be_visible(timeout=20000)
  page.screenshot(path='/tmp/warehouse-final.png',full_page=True)
  # Load the actual colliding Newton test record, then verify both risk visualizations.
  record=json.load(open(glob.glob('/tmp/pytest-of-root/pytest-*/test_contacts_and_exact_3d_pos0/collision-record.json')[-1]))
  collision=api('load',record=json.dumps(record),algorithm='orca',agents=1,scenario='basic',frames=30)
  sessions.add(collision['token']);api('display',token=collision['token'],path='true',risk='true')
  proof=c.new_page();proof.on('pageerror',lambda e:errors.append(str(e)));proof.goto('http://localhost:3000'+collision['viewer_url']);proof.locator('canvas[data-engine]').wait_for(timeout=20000);proof.wait_for_timeout(1600)
  proof.screenshot(path='/tmp/warehouse-collision.png')
  assert collision['current']['risk'] and collision['current']['contact_shapes'];evidence['collision_record_render']=True
  proof.close()
  print('EVIDENCE',evidence);print('ERRORS',errors);assert not errors
 finally:
  for token in sessions:
   try:api('close',token=token)
   except:pass
  json.dump({'evidence':evidence,'errors':errors},open('/tmp/warehouse-final-browser-results.json','w'),ensure_ascii=False,indent=2)
  b.close()
