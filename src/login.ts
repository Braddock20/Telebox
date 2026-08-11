import 'dotenv/config';
import {createInterface} from 'node:readline/promises';
import {config,AccountConfig} from './config.js';

async function load(engine:'teleproto'|'gramjs',a:AccountConfig){
 const pkg=engine==='teleproto'?'teleproto':'telegram';
 const mod:any=await import(pkg);
 const sessions:any=await import(engine==='teleproto'?'teleproto/sessions':'telegram/sessions');
 const {TelegramClient}=mod; const {StringSession}=sessions;
 const rl=createInterface({input:process.stdin,output:process.stdout});
 const client=new TelegramClient(new StringSession(a.session||''),a.apiId,a.apiHash,{connectionRetries:5});
 await client.start({
  phoneNumber:async()=>rl.question('Phone: '),
  phoneCode:async()=>rl.question('Code: '),
  password:async()=>rl.question('2FA password: '),
  onError:(e:any)=>{console.error(e);return true;}
 });
 console.log(`\\nENGINE=${engine}`);
 console.log(`ACCOUNT=${a.name}`);
 console.log(`STRING_SESSION=${client.session.save()}`);
 await client.disconnect(); rl.close();
}
const name=process.argv[2];
if(!name){console.error('Usage: npm run login -- acc1');process.exit(1);}
const account=config.accounts.find(x=>x.name===name); if(!account){console.error(`Unknown account: ${name}`);process.exit(1);}
const a=account;
const order=a.engine==='auto'?config.engineOrder:[a.engine];
let done=false; let last:any;
for(const e of order){try{await load(e,a);done=true;break}catch(err){last=err;console.error(`${e} login failed:`,err)}}
if(!done) throw last;
