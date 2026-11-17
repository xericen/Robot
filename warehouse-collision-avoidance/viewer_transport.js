// The installed Viser worker and renderer retain their native message protocol.
(() => {
  const endpoint=new URL(__WAREHOUSE_ENDPOINT__,window.location.href).href;
  const shim='('+function(endpoint){
    class HttpSocket {
      static CONNECTING=0;static OPEN=1;static CLOSING=2;static CLOSED=3;
      readyState=0;binaryType='arraybuffer';bufferedAmount=0;
      constructor(){
        this.outgoing=[];this.sending=false;
        fetch(endpoint+'/open',{method:'POST'}).then(r=>{if(!r.ok)throw Error('Viser transport '+r.status);return r.json();})
        .then(data=>{this.id=data.id;this.batch=data.framing===1;if(this.readyState===3){fetch(endpoint+'/close/'+this.id,{method:'POST'});return;}
          this.readyState=1;this.onopen?.({});this.poll();}).catch(e=>this.fail(e));
      }
      async poll(){
        try{
          while(this.readyState===1){
            const r=await fetch(endpoint+'/poll/'+this.id,{method:'POST',headers:{'X-Warehouse-Binary':'1'}});
            if(!r.ok)throw Error('Viser poll '+r.status);
            let closed=false;
            if((r.headers.get('Content-Type')||'').includes('application/octet-stream')){
              const buffer=await r.arrayBuffer(),view=new DataView(buffer);
              for(let offset=0;offset<buffer.byteLength;){
                if(offset+4>buffer.byteLength)throw Error('Incomplete viewer packet');
                const size=view.getUint32(offset);offset+=4;
                if(offset+size>buffer.byteLength)throw Error('Incomplete viewer message');
                if(this.readyState===1)this.onmessage?.({data:buffer.slice(offset,offset+size)});
                offset+=size;
              }
              closed=r.headers.get('X-Warehouse-Closed')==='1';
            }else{
              const data=await r.json();closed=data.closed;
              for(const raw of data.messages){
                if(this.readyState!==1)break;
                this.onmessage?.({data:Uint8Array.from(atob(raw),c=>c.charCodeAt(0)).buffer});
              }
            }
            if(closed){this.fail(Error('Viser connection closed'));break;}
          }
        }catch(e){this.fail(e);}
      }
      send(data){
        if(this.readyState!==1)return;
        const bytes=ArrayBuffer.isView(data)?new Uint8Array(data.buffer,data.byteOffset,data.byteLength):new Uint8Array(data);
        this.outgoing.push(bytes);this.bufferedAmount+=bytes.byteLength;
        if(this.bufferedAmount>2*1024*1024){this.fail(Error('Viewer outgoing queue full'));return;}
        this.flush();
      }
      async flush(){
        if(this.sending)return;this.sending=true;
        try{
          while(this.readyState===1&&this.outgoing.length){
            const messages=this.outgoing.splice(0,this.batch?16:1),size=messages.reduce((n,b)=>n+4+b.byteLength,0);
            const buffer=new ArrayBuffer(size),view=new DataView(buffer),bytes=new Uint8Array(buffer);
            let offset=0;
            for(const message of messages){view.setUint32(offset,message.byteLength);offset+=4;bytes.set(message,offset);offset+=message.byteLength;}
            const r=await fetch(endpoint+'/send/'+this.id,{method:'POST',headers:this.batch?{'X-Warehouse-Batch':'1'}:{},body:this.batch?buffer:messages[0]});
            if(!r.ok)throw Error('Viser send '+r.status);
            this.bufferedAmount-=size-4*messages.length;
          }
        }catch(e){this.fail(e);}finally{this.sending=false;}
      }
      close(){
        if(this.readyState===3)return;this.readyState=3;this.outgoing=[];
        if(this.id)fetch(endpoint+'/close/'+this.id,{method:'POST'}).catch(()=>{});
        this.onclose?.({code:1000,reason:'closed'});
      }
      fail(error){if(this.readyState===3)return;this.onerror?.(error);this.close();}
    }
    globalThis.WebSocket=HttpSocket;
  }.toString()+')('+JSON.stringify(endpoint)+');\n';
  // Markers follow the ordered pose updates. Let the native frame-synchronized
  // handler and pose appliers run before acknowledging presentation.
  let pending=null,painting=false;
  const present=()=>{
    if(painting||!pending)return;painting=true;
    const marker=pending;pending=null;
    requestAnimationFrame(()=>requestAnimationFrame(()=>requestAnimationFrame(()=>{
      fetch(endpoint+'/present',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(marker)})
        .catch(()=>{}).finally(()=>{painting=false;present();});
    })));
  };
  const NativeWorker=window.Worker;
  window.Worker=class extends NativeWorker{
    constructor(...args){
      super(...args);
      this.addEventListener('message',event=>{
        if(event.data?.type!=='message_batch')return;
        for(const message of event.data.messages||[]){
          if(message.name!=='/warehouse/__presented_frame__')continue;
          const text=message.updates?.text??message.props?.text;
          if(!text)continue;
          try{pending=JSON.parse(text);present();}catch(_){}
        }
      });
    }
  };
  const NativeBlob=window.Blob;
  window.Blob=class extends NativeBlob{
    constructor(parts,options){super(options?.type?.includes('javascript')?[shim,...parts]:parts,options);}
  };
})();
