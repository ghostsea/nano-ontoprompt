import { useState } from 'react'

export default function StorageInspector({
  config, onChange,
}: {
  config: Record<string, unknown>
  onChange: (key: string, value: unknown) => void
}) {
  const schemaEnabled = config.schema_inference !== false
  const [showAdvanced, setShowAdvanced] = useState(false)

  return (
    <>
      <div>
        <label className="text-xs text-gray-500 mb-1 block">存储模式</label>
        <select
          value={String(config.storage_mode || 'auto')}
          onChange={e => onChange('storage_mode', e.target.value)}
          className="w-full border rounded-lg px-3 py-1.5 text-sm"
        >
          <option value="auto">自动检测</option>
          <option value="raw_dataset">Raw Dataset</option>
          <option value="media_set">Media Set</option>
        </select>
      </div>
      <div>
        <label className="text-xs text-gray-500 mb-1 block">版本化</label>
        <select
          value={String(config.versioning || 'snapshot')}
          onChange={e => onChange('versioning', e.target.value)}
          className="w-full border rounded-lg px-3 py-1.5 text-sm"
        >
          <option value="snapshot">SNAPSHOT（快照）</option>
          <option value="append">APPEND（增量）</option>
        </select>
      </div>

      {/**** Schema 推断 ****/}
      <div>
        <label className="text-xs text-gray-500 mb-1 block">Schema 推断</label>
        <label className="flex items-center gap-2 text-sm cursor-pointer">
          <input
            type="checkbox"
            checked={schemaEnabled}
            onChange={e => onChange('schema_inference', e.target.checked)}
            className="accent-black"
          />
          <span className="text-xs">自动推断 Schema</span>
        </label>
      </div>

      {schemaEnabled && (
        <div className="pl-3 border-l-2 border-gray-100 space-y-3">
          <div>
            <label className="text-xs text-gray-500 mb-1 block">采样行数</label>
            <input
              type="number"
              value={String(config.sample_size || 10000)}
              onChange={e => onChange('sample_size', parseInt(e.target.value) || 10000)}
              min={100}
              max={1000000}
              className="w-full border rounded-lg px-3 py-1.5 text-sm"
            />
            <p className="text-[10px] text-gray-400 mt-0.5">用于 Schema 检测的样本行数（100 ~ 1,000,000）</p>
          </div>
          <div>
            <label className="text-xs text-gray-500 mb-1 block">列类型检测</label>
            <select
              value={String(config.type_detection || 'auto')}
              onChange={e => onChange('type_detection', e.target.value)}
              className="w-full border rounded-lg px-3 py-1.5 text-sm"
            >
              <option value="auto">自动检测（推荐）</option>
              <option value="strict">严格模式（全量扫描）</option>
              <option value="text_only">全部视为文本</option>
            </select>
          </div>
          <div>
            <label className="flex items-center gap-2 text-sm cursor-pointer">
              <input
                type="checkbox"
                checked={config.detect_dates !== false}
                onChange={e => onChange('detect_dates', e.target.checked)}
                className="accent-black"
              />
              <span className="text-xs">自动识别日期格式</span>
            </label>
          </div>
          <div>
            <label className="flex items-center gap-2 text-sm cursor-pointer">
              <input
                type="checkbox"
                checked={config.detect_wide_table !== false}
                onChange={e => onChange('detect_wide_table', e.target.checked)}
                className="accent-black"
              />
              <span className="text-xs">检测宽表（列数 &gt; 80 时提示）</span>
            </label>
          </div>
          <div>
            <label className="flex items-center gap-2 text-sm cursor-pointer">
              <input
                type="checkbox"
                checked={config.auto_optimize_types !== false}
                onChange={e => onChange('auto_optimize_types', e.target.checked)}
                className="accent-black"
              />
              <span className="text-xs">自动优化存储格式（Parquet）</span>
            </label>
          </div>
        </div>
      )}

      <div>
        <label className="text-xs text-gray-500 mb-1 block">数据保留策略</label>
        <select
          value={String(config.retention || 'indefinite')}
          onChange={e => onChange('retention', e.target.value)}
          className="w-full border rounded-lg px-3 py-1.5 text-sm"
        >
          <option value="indefinite">永久保留</option>
          <option value="10_versions">保留最近 10 个版本</option>
          <option value="30_days">保留 30 天</option>
          <option value="90_days">保留 90 天</option>
        </select>
      </div>
    </>
  )
}
