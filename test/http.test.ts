import test from 'node:test';
import assert from 'node:assert/strict';

test('HTTP server exposes root and health without Telegram credentials', async()=>{
 process.env.API_KEY='smoke-key';
 process.env.DATABASE_PATH=`/tmp/telegram-storage-http-${Date.now()}.db`;
 process.env.TEMP_DIR=`/tmp/telegram-storage-http-${Date.now()}`;
 const {buildServer}=await import(`../src/server.ts?x=${Date.now()}`);
 const app=buildServer();
 const root=await app.inject({method:'GET',url:'/'});
 assert.equal(root.statusCode,200);
 assert.equal(root.json().version,'2.0.0');
 const health=await app.inject({method:'GET',url:'/health'});
 assert.equal(health.statusCode,200);
 const denied=await app.inject({method:'GET',url:'/storage/stats'});
 assert.equal(denied.statusCode,401);
 await app.close();
});
