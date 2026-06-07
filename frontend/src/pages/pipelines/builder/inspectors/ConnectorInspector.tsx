import { useState, useCallback } from 'react'
import { useDropzone } from 'react-dropzone'
import { Upload, X, FileUp, Loader2, CheckCircle, XCircle } from 'lucide-react'
import { apiClientV2 } from '@/api/client'

const SOURCE_LABEL: Record<string, string> = {
  file: '文件上传', postgresql: 'PostgreSQL', mysql: 'MySQL',
  mongodb: 'MongoDB', rest_api: 'REST API',
}

const DB_CONFIG_FIELDS: Record<string, { key: string; label: string; placeholder: string; type?: string }[]> = {
  postgresql: [
    { key: 'host', label: '主机', placeholder: 'localhost' },
    { key: 'port', label: '端口', placeholder: '5432' },
    { key: 'database', label: '数据库名', placeholder: 'mydb' },
    { key: 'user', label: '用户名', placeholder: 'postgres' },
    { key: 'password', label: '密码', placeholder: '••••••', type: 'password' },
  ],
  mysql: [
    { key: 'host', label: '主机', placeholder: 'localhost' },
    { key: 'port', label: '端口', placeholder: '3306' },
    { key: 'database', label: '数据库名', placeholder: 'mydb' },
    { key: 'user', label: '用户名', placeholder: 'root' },
    { key: 'password', label: '密码', placeholder: '••••••', type: 'password' },
  ],
  mongodb: [
    { key: 'uri', label: '连接字符串', placeholder: 'mongodb://localhost:27017/mydb' },
  ],
  rest_api: [
    { key: 'url', label: 'API URL', placeholder: 'https://api.example.com/data' },
    { key: 'headers', label: '请求头 (JSON)', placeholder: '{"Authorization": "Bearer token"}' },
    { key: 'method', label: '请求方法', placeholder: 'GET' },
  ],
}

