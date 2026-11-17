"""Local WIZ regression: default Start must physically reach the goal and stop.

Requires Playwright; WAREHOUSE_BASE_URL defaults to http://localhost:3000.
Optional WAREHOUSE_CHROMIUM executable and WAREHOUSE_LEGACY_FRAMES budget.
Only the test-created session is closed; existing user sessions are preserved.
"""
import os,json,time
from playwright.sync_api import sync_playwright,expect
from urllib.parse import urlparse
BASE = os.getenv("WAREHOUSE_BASE_URL", "http://localhost:3000").rstrip("/")
with sync_playwright() as p:
 b=p.chromium.launch(headless=True,**({'executable_path':os.environ['WAREHOUSE_CHROMIUM']} if os.getenv('WAREHOUSE_CHROMIUM') else {}),args=['--no-sandbox','--enable-unsafe-swiftshader'])
 c=b.new_context(viewport={'width':1273,'height':818})
 if urlparse(BASE).hostname == 'localhost':
  c.add_cookies([{'name':'season-wiz-project','value':'main','domain':'localhost','path':'/'},{'name':'season-wiz-devmode','value':'true','domain':'localhost','path':'/'}])
 page=c.new_page();errors=[];latest={};evidence={};token=[''];api_url=[BASE+'/wiz/api/page.algorithm.run/live_newton'];passed=False
 page.on('pageerror',lambda e:errors.append(str(e)));page.on('console',lambda m:errors.append(m.text) if m.type=='error' else None)
 def capture(r):
  if '/live_newton' in r.url:
   api_url[0]=r.url
   try:
    data=r.json()
    if data['code']==200 and 'current' in data['data']:
     latest.clear();latest.update(data['data']);token[0]=latest['token']
   except:pass
 page.on('response',capture)
 try:
  page.goto(BASE+'/algorithm?section=implementation&public=1')
  if os.getenv('WAREHOUSE_LEGACY_FRAMES'):
   page.get_by_role('button',name='환경 설정',exact=True).click()
   page.get_by_label('실험 최대 실행 프레임',exact=False).fill(os.environ['WAREHOUSE_LEGACY_FRAMES'])
   page.get_by_role('button',name='시뮬레이션',exact=True).click()
  page.get_by_role('button',name='Start',exact=True).click()
  viewer=page.frame_locator('iframe[title="Newton ViewerViser 3D Warehouse"]')
  expect(viewer.get_by_text('Newton CPU · Warehouse',exact=True)).to_be_visible(timeout=30000)
  page.wait_for_timeout(3000)
  page.locator('.control-card').get_by_role('button',name='Pause',exact=True).click()
  expect(page.locator('.mode-badge')).to_have_text('실시간 물리 정지')
  page.wait_for_timeout(400)
  assert latest['current']['robot'][0]>latest['start'][0]+1,latest['current']
  t=latest['current']['t'];page.wait_for_timeout(600);assert latest['current']['t']==t
  evidence['moving_before_pause']=latest['current']['robot'];evidence['pause_time']=t
  evidence['requested_frame_limit']=latest['requested_frame_limit'];evidence['frame_limit']=latest['frame_limit']
  if os.getenv('WAREHOUSE_LEGACY_FRAMES'):
   assert latest['requested_frame_limit']==int(os.environ['WAREHOUSE_LEGACY_FRAMES'])
   assert latest['frame_budget_extended']
  page.locator('.control-card').get_by_role('button',name='Resume',exact=True).click()
  expect(page.locator('.status')).to_contain_text('목표 도달 완료',timeout=120000)
  assert latest['status']=='success' and latest['current']['reached'],latest
  assert latest['goal_distance_m']<=.25 and sum(v*v for v in latest['current']['velocity'])**.5<=.02
  evidence.update(status=latest['status'],sim_time=latest['current']['t'],position=latest['current']['robot'],velocity=latest['current']['velocity'],goal=latest['goal'],distance=latest['goal_distance_m'],path_length=latest['path_length_m'])
  page.screenshot(path='/tmp/warehouse-goal-3d-success.png',full_page=True)
  page.get_by_role('button',name='2D Top View',exact=True).click()
  transform=page.locator('.primary-robot').get_attribute('transform');evidence['svg_position']=transform
  expect(page.get_by_text('도달 · 정지',exact=True)).to_be_visible()
  page.screenshot(path='/tmp/warehouse-goal-success.png',full_page=True)
  with page.expect_response(lambda r: 'live_newton' in r.url and 'action=reset' in (r.request.post_data or '')) as reset_reply:
   page.get_by_role('button',name='Reset',exact=True).click()
  reset_data=reset_reply.value.json()['data']
  expect(page.locator('.viewer-card .badge')).to_have_text('0s')
  assert abs(reset_data['current']['robot'][0]-reset_data['start'][0])<1e-5 and not reset_data['current']['reached']
  evidence['reset']=True
  assert not errors,errors
  passed=True
  print('EVIDENCE',evidence);print('ERRORS',errors)
 finally:
  if token[0]:c.request.post(api_url[0],form={'action':'close','token':token[0]})
  json.dump({'passed':passed,'base_url':BASE,'evidence':evidence,'errors':errors},open('/tmp/warehouse-goal-browser-results.json','w'),ensure_ascii=False,indent=2)
  b.close()
