import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { useTranslation } from 'react-i18next'
import { modelApi } from '@/api/ontologies'
import ConfirmDialog from '@/components/ConfirmDialog'
import type { ModelConfig } from '@/types/ontology'
import { Trash2, TestTube2, Plus } from 'lucide-react'

const USAGE_TAGS = ['VLM提取', '结构化提取', '宽表分析', 'Ontology Mapping', 'NL-to-Cypher']

export default function ModelsPage() {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [showCreate, setShowCreate] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState<ModelConfig | null>(null)
  const [testResult, setTestResult] = useState<Record<string, string>>({})
  const [formTags, setFormTags] = useState<string[]>([])
  const { register, handleSubmit, reset, watch } = useForm<any>()
  const modelsField = watch('models_str', '')

  const { data: models = [], isLoading } = useQuery({
    queryKey: ['models'],
    queryFn: () => modelApi.list() as any,
  })

  const createMut = useMutation({
    mutationFn: (data: any) => modelApi.create({
      ...data,
      models: data.models_str ? data.models_str.split('\n').map((s: string) => s.trim()).filter(Boolean) : [],
      usage_tags: formTags,
    }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['models'] }); setShowCreate(false); reset(); setFormTags([]) },
  })

  const deleteMut = useMutation({
    mutationFn: (id: string) => modelApi.delete(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['models'] }); setDeleteTarget(null) },
  })

  const testMut = useMutation({
    mutationFn: (id: string) => modelApi.test(id),
    onSuccess: (res: any, id) => setTestResult(prev => ({ ...prev, [id]: t('model.test_success') })),
    onError: (err: any, id) => setTestResult(prev => ({ ...prev, [id]: t('model.test_failed', { error: err?.detail || t('model.connection_failed') }) })),
  })

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-semibold">{t('model.title')}</h2>
        <button onClick={() => { setShowCreate(true); reset(); setFormTags([]) }}
          className="flex items-center gap-2 bg-black text-white px-4 py-2 rounded-lg text-sm">
          <Plus size={14} /> {t('model.create')}
        </button>
      </div>

      <div className="grid gap-4">
        {isLoading ? <p className="text-gray-400 text-sm">{t('common.loading')}</p> :
          (models as ModelConfig[]).map(m => (
            <div key={m.id} className="bg-white border rounded-lg p-4">
              <div className="flex items-start justify-between">
                <div>
                  <h3 className="font-semibold">{m.name}</h3>
                  <p className="text-sm text-gray-500">{m.provider}{m.api_base ? ` · ${m.api_base}` : ''}</p>
                  {m.models?.length > 0 && (
                    <div className="flex gap-1 mt-2 flex-wrap">
                      {m.models.map(mn => (
                        <span key={mn} className="bg-gray-100 text-gray-700 text-xs px-2 py-0.5 rounded">{mn}</span>
                      ))}
                    </div>
                  )}
                  {((m as any).usage_tags || []).length > 0 && (
                    <div className="flex gap-1 flex-wrap mt-1">
                      {((m as any).usage_tags || []).map((tag: string) => (
                        <span key={tag} className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full">{tag}</span>
                      ))}
                    </div>
                  )}
                  {testResult[m.id] && (
                    <p className={`text-xs mt-1 ${testResult[m.id].startsWith('✓') ? 'text-green-600' : 'text-red-500'}`}>
                      {testResult[m.id]}
                    </p>
                  )}
                </div>
                <div className="flex gap-2">
                  <button onClick={() => testMut.mutate(m.id)} disabled={testMut.isPending}
                    className="p-1.5 border rounded hover:bg-gray-50" title="测试连接">
                    <TestTube2 size={14} />
                  </button>
                  <button onClick={() => setDeleteTarget(m)} className="p-1.5 border rounded hover:bg-gray-50 text-red-500">
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>
            </div>
          ))
        }
        {!isLoading && (models as ModelConfig[]).length === 0 && (
          <div className="bg-white border rounded-lg p-8 text-center text-gray-400">
            {t('model.empty')}
          </div>
        )}
      </div>

      {showCreate && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-lg p-6 w-[480px] max-h-screen overflow-y-auto">
            <h3 className="font-semibold mb-4">{t('model.create')}</h3>
            <form onSubmit={handleSubmit(d => createMut.mutate(d))} className="space-y-3">
              <div>
                <label className="block text-sm font-medium mb-1">{t('model.name')} *</label>
                <input {...register('name', { required: true })} className="w-full border rounded-lg px-3 py-2 text-sm" />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">{t('model.provider')} *</label>
                <select {...register('provider', { required: true })} className="w-full border rounded-lg px-3 py-2 text-sm">
                  <option value="openai">OpenAI</option>
                  <option value="anthropic">Anthropic</option>
                  <option value="compatible">OpenAI-Compatible</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">{t('model.api_key')}</label>
                <input {...register('api_key')} type="password" className="w-full border rounded-lg px-3 py-2 text-sm" />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">{t('model.api_base')}</label>
                <input {...register('api_base')} placeholder="https://api.openai.com/v1" className="w-full border rounded-lg px-3 py-2 text-sm" />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">{t('model.models')} {t('model.per_line')}</label>
                <textarea {...register('models_str')} rows={4} placeholder={"gpt-4o\ngpt-4o-mini"}
                  className="w-full border rounded-lg px-3 py-2 text-sm font-mono resize-none" />
              </div>
              <div>
                <label className="text-xs text-gray-500 mb-2 block">用途标签（可多选）</label>
                <div className="flex flex-wrap gap-2">
                  {USAGE_TAGS.map(tag => {
                    const selected = formTags.includes(tag)
                    return (
                      <button
                        key={tag}
                        type="button"
                        onClick={() => setFormTags(prev =>
                          selected ? prev.filter(t => t !== tag) : [...prev, tag]
                        )}
                        className={`text-xs px-3 py-1.5 rounded-full border transition-colors ${
                          selected ? 'bg-black text-white border-black' : 'border-gray-200 text-gray-600 hover:bg-gray-50'
                        }`}
                      >
                        {tag}
                      </button>
                    )
                  })}
                </div>
              </div>
              <div className="flex justify-end gap-3 pt-2">
                <button type="button" onClick={() => setShowCreate(false)} className="px-4 py-2 border rounded-lg text-sm">{t('common.cancel')}</button>
                <button type="submit" disabled={createMut.isPending} className="px-4 py-2 bg-black text-white rounded-lg text-sm">{t('common.save')}</button>
              </div>
            </form>
          </div>
        </div>
      )}

      <ConfirmDialog
        open={!!deleteTarget}
        title={t('model.confirm_delete')}
        message={t('model.confirm_delete_msg', { name: deleteTarget?.name })}
        onConfirm={() => deleteTarget && deleteMut.mutate(deleteTarget.id)}
        onCancel={() => setDeleteTarget(null)}
      />
    </div>
  )
}
