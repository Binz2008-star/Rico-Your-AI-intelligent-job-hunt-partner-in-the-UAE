/**
 * Cache and Data Synchronization Layer
 * Provides intelligent caching, data synchronization, and offline support.
 * Integrates with IndexedDB for persistent caching and memory layer.
 */

import { openDB, DBSchema, IDBPDatabase } from 'idb';

// ============================================================================
// Cache Database Schema
// ============================================================================

interface RicoCacheDB extends DBSchema {
  cache: {
    key: string;
      value: {
        key: string;
        data: any;
        timestamp: number;
        expiry: number;
        ttl: number;
        tags: string[];
        version: number;
    };
    indexes: {
      'by-timestamp': number;
      'by-tag': string;
      'by-expiry': number;
    };
  };
  sync_queue: {
    key: string;
    value: {
      id: string;
      operation: 'create' | 'update' | 'delete';
      resource: string;
      data: any;
      timestamp: number;
      attempts: number;
      status: 'pending' | 'syncing' | 'failed';
    };
    indexes: {
      'by-status': string;
      'by-resource': string;
      'by-timestamp': number;
    };
  };
}

const DB_NAME = 'rico-cache';
const DB_VERSION = 1;

let db: IDBPDatabase<RicoCacheDB> | null = null;

async function getDB(): Promise<IDBPDatabase<RicoCacheDB>> {
  if (db) return db;

  db = await openDB<RicoCacheDB>(DB_NAME, DB_VERSION, {
    upgrade(db: IDBPDatabase<RicoCacheDB>) {
      // Cache store
      if (!db.objectStoreNames.contains('cache')) {
        const store = db.createObjectStore('cache', { keyPath: 'key' });
        store.createIndex('by-timestamp', 'timestamp');
        store.createIndex('by-tag', 'tags', { multiEntry: true });
        store.createIndex('by-expiry', 'expiry');
      }

      // Sync queue store
      if (!db.objectStoreNames.contains('sync_queue')) {
        const store = db.createObjectStore('sync_queue', { keyPath: 'id' });
        store.createIndex('by-status', 'status');
        store.createIndex('by-resource', 'resource');
        store.createIndex('by-timestamp', 'timestamp');
      }
    },
  });

  return db;
}

// ============================================================================
// Cache Configuration
// ============================================================================

export interface CacheConfig {
  ttl: number; // Time to live in milliseconds
  tags: string[];
  version?: number;
}

export const DEFAULT_TTL = 5 * 60 * 1000; // 5 minutes
export const LONG_TTL = 30 * 60 * 1000; // 30 minutes
export const SHORT_TTL = 1 * 60 * 1000; // 1 minute

export const CACHE_CONFIGS: Record<string, CacheConfig> = {
  'jobs:list': { ttl: SHORT_TTL, tags: ['jobs', 'list'] },
  'jobs:detail': { ttl: LONG_TTL, tags: ['jobs', 'detail'] },
  'applications:list': { ttl: SHORT_TTL, tags: ['applications', 'list'] },
  'applications:detail': { ttl: LONG_TTL, tags: ['applications', 'detail'] },
  'pipeline:status': { ttl: 30 * 1000, tags: ['pipeline', 'status'] }, // 30 seconds
  'stats:overview': { ttl: 5 * 60 * 1000, tags: ['stats', 'overview'] }, // 5 minutes
  'settings:user': { ttl: LONG_TTL, tags: ['settings', 'user'] },
  'chat:conversation': { ttl: LONG_TTL, tags: ['chat', 'conversation'] },
};

// ============================================================================
// Cache API
// ============================================================================

export class CacheManager {
  /**
   * Get cached data by key
   */
  async get(key: string): Promise<any | null> {
    const database = await getDB();
    const cached = await database.get('cache', key);

    if (!cached) return null;

    // Check if expired
    const now = Date.now();
    const expiry = cached.timestamp + cached.ttl;

    if (now > expiry) {
      await database.delete('cache', key);
      return null;
    }

    return cached.data;
  }

