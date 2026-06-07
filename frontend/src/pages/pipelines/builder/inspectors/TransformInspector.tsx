import { useState, useMemo, useEffect } from 'react'
import { Plus, Trash2, Eye, Loader2, AlertTriangle, ExternalLink } from 'lucide-react'
import { apiClientV2 } from '@/api/client'

/** 所有可用的 Transform 步骤，按路径分类 */
const AVAILABLE_OPS = [
  // Path A: 结构化
  { op: 'rename_columns', label: '重命名列', path: 'A', enabled: true },
  { op: 'drop_nulls', label: '删除空值行', path: 'A', enabled: true },
  { op: 'fill_nulls', label: '填充空值', path: 'A', enabled: true },
  { op: 'drop_duplicates', label: '去重', path: 'A', enabled: true },
  { op: 'normalize_dates', label: '日期标准化', path: 'A', enabled: true },
  { op: 'select_columns', label: '选择列', path: 'A', enabled: true },
  { op: 'filter_rows', label: '过滤行', path: 'A', enabled: true },
  { op: 'sort', label: '排序', path: 'A', enabled: true },
  { op: 'join', label: 'Join 关联', path: 'A', enabled: false },
  { op: 'aggregate', label: 'Aggregate 聚合', path: 'A', enabled: false },
  { op: 'group_by', label: 'Group By 分组', path: 'A', enabled: false },
  { op: 'window', label: 'Window 窗口函数', path: 'A', enabled: false },
  { op: 'pivot', label: 'Pivot 透视', path: 'A', enabled: false },
  { op: 'union', label: 'Union 合并', path: 'A', enabled: false },
  // Wide Table Split
  { op: 'detect_wide_table', label: '检测宽表', path: 'WIDE', enabled: true },
  { op: 'suggest_split', label: '建议拆分方案', path: 'WIDE', enabled: true },
  { op: 'apply_split', label: '执行拆分', path: 'WIDE', enabled: true },
  // Path B: 半结构化
  { op: 'parse_json', label: '解析 JSON', path: 'B', enabled: true },
  { op: 'parse_xml', label: '解析 XML', path: 'B', enabled: true },
  { op: 'flatten_json', label: 'JSON Flatten 摊平', path: 'B', enabled: true },
  { op: 'explode_array', label: '数组 Explode', path: 'B', enabled: true },
  { op: 'extract_field', label: 'Extract Field 字段提取', path: 'B', enabled: false },
  { op: 'schema_inference', label: 'Schema Inference 推断', path: 'B', enabled: false },
  // Path C: 非结构化
  { op: 'document_to_markdown', label: '文档转 Markdown', path: 'C', enabled: true },
  { op: 'ocr_extract', label: 'OCR 文字提取', path: 'C', enabled: true },
  { op: 'vlm_extract', label: 'VLM 视觉提取', path: 'C', enabled: true },
  { op: 'llm_structurize', label: 'LLM 结构化提取', path: 'C', enabled: true },
  { op: 'chunking', label: 'Chunking 文档分块', path: 'C', enabled: false },
  { op: 'entity_extraction', label: 'Entity Extraction 实体提取', path: 'C', enabled: false },
  { op: 'classification', label: 'Classification 分类', path: 'C', enabled: false },
  { op: 'embedding', label: 'Embedding 向量化', path: 'C', enabled: false },
  { op: 'summarization', label: 'Summarization 摘要', path: 'C', enabled: false },
]

/** 路径 → 可用步骤的映射表 */
const PATH_OPS_MAP: Record<string, typeof AVAILABLE_OPS> = {
  auto: AVAILABLE_OPS,
  structured: AVAILABLE_OPS.filter(o => o.path === 'A'),
  semi_structured: AVAILABLE_OPS.filter(o => o.path === 'B'),
  unstructured: AVAILABLE_OPS.filter(o => o.path === 'C'),
  wide_table: AVAILABLE_OPS.filter(o => o.path === 'WIDE'),
}

/** 路径中文名 */
const PATH_LABEL: Record<string, string> = {
  auto: '全部路径',
  structured: 'Path A · 结构化',
  semi_structured: 'Path B · 半结构化',
  unstructured: 'Path C · 非结构化',
  wide_table: '宽表拆分',
}

