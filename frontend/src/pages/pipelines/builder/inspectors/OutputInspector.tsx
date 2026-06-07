import { useState, useEffect } from 'react'
import { Eye, Database, ExternalLink, Loader2 } from 'lucide-react'
import { apiClientV2 } from '@/api/client'

export default function OutputInspector({
  config, onChange,
}: {
  config: Record<string, unknown>
  onChange: (key: string, value: unknown) => void
}) {
  const curatedId = (config as any).curated_dataset_id
  const [preview, setPreview] = useState<any[] | null>(null)
  const [previewLoading, setPreviewLoading] = useState(false)
  const [datasetInfo, setDatasetInfo] = useState<{ name: string; rows: number } | null>(null)

  // 如果有 curated_dataset_id，自动加载数据集信息
  useEffect(() => {
    if (!curatedId) return
    setPreviewLoading(true)
    Promise.all([
      apiClientV2.get(`/curated/${curatedId}`).catch(() => null),
      apiClientV2.get(`/datasets/${curatedId}/versions`).catch(() => null),
    ]).then(([info, versions]: any) => {
      if (info) setDatasetInfo({ name: info.name || '', rows: info.row_count || 0 })
      if (versions && versions.length > 0) {
        const vno = versions[0].version_no
        apiClientV2.get(`/datasets/${curatedId}/versions/${vno}/preview?limit=5`)
          .then((d: any) => setPreview(Array.isArray(d) ? d : []))
          .catch(() => {})
      }
    }).finally(() => setPreviewLoading(false))
  }, [curatedId])

  return (
    <>
      {curatedId && (
        <div className="bg-green-50 border border-green-200 rounded-lg p-3 space-y-2">
          <div className="flex items-center gap-1.5 text-xs text-green-700 font-medium">
            <Database size={12} /> 已生成 Curated Dataset
          </div>
          {datasetInfo && (
            <div className="text-xs text-green-600 space-y-0.5">
              <p>名称: {datasetInfo.name}</p>
              <p>行数: {datasetInfo.rows}</p>
            </div>
          )}
          <p className="text-[10px] text-green-500 font-mono break-all">{curatedId}</p>
          {previewLoading ? (
            <div className="flex items-center gap-1 text-xs text-gray-400"><Loader2 size={10} className="animate-spin" /> 加载预览...</div>
          ) : preview && preview.length > 0 ? (
            <div className="bg-white rounded border text-[10px] max-h-28 overflow-y-auto">
              <div className="text-gray-500 px-2 py-1 border-b font-medium">数据预览 ({preview.length} 行)</div>
              {preview.slice(0, 3).map((row: any, i: number) => (
                <div key={i} className="px-2 py-0.5 border-b last:border-0 truncate text-gray-600">
                  {JSON.stringify(row).slice(0, 100)}
                </div>
              ))}
            </div>
          ) : (
            <p className="text-[10px] text-green-400">暂无预览数据</p>
          )}
        </div>
      )}

      <div>
        <label className="text-xs text-gray-500 mb-1 block">输出类型</label>
        <select
          value={String(config.dataset_type || 'curated_dataset')}
          onChange={e => onChange('dataset_type', e.target.value)}
          className="w-full border rounded-lg px-3 py-1.5 text-sm"
        >
          <option value="curated_dataset">Curated Dataset</option>
        </select>
      </div>
      <div>
        <label className="text-xs text-gray-500 mb-1 block">主键字段</label>
        <input
          value={String((config.primary_key as string[])?.join(', ') || '')}
          onChange={e => onChange('primary_key', e.target.value.split(',').map(s => s.trim()))}
          placeholder="例：order_id"
          className="w-full border rounded-lg px-3 py-1.5 text-sm"
        />
      </div>
      <div>
        <label className="text-xs text-gray-500 mb-1 block">需要审核</label>
        <label className="flex items-center gap-2 text-sm cursor-pointer">
          <input type="checkbox" checked={config.review_required !== false}
            onChange={e => onChange('review_required', e.target.checked)} className="accent-black" />
          <span className="text-xs">输出后需要人工审核</span>
        </label>
      </div>
    </>
  )
}
