import math
import random
import time

class Simulation:
    """Robot-only finite-horizon VO and ORCA half-plane experiments."""
    @staticmethod
    def run(n, seed, safety, pattern, method, trace=False):
        rng = random.Random(seed)
        people = []
        for _ in range(n):
            angle = rng.uniform(0, 2 * math.pi)
            people.append([rng.uniform(3, 17), rng.uniform(1, 11),
                           math.cos(angle) * .6 if pattern == "random" else 0,
                           math.sin(angle) * .6 if pattern == "random" else rng.choice([-.6, .6])])
        x, y, vx, vy = 1., 6., 0., 0.
        dt, radius, horizon = .1, .6 + safety, 3.
        distance = runtime = 0.
        checks = collisions = violations = 0
        active_collision, active_violation = set(), set()
        frames = []
        success = False
        def det(a, b): return a[0]*b[1]-a[1]*b[0]
        def dot(a, b): return a[0]*b[0]+a[1]*b[1]
        for step in range(600):
            dx, dy = 19-x, 6-y
            length = math.hypot(dx, dy)
            pref = (dx/max(length, 1e-9)*min(1., length/dt), dy/max(length, 1e-9)*min(1., length/dt))
            started = time.perf_counter_ns()
            if method == "Naive":
                ax, ay = pref
                for p in people:
                    checks += 1
                    rx, ry = x-p[0], y-p[1]
                    d = math.hypot(rx, ry)
                    if d < radius+1:
                        strength = (radius+1-d)/(max(d, .01))
                        ax += rx*strength
                        ay += ry*strength
                speed = max(1., math.hypot(ax, ay))
                nextv = (ax/speed, ay/speed)
            elif method == "VO":
                candidates = [pref, (0., 0.)]
                candidates += [(speed*math.cos(a*math.pi/16), speed*math.sin(a*math.pi/16)) for speed in (.5, 1.) for a in range(32)]
                best, score = (0., 0.), float("inf")
                for candidate in candidates:
                    safe = True
                    for p in people:
                        checks += 1
                        rx, ry = p[0]-x, p[1]-y
                        wx, wy = candidate[0]-p[2], candidate[1]-p[3]
                        t = max(0., min(horizon, (rx*wx+ry*wy)/max(wx*wx+wy*wy, 1e-9)))
                        if math.hypot(rx-wx*t, ry-wy*t) < radius:
                            safe = False
                            break
                    cost = (candidate[0]-pref[0])**2+(candidate[1]-pref[1])**2
                    if safe and cost < score: best, score = candidate, cost
                nextv = best
            else:
                lines = []
                for p in people:
                    checks += 1
                    pos = (p[0]-x, p[1]-y)
                    rel = (vx-p[2], vy-p[3])
                    d2 = dot(pos, pos)
                    if d2 > radius*radius:
                        w = (rel[0]-pos[0]/horizon, rel[1]-pos[1]/horizon)
                        w2, dp = dot(w,w), dot(w,pos)
                        if dp < 0 and dp*dp > radius*radius*w2:
                            wl = math.sqrt(w2)
                            unit = (w[0]/max(wl,1e-9), w[1]/max(wl,1e-9))
                            direction = (unit[1], -unit[0])
                            u = ((radius/horizon-wl)*unit[0], (radius/horizon-wl)*unit[1])
                        else:
                            leg = math.sqrt(d2-radius*radius)
                            if det(pos,w)>0:
                                direction=((pos[0]*leg-pos[1]*radius)/d2,(pos[0]*radius+pos[1]*leg)/d2)
                            else:
                                direction=(-(pos[0]*leg+pos[1]*radius)/d2,(pos[0]*radius-pos[1]*leg)/d2)
                            dp = dot(rel,direction)
                            u=(dp*direction[0]-rel[0],dp*direction[1]-rel[1])
                    else:
                        w=(rel[0]-pos[0]/dt,rel[1]-pos[1]/dt)
                        wl=math.hypot(*w)
                        unit=(w[0]/wl,w[1]/wl) if wl>1e-9 else (-1.,0.)
                        direction=(unit[1],-unit[0])
                        u=((radius/dt-wl)*unit[0],(radius/dt-wl)*unit[1])
                    # Prescribed pedestrians do not reciprocate: robot takes full responsibility.
                    lines.append(((vx+u[0],vy+u[1]),direction))
                result = pref
                feasible = True
                for i,(point,direction) in enumerate(lines):
                    checks += 1
                    if det(direction,(point[0]-result[0],point[1]-result[1])) <= 1e-9: continue
                    proj=dot(point,direction)
                    discriminant=proj*proj+1-dot(point,point)
                    if discriminant<0:
                        feasible=False
                        break
                    left,right=-proj-math.sqrt(discriminant),-proj+math.sqrt(discriminant)
                    for prior,other in lines[:i]:
                        checks += 1
                        denominator=det(direction,other)
                        numerator=det(other,(point[0]-prior[0],point[1]-prior[1]))
                        if abs(denominator)<1e-9:
                            if numerator<0: feasible=False; break
                            continue
                        t=numerator/denominator
                        if denominator>=0: right=min(right,t)
                        else: left=max(left,t)
                        if left>right: feasible=False; break
                    if not feasible: break
                    t=max(left,min(right,dot(direction,(pref[0]-point[0],pref[1]-point[1]))))
                    result=(point[0]+t*direction[0],point[1]+t*direction[1])
                nextv=result if feasible else (0.,0.)
            runtime += (time.perf_counter_ns()-started)/1e6
            vx,vy=nextv
            nx,ny=max(.3,min(19.7,x+vx*dt)),max(.3,min(11.7,y+vy*dt))
            distance += math.hypot(nx-x,ny-y)
            current_c,current_v=set(),set()
            for i,p in enumerate(people):
                px,py=p[0]+p[2]*dt,p[1]+p[3]*dt
                if px<.3 or px>19.7: p[2]*=-1; px=max(.3,min(19.7,px))
                if py<.3 or py>11.7: p[3]*=-1; py=max(.3,min(11.7,py))
                # Swept relative segment avoids missed between-frame contacts.
                rx,ry=x-p[0],y-p[1]
                sx,sy=(nx-x)-(px-p[0]),(ny-y)-(py-p[1])
                t=max(0.,min(1.,-(rx*sx+ry*sy)/max(sx*sx+sy*sy,1e-12)))
                d=math.hypot(rx+t*sx,ry+t*sy)
                if d<.6: current_c.add(i)
                if d<radius: current_v.add(i)
                p[0],p[1]=px,py
            collisions+=len(current_c-active_collision)
            violations+=len(current_v-active_violation)
            active_collision,active_violation=current_c,current_v
            x,y=nx,ny
            if trace and step%2==0: frames.append({"t":round((step+1)*dt,1),"robot":[x,y],"people":[p[:2] for p in people]})
            if math.hypot(19-x,6-y)<.3: success=True; break
        if trace: frames.append({"t":round((step+1)*dt,1),"robot":[x,y],"people":[p[:2] for p in people]})
        return dict(method=method,n=n,seed=seed,time=round((step+1)*dt,2) if success else None,
                    elapsed=round((step+1)*dt,2),distance=round(distance,3),collisions=collisions,
                    violations=violations,success=success,runtime=round(runtime,4),
                    perStep=round(runtime/(step+1),5),checks=checks,steps=step+1,frames=frames)

Model = Simulation