  /**
   * Set cached data
   */
  async set(key: string, data: any, config: Partial<CacheConfig> = {}): Promise<void> {
    const database = await getDB();
    const fullConfig: CacheConfig = {
      ttl: DEFAULT_TTL,
      tags: [],
      ...config,
    };

    const cacheEntry = {
      key,
      data,
      timestamp: Date.now(),
      expiry: Date.now() + fullConfig.ttl,
      ttl: fullConfig.ttl,
      tags: fullConfig.tags,
      version: fullConfig.version || 1,
    };

    await database.put('cache', cacheEntry);
  }

  /**
   * Delete cached data by key
   */
  async delete(key: string): Promise<void> {
    const database = await getDB();
    await database.delete('cache', key);
  }

  /**
   * Invalidate cache by tags
   */
  async invalidateByTag(tag: string): Promise<void> {
    const database = await getDB();
    const keys = await database.getAllKeysFromIndex('cache', 'by-tag', tag);

    for (const key of keys) {
      await database.delete('cache', key);
    }
  }

  /**
   * Invalidate cache by prefix
   */
  async invalidateByPrefix(prefix: string): Promise<void> {
    const database = await getDB();
    const allKeys = await database.getAllKeys('cache');

    for (const key of allKeys) {
      if (key.startsWith(prefix)) {
        await database.delete('cache', key);
      }
    }
  }

  /**
   * Clear all cache
   */
  async clear(): Promise<void> {
    const database = await getDB();
    await database.clear('cache');
  }

  /**
   * Clean expired cache entries
   */
  async cleanExpired(): Promise<number> {
    const database = await getDB();
    const now = Date.now();
    const all = await database.getAll('cache');
    let deleted = 0;

    for (const entry of all) {
      const expiry = entry.timestamp + entry.ttl;
      if (now > expiry) {
        await database.delete('cache', entry.key);
        deleted++;
      }
    }

    return deleted;
  }

  /**
   * Get cache statistics
   */
  async getStats(): Promise<{
    total: number;
    expired: number;
    byTag: Record<string, number>;
    totalSize: number;
  }> {
    const database = await getDB();
    const all = await database.getAll('cache');
    const now = Date.now();
    let expired = 0;
    const byTag: Record<string, number> = {};
    let totalSize = 0;

    for (const entry of all) {
      const expiry = entry.timestamp + entry.ttl;
      if (now > expiry) {
        expired++;
      }

      for (const tag of entry.tags) {
        byTag[tag] = (byTag[tag] || 0) + 1;
      }

      totalSize += JSON.stringify(entry).length;
    }

    return {
      total: all.length,
      expired,
      byTag,
      totalSize,
    };
  }
}

// ============================================================================
// Synchronization Queue
// ============================================================================

export interface SyncOperation {
  id: string;
  operation: 'create' | 'update' | 'delete';
  resource: string;
  data: any;
  timestamp: number;
  attempts: number;
  status: 'pending' | 'syncing' | 'failed';
}

