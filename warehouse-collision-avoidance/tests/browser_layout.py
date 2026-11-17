"""Warehouse preset, model and avoidance replay regression in real Chromium."""
import os,json,time,math
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright,expect
BASE=os.getenv('WAREHOUSE_BASE_URL','http://localhost:3000').rstrip('/')
with sync_playwright() as p:
 b=p.chromium.launch(headless=True,**({'executable_path':os.environ['WAREHOUSE_CHROMIUM']} if os.getenv('WAREHOUSE_CHROMIUM') else {}),args=['--no-sandbox','--enable-unsafe-swiftshader']);c=b.new_context(viewport={'width':1273,'height':818})
 if urlparse(BASE).hostname=='localhost':c.add_cookies([{'name':'season-wiz-devmode','value':'true','domain':'localhost','path':'/'}])
 page=c.new_page();errors=[];latest={};runs=[];tokens=set();evidence={};passed=False
 page.on('pageerror',lambda e:errors.append(str(e)));page.on('console',lambda m:errors.append(m.text) if m.type=='error' else None)
 def capture(r):
  if 'page.algorithm.run' in r.url:
   try:
    data=r.json()
    if data.get('code')==200 and '/live_newton' in r.url and 'current' in data['data']:
     latest.clear();latest.update(data['data']);tokens.add(data['data']['token'])
    if data.get('code')==200 and '/run_newton' in r.url:runs.clear();runs.extend(data['data'])
   except:pass
 page.on('response',capture)
 try:
  page.goto(BASE+'/algorithm?section=implementation&public=1')
  for name,workers,robots in [('easy',2,1),('medium',4,1),('hard',7,3),('crowded',12,5)]:
   page.get_by_role('button',name='환경 설정',exact=True).click();page.get_by_label('시나리오 / 장애물',exact=False).select_option(name)
   field=page.get_by_label('추가 에이전트 수',exact=False)
   if name!='crowded':assert field.is_disabled()
   else:assert field.input_value()=='16'
   page.get_by_role('button',name='시뮬레이션',exact=True).click();page.get_by_role('button',name='Start',exact=True).click()
   expect(page.locator('.section-head h2').first).to_contain_text(name,timeout=30000)
   viewer=page.frame_locator('iframe[title="Newton ViewerViser 3D Warehouse"]')
   expect(viewer.get_by_text('Newton CPU · Warehouse',exact=True)).to_be_visible(timeout=30000)
   page.locator('.control-card').get_by_role('button',name='Pause',exact=True).click();expect(page.locator('.mode-badge')).to_have_text('실시간 물리 정지');page.wait_for_timeout(400)
   assert latest['worker_count']==workers and latest['other_robot_count']+1==robots
   assert latest['width']==38 and latest['height']==26
   evidence[name]={'robots':robots,'workers':workers,'bodies':len(latest['bodies'])}
   if name=='hard':
    page.get_by_role('button',name='전체화면',exact=True).click();page.wait_for_timeout(1000);page.screenshot(path='/tmp/warehouse-hard-models.png');page.evaluate('document.exitFullscreen()')
  # Actual identical-condition Newton comparison and recorded avoidance playback.
  page.get_by_role('button',name='환경 설정',exact=True).click();page.get_by_label('시나리오 / 장애물',exact=False).select_option('medium');page.get_by_label('실험 최대 실행 프레임',exact=False).fill('1800')
  page.get_by_role('button',name='알고리즘 비교',exact=True).click();page.get_by_label('비교 범위',exact=True).select_option('selected');page.get_by_role('button',name='선택 맵 · 세 알고리즘 실행',exact=True).click();expect(page.get_by_role('button',name='선택 맵 · 세 알고리즘 실행',exact=True)).to_be_enabled(timeout=120000)
  assert len(runs)==3, page.locator('.status').inner_text()
  assert all(r['status']=='success' and r['worker_count']==4 and r['collisions']==0 for r in runs)
  assert all(r['shelves']==runs[0]['shelves'] and r['astar_path']==runs[0]['astar_path'] and r['seed']==runs[0]['seed'] for r in runs)
  evidence['comparison']=[{k:r[k] for k in ['algorithm','status','sim_time_s','collisions','safety_violations','goal_distance_m']} for r in runs]
  orca=next(r for r in runs if r['algorithm']=='ORCA');index=max(range(len(orca['frames'])),key=lambda i:abs(orca['frames'][i]['target_velocity'][1]))
  evidence['avoidance']={'time':orca['frames'][index]['t'],'lateral_target':orca['frames'][index]['target_velocity'][1],'position':orca['frames'][index]['robot']}
  page.locator('.unified-dashboard .table-scroll').get_by_role('button',name='ORCA',exact=True).click();expect(page.locator('.section-head h2').first).to_contain_text('medium',timeout=30000)
  expect(page.locator('.mode-badge')).to_have_text('저장 기록 정지',timeout=30000)
  viewer=page.frame_locator('iframe[title="Newton ViewerViser 3D Warehouse"]');expect(viewer.get_by_text('Newton CPU · Warehouse',exact=True)).to_be_visible(timeout=30000)
  slider=page.locator('.playback input');slider.fill(str(index));slider.dispatch_event('change');page.wait_for_timeout(1000)
  assert abs(latest['current']['t']-orca['frames'][index]['t'])<.001
  page.get_by_role('button',name='전체화면',exact=True).click();page.wait_for_timeout(800);page.screenshot(path='/tmp/warehouse-avoidance-3d.png');page.evaluate('document.exitFullscreen()')
  page.get_by_role('button',name='2D Top View',exact=True).click();point=latest['current']['body_q'][0];scale=min(900/latest['width'],600/latest['height']);import re
  xy=list(map(float,re.findall(r'[-+]?\d*\.?\d+(?:e[-+]?\d+)?',page.locator('.primary-robot').get_attribute('transform'))))
  assert abs(xy[0]-point[0]*scale)<1e-6 and abs(xy[1]-(latest['height']-point[1])*scale)<1e-6
  page.screenshot(path='/tmp/warehouse-expanded-2d.png',full_page=True);evidence['2d_matches_newton']=True
  assert not errors,errors;passed=True;print('EVIDENCE',evidence);print('ERRORS',errors)
 except Exception:
  print('STATUS',page.locator('.status').inner_text());page.screenshot(path='/tmp/warehouse-layout-failure.png',full_page=True);raise
 finally:
  for token in tokens:
   try:c.request.post(BASE+'/wiz/api/page.algorithm.run/live_newton',form={'action':'close','token':token})
   except:pass
  json.dump({'passed':passed,'evidence':evidence,'errors':errors},open('/tmp/warehouse-layout-browser-results.json','w'),ensure_ascii=False,indent=2);b.close()
