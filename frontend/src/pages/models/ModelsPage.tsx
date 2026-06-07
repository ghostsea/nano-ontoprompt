import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { useTranslation } from 'react-i18next'
import { modelApi } from '@/api/ontologies'
import ConfirmDialog from '@/components/ConfirmDialog'
import type { ModelConfig } from '@/types/ontology'
import { Trash2, TestTube2, Plus, Pencil, X, Loader2 } from 'lucide-react'

const USAGE_TAGS = ['VLM提取', '结构化提取', '宽表分析', 'Ontology Mapping', 'NL-to-Cypher']

export default function ModelsPage() {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const [showCreate, setShowCreate] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState<ModelConfig | null>(null)
  const [testResult, setTestResult] = useState<Record<string, string>>({})
  const [formTags, setFormTags] = useState<string[]>([])
  const { register, handleSubmit, reset, watch } = useForm<any>()

  const { data: models = [], isLoading } = useQuery({
    queryKey: ['models'], queryFn: () => modelApi.list() as any,
  })

  const createMut = useMutation({
    mutationFn: (data: any) => modelApi.create({
      ...data, models: data.models_str ? data.models_str.split('\n').map((s: string) => s.trim()).filter(Boolean) : [], usage_tags: formTags,
    }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['models'] }); setShowCreate(false); reset(); setFormTags([]) },
  })

  const deleteMut = useMutation({
    mutationFn: (id: string) => modelApi.delete(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['models'] }); setDeleteTarget(null) },
  })

  const testMut = useMutation({
    mutationFn: (id: string) => modelApi.test(id),
    onSuccess: (res: any, id) => setTestResult(prev => ({ ...prev, [id]: '✅ 连接成功' })),
    onError: (err: any, id) => setTestResult(prev => ({ ...prev, [id]: `❌ ${err?.detail || '连接失败'}` })),
  })

  // ── 编辑 ──
  const [editTarget, setEditTarget] = useState<ModelConfig | null>(null)
  const [editTags, setEditTags] = useState<string[]>([])
  const { register: regEdit, handleSubmit: handleEditSubmit, setValue } = useForm<any>()

  const updateMut = useMutation({
    mutationFn: ({ id, data }: { id: string; data: any }) => modelApi.update(id, {
      ...data, models: data.models_str ? data.models_str.split('\n').map((s: string) => s.trim()).filter(Boolean) : [], usage_tags: editTags,
    }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['models'] }); setEditTarget(null); setEditTags([]) },
  })

  const openEdit = (m: ModelConfig) => {
    setEditTarget(m); setEditTags((m as any).usage_tags || [])
    setValue('name', m.name); setValue('provider', m.provider)
    setValue('api_base', m.api_base || '')
    setValue('models_str', (m.models || []).join('\n'))
  }

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
                      {m.models.map(mn => <span key={mn} className="bg-gray-100 text-gray-700 text-xs px-2 py-0.5 rounded">{mn}</span>)}
                    </div>
                  )}
                  {((m as any).usage_tags || []).length > 0 && (
                    <div className="flex gap-1 flex-wrap mt-1">
                      {((m as any).usage_tags || []).map((tag: string) => (
                        <span key={tag} className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full">{tag}</span>
                      ))}
                    </div>
                  )}
                  {testResult[m.id] && <p className={`text-xs mt-1 ${testResult[m.id].startsWith('✅') ? 'text-green-600' : 'text-red-500'}`}>{testResult[m.id]}</p>}
                </div>
                <div className="flex gap-2">
                  <button onClick={() => testMut.mutate(m.id)} disabled={testMut.isPending} className="p-1.5 border rounded hover:bg-gray-50" title="测试连接"><TestTube2 size={14} /></button>
                  <button onClick={() => openEdit(m)} className="p-1.5 border rounded hover:bg-gray-50 text-blue-600" title="编辑"><Pencil size={14} /></button>
                  <button onClick={() => setDeleteTarget(m)} className="p-1.5 border rounded hover:bg-gray-50 text-red-500"><Trash2 size={14} /></button>
                </div>
              </div>
            </div>
          ))
        }
        {!isLoading && (models as ModelConfig[]).length === 0 && (
          <div className="bg-white border rounded-lg p-8 text-center text-gray-400">{t('model.empty')}</div>
        )}
      </div>

      {/* 新建弹窗 */}
      {showCreate && <ModelFormModal title="新建模型" onClose={() => setShowCreate(false)} onSubmit={d => createMut.mutate(d)}
        isPending={createMut.isPending} formTags={formTags} setFormTags={setFormTags} register={register}
        handleSubmit={handleSubmit} reset={reset} />}

      {/* 编辑弹窗 */}
      {editTarget && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={() => setEditTarget(null)}>
          <div className="bg-white rounded-lg shadow-lg p-6 w-[480px]" onClick={e => e.stopPropagation()}>
            <div className="flex justify-between items-center mb-4">
              <h3 className="font-semibold">编辑模型</h3>
              <button onClick={() => setEditTarget(null)} className="text-gray-400 hover:text-black"><X size={16} /></button>
            </div>
            <form onSubmit={handleEditSubmit(d => updateMut.mutate({ id: editTarget.id, data: d }))} className="space-y-3">
              <div><label className="block text-sm font-medium mb-1">名称 *</label>
                <input {...regEdit('name', { required: true })} className="w-full border rounded-lg px-3 py-2 text-sm" /></div>
              <div><label className="block text-sm font-medium mb-1">Provider *</label>
                <select {...regEdit('provider', { required: true })} className="w-full border rounded-lg px-3 py-2 text-sm">
                  <option value="openai">OpenAI</option>
                  <option value="anthropic">Anthropic</option>
                  <option value="compatible">OpenAI-Compatible</option>
                </select></div>
              <div><label className="block text-sm font-medium mb-1">API Base</label>
                <input {...regEdit('api_base')} className="w-full border rounded-lg px-3 py-2 text-sm" /></div>
              <div><label className="block text-sm font-medium mb-1">模型名（每行一个）</label>
                <textarea {...regEdit('models_str')} rows={3} className="w-full border rounded-lg px-3 py-2 text-sm font-mono" /></div>
              <div><label className="text-xs text-gray-500 mb-2 block">用途标签</label>
                <div className="flex flex-wrap gap-2">
                  {USAGE_TAGS.map(tag => {
                    const sel = editTags.includes(tag)
                    return <button key={tag} type="button" onClick={() => setEditTags(prev => sel ? prev.filter(t => t !== tag) : [...prev, tag])}
                      className={`text-xs px-3 py-1.5 rounded-full border ${sel ? 'bg-black text-white border-black' : 'border-gray-200 text-gray-600'}`}>{tag}</button>
                  })}
                </div></div>
              <div className="flex justify-end gap-3 pt-2">
                <button type="button" onClick={() => setEditTarget(null)} className="px-4 py-2 border rounded-lg text-sm">取消</button>
                <button type="submit" disabled={updateMut.isPending} className="flex items-center gap-1.5 px-4 py-2 bg-black text-white rounded-lg text-sm disabled:opacity-50">
                  {updateMut.isPending && <Loader2 size={13} className="animate-spin" />}保存
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      <ConfirmDialog open={!!deleteTarget} title={t('model.confirm_delete')} message={t('model.confirm_delete_msg', { name: deleteTarget?.name })}
        onConfirm={() => deleteTarget && deleteMut.mutate(deleteTarget.id)} onCancel={() => setDeleteTarget(null)} />
    </div>
  )
}

