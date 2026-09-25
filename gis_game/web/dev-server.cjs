// Tiny local static server for the training lake and additional map JSON files.
const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const port = Number(process.env.GIS_PORT || 8765);
const mime = { '.html':'text/html; charset=utf-8', '.css':'text/css; charset=utf-8', '.js':'text/javascript; charset=utf-8', '.json':'application/json; charset=utf-8', '.png':'image/png' };
http.createServer((req,res)=>{
  const pathname = decodeURIComponent(new URL(req.url, 'http://localhost').pathname);
  const file = path.resolve(root, '.' + (pathname === '/' ? '/web/index.html' : pathname));
  if (!(file === root || file.startsWith(root + path.sep))) { res.writeHead(403); res.end(); return; }
  fs.readFile(file,(error,data)=>{
    if(error){res.writeHead(404);res.end('Not found');return}
    res.writeHead(200,{'Content-Type':mime[path.extname(file)]||'application/octet-stream','Cache-Control':'no-store'});
    res.end(data);
  });
}).listen(port,'127.0.0.1',()=>console.log(`Goat Island Skiff Sail Lab: http://127.0.0.1:${port}/web/index.html`));
