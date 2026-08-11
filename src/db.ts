import Database from 'better-sqlite3';
import {mkdirSync} from 'node:fs';
import {dirname} from 'node:path';
import {randomUUID} from 'node:crypto';
import {config} from './config.js';

export interface FileRecord {
  id: string; filename: string; size: number; mimeType: string|null; hash: string|null;
  accountName: string; channelId: string; messageId: string; createdAt: string; updatedAt: string;
}

mkdirSync(dirname(config.databasePath), {recursive:true});
export const db = new Database(config.databasePath);
db.pragma('journal_mode = WAL');
db.exec(`
CREATE TABLE IF NOT EXISTS files (
 id TEXT PRIMARY KEY, filename TEXT NOT NULL, size INTEGER NOT NULL,
 mime_type TEXT, content_hash TEXT, account_name TEXT NOT NULL,
 channel_id TEXT NOT NULL, message_id TEXT NOT NULL,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL, deleted INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_files_hash ON files(content_hash);
CREATE INDEX IF NOT EXISTS idx_files_account ON files(account_name);
`);

export function getFile(id:string): FileRecord|null {
 const r:any = db.prepare('SELECT * FROM files WHERE id=? AND deleted=0').get(id);
 return r ? map(r) : null;
}
export function findHash(hash:string): FileRecord|null {
 const r:any = db.prepare('SELECT * FROM files WHERE content_hash=? AND deleted=0 LIMIT 1').get(hash);
 return r ? map(r) : null;
}
export function insertFile(x: Omit<FileRecord,'id'|'createdAt'|'updatedAt'>): FileRecord {
 const id=randomUUID(), now=new Date().toISOString();
 db.prepare(`INSERT INTO files(id,filename,size,mime_type,content_hash,account_name,channel_id,message_id,created_at,updated_at,deleted)
 VALUES(@id,@filename,@size,@mimeType,@hash,@accountName,@channelId,@messageId,@createdAt,@updatedAt,0)`).run({...x,id,createdAt:now,updatedAt:now});
 return getFile(id)!;
}
export function deleteFile(id:string): boolean {
 const r=db.prepare('UPDATE files SET deleted=1,updated_at=? WHERE id=? AND deleted=0').run(new Date().toISOString(),id);
 return r.changes===1;
}
export function stats() {
 const total:any=db.prepare('SELECT COUNT(*) c, COALESCE(SUM(size),0) s FROM files WHERE deleted=0').get();
 const rows:any[]=db.prepare('SELECT account_name a, COUNT(*) c, COALESCE(SUM(size),0) s FROM files WHERE deleted=0 GROUP BY account_name').all();
 return {totalFiles:Number(total.c),totalSizeBytes:Number(total.s),byAccount:rows.map(r=>({account:r.a,files:Number(r.c),totalSizeBytes:Number(r.s)}))};
}
function map(r:any):FileRecord { return {id:r.id,filename:r.filename,size:Number(r.size),mimeType:r.mime_type,hash:r.content_hash,accountName:r.account_name,channelId:r.channel_id,messageId:r.message_id,createdAt:r.created_at,updatedAt:r.updated_at}; }
