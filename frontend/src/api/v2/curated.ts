import { apiClient } from '@/api/client'

export interface CuratedDataset {
  id: string
  name: string
  status: string
  quality_score: number | null
}

const curatedApi = {
  list: () => apiClient.get<CuratedDataset[]>('/api/v2/curated').then(r => r.data),
  get: (id: string) => apiClient.get<CuratedDataset>(`/api/v2/curated/${id}`).then(r => r.data),
  preview: (id: string) => apiClient.get(`/api/v2/curated/${id}/preview`).then(r => r.data),
  quality: (id: string) => apiClient.get(`/api/v2/curated/${id}/quality`).then(r => r.data),
  review: (id: string, action: 'approve' | 'reject', notes = '') =>
    apiClient.post(`/api/v2/curated/${id}/review?action=${action}&notes=${encodeURIComponent(notes)}`).then(r => r.data),
}

export default curatedApi