export default function ConnectorInspector({
  config, onChange,
}: {
  config: Record<string, unknown>
  onChange: (key: string, value: unknown) => void
}) {
  const sourceType = String(config.source_type || 'file')
  const cv = (config.config_values || {}) as Record<string, string>
  const storedFiles = (config.files || []) as Array<{ name: string; size: number }>
  const [dragFiles, setDragFiles] = useState<File[]>([])
  const [testStatus, setTestStatus] = useState<'idle' | 'testing' | 'success' | 'failed'>('idle')
  const [testMessage, setTestMessage] = useState('')

  const onDrop = useCallback((accepted: File[]) => {
    const newFiles = [...dragFiles, ...accepted]
    setDragFiles(newFiles)
    onChange('files', newFiles.map(f => ({ name: f.name, size: f.size })))
  }, [dragFiles, onChange])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({ onDrop, multiple: true })

  const removeFile = (idx: number) => {
    const newFiles = dragFiles.filter((_, i) => i !== idx)
    setDragFiles(newFiles)
    onChange('files', newFiles.map(f => ({ name: f.name, size: f.size })))
  }

  const handleTestConnection = async () => {
    setTestStatus('testing'); setTestMessage('')
    try {
      if (sourceType === 'file') {
        setTestStatus(dragFiles.length > 0 || storedFiles.length > 0 ? 'success' : 'failed')
        setTestMessage(dragFiles.length > 0 || storedFiles.length > 0 ? '文件已就绪' : '请先上传文件')
        return
      }
      await apiClientV2.post('/connections/test-config', { type: sourceType, config: cv })
      setTestStatus('success'); setTestMessage('连接成功')
    } catch (e: unknown) {
      setTestStatus('failed')
      const err = e as { detail?: string; message?: string }
      setTestMessage(err?.detail || err?.message || '连接失败')
    }
  }

  // 有存储配置时显示摘要
  const hasStoredConfig = (sourceType && sourceType !== 'file') ? Object.keys(cv).length > 0 : storedFiles.length > 0

  return (
    <>
      {/**** 已保存的配置摘要 ****/}
      {hasStoredConfig && (
        <div className="bg-blue-50 border border-blue-100 rounded-lg p-2.5 text-xs space-y-0.5">
          <p className="text-blue-700 font-medium mb-1">📋 已保存配置</p>
          <p className="text-blue-600">类型: {SOURCE_LABEL[sourceType] || sourceType}</p>
          {sourceType === 'file' && storedFiles.map((f, i) => (
            <p key={i} className="text-blue-500 truncate">📄 {f.name} ({(f.size / 1024).toFixed(1)} KB)</p>
          ))}
          {sourceType !== 'file' && Object.entries(cv).map(([k, v]) => (
            k !== 'password' ? <p key={k} className="text-blue-500">{k}: {String(v).slice(0, 30)}</p> :
            <p key={k} className="text-blue-500">{k}: ••••••</p>
          ))}
        </div>
      )}

      {/**** 数据源类型选择 ****/}
      <div>
        <label className="text-xs text-gray-500 mb-1 block">数据源类型</label>
        <select value={sourceType}
          onChange={e => { onChange('source_type', e.target.value); onChange('config_values', {}); setDragFiles([]); setTestStatus('idle') }}
          className="w-full border rounded-lg px-3 py-1.5 text-sm">
          <option value="file">文件上传</option>
          <option value="postgresql">PostgreSQL</option>
          <option value="mysql">MySQL</option>
          <option value="mongodb">MongoDB</option>
          <option value="rest_api">REST API</option>
        </select>
      </div>

      {/**** 文件上传模式 ****/}
      {sourceType === 'file' && (
        <div>
          <label className="text-xs text-gray-500 mb-1 block">上传文件</label>
          <div {...getRootProps()}
            className={`border-2 border-dashed rounded-lg p-4 text-center cursor-pointer transition-colors ${isDragActive ? 'border-blue-500 bg-blue-50' : 'border-gray-200 hover:border-gray-400'}`}>
            <input {...getInputProps()} />
            <Upload size={20} className="mx-auto mb-1 text-gray-400" />
            {isDragActive ? <p className="text-xs text-blue-500 font-medium">松开以添加文件</p> : (
              <><p className="text-xs text-gray-500">拖拽文件到此处</p>
              <p className="text-xs text-gray-400 mt-0.5">或<span className="underline ml-0.5 cursor-pointer">点击选择</span></p></>
            )}
          </div>
          {(dragFiles.length > 0 || storedFiles.length > 0) && (
            <div className="mt-2 space-y-1">
              {(sourceType !== 'file' ? dragFiles : [...storedFiles, ...dragFiles]).map((f: any, i: number) => (
                <div key={i} className="flex items-center gap-2 text-xs bg-gray-50 rounded px-2 py-1.5">
                  <FileUp size={11} className="text-gray-400 shrink-0" />
                  <span className="flex-1 truncate text-gray-700">{f.name}</span>
                  <span className="text-gray-400 shrink-0">{(f.size / 1024).toFixed(1)} KB</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/**** 数据库/API 配置参数 ****/}
      {sourceType !== 'file' && (
        <div className="space-y-3">
          {DB_CONFIG_FIELDS[sourceType]?.map(field => (
            <div key={field.key}>
              <label className="text-xs text-gray-500 mb-1 block">{field.label}</label>
              <input type={field.type || 'text'}
                value={String((config as any).config_values?.[field.key] || '')}
                onChange={e => {
                  const cv2 = { ...((config as any).config_values || {}), [field.key]: e.target.value }
                  onChange('config_values', cv2); setTestStatus('idle')
                }}
                placeholder={field.placeholder} className="w-full border rounded-lg px-3 py-1.5 text-sm" />
            </div>
          ))}
        </div>
      )}

      {/**** 测试连接 按钮 ****/}
      <div>
        <button onClick={handleTestConnection} disabled={testStatus === 'testing'}
          className={`w-full flex items-center justify-center gap-1.5 px-3 py-1.5 text-xs rounded-lg border transition-colors ${
            testStatus === 'success' ? 'bg-green-50 text-green-700 border-green-200' :
            testStatus === 'failed' ? 'bg-red-50 text-red-700 border-red-200' :
            'bg-white text-gray-600 border-gray-200 hover:bg-gray-50'}`}>
          {testStatus === 'testing' && <Loader2 size={11} className="animate-spin" />}
          {testStatus === 'success' && <CheckCircle size={11} />}
          {testStatus === 'failed' && <XCircle size={11} />}
          {testStatus === 'testing' ? '测试中...' : testStatus === 'success' ? '连接成功' : testStatus === 'failed' ? testMessage : '测试连接'}
        </button>
      </div>

      {/**** 同步模式 ****/}
      <div>
        <label className="text-xs text-gray-500 mb-1 block">同步模式</label>
        <select value={String(config.sync_mode || 'snapshot')}
          onChange={e => onChange('sync_mode', e.target.value)}
          className="w-full border rounded-lg px-3 py-1.5 text-sm">
          <option value="snapshot">SNAPSHOT（全量覆盖）</option>
          <option value="append">APPEND（增量追加）</option>
        </select>
      </div>
    </>
  )
}
