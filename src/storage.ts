import {createHash} from 'node:crypto';
import {createReadStream,createWriteStream,statSync,unlinkSync,mkdirSync} from 'node:fs';
import {pipeline} from 'node:stream/promises';
import {basename,join} from 'node:path';
import {config} from './config.js';
import {accounts,AccountState} from './telegram.js';
import {findHash,insertFile,getFile,deleteFile,FileRecord} from './db.js';

mkdirSync(config.tempDir,{recursive:true});

export async function stageUpload(stream:NodeJS.ReadableStream, filename:string) {
 const safe=basename(filename).replace(/[\\r\\n]/g,'_').slice(0,512) || 'upload';
 const path=join(config.tempDir,`${Date.now()}-${Math.random().toString(16).slice(2)}-${safe}`);
 const hash=createHash('sha256');
 let size=0;
 const out=createWriteStream(path);
 stream.on('data',(c:any)=>{size+=c.length;hash.update(c); if(size>config.maxFileSizeBytes) stream.destroy(new Error('File exceeds MAX_FILE_SIZE_MB'));});
 try {await pipeline(stream,out);} catch(e){try{unlinkSync(path)}catch{}; throw e;}
 return {path,filename:safe,size,hash:hash.digest('hex')};
}

export async function upload(path:string,filename:string,size:number,hash:string,mimeType:string|null):Promise<FileRecord> {
 const duplicate=findHash(hash); if(duplicate){try{unlinkSync(path)}catch{};return duplicate;}
 let last:any;
 for(let attempt=0;attempt<config.maxRetries;attempt++){
   let s:AccountState;
   try{s=accounts.select();}catch(e){last=e;break;}
   try{
     const msg=await s.engine!.sendFile(s.config.channelId,path,filename,config.uploadWorkers);
     if(!msg?.id) throw new Error('Telegram returned no message');
     const rec=insertFile({filename,size,mimeType,hash,accountName:s.config.name,channelId:s.config.channelId,messageId:String(msg.id)});
     accounts.success(s); try{unlinkSync(path)}catch{}; return rec;
   }catch(e:any){
     last=e; accounts.fail(s,e);
     if(isFloodWait(e)) {
       const sec=Math.max(1,Math.min(config.floodWaitMaxSeconds,floodSeconds(e)));
       if(sec>0 && sec<=config.floodWaitMaxSeconds) await sleep(sec*1000);
     }
   }
 }
 try{unlinkSync(path)}catch{}
 throw new Error(`Upload failed after ${config.maxRetries} attempts: ${last?.message??last}`);
}
export async function download(id:string,destination:string) {
 const rec=getFile(id); if(!rec) throw Object.assign(new Error('File not found'),{code:404});
 const s=accounts.states.get(rec.accountName);
 if(!s?.engine) throw new Error(`Account ${rec.accountName} unavailable`);
 const msg=await s.engine.getMessage(rec.channelId,rec.messageId);
 if(!msg?.document) throw Object.assign(new Error('Telegram message/document not found'),{code:404});
 await s.engine.download(msg,destination,config.downloadWorkers);
 return rec;
}
export async function remove(id:string) {
 const rec=getFile(id); if(!rec) return false;
 deleteFile(id);
 const s=accounts.states.get(rec.accountName);
 if(s?.engine){try{await s.engine.deleteMessage(rec.channelId,rec.messageId)}catch(e){console.warn('[telegram] remote delete failed:',e)}}
 return true;
}
export function info(id:string){return getFile(id);}
function isFloodWait(e:any){return Number(e?.seconds??e?.value??e?.floodWait??0)>0||/FLOOD_WAIT/i.test(String(e?.message??e));}
function floodSeconds(e:any){const m=String(e?.message??'').match(/FLOOD_WAIT[_ ]?(\\d+)/i);return Number(e?.seconds??e?.value??e?.floodWait??m?.[1]??1);}
function sleep(ms:number){return new Promise(r=>setTimeout(r,ms));}
