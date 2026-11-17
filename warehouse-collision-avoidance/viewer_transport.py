"""Ordered, bounded binary HTTP tunnel with backward-compatible JSON framing."""
import base64,struct,json,queue,threading,time,uuid
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from websockets.sync.client import connect

def pack_messages(messages):
    return b"".join(struct.pack("!I",len(m))+m for m in messages)

def unpack_messages(payload):
    offset=0;messages=[]
    while offset<len(payload):
        if len(payload)-offset<4:raise ValueError("truncated packet header")
        length=struct.unpack_from("!I",payload,offset)[0];offset+=4
        if length>len(payload)-offset:raise ValueError("truncated packet")
        messages.append(payload[offset:offset+length]);offset+=length
    return messages

class Connection:
    def __init__(self,port):
        self.socket=connect("ws://127.0.0.1:"+str(port),subprotocols=["viser-v1.1.1"],proxy=None,max_size=16*1024*1024)
        self.messages=queue.Queue(maxsize=8);self.deferred=None;self.drain_lock=threading.Lock()
        self.touched=time.monotonic();self.closed=False
        threading.Thread(target=self.receive,daemon=True).start()

    def receive(self):
        try:
            while not self.closed and time.monotonic()-self.touched<60:
                try:message=self.socket.recv(timeout=5)
                except TimeoutError:continue
                message=message.encode() if isinstance(message,str) else message
                while not self.closed:
                    try:self.messages.put(message,timeout=.2);break
                    except queue.Full:continue
        except Exception:pass
        finally:self.closed=True;self.socket.close()

    def drain(self,max_messages=4,max_bytes=512*1024):
        with self.drain_lock:
            first=self.deferred;self.deferred=None
            if first is None:
                try:first=self.messages.get(timeout=.1)
                except queue.Empty:return []
            result=[first];total=len(first)
            while len(result)<max_messages:
                try:item=self.messages.get_nowait()
                except queue.Empty:break
                if total+len(item)>max_bytes:
                    self.deferred=item;break
                result.append(item);total+=len(item)
            return result

    def close(self):
        self.closed=True;self.socket.close()

def start_transport(viewer_port,on_present=None):
    connections={};lock=threading.Lock()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_POST(self):
            try:
                action,_,key=self.path.strip("/").partition("/")
                length=int(self.headers.get("Content-Length",0))
                if length>2*1024*1024:raise ValueError("message too large")
                body=self.rfile.read(length)
                if action=="present":
                    if on_present is None:raise ValueError("presentation feedback unavailable")
                    on_present(json.loads(body))
                    payload=b'{"ok":true}'
                    self.send_response(200);self.send_header("Content-Type","application/json")
                    self.send_header("Content-Length",str(len(payload)));self.end_headers();self.wfile.write(payload)
                    return
                with lock:
                    for stale in [k for k,c in connections.items() if c.closed or time.monotonic()-c.touched>60]:
                        connections.pop(stale).close()
                    if action=="open":
                        if len(connections)>=4:raise ValueError("too many browser clients")
                        key=uuid.uuid4().hex;connections[key]=Connection(viewer_port);result={"id":key,"framing":1}
                    else:
                        connection=connections[key];connection.touched=time.monotonic();result={}
                binary=False;closed=False
                if action=="poll":
                    messages=connection.drain()
                    closed=connection.closed and connection.messages.empty() and connection.deferred is None
                    binary=self.headers.get("X-Warehouse-Binary")=="1"
                    result=pack_messages(messages) if binary else {"messages":[base64.b64encode(m).decode() for m in messages],"closed":closed}
                elif action=="send":
                    messages=unpack_messages(body) if self.headers.get("X-Warehouse-Batch")=="1" else [body]
                    for message in messages:connection.socket.send(message)
                elif action=="close":connection.close()
                elif action!="open":raise ValueError("invalid action")
                payload=result if binary else json.dumps(result).encode()
                self.send_response(200);self.send_header("Content-Type","application/octet-stream" if binary else "application/json")
                self.send_header("X-Warehouse-Closed","1" if closed else "0")
                self.send_header("Content-Length",str(len(payload)));self.end_headers();self.wfile.write(payload)
            except (ValueError,KeyError,OSError):self.send_error(400)
    server=ThreadingHTTPServer(("127.0.0.1",0),Handler);server.daemon_threads=True
    threading.Thread(target=server.serve_forever,daemon=True).start()
    return server
