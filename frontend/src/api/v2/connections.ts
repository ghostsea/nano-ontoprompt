import { apiClient } from '@/api/client'

export interface Connection {
  id: string
  name: string
  kind: string
  status: string
}

export interface ConnectionCreate {
  name: string
  kind: string
  config: Record<string, unknown>
}

const connectionsApi = {
  list: () => apiClient.get<Connection[]>('/api/v2/connections').then(r => r.data),
  get: (id: string) => apiClient.get<Connection>(`/api/v2/connections/${id}`).then(r => r.data),
  create: (body: ConnectionCreate) => apiClient.post<Connection>('/api/v2/connections', body).then(r => r.data),
  test: (id: string) => apiClient.post(`/api/v2/connections/${id}/test`).then(r => r.data),
  delete: (id: string) => apiClient.delete(`/api/v2/connections/${id}`),
}

export default connectionsApi
