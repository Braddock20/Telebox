import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdirSync,writeFileSync,readFileSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';

test('config module loads with zero Telegram accounts', async()=>{
 const p=join(tmpdir(),`ts-smoke-${Date.now()}`); mkdirSync(p);
 process.env.API_KEY='smoke-key'; process.env.DATABASE_PATH=join(p,'db.sqlite'); process.env.TEMP_DIR=join(p,'tmp');
 const {config}=await import(`../src/config.ts?x=${Date.now()}`);
 assert.equal(config.apiKey,'smoke-key');
 assert.equal(config.accounts.length,0);
 rmSync(p,{recursive:true,force:true});
});

test('metadata database round-trip', async()=>{
 const p=join(tmpdir(),`ts-db-${Date.now()}`); mkdirSync(p);
 process.env.API_KEY='smoke-key'; process.env.DATABASE_PATH=join(p,'db.sqlite'); process.env.TEMP_DIR=join(p,'tmp');
 const {insertFile,getFile,findHash,deleteFile}=await import(`../src/db.ts?x=${Date.now()}`);
 const r=insertFile({filename:'hello.txt',size:5,mimeType:'text/plain',hash:'abc',accountName:'a',channelId:'-1001',messageId:'42'});
 assert.equal(getFile(r.id)?.filename,'hello.txt');
 assert.equal(findHash('abc')?.id,r.id);
 assert.equal(deleteFile(r.id),true);
 assert.equal(getFile(r.id),null);
 rmSync(p,{recursive:true,force:true});
});
