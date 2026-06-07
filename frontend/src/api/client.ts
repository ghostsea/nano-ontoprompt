import axios from 'axios'

function addInterceptors(client: ReturnType<typeof axios.create>) {
  client.interceptors.request.use(config => {
    const token = localStorage.getItem('token')
    if (token) config.headers.Authorization = `Bearer ${token}`
    return config
  })
  client.interceptors.response.use(
    res => res.data.data !== undefined ? res.data.data : res.data,
    err => Promise.reject(err.response?.data ?? err)
  )
  return client
}

export const apiClient   = addInterceptors(axios.create({ baseURL: '/api/v1' }))
export const apiClientV2 = addInterceptors(axios.create({ baseURL: '/api/v2' }))
