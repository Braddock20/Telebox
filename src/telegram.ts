import {config, AccountConfig, EngineName} from './config.js';

type AnyClient = any;

export interface TelegramMessage {
  id: number|string;
  document?: {size?: number; id?: bigint|number|string; accessHash?: bigint|number|string};
}

export interface TelegramEngine {
  readonly name: EngineName;
  connect(): Promise<void>;
  disconnect(): Promise<void>;
  authorized(): Promise<boolean>;
  me(): Promise<any>;
  sendFile(channelId:string, filePath:string, filename:string, workers:number): Promise<TelegramMessage>;
  getMessage(channelId:string, messageId:string): Promise<TelegramMessage|null>;
  download(message:TelegramMessage, destination:string, workers:number): Promise<void>;
  deleteMessage(channelId:string, messageId:string): Promise<void>;
}

async function loadEngine(name:EngineName, a:AccountConfig):Promise<TelegramEngine> {
  const pkg = name === 'teleproto' ? 'teleproto' : 'telegram';
  const mod:any = await import(pkg);
  const {TelegramClient} = mod;
  const sessions:any = await import(name === 'teleproto' ? 'teleproto/sessions' : 'telegram/sessions');
  const {StringSession} = sessions;
  const client = new TelegramClient(new StringSession(a.session || ''), a.apiId, a.apiHash, {
    connectionRetries: 5, retryDelay: 2, autoReconnect: true
  });
  return new ClientAdapter(name, client, a);
}

class ClientAdapter implements TelegramEngine {
  constructor(public readonly name:EngineName, private client:AnyClient, private account:AccountConfig) {}
  connect(){return this.client.connect();}
  disconnect(){return this.client.disconnect();}
  authorized(){return this.client.isUserAuthorized();}
  me(){return this.client.getMe();}
  async sendFile(channelId:string,filePath:string,filename:string,workers:number) {
    return this.client.sendFile(channelId,{file:filePath,caption:filename,forceDocument:true,workers});
  }
  async getMessage(channelId:string,messageId:string) {
    const r=await this.client.getMessages(channelId,{ids:Number(messageId)});
    if (Array.isArray(r)) return r[0] ?? null;
    return r ?? null;
  }
  async download(message:TelegramMessage,destination:string,workers:number) {
    await this.client.downloadMedia(message,{outputFile:destination,workers});
  }
  async deleteMessage(channelId:string,messageId:string){await this.client.deleteMessages(channelId,[Number(messageId)]);}
}

export interface AccountState {
  config:AccountConfig;
  engine?:TelegramEngine;
  healthy:boolean;
  lastError:string|null;
  uploads:number;
  failures:number;
  floodUntil:number;
}

export class AccountManager {
  states = new Map<string,AccountState>();
  private rr=0;

  async initialize() {
    if (!config.accounts.length) throw new Error('No Telegram accounts configured');
    await Promise.all(config.accounts.map(a=>this.initAccount(a)));
  }
  private async initAccount(a:AccountConfig) {
    const state:AccountState={config:a,healthy:false,lastError:null,uploads:0,failures:0,floodUntil:0};
    this.states.set(a.name,state);
    const order=a.engine==='auto' ? config.engineOrder : [a.engine];
    let last:any;
    for (const engine of order) {
      try {
        const client=await loadEngine(engine,a);
        await client.connect();
        if (!await client.authorized()) throw new Error('Session is not authorized; run npm run login -- '+a.name);
        state.engine=client; state.healthy=true; state.lastError=null;
        console.log(`[telegram] ${a.name}: ${engine} ready`);
        return;
      } catch(e:any) {
        last=e;
        console.warn(`[telegram] ${a.name}: ${engine} failed: ${e?.message ?? e}`);
      }
    }
    state.lastError=String(last?.message ?? last ?? 'Unable to initialize');
  }
  async close(){await Promise.all([...this.states.values()].map(async s=>s.engine?.disconnect()));}
  healthyAccounts(){const now=Date.now(); return [...this.states.values()].filter(s=>s.healthy&&s.engine&&s.floodUntil<=now);}
  select():AccountState {
    const h=this.healthyAccounts(); if(!h.length) throw new Error('No healthy Telegram accounts available');
    if(config.uploadStrategy==='random') return h[Math.floor(Math.random()*h.length)];
    if(config.uploadStrategy==='least_used') return h.reduce((x,y)=>y.uploads<x.uploads?y:x,h[0]);
    const s=h[this.rr%h.length]; this.rr=(this.rr+1)%h.length; return s;
  }
  fail(s:AccountState,e:any){s.failures++;s.lastError=String(e?.message??e); if(isFlood(e)){const sec=floodSeconds(e); s.floodUntil=Date.now()+sec*1000;}}
  success(s:AccountState){s.uploads++;s.lastError=null;s.floodUntil=0;s.healthy=true;}
  status(){return [...this.states.values()].map(s=>({name:s.config.name,engine:s.engine?.name??null,healthy:s.healthy,floodUntil:s.floodUntil||null,uploads:s.uploads,failures:s.failures,lastError:s.lastError,channelId:s.config.channelId}));}
}
function isFlood(e:any){return Number(e?.seconds??e?.value??e?.floodWait??0)>0 || /FLOOD_WAIT/i.test(String(e?.message??e));}
function floodSeconds(e:any){return Math.max(1,Number(e?.seconds??e?.value??e?.floodWait??String(e?.message??'').match(/FLOOD_WAIT[_ ]?(\\d+)/i)?.[1]??1));}

export const accounts=new AccountManager();
