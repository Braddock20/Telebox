import 'dotenv/config';

export type EngineName = 'teleproto' | 'gramjs';
export type EngineMode = EngineName | 'auto';

export interface AccountConfig {
  name: string;
  apiId: number;
  apiHash: string;
  session: string;
  channelId: string;
  engine: EngineMode;
}

const env = (key: string, fallback = '') => process.env[key] ?? fallback;

function accountConfigs(): AccountConfig[] {
  const indexes = new Set<number>();
  for (const key of Object.keys(process.env)) {
    const m = /^TELEGRAM_ACCOUNT_(\d+)_NAME$/i.exec(key);
    if (m) indexes.add(Number(m[1]));
  }
  return [...indexes].sort((a,b)=>a-b).map(i => {
    const p = `TELEGRAM_ACCOUNT_${i}_`;
    const name = env(`${p}NAME`);
    const apiId = Number(env(`${p}API_ID`));
    const apiHash = env(`${p}API_HASH`);
    const session = env(`${p}SESSION`);
    const channelId = env(`${p}CHANNEL_ID`);
    const engine = (env(`${p}ENGINE`, 'auto').toLowerCase() as EngineMode);
    if (!name || !Number.isInteger(apiId) || apiId <= 0 || !apiHash || !channelId) {
      throw new Error(`Incomplete Telegram account ${i}`);
    }
    if (!['auto','teleproto','gramjs'].includes(engine)) throw new Error(`Invalid engine for ${name}`);
    return {name, apiId, apiHash, session, channelId, engine};
  });
}

export const config = {
  host: env('HOST','0.0.0.0'),
  port: Number(env('PORT','8080')),
  apiKey: env('API_KEY'),
  databasePath: env('DATABASE_PATH','./data/storage.db'),
  tempDir: env('TEMP_DIR','./data/tmp'),
  engineOrder: env('ENGINE_ORDER','teleproto,gramjs').split(',').map(x=>x.trim()).filter(Boolean) as EngineName[],
  uploadStrategy: env('UPLOAD_STRATEGY','least_used'),
  maxRetries: Math.max(1, Number(env('MAX_RETRIES','4'))),
  floodWaitMaxSeconds: Math.max(0, Number(env('FLOOD_WAIT_MAX_SECONDS','300'))),
  uploadWorkers: Math.max(1, Math.min(16, Number(env('UPLOAD_WORKERS','8')))),
  downloadWorkers: Math.max(1, Math.min(16, Number(env('DOWNLOAD_WORKERS','8')))),
  maxFileSizeBytes: Math.max(1, Number(env('MAX_FILE_SIZE_MB','4096'))) * 1024 * 1024,
  accounts: accountConfigs()
};

if (config.engineOrder.some(x => !['teleproto','gramjs'].includes(x))) {
  throw new Error('ENGINE_ORDER may contain only teleproto and gramjs');
}
if (config.apiKey === 'replace-with-a-long-random-secret') {
  throw new Error('Set a real API_KEY');
}
