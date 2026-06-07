import { apiClient } from '@/api/client'

export interface Dataset { id: string; name: string; kind: string }

const datasetsApi = {
  list: (kind?: string) => apiClient.get<Dataset[]>('/api/v2/datasets', { params: kind ? { kind } : {} }).then(r => r.data),
  get: (id: string) => apiClient.get<Dataset>(`/api/v2/datasets/${id}`).then(r => r.data),
  versions: (id: string) => apiClient.get(`/api/v2/datasets/${id}/versions`).then(r => r.data),
  preview: (id: string, versionNo: number, limit = 100) =>
    apiClient.get(`/api/v2/datasets/${id}/versions/${versionNo}/preview`, { params: { limit } }).then(r => r.data),
}

export default datasetsApi