export default function TransformInspector({
  config, onChange, nodeId,
}: {
  config: Record<string, unknown>
  onChange: (key: string, value: unknown) => void
  nodeId: string
}) {
  const currentPath = String(config.path || 'auto')
  const steps = (config.steps || []) as Array<{ op: string; params?: Record<string, unknown> }>
  const [showCatalog, setShowCatalog] = useState(false)

  // 根据当前路径筛选可用步骤
  const filteredOps = useMemo(() => {
    return PATH_OPS_MAP[currentPath] || AVAILABLE_OPS
  }, [currentPath])

  // ── 模型列表 ──
  const [models, setModels] = useState<Array<{ id: string; name: string; provider: string; models: string[] }>>([])
  useEffect(() => {
    apiClientV2.get('/models').then((r: any) => {
      const list = Array.isArray(r) ? r : r?.data ?? []
      setModels(list)
    }).catch(() => {})
  }, [])

  const addStep = (op: string) => {
    const newSteps = [...steps, { op, params: {} }]
    onChange('steps', newSteps)
    setShowCatalog(false)
  }

  const removeStep = (idx: number) => {
    const newSteps = steps.filter((_, i) => i !== idx)
    onChange('steps', newSteps)
  }

  const updateStepParam = (idx: number, key: string, value: unknown) => {
    const newSteps = [...steps]
    newSteps[idx] = { ...newSteps[idx], params: { ...(newSteps[idx].params || {}), [key]: value } }
    onChange('steps', newSteps)
  }

  // ── 步骤预览 ────────────────────────────────────────────
  const [previewMap, setPreviewMap] = useState<Record<number, { loading: boolean; data?: any[]; error?: string }>>({})

  const handlePreview = async (idx: number, op: string) => {
    setPreviewMap(p => ({ ...p, [idx]: { loading: true } }))
    try {
      const result: any = await apiClientV2.post('/pipelines/preview-step', {
        op,
        params: steps[idx]?.params || {},
        sample_data: [{ col: 'sample1' }, { col: 'sample2' }],
      })
      setPreviewMap(p => ({
        ...p,
        [idx]: { loading: false, data: result.preview || [], error: result.error },
      }))
    } catch {
      setPreviewMap(p => ({ ...p, [idx]: { loading: false, error: '预览请求失败' } }))
    }
  }

  return (
    <>
      {/**** 处理路径选择 ****/}
      <div>
        <label className="text-xs text-gray-500 mb-1 block">处理路径</label>
        <select
          value={currentPath}
          onChange={e => {
            const newPath = e.target.value
            onChange('path', newPath)
            // 切换路径时，清除不兼容的步骤
            const validOps = PATH_OPS_MAP[newPath] || AVAILABLE_OPS
            const validOpNames = new Set(validOps.map(o => o.op))
            const filtered = steps.filter(s => validOpNames.has(s.op))
            if (filtered.length !== steps.length) {
              onChange('steps', filtered)
            }
          }}
          className="w-full border rounded-lg px-3 py-1.5 text-sm"
        >
          <option value="auto">自动检测</option>
          <option value="structured">Path A · 结构化</option>
          <option value="semi_structured">Path B · 半结构化</option>
          <option value="unstructured">Path C · 非结构化</option>
          <option value="wide_table">宽表拆分</option>
        </select>
        {currentPath !== 'auto' && (
          <p className="text-xs text-gray-400 mt-0.5">
            当前: {PATH_LABEL[currentPath]} · {filteredOps.length} 个可用步骤
          </p>
        )}
      </div>

      {/**** 引擎选择 ****/}
      <div>
        <label className="text-xs text-gray-500 mb-1 block">引擎</label>
        <select
          value={String(config.engine || 'pandas')}
          onChange={e => onChange('engine', e.target.value)}
          className="w-full border rounded-lg px-3 py-1.5 text-sm"
        >
          <option value="pandas">pandas</option>
          {currentPath === 'A' && <option value="duckdb">DuckDB（大文件）</option>}
          {(currentPath === 'C' || currentPath === 'auto') && (
            <>
              <option value="llm">LLM（语义提取）</option>
              <option value="vlm">VLM（视觉提取）</option>
              <option value="ocr">OCR（文字识别）</option>
            </>
          )}
          {(currentPath === 'B' || currentPath === 'auto') && (
            <option value="json_engine">JSON/XML 解析引擎</option>
          )}
        </select>

        {/**** LLM/VLM 模型配置提醒与选择 ****/}
        {(String(config.engine) === 'llm' || String(config.engine) === 'vlm') && (
          <div className="mt-1.5 space-y-1">
            {!models.length ? (
              <div className="flex items-start gap-1.5 text-amber-600 bg-amber-50 rounded px-2 py-1.5 text-[10px]">
                <AlertTriangle size={11} className="shrink-0 mt-0.5" />
                <span>
                  未配置 LLM/VLM 模型。
                  <a href="/models" className="underline inline-flex items-center gap-0.5 font-medium">
                    前往模型设置 <ExternalLink size={9} />
                  </a>
                </span>
              </div>
            ) : (
              <div className="p-1.5 bg-gray-50 rounded space-y-1">
                <label className="text-[10px] text-gray-500 block">选择 {String(config.engine) === 'vlm' ? 'VLM' : 'LLM'} 模型</label>
                <select
                  value={String((config as any).model_id || '')}
                  onChange={e => onChange('model_id', e.target.value)}
                  className="w-full border rounded px-2 py-1 text-xs"
                >
                  <option value="">-- 请选择模型 --</option>
                  {models.map(m => (
                    <optgroup key={m.id} label={`${m.name} (${m.provider})`}>
                      {(m.models || []).map((md: string) => (
                        <option key={md} value={`${m.id}:${md}`}>{md}</option>
                      ))}
                    </optgroup>
                  ))}
                </select>
              </div>
            )}
          </div>
        )}

        {/**** OCR 引擎配置 ****/}
        {String(config.engine) === 'ocr' && (
          <div className="mt-1.5 space-y-1.5">
            {!models.length && (
              <div className="flex items-start gap-1.5 text-amber-600 bg-amber-50 rounded px-2 py-1.5 text-[10px]">
                <AlertTriangle size={11} className="shrink-0 mt-0.5" />
                <span>未配置 OCR 模型。</span>
              </div>
            )}
            <div>
              <label className="text-[10px] text-gray-400 mb-0.5 block">OCR 引擎</label>
              <select
                value={String((config as any).ocr_engine || 'paddleocr')}
                onChange={e => onChange('ocr_engine', e.target.value)}
                className="w-full border rounded px-2 py-1 text-xs"
              >
                <option value="paddleocr">PaddleOCR（默认，中文最佳）</option>
                <option value="tesseract">Tesseract（多语言）</option>
                <option value="easyocr">EasyOCR（轻量）</option>
              </select>
            </div>
            <div>
              <label className="text-[10px] text-gray-400 mb-0.5 block">OCR 语言</label>
              <input
                value={String((config as any).ocr_lang || 'chi_sim+eng')}
                onChange={e => onChange('ocr_lang', e.target.value)}
                placeholder="chi_sim+eng"
                className="w-full border rounded px-2 py-1 text-xs"
              />
            </div>
          </div>
        )}
      </div>

      {/**** Transform 步骤列表 ****/}
      <div>
        <div className="flex items-center justify-between mb-1">
          <label className="text-xs text-gray-500">处理步骤</label>
          <button
            onClick={() => setShowCatalog(!showCatalog)}
            className="flex items-center gap-0.5 text-xs text-blue-500 hover:text-blue-700"
          >
            <Plus size={11} /> 添加步骤
          </button>
        </div>

        {showCatalog && (
          <div className="border rounded-lg p-2 mb-2 max-h-40 overflow-y-auto space-y-0.5">
            {filteredOps.length === 0 ? (
              <p className="text-xs text-gray-400 italic px-1">当前路径无可用步骤</p>
            ) : (
              filteredOps.map(op => (
                op.enabled ? (
                  <button
                    key={op.op}
                    onClick={() => addStep(op.op)}
                    className="w-full text-left text-xs px-2 py-1 rounded hover:bg-gray-50 flex items-center gap-2"
                  >
                    <span className="text-gray-300 text-[10px] font-mono">{op.path}</span>
                    <span className="font-medium">{op.label}</span>
                  </button>
                ) : (
                  <div
                    key={op.op}
                    className="w-full text-left text-xs px-2 py-1 rounded flex items-center gap-2 opacity-50"
                    title="即将推出"
                  >
                    <span className="text-gray-300 text-[10px] font-mono">{op.path}</span>
                    <span className="text-gray-400">{op.label}</span>
                    <span className="ml-auto text-[9px] text-gray-400 border border-dashed rounded px-1">即将推出</span>
                  </div>
                )
              ))
            )}
          </div>
        )}

        {steps.length === 0 ? (
          <p className="text-xs text-gray-400 italic">暂无步骤</p>
        ) : (
          <div className="space-y-1.5">
            {steps.map((step, i) => (
              <div key={i} className="border rounded-lg p-2 text-xs space-y-1">
                <div className="flex items-center justify-between">
                  <span className="font-medium">
                    {i + 1}. {AVAILABLE_OPS.find(o => o.op === step.op)?.label || step.op}
                  </span>
                  <div className="flex items-center gap-0.5">
                    <button
                      onClick={() => handlePreview(i, step.op)}
                      className="text-gray-400 hover:text-blue-500 p-0.5"
                      title="预览此步骤输出"
                    >
                      {previewMap[i]?.loading ? <Loader2 size={11} className="animate-spin" /> : <Eye size={11} />}
                    </button>
                    <button
                      onClick={() => removeStep(i)}
                      className="text-gray-400 hover:text-red-500 p-0.5"
                    >
                      <Trash2 size={11} />
                    </button>
                  </div>
                </div>
                {previewMap[i]?.data && (
                  <div className="bg-gray-50 rounded p-1.5 mt-1 max-h-24 overflow-y-auto">
                    <div className="text-[10px] text-gray-500 mb-0.5 font-medium">预览输出 ({previewMap[i]!.data!.length} 行)</div>
                    {previewMap[i]!.data!.slice(0, 5).map((row, ri) => (
                      <div key={ri} className="text-[10px] text-gray-600 truncate">
                        {JSON.stringify(row).slice(0, 80)}
                      </div>
                    ))}
                  </div>
                )}
                {previewMap[i]?.error && (
                  <div className="text-[10px] text-red-400">{previewMap[i]!.error}</div>
                )}

                {/* 各步骤参数配置 */}
                {step.op === 'drop_duplicates' && (
                  <>
                    <input
                      value={String((step.params as any)?.columns || '')}
                      onChange={e => updateStepParam(i, 'columns', e.target.value.split(',').map(s => s.trim()))}
                      placeholder="去重列（逗号分隔）"
                      className="w-full border rounded px-2 py-1 text-xs"
                    />
                    <label className="flex items-center gap-1.5 text-gray-500">
                      <input
                        type="checkbox"
                        checked={(step.params as any)?.keep_first !== false}
                        onChange={e => updateStepParam(i, 'keep_first', e.target.checked)}
                        className="accent-black"
                      />
                      <span>保留首次出现</span>
                    </label>
                  </>
                )}
                {step.op === 'fill_nulls' && (
                  <div className="flex gap-1">
                    <input
                      value={String((step.params as any)?.column || '')}
                      onChange={e => updateStepParam(i, 'column', e.target.value)}
                      placeholder="列名"
                      className="flex-1 border rounded px-2 py-1 text-xs"
                    />
                    <input
                      value={String((step.params as any)?.value || '')}
                      onChange={e => updateStepParam(i, 'value', e.target.value)}
                      placeholder="填充值"
                      className="flex-1 border rounded px-2 py-1 text-xs"
                    />
                  </div>
                )}
                {step.op === 'rename_columns' && (
                  <div className="flex gap-1">
                    <input
                      value={String((step.params as any)?.old_name || '')}
                      onChange={e => updateStepParam(i, 'old_name', e.target.value)}
                      placeholder="原列名"
                      className="flex-1 border rounded px-2 py-1 text-xs"
                    />
                    <span className="text-gray-400 self-center">→</span>
                    <input
                      value={String((step.params as any)?.new_name || '')}
                      onChange={e => updateStepParam(i, 'new_name', e.target.value)}
                      placeholder="新列名"
                      className="flex-1 border rounded px-2 py-1 text-xs"
                    />
                  </div>
                )}
                {step.op === 'select_columns' && (
                  <input
                    value={String((step.params as any)?.columns || '')}
                    onChange={e => updateStepParam(i, 'columns', e.target.value.split(',').map(s => s.trim()))}
                    placeholder="选择的列名（逗号分隔）"
                    className="w-full border rounded px-2 py-1 text-xs"
                  />
                )}
                {step.op === 'filter_rows' && (
                  <div className="flex gap-1">
                    <input
                      value={String((step.params as any)?.column || '')}
                      onChange={e => updateStepParam(i, 'column', e.target.value)}
                      placeholder="列名"
                      className="flex-1 border rounded px-2 py-1 text-xs"
                    />
                    <input
                      value={String((step.params as any)?.value || '')}
                      onChange={e => updateStepParam(i, 'value', e.target.value)}
                      placeholder="过滤值"
                      className="flex-1 border rounded px-2 py-1 text-xs"
                    />
                    <select
                      value={String((step.params as any)?.operator || 'eq')}
                      onChange={e => updateStepParam(i, 'operator', e.target.value)}
                      className="border rounded px-1 py-1 text-xs"
                    >
                      <option value="eq">=</option>
                      <option value="neq">≠</option>
                      <option value="gt">&gt;</option>
                      <option value="lt">&lt;</option>
                      <option value="contains">包含</option>
                    </select>
                  </div>
                )}
                {step.op === 'sort' && (
                  <div className="flex gap-1">
                    <input
                      value={String((step.params as any)?.column || '')}
                      onChange={e => updateStepParam(i, 'column', e.target.value)}
                      placeholder="排序列"
                      className="flex-1 border rounded px-2 py-1 text-xs"
                    />
                    <select
                      value={String((step.params as any)?.direction || 'asc')}
                      onChange={e => updateStepParam(i, 'direction', e.target.value)}
                      className="border rounded px-1 py-1 text-xs"
                    >
                      <option value="asc">升序</option>
                      <option value="desc">降序</option>
                    </select>
                  </div>
                )}
                {step.op === 'normalize_dates' && (
                  <input
                    value={String((step.params as any)?.columns || '')}
                    onChange={e => updateStepParam(i, 'columns', e.target.value.split(',').map(s => s.trim()))}
                    placeholder="日期列（逗号分隔）"
                    className="w-full border rounded px-2 py-1 text-xs"
                  />
                )}
                {step.op === 'parse_json' && (
                  <input
                    value={String((step.params as any)?.column || 'raw_json')}
                    onChange={e => updateStepParam(i, 'column', e.target.value)}
                    placeholder="JSON 列名"
                    className="w-full border rounded px-2 py-1 text-xs"
                  />
                )}
                {step.op === 'parse_xml' && (
                  <div className="flex gap-1">
                    <input
                      value={String((step.params as any)?.column || 'raw_xml')}
                      onChange={e => updateStepParam(i, 'column', e.target.value)}
                      placeholder="XML 列名"
                      className="flex-1 border rounded px-2 py-1 text-xs"
                    />
                    <input
                      value={String((step.params as any)?.row_path || '')}
                      onChange={e => updateStepParam(i, 'row_path', e.target.value)}
                      placeholder="行路径"
                      className="flex-1 border rounded px-2 py-1 text-xs"
                    />
                  </div>
                )}
                {step.op === 'document_to_markdown' && (
                  <div className="space-y-1">
                    <input
                      value={String((step.params as any)?.path_column || 'storage_path')}
                      onChange={e => updateStepParam(i, 'path_column', e.target.value)}
                      placeholder="文件路径列"
                      className="w-full border rounded px-2 py-1 text-xs"
                    />
                    <select
                      value={String((step.params as any)?.strategy || 'markitdown')}
                      onChange={e => updateStepParam(i, 'strategy', e.target.value)}
                      className="w-full border rounded px-2 py-1 text-xs"
                    >
                      <option value="markitdown">MarkItDown 转换</option>
                      <option value="ocr">OCR 文字识别</option>
                      <option value="vlm">VLM 视觉提取</option>
                    </select>
                  </div>
                )}
                {step.op === 'llm_structurize' && (
                  <div className="space-y-1">
                    <input
                      value={String((step.params as any)?.model_id || '')}
                      onChange={e => updateStepParam(i, 'model_id', e.target.value)}
                      placeholder="模型 ID"
                      className="w-full border rounded px-2 py-1 text-xs"
                    />
                    <input
                      value={String((step.params as any)?.prompt_template || '')}
                      onChange={e => updateStepParam(i, 'prompt_template', e.target.value)}
                      placeholder="提取提示词"
                      className="w-full border rounded px-2 py-1 text-xs"
                    />
                  </div>
                )}
                {step.op === 'apply_split' && (
                  <input
                    value={String((step.params as any)?.output_datasets || '')}
                    onChange={e => updateStepParam(i, 'output_datasets', e.target.value.split(',').map(s => s.trim()))}
                    placeholder="输出数据集名（逗号分隔）"
                    className="w-full border rounded px-2 py-1 text-xs"
                  />
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/**** 错误策略 ****/}
      <div>
        <label className="text-xs text-gray-500 mb-1 block">错误策略</label>
        <select
          value={String(config.error_policy || 'fail_fast')}
          onChange={e => onChange('error_policy', e.target.value)}
          className="w-full border rounded-lg px-3 py-1.5 text-sm"
        >
          <option value="fail_fast">快速失败</option>
          <option value="skip_bad_rows">跳过错误行</option>
          <option value="quarantine">隔离异常数据</option>
        </select>
      </div>
    </>
  )
}
