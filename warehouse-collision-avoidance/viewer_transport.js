// Installed only inside Viser's JavaScript worker Blob. The Viser renderer,
// camera controls and wire protocol are provided by the installed Viser client.
(() => {
  const endpoint = new URL(__WAREHOUSE_ENDPOINT__, window.location.href).href;
  const shim = '(' + function(endpoint) {
    class HttpSocket {
      static CONNECTING=0; static OPEN=1; static CLOSING=2; static CLOSED=3;
      readyState=0; binaryType='arraybuffer'; bufferedAmount=0;
      constructor() {
        this.pending=Promise.resolve();
        fetch(endpoint+'/open',{method:'POST'}).then(r=>{
          if(!r.ok) throw Error('Viser transport '+r.status);
          return r.json();
        }).then(data=>{
          this.id=data.id;
          if(this.readyState===3) { fetch(endpoint+'/close/'+this.id,{method:'POST'}); return; }
          this.readyState=1; this.onopen?.({}); this.poll();
        }).catch(e=>this.fail(e));
      }
      async poll() {
        try {
          while(this.readyState===1) {
            const r=await fetch(endpoint+'/poll/'+this.id,{method:'POST'});
            if(!r.ok) throw Error('Viser poll '+r.status);
            const data=await r.json();
            for(const raw of data.messages) {
              if(this.readyState!==1) break;
              const bytes=Uint8Array.from(atob(raw),c=>c.charCodeAt(0));
              this.onmessage?.({data:bytes.buffer});
            }
            if(data.closed) {this.fail(Error('Viser connection closed'));break;}
          }
        } catch(e) {this.fail(e);}
      }
      send(data) {
        if(this.readyState!==1) return;
        this.pending=this.pending.then(async()=>{
          const r=await fetch(endpoint+'/send/'+this.id,{method:'POST',body:data});
          if(!r.ok) throw Error('Viser send '+r.status);
        }).catch(e=>this.fail(e));
      }
      close() {
        if(this.readyState===3) return;
        this.readyState=3;
        if(this.id) fetch(endpoint+'/close/'+this.id,{method:'POST'}).catch(()=>{});
        this.onclose?.({code:1000,reason:'closed'});
      }
      fail(error) {
        if(this.readyState===3) return;
        this.onerror?.(error); this.close();
      }
    }
    globalThis.WebSocket=HttpSocket;
  }.toString() + ')('+JSON.stringify(endpoint)+');\n';
  const NativeBlob=window.Blob;
  window.Blob=class extends NativeBlob {
    constructor(parts,options) {
      super(options?.type?.includes('javascript') ? [shim,...parts] : parts,options);
    }
  };
})();
