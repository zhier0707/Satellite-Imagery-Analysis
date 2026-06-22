/**
 * 后端 API 封装（含 auth / user / records / change / reports / admin）
 *
 * 通过 Vite 代理，所有 /api/* 请求会被反代到 http://127.0.0.1:8000
 * 拦截器自动附加 Authorization 头，401 时尝试用 refresh_token 刷新一次
 */
import axios, { AxiosError, AxiosRequestConfig } from 'axios'
import { ElMessage } from 'element-plus'

// ==================== HTTP 实例 ====================
const http = axios.create({ baseURL: '/api', timeout: 60_000 })

// ==================== 拦截器 ====================
let isRefreshing = false
let pendingQueue: Array<(t: string | null) => void> = []

http.interceptors.request.use((cfg) => {
  const t = localStorage.getItem('access_token')
  if (t) cfg.headers.Authorization = `Bearer ${t}`
  return cfg
})

http.interceptors.response.use(
  (r) => r,
  async (err: AxiosError) => {
    const orig = err.config as AxiosRequestConfig & { _retry?: boolean }
    if (err.response?.status === 401 && !orig._retry) {
      orig._retry = true
      const refresh = localStorage.getItem('refresh_token')
      if (!refresh) {
        // 无 refresh_token 直接放行让上层 401
        return Promise.reject(err)
      }
      if (isRefreshing) {
        // 已在刷新中，排队
        return new Promise<string | null>((resolve) => {
          pendingQueue.push(resolve)
        }).then((newToken) => {
          if (newToken) {
            orig.headers = { ...(orig.headers || {}), Authorization: `Bearer ${newToken}` }
          }
          return http(orig)
        })
      }
      isRefreshing = true
      try {
        const r = await axios.post('/api/auth/refresh', { refresh_token: refresh })
        const newAccess = r.data.access_token
        localStorage.setItem('access_token', newAccess)
        pendingQueue.forEach((cb) => cb(newAccess))
        pendingQueue = []
        orig.headers = { ...(orig.headers || {}), Authorization: `Bearer ${newAccess}` }
        return http(orig)
      } catch (e) {
        pendingQueue.forEach((cb) => cb(null))
        pendingQueue = []
        localStorage.removeItem('access_token')
        localStorage.removeItem('refresh_token')
        ElMessage.error('登录已过期，请重新登录')
        return Promise.reject(e)
      } finally {
        isRefreshing = false
      }
    }
    return Promise.reject(err)
  },
)

// ==================== 类型定义 ====================
export interface TopItem { label: string; score: number }
export interface ClassifyResult { top1: TopItem; top5: TopItem[]; mock?: boolean; record_id?: number }
export interface HeatmapResult { png_base64: string; mock?: boolean }
export interface StatsResult {
  window_hours: number; total: number
  counts: Record<string, number>; server_uptime_s: number
}

export interface UserOut {
  id: number; username: string; email: string; role: 'user' | 'admin'
  is_active: boolean; created_at: string
}

export interface TokenOut { access_token: string; refresh_token: string; token_type: string; user: UserOut }

export interface RecordOut {
  id: number; image_path: string
  top1_label: string; top1_score: number
  top5_json: string; created_at: string
  user_id?: number; username?: string
}

export interface ChangeResult {
  top1_a: TopItem; top1_b: TopItem
  top5_a: TopItem[]; top5_b: TopItem[]
  changes: Array<{ type: 'top1_changed' | 'label_lost' | 'label_gained'; label: string; score_a?: number; score_b?: number }>
  summary: string
  job_id?: number
}

export type ReportKind = 'pdf' | 'excel' | 'csv'
export interface ReportJob {
  id: number; kind: ReportKind
  status: 'queued' | 'running' | 'completed' | 'failed'
  output_path?: string | null
  error?: string | null
  time_range_start?: string | null
  time_range_end?: string | null
  class_filter?: string | null
  created_at: string; finished_at?: string | null
}

export interface TrainingJob {
  id: number; stage: string
  status: 'queued' | 'running' | 'completed' | 'failed' | 'stopped'
  pid?: number | null
  metrics_json?: string | null
  started_at?: string | null
  finished_at?: string | null
  error?: string | null
  log_tail?: string
  created_at: string
}

