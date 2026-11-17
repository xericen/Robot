const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const source=fs.readFileSync(path.resolve(__dirname,'../../src/app/page.algorithm.run/view.ts'),'utf8');
function method(signature,args){
  let at=source.indexOf(signature);assert(at>=0,signature);
  const begin=source.indexOf('{',at);let depth=1,end=begin+1;
  for(;depth;end++){if(source[end]==='{')depth++;if(source[end]==='}')depth--;}
  return new Function(...args,source.slice(begin+1,end-1));
}
const view={parallelRuns:[]};
Object.defineProperty(view,'parallelFrameIndex',{get:method('public get parallelFrameIndex()',[])});
view.parallelPath=method('public parallelPath(row:any)',['row']);
view.parallelCurrent=method('public parallelCurrent(row:any)',['row']);
function row(length,phase='running'){return {data:{phase,frames:Array.from({length},(_,i)=>({robot:[i,i/2],t:i/30}))}};}
const a=row(5401),b=row(5401),c=row(5401);view.parallelRuns=[a,b,c];
const points=view.parallelPath(a).split(' ');
assert.equal(points.length,256);assert.equal(points[0],'0,0');assert.equal(points.at(-1),'5400,2700');
assert.equal(view.parallelPath(a),view.parallelPath(a));
const finished=row(2001,'replay_paused');view.parallelRuns=[a,finished,c];
assert.equal(view.parallelCurrent(finished).t,2000/30);
assert.equal(view.parallelCurrent(a).t,5400/30);
view.parallelRuns=[row(1),row(1),row(1)];
assert.equal(view.parallelPath(view.parallelRuns[0]),'0,0');
console.log('4 UI regressions passed: bounded path, cached path, finished robot clamp, reset.');