/** 新建模型表单弹窗 */
function ModelFormModal({ title, onClose, onSubmit, isPending, formTags, setFormTags, register, handleSubmit, reset }: any) {
  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={onClose}>
      <div className="bg-white rounded-lg shadow-lg p-6 w-[480px]" onClick={e => e.stopPropagation()}>
        <h3 className="font-semibold mb-4">{title}</h3>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-3">
          <div><label className="block text-sm font-medium mb-1">名称 *</label>
            <input {...register('name', { required: true })} className="w-full border rounded-lg px-3 py-2 text-sm" /></div>
          <div><label className="block text-sm font-medium mb-1">Provider *</label>
            <select {...register('provider', { required: true })} className="w-full border rounded-lg px-3 py-2 text-sm">
              <option value="openai">OpenAI</option><option value="anthropic">Anthropic</option><option value="compatible">OpenAI-Compatible</option>
            </select></div>
          <div><label className="block text-sm font-medium mb-1">API Key</label>
            <input {...register('api_key')} type="password" className="w-full border rounded-lg px-3 py-2 text-sm" /></div>
          <div><label className="block text-sm font-medium mb-1">API Base</label>
            <input {...register('api_base')} placeholder="https://api.openai.com/v1" className="w-full border rounded-lg px-3 py-2 text-sm" /></div>
          <div><label className="block text-sm font-medium mb-1">模型名（每行一个）</label>
            <textarea {...register('models_str')} rows={3} placeholder="gpt-4o&#10;gpt-4o-mini" className="w-full border rounded-lg px-3 py-2 text-sm font-mono" /></div>
          <div><label className="text-xs text-gray-500 mb-2 block">用途标签</label>
            <div className="flex flex-wrap gap-2">{[...USAGE_TAGS].map(tag => {
              const sel = formTags.includes(tag)
              return <button key={tag} type="button" onClick={() => setFormTags((prev: string[]) => sel ? prev.filter((t: string) => t !== tag) : [...prev, tag])}
                className={`text-xs px-3 py-1.5 rounded-full border ${sel ? 'bg-black text-white border-black' : 'border-gray-200 text-gray-600 hover:bg-gray-50'}`}>{tag}</button>
            })}</div></div>
          <div className="flex justify-end gap-3 pt-2">
            <button type="button" onClick={onClose} className="px-4 py-2 border rounded-lg text-sm">取消</button>
            <button type="submit" disabled={isPending} className="flex items-center gap-1.5 px-4 py-2 bg-black text-white rounded-lg text-sm disabled:opacity-50">
              {isPending && <Loader2 size={13} className="animate-spin" />}保存
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
