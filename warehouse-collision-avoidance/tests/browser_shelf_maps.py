"""Six map buttons, live switch/reset and real ViewerViser browser rendering."""
import os,json,time
from pathlib import Path
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright,expect
BASE=os.getenv('WAREHOUSE_BASE_URL','http://localhost:3000').rstrip('/')
OUTPUT=Path(os.getenv('WAREHOUSE_MAP_OUTPUT','/tmp/warehouse-map-evidence'));OUTPUT.mkdir(parents=True,exist_ok=True)
with sync_playwright() as p:
 b=p.chromium.launch(headless=True,**({'executable_path':os.environ['WAREHOUSE_CHROMIUM']} if os.getenv('WAREHOUSE_CHROMIUM') else {}),args=['--no-sandbox','--enable-unsafe-swiftshader']);c=b.new_context(viewport={'width':1500,'height':1100});c.add_cookies([{'name':'season-wiz-devmode','value':'true','domain':'localhost','path':'/'}]);page=c.new_page();errors=[];latest={};sessions=set();evidence=[];passed=False;main_navigations=[]
 page.on('framenavigated',lambda f:main_navigations.append(f.url) if f==page.main_frame else None)
 page.on('pageerror',lambda e:errors.append(str(e)));page.on('console',lambda m:errors.append(m.text) if m.type=='error' else None)
 def response(r):
  if 'live_newton' in r.url:
   try:
    s=r.json()
    if s['code']==200 and isinstance(s['data'],dict) and 'current' in s['data']:latest.clear();latest.update(s['data']);sessions.add(latest['token'])
   except:pass
 page.on('response',response)
 try:
  page.goto(BASE+'/algorithm?section=implementation&public=1');expect(page.locator('.map-buttons button')).to_have_count(6,timeout=20000)
  main_navigations.clear()
  for i,name in [(1,'Standard'),(2,'Horizontal'),(3,'Zigzag'),(4,'Maze'),(5,'Dense'),(6,'Fishbone'),(2,'Horizontal'),(1,'Standard')]:
   button=page.get_by_role('button',name=f'Map {i}: {name}',exact=True);button.click()
   expect(page.locator('.section-head h2').first).to_contain_text(f'Map {i}: {name}',timeout=30000)
   expect(page.locator('.mode-badge')).to_have_text('실시간 물리 정지',timeout=30000)
   expect(page.get_by_role('button',name='Start',exact=True)).to_be_enabled(timeout=30000)
   assert latest['mapId']==f'map{i}' and latest['current']['t']==0
   assert len(latest['shelves'])==6 and latest['width']==38 and latest['height']==26
   assert [b['id'] for b in latest['bodies']]==['R0','worker-0','worker-1','worker-2','worker-3']
   assert latest['current']['robot']==latest['start']
   assert latest['frame_count']==1
   assert len(page.locator('polyline.trajectory').get_attribute('points').split())==1
   viewer=page.frame_locator('iframe[title="Newton ViewerViser 3D Warehouse"]');expect(viewer.get_by_text('Newton CPU · Warehouse',exact=True)).to_be_visible(timeout=30000);viewer.locator('canvas[data-engine]').wait_for();page.wait_for_timeout(1000)
   assert button.get_attribute('aria-pressed')=='true'
   page.get_by_role('button',name='전체화면',exact=True).click();page.wait_for_timeout(400);page.screenshot(path=str(OUTPUT/f'newton-map-{i}.png'));page.evaluate('document.exitFullscreen()')
   page.get_by_role('button',name='2D Top View',exact=True).click();assert page.locator('rect.shelf').count()==6;page.get_by_role('button',name='3D View',exact=True).click()
   token=latest['token'];page.locator('.control-card').get_by_role('button',name='Resume',exact=True).click();page.wait_for_timeout(1800)
   evidence.append({'map':f'map{i}','token':token,'shelves':latest['shelves'],'path':latest['astar_path'],'time_after_resume':latest['current']['t']})
   assert evidence[-1]['time_after_resume']>0
  assert len(set(e['token'] for e in evidence))==8
  assert len(set(json.dumps(e['shelves']) for e in evidence[:6]))==6
  assert len(main_navigations)==0,main_navigations
  assert page.locator('iframe[title="Newton ViewerViser 3D Warehouse"]').count()==1
  assert not errors,errors;passed=True;print('Verified six map buttons, 8 transitions, 6 distinct scenes, 5 preserved bodies and fresh paths; errors',errors)
 except Exception:
  print('STATUS',page.locator('.status').inner_text());page.screenshot(path=str(OUTPUT/'failure.png'),full_page=True);raise
 finally:
  for token in sessions:
   try:c.request.post(BASE+'/wiz/api/page.algorithm.run/live_newton',form={'action':'close','token':token})
   except:pass
  json.dump({'passed':passed,'errors':errors,'transitions':evidence},open(OUTPUT/'browser-results.json','w'),ensure_ascii=False,indent=2);b.close()
