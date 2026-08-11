import Fastify from 'fastify';
import multipart from '@fastify/multipart';
import swagger from '@fastify/swagger';
import swaggerUi from '@fastify/swagger-ui';
import {createReadStream,existsSync,unlinkSync} from 'node:fs';
import {mkdirSync} from 'node:fs';
import {join} from 'node:path';
import {config} from './config.js';
import {accounts} from './telegram.js';
import {stageUpload,upload,download,remove,info} from './storage.js';
import {stats} from './db.js';

export function buildServer() {
 const app=Fastify({logger:true});
 app.register(swagger,{openapi:{info:{title:'Telegram Storage API',version:'2.0.0'}}});
 app.register(swaggerUi,{routePrefix:'/docs'});
 app.register(multipart,{limits:{fileSize:config.maxFileSizeBytes,files:1}});
 const auth=(req:any,reply:any)=>{if(!config.apiKey) return; if(req.headers['x-api-key']!==config.apiKey) return reply.code(401).send({error:'Invalid or missing API key'});};

 app.get('/',async()=>({service:'Telegram Storage API',version:'2.0.0',engine:'teleproto+gramjs',docs:'/docs'}));
 app.get('/health',async()=>{const a=accounts.status();return {status:a.some(x=>x.healthy)?'ok':'degraded',accounts:a};});
 app.get('/storage/stats',{preHandler:auth},async()=>stats());
 app.post('/files',{preHandler:auth},async(req,reply)=>{
   const part=await req.file(); if(!part) return reply.code(400).send({error:'file is required'});
   let staged;
   try{
     staged=await stageUpload(part.file,part.filename);
     const rec=await upload(staged.path,staged.filename,staged.size,staged.hash,part.mimetype||null);
     return reply.code(201).send(publicInfo(rec));
   }catch(e:any){
     if(String(e?.message).includes('File too large')||String(e?.message).includes('exceeds')) return reply.code(413).send({error:e.message});
     req.log.error(e); return reply.code(500).send({error:e?.message??'Upload failed'});
   }
 });
 app.get('/files/:id',{preHandler:auth},async(req:any,reply)=>{
   const r=info(req.params.id); return r?reply.send(publicInfo(r)):reply.code(404).send({error:'File not found'});
 });
 app.get('/files/:id/download',{preHandler:auth},async(req:any,reply)=>{
   const id=req.params.id, rec=info(id); if(!rec) return reply.code(404).send({error:'File not found'});
   const path=join(config.tempDir,`download-${id}`);
   try{await download(id,path); return reply.header('Content-Disposition',`attachment; filename="${rec.filename.replace(/"/g,'')}"`).type(rec.mimeType||'application/octet-stream').send(createReadStream(path).on('close',()=>{try{unlinkSync(path)}catch{}}));}
   catch(e:any){try{unlinkSync(path)}catch{}; const code=e?.code===404?404:500; return reply.code(code).send({error:e?.message??'Download failed'});}
 });
 app.delete('/files/:id',{preHandler:auth},async(req:any,reply)=>{const ok=await remove(req.params.id);return ok?{status:'deleted',id:req.params.id}:reply.code(404).send({error:'File not found'});});
 return app;
}
function publicInfo(r:any){return {id:r.id,filename:r.filename,size:r.size,mimeType:r.mimeType,createdAt:r.createdAt,updatedAt:r.updatedAt};}

if (process.argv[1] && process.argv[1].endsWith('server.ts')) {
 mkdirSync(config.tempDir,{recursive:true});
 await accounts.initialize();
 const app=buildServer();
 await app.listen({host:config.host,port:config.port});
 process.on('SIGINT',async()=>{await app.close();await accounts.close();process.exit(0)});
 process.on('SIGTERM',async()=>{await app.close();await accounts.close();process.exit(0)});
}