export class SyncQueue {
  /**
   * Add operation to sync queue
   */
  async add(operation: Omit<SyncOperation, 'id' | 'timestamp' | 'attempts' | 'status'>): Promise<string> {
    const database = await getDB();
    const id = `${operation.resource}-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;

    const syncOp: SyncOperation = {
      id,
      ...operation,
      timestamp: Date.now(),
      attempts: 0,
      status: 'pending',
    };

    await database.put('sync_queue', syncOp);
    return id;
  }

  /**
   * Get pending operations
   */
  async getPending(resource?: string): Promise<SyncOperation[]> {
    const database = await getDB();
    const all = await database.getAllFromIndex('sync_queue', 'by-status', 'pending');

    if (resource) {
      return all.filter(op => op.resource === resource);
    }

    return all;
  }

  /**
   * Mark operation as syncing
   */
  async markSyncing(id: string): Promise<void> {
    const database = await getDB();
    const op = await database.get('sync_queue', id);
    if (op) {
      await database.put('sync_queue', { ...op, status: 'syncing' });
    }
  }

  /**
   * Mark operation as completed (delete from queue)
   */
  async complete(id: string): Promise<void> {
    const database = await getDB();
    await database.delete('sync_queue', id);
  }

  /**
   * Mark operation as failed
   */
  async fail(id: string): Promise<void> {
    const database = await getDB();
    const op = await database.get('sync_queue', id);
    if (op) {
      await database.put('sync_queue', {
        ...op,
        status: 'failed',
        attempts: op.attempts + 1,
      });
    }
  }

  /**
   * Retry failed operations
   */
  async retryFailed(maxAttempts = 3): Promise<void> {
    const database = await getDB();
    const failed = await database.getAllFromIndex('sync_queue', 'by-status', 'failed');

    for (const op of failed) {
      if (op.attempts < maxAttempts) {
        await database.put('sync_queue', {
          ...op,
          status: 'pending',
          attempts: op.attempts + 1,
        });
      }
    }
  }

  /**
   * Clear queue
   */
  async clear(): Promise<void> {
    const database = await getDB();
    await database.clear('sync_queue');
  }
}

// ============================================================================
// Cached API Wrapper
// ============================================================================

export function createCachedAPI<T extends (...args: any[]) => Promise<any>>(
  apiFunction: T,
  cacheKey: string | ((...args: Parameters<T>) => string),
  config?: Partial<CacheConfig>,
): T {
  return (async (...args: Parameters<T>): Promise<any> => {
    const cacheManager = new CacheManager();
    const key = typeof cacheKey === 'function' ? cacheKey(...args) : cacheKey;
    const fullConfig = config || CACHE_CONFIGS[key] || { ttl: DEFAULT_TTL, tags: [] };

    // Try to get from cache
    const cached = await cacheManager.get(key);
    if (cached !== null) {
      return cached;
    }

    // Fetch from API
    const result = await apiFunction(...args);

    // Cache the result
    await cacheManager.set(key, result, fullConfig);

    return result;
  }) as T;
}

export function createInvalidatingAPI<T extends (...args: any[]) => Promise<any>>(
  apiFunction: T,
  invalidateTags: string[],
  cacheKey?: string | ((...args: Parameters<T>) => string),
  config?: Partial<CacheConfig>,
): T {
  return (async (...args: Parameters<T>): Promise<any> => {
    const cacheManager = new CacheManager();
    const key = cacheKey ? (typeof cacheKey === 'function' ? cacheKey(...args) : cacheKey) : null;
    const fullConfig = config || CACHE_CONFIGS[key || ''] || { ttl: DEFAULT_TTL, tags: [] };

    // Invalidate related cache entries
    for (const tag of invalidateTags) {
      await cacheManager.invalidateByTag(tag);
    }

    // Fetch from API
    const result = await apiFunction(...args);

    // Cache the result if key provided
    if (key) {
      await cacheManager.set(key, result, fullConfig);
    }

    return result;
  }) as T;
}

// ============================================================================
// Offline Support
// ============================================================================

export class OfflineManager {
  private isOnline = false;
  private listeners: Set<(online: boolean) => void> = new Set();

  constructor() {
    if (typeof window !== 'undefined') {
      this.isOnline = window.navigator.onLine;
      window.addEventListener('online', () => this.handleOnlineChange(true));
      window.addEventListener('offline', () => this.handleOnlineChange(false));
    }
  }

  private handleOnlineChange(online: boolean): void {
    this.isOnline = online;
    this.listeners.forEach(listener => listener(online));

    if (online) {
      this.syncPending();
    }
  }

  get online(): boolean {
    return this.isOnline;
  }

  onStatusChange(listener: (online: boolean) => void): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  async syncPending(): Promise<void> {
    if (!this.isOnline) return;

    const syncQueue = new SyncQueue();
    const pending = await syncQueue.getPending();

    if (pending.length > 0) {
      console.warn(
        `Offline sync is disabled until real network execution is implemented. ${pending.length} queued operation(s) remain pending.`
      );
    }
  }
}

// ============================================================================
// Export singleton instances
// ============================================================================

export const cacheManager = new CacheManager();
export const syncQueue = new SyncQueue();
export const offlineManager = typeof window !== 'undefined' ? new OfflineManager() : null;