// ==================== 业务 API ====================
// ---- 分类/统计/热力图 ----
export async function classify(image: File): Promise<ClassifyResult> {
  const fd = new FormData()
  fd.append('image', image)
  const r = await http.post<ClassifyResult>('/classify', fd, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return r.data
}

export async function heatmap(image: File, targetClass = 0): Promise<HeatmapResult> {
  const fd = new FormData()
  fd.append('image', image)
  fd.append('target_class', String(targetClass))
  const r = await http.post<HeatmapResult>('/heatmap', fd, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return r.data
}

export async function getStats(): Promise<StatsResult> {
  const r = await http.get<StatsResult>('/stats')
  return r.data
}

export async function recordStat(label: string, score: number): Promise<void> {
  await http.post('/stats/record', { label, score, ts: Date.now() / 1000 })
}

// ---- Auth ----
export async function register(payload: { username: string; email: string; password: string }): Promise<TokenOut> {
  const r = await http.post<TokenOut>('/auth/register', payload)
  return r.data
}
export async function login(payload: { username: string; password: string }): Promise<TokenOut> {
  const r = await http.post<TokenOut>('/auth/login', payload)
  return r.data
}
export async function logout(): Promise<void> {
  await http.post('/auth/logout')
}
export async function fetchMe(): Promise<UserOut> {
  const r = await http.get<UserOut>('/auth/me')
  return r.data
}

// ---- Records ----
export async function listMyRecords(page = 1, pageSize = 20): Promise<{ items: RecordOut[]; total: number }> {
  const r = await http.get<{ items: RecordOut[]; total: number }>('/records', {
    params: { page, page_size: pageSize },
  })
  return r.data
}
export async function getRecord(id: number): Promise<RecordOut> {
  const r = await http.get<RecordOut>(`/records/${id}`)
  return r.data
}

// ---- Change ----
export async function changeDetect(imageA: File, imageB: File): Promise<ChangeResult> {
  const fd = new FormData()
  fd.append('image_a', imageA)
  fd.append('image_b', imageB)
  const r = await http.post<ChangeResult>('/change', fd, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return r.data
}

// ---- Reports ----
export async function createReport(payload: {
  kind: ReportKind
  time_range_start?: string
  time_range_end?: string
  class_filter?: string[]
}): Promise<ReportJob> {
  const r = await http.post<ReportJob>('/reports/export', payload)
  return r.data
}
export async function listMyReports(page = 1, pageSize = 20): Promise<{ items: ReportJob[]; total: number }> {
  const r = await http.get<{ items: ReportJob[]; total: number }>('/reports', {
    params: { page, page_size: pageSize },
  })
  return r.data
}
export async function getReport(id: number): Promise<ReportJob> {
  const r = await http.get<ReportJob>(`/reports/${id}`)
  return r.data
}
export function reportDownloadUrl(id: number): string {
  return `/api/reports/${id}/download`
}

/**
 * 通过 http 实例下载报表二进制(自动走拦截器,带 Authorization 头)。
 * 失败时抛出 axios 错误供上层捕获展示。
 * 成功时返回 Blob,由调用方结合 URL.createObjectURL 触发浏览器下载。
 */
export async function downloadReportBlob(id: number): Promise<Blob> {
  const r = await http.get<Blob>(`/reports/${id}/download`, {
    responseType: 'blob',
  })
  return r.data
}

// ---- Admin: Users ----
export async function adminListUsers(): Promise<UserOut[]> {
  const r = await http.get<UserOut[]>('/admin/users')
  return r.data
}
export async function adminUpdateUser(id: number, patch: Partial<Pick<UserOut, 'role' | 'is_active'>>): Promise<UserOut> {
  const r = await http.patch<UserOut>(`/admin/users/${id}`, patch)
  return r.data
}
export async function adminDeleteUser(id: number): Promise<void> {
  await http.delete(`/admin/users/${id}`)
}

// ---- Admin: Records ----
export async function adminListRecords(userId?: number, page = 1, pageSize = 50): Promise<{ items: RecordOut[]; total: number }> {
  const r = await http.get<{ items: RecordOut[]; total: number }>('/admin/records', {
    params: { user_id: userId, page, page_size: pageSize },
  })
  return r.data
}

// ---- Admin: Training ----
export async function adminListTraining(page = 1, pageSize = 20): Promise<{ items: TrainingJob[]; total: number }> {
  const r = await http.get<{ items: TrainingJob[]; total: number }>('/admin/training', {
    params: { page, page_size: pageSize },
  })
  return r.data
}
export async function adminGetTraining(id: number): Promise<TrainingJob> {
  const r = await http.get<TrainingJob>(`/admin/training/${id}`)
  return r.data
}
export async function adminStartTraining(payload: {
  stage: number; epochs: number; batch_size: number; lr: number
  resume_from?: string; weights?: string
}): Promise<TrainingJob> {
  const r = await http.post<TrainingJob>('/admin/training/start', payload)
  return r.data
}
export async function adminStopTraining(id: number): Promise<void> {
  await http.post(`/admin/training/${id}/stop`)
}

// ---- Admin: Converts ----
export async function adminStartConvert(payload: {
  weights: string; output?: string; image_size?: number; opset?: number
}): Promise<TrainingJob> {
  const r = await http.post<TrainingJob>('/admin/converts/start', payload)
  return r.data
}

// ==================== Phase B: 3D 大屏聚合数据 ====================
/**
 * 大屏 KPI 4 字段
 * - total_records  累计记录数（admin 看全平台，user 仅自己）
 * - today_new      今日新增
 * - active_users   近 7 天活跃用户数
 * - accuracy_avg   平均 top1 置信度（0-1，保留 4 位小数）
 */
export interface DashboardKpi {
  total_records: number
  today_new: number
  active_users: number
  accuracy_avg: number
}

/** 时间序列单日点（最近 30 天） */
export interface DashboardTimePoint {
  date: string
  count: number
}

/** Top 分类点（后端当前不含 lng/lat，仅 id/label/score） */
export interface DashboardLocation {
  id: number
  label: string
  score: number
}

/** GET /api/stats/dashboard 完整响应 */
export interface DashboardStats {
  kpi: DashboardKpi
  classification_distribution: Record<string, number>
  time_series: DashboardTimePoint[]
  top_locations: DashboardLocation[]
  generated_at: string
}

export async function getDashboardStats(): Promise<DashboardStats> {
  const r = await http.get<DashboardStats>('/stats/dashboard')
  return r.data
}

// ==================== LBS (高德代理) ====================
// ---- 地理编码 ----
export interface GeocodeResult {
  formatted_address: string
  location: [number, number]
  level?: string
  adcode?: string
}
export interface RegeocodeResult {
  formatted_address: string
  addressComponent: {
    province?: string
    city?: string
    district?: string
    township?: string
    street?: string
    streetNumber?: string
  }
  pois?: Array<{ id: string; name: string; type?: string; location: [number, number] }>
}
export async function geocode(address: string): Promise<GeocodeResult> {
  const r = await http.get<GeocodeResult>('/lbs/geocode', { params: { address } })
  return r.data
}
export async function regeocode(lng: number, lat: number): Promise<RegeocodeResult> {
  const r = await http.get<RegeocodeResult>('/lbs/regeocode', { params: { lng, lat } })
  return r.data
}

// ---- POI 搜索 ----
export interface POI {
  id: string
  name: string
  type?: string
  address?: string
  location: [number, number]
  distance?: number
  adcode?: string
}
export async function poiTextSearch(params: {
  keywords: string
  city?: string
  offset?: number
}): Promise<POI[]> {
  const r = await http.get<POI[]>('/lbs/place/text', { params })
  return r.data
}
export async function poiAroundSearch(params: {
  lng: number
  lat: number
  radius?: number
  types?: string
}): Promise<POI[]> {
  const r = await http.get<POI[]>('/lbs/place/around', { params })
  return r.data
}

// ---- 静态图 / 分享 ----
export async function staticMapUrl(params: {
  lng: number
  lat: number
  zoom?: number
  size?: string
}): Promise<{ url: string }> {
  const r = await http.get<{ url: string }>('/lbs/staticmap', { params })
  return r.data
}
export interface ShareMapResult {
  url: string
  qrcode_base64: string
}
export async function shareMap(payload: {
  title: string
  markers: Array<{ lng: number; lat: number; name?: string }>
}): Promise<ShareMapResult> {
  const r = await http.post<ShareMapResult>('/lbs/share', payload)
  return r.data
}

// ---- Admin: All Reports ----
export async function adminListAllReports(page = 1, pageSize = 50): Promise<{ items: ReportJob[]; total: number }> {
  const r = await http.get<{ items: ReportJob[]; total: number }>('/admin/reports', {
    params: { page, page_size: pageSize },
  })
  return r.data
}
