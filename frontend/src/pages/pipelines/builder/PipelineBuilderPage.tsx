import { useCallback, useRef, useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  ReactFlow, MiniMap, Controls, Background,
  useNodesState, useEdgesState, addEdge, ReactFlowProvider,
  type Connection, type Node, type Edge,
  type NodeTypes, type OnNodesChange, type OnEdgesChange,
  MarkerType,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { Save, Play, CheckCircle, X, ArrowLeft, Loader2, AlertTriangle } from 'lucide-react'
import pipelinesApi, { type Pipeline, type ValidateResult } from '@/api/v2/pipelines'
import ConnectorNode from './nodes/ConnectorNode'
import StorageNode from './nodes/StorageNode'
import TransformNode from './nodes/TransformNode'
import OutputNode from './nodes/OutputNode'
import ConnectorInspector from './inspectors/ConnectorInspector'
import StorageInspector from './inspectors/StorageInspector'
import TransformInspector from './inspectors/TransformInspector'
import OutputInspector from './inspectors/OutputInspector'

const nodeTypes: NodeTypes = {
  connector: ConnectorNode,
  storage: StorageNode,
  transform: TransformNode,
  output: OutputNode,
}

const DEFAULT_POSITION = { x: 100, y: 200 }

const NODE_DEFAULTS: Record<string, { label: string; color: string; config: Record<string, unknown> }> = {
  connector: { label: '连接器', color: '#3B82F6', config: { source_type: 'file', config_values: {} } },
  storage: { label: '存储器', color: '#10B981', config: { storage_mode: 'auto' } },
  transform: { label: '转换器', color: '#F59E0B', config: { path: 'auto', steps: [] } },
  output: { label: '输出', color: '#8B5CF6', config: { dataset_type: 'curated_dataset', primary_key: [] } },
}

const TOOLS = [
  { type: 'connector', label: '连接器', desc: '数据源连接' },
  { type: 'storage', label: '存储器', desc: '原始数据存储' },
  { type: 'transform', label: '转换器', desc: '数据转换' },
  { type: 'output', label: '输出', desc: '输出 Curated Dataset' },
]

interface SelectedNodeData {
  id: string
  type: string
  label: string
  config: Record<string, unknown>
}

export default function PipelineBuilderPage() {
  const { pipelineId } = useParams<{ pipelineId: string }>()
  const navigate = useNavigate()
  const reactFlowWrapper = useRef<HTMLDivElement>(null)
  const inspectorRef = useRef<HTMLDivElement>(null)
  const reactFlowInstanceRef = useRef<any>(null)

  const [nodes, setNodes, onNodesChange] = useNodesState([])
  const [edges, setEdges, onEdgesChange] = useEdgesState([])
  const [selectedNode, setSelectedNode] = useState<SelectedNodeData | null>(null)
  const [pipeline, setPipeline] = useState<Pipeline | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [running, setRunning] = useState(false)
  const [validation, setValidation] = useState<ValidateResult | null>(null)
  const [saveStatus, setSaveStatus] = useState<'saved' | 'unsaved' | 'saving'>('saved')

  // 右侧面板可拖拽调整宽度
  const [inspectorWidth, setInspectorWidth] = useState(288)
  const isDraggingPanel = useRef(false)

  const handlePanelResizeStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault()
    isDraggingPanel.current = true
    document.body.style.cursor = 'col-resize'
    document.body.style.userSelect = 'none'
  }, [])

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isDraggingPanel.current) return
      const newWidth = Math.max(240, Math.min(600, window.innerWidth - e.clientX - 48))
      setInspectorWidth(newWidth)
    }
    const handleMouseUp = () => {
      isDraggingPanel.current = false
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
    }
    window.addEventListener('mousemove', handleMouseMove)
    window.addEventListener('mouseup', handleMouseUp)
    return () => {
      window.removeEventListener('mousemove', handleMouseMove)
      window.removeEventListener('mouseup', handleMouseUp)
    }
  }, [])

  // Load pipeline
  useEffect(() => {
    if (!pipelineId) return
    setLoading(true)
    pipelinesApi.get(pipelineId)
      .then(pl => {
        setPipeline(pl)
        const def = pl.definition || { nodes: [], edges: [] }
        const loadedNodes: Node[] = (def.nodes as any[] || []).map((n: any) => ({
          id: n.id,
          type: n.type,
          position: n.position || DEFAULT_POSITION,
          data: { label: n.label || '', config: n.config || {} },
        }))
        const loadedEdges: Edge[] = (def.edges as any[] || []).map((e: any) => ({
          id: e.id,
          source: e.source,
          target: e.target,
          type: 'smoothstep',
          markerEnd: { type: MarkerType.ArrowClosed },
        }))
        setNodes(loadedNodes)
        setEdges(loadedEdges)
      })
      .catch(() => navigate('/pipelines'))
      .finally(() => setLoading(false))
  }, [pipelineId])

  // Save pipeline definition
  const saveDefinition = useCallback(async () => {
    if (!pipelineId) return
    setSaving(true)
    setSaveStatus('saving')
    try {
      const definition = {
        nodes: nodes.map(n => ({
          id: n.id,
          type: n.type,
          position: n.position,
          label: (n.data as any).label || '',
          config: (n.data as any).config || {},
        })),
        edges: edges.map(e => ({
          id: e.id,
          source: e.source,
          target: e.target,
        })),
      }
      await pipelinesApi.update(pipelineId, { definition: definition as any })
      setSaveStatus('saved')
    } catch {
      setSaveStatus('unsaved')
    } finally {
      setSaving(false)
    }
  }, [pipelineId, nodes, edges])

  // Keyboard save shortcut
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        e.preventDefault()
        saveDefinition()
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [saveDefinition])

  // Mark unsaved on changes
  useEffect(() => {
    if (!loading) setSaveStatus('unsaved')
  }, [nodes, edges])

  // Run pipeline
  const handleRun = async () => {
    if (!pipelineId) return
    setRunning(true)

    // 重置所有节点状态为 idle
    setNodes(nds => nds.map(n => ({
      ...n,
      data: { ...n.data, status: 'idle' },
    })))

    try {
      await saveDefinition()

      // 模拟节点依次运行的效果（视觉反馈）
      const def = (await pipelinesApi.get(pipelineId)).definition || { nodes: [], edges: [] }
      const nodeIds = (def.nodes as any[] || []).map((n: any) => n.id)

      // 逐个标记为 running
      for (const nid of nodeIds) {
        setNodes(nds => nds.map(n =>
          n.id === nid ? { ...n, data: { ...n.data, status: 'running' } } : n
        ))
        await new Promise(r => setTimeout(r, 300))
      }

      // 执行 run-sync
      const result = await pipelinesApi.runSync(pipelineId)
      const nodeStatus = (result as any).stats?.node_status || {}
      const runSucceeded = (result as any).status === 'success'
      const curatedId = (result as any).stats?.curated_dataset_id || ''

      // 应用节点状态 + curated_dataset_id 存入 Output 节点
      setNodes(nds => nds.map(n => {
        const base = { ...n.data, status: nodeStatus[n.id] || (runSucceeded ? 'success' : 'failed') }
        if (n.type === 'output' && curatedId) {
          base.config = { ...((base as any).config || {}), curated_dataset_id: curatedId }
        }
        return { ...n, data: base }
      }))

      // 刷新 pipeline 状态
      const pl = await pipelinesApi.get(pipelineId)
      setPipeline(pl)
    } catch (e) {
      // 运行失败，所有节点标记为 failed
      setNodes(nds => nds.map(n => ({
        ...n,
        data: { ...n.data, status: 'failed' },
      })))
    } finally {
      setRunning(false)
    }
  }

  // Validate
  const handleValidate = async () => {
    if (!pipelineId) return
    try {
      const result = await pipelinesApi.validate(pipelineId)
      setValidation(result)
    } catch {
      setValidation({ valid: false, errors: [], warnings: [{ node_id: '', severity: 'error', message: '校验失败' }] })
    }
  }

  // Publish
  const handlePublish = async () => {
    if (!pipelineId) return
    try {
      const result = await pipelinesApi.publish(pipelineId)
      const pl = await pipelinesApi.get(pipelineId)
      setPipeline(pl)
      alert(`Pipeline 已发布，版本 v${result.version}`)
    } catch (e: unknown) {
      const err = e as { detail?: string }
      alert(err?.detail || '发布失败')
    }
  }

  // Drag & drop from toolbar
  const onDragStart = useCallback((event: React.DragEvent, nodeType: string) => {
    event.dataTransfer.setData('application/reactflow', nodeType)
    event.dataTransfer.effectAllowed = 'move'
  }, [])

  const onDrop = useCallback((event: React.DragEvent) => {
    event.preventDefault()
    const type = event.dataTransfer.getData('application/reactflow')
    if (!type || !NODE_DEFAULTS[type]) return

    // 将鼠标屏幕位置转为画布坐标
    const position = reactFlowInstanceRef.current?.screenToFlowPosition({
      x: event.clientX,
      y: event.clientY,
    }) || { x: event.clientX - 150, y: event.clientY - 40 }

    const defaults = NODE_DEFAULTS[type]
    const id = `${type}_${Date.now()}`
    const newNode: Node = {
      id,
      type,
      position,
      data: { label: `${defaults.label}_${nodes.length + 1}`, config: { ...defaults.config } },
    }
    setNodes(nds => nds.concat(newNode))
  }, [nodes, setNodes])

  const onDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault()
    event.dataTransfer.dropEffect = 'move'
  }, [])

  // Connect nodes
  const onConnect = useCallback((connection: Connection) => {
    const edge: Edge = {
      ...connection,
      id: `edge_${Date.now()}`,
      type: 'smoothstep',
      markerEnd: { type: MarkerType.ArrowClosed },
    }
    setEdges(eds => addEdge(edge, eds))
  }, [setEdges])

  // Select node
  const onNodeClick = useCallback((_: React.MouseEvent, node: Node) => {
    setSelectedNode({
      id: node.id,
      type: node.type || '',
      label: (node.data as any).label || '',
      config: (node.data as any).config || {},
    })
  }, [])

  const onPaneClick = useCallback(() => {
    setSelectedNode(null)
    setValidation(null)
  }, [])

  // Update node data from inspector
  const updateNodeData = useCallback((nodeId: string, data: Record<string, unknown>) => {
    setNodes(nds => nds.map(n => {
      if (n.id === nodeId) {
        const newData = { ...n.data as any, ...data }
        return { ...n, data: newData }
      }
      return n
    }))
    // Also update selected node state
    setSelectedNode(prev => prev && prev.id === nodeId ? { ...prev, ...data } as any : prev)
  }, [setNodes])

  if (loading) {
    return <div className="text-gray-400 text-sm p-8 text-center">加载 Pipeline...</div>
  }

  if (!pipeline) {
    return <div className="text-gray-400 text-sm p-8 text-center">Pipeline 未找到</div>
  }

  return (
    <ReactFlowProvider>
      <div className="h-[calc(100vh-5rem)] flex flex-col -m-6">
      {/* Top Bar */}
      <div className="flex items-center gap-3 px-4 py-2 bg-white border-b shrink-0">
        <button
          onClick={() => navigate('/pipelines')}
          className="p-1.5 rounded hover:bg-gray-100 text-gray-500"
        >
          <ArrowLeft size={16} />
        </button>
        <span className="font-semibold text-sm">{pipeline.name}</span>
        <span className={`text-xs px-1.5 py-0.5 rounded border ${
          pipeline.status === 'published' ? 'bg-green-50 text-green-600 border-green-200' :
          pipeline.status === 'failed' ? 'bg-red-50 text-red-600 border-red-200' :
          'bg-gray-100 text-gray-600 border-gray-200'
        }`}>
          {pipeline.status}
        </span>
        <span className="text-xs text-gray-400">v{pipeline.version || 1}</span>
        <span className="text-xs text-gray-400 font-mono">{pipeline.branch || 'main'}</span>

        {/* Save status */}
        {saveStatus === 'saving' && <span className="text-xs text-amber-500 ml-2">保存中...</span>}
        {saveStatus === 'saved' && <span className="text-xs text-green-500 ml-2">已保存</span>}
        {saveStatus === 'unsaved' && <span className="text-xs text-gray-400 ml-2">未保存</span>}

        <div className="flex-1" />

        <button
          onClick={saveDefinition}
          disabled={saving}
          className="flex items-center gap-1 px-3 py-1.5 text-xs border rounded-lg hover:bg-gray-50 disabled:opacity-50"
        >
          <Save size={13} />
          {saving ? '保存中...' : '保存'}
        </button>
        <button
          onClick={handleValidate}
          className="flex items-center gap-1 px-3 py-1.5 text-xs border rounded-lg hover:bg-gray-50"
        >
          <CheckCircle size={13} />
          校验
        </button>
        <button
          onClick={handleRun}
          disabled={running}
          className="flex items-center gap-1 px-3 py-1.5 text-xs bg-gray-800 text-white rounded-lg hover:bg-black disabled:opacity-50"
        >
          {running ? <Loader2 size={13} className="animate-spin" /> : <Play size={13} />}
          {running ? '运行中...' : '运行'}
        </button>
        <button
          onClick={handlePublish}
          className="flex items-center gap-1 px-3 py-1.5 text-xs bg-black text-white rounded-lg hover:bg-gray-800"
        >
          发布
        </button>
      </div>

      {/* Validation messages */}
      {validation && !validation.valid && (
        <div className="bg-red-50 border-b border-red-200 px-4 py-2 shrink-0">
          <div className="flex items-center gap-1 text-xs text-red-600 font-medium mb-1">
            <AlertTriangle size={12} /> 校验未通过
          </div>
          {validation.errors.map((e, i) => (
            <p key={i} className="text-xs text-red-500 ml-4">{e.message}</p>
          ))}
        </div>
      )}
      {validation?.warnings && validation.warnings.length > 0 && validation.valid && (
        <div className="bg-amber-50 border-b border-amber-200 px-4 py-2 shrink-0">
          <div className="flex items-center gap-1 text-xs text-amber-600 font-medium mb-1">
            <AlertTriangle size={12} /> 警告
          </div>
          {validation.warnings.map((w, i) => (
            <p key={i} className="text-xs text-amber-500 ml-4">{w.message}</p>
          ))}
        </div>
      )}

      {/* Main Content: Toolbar + Canvas + Inspector */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left Toolbar */}
        <div className="w-48 bg-gray-50 border-r p-2 space-y-1 shrink-0">
          <p className="text-xs font-medium text-gray-500 px-2 py-1">节点工具</p>
          {TOOLS.map(tool => (
            <div
              key={tool.type}
              draggable
              onDragStart={e => onDragStart(e, tool.type)}
              className="flex items-center gap-2 px-3 py-2 rounded-lg text-xs cursor-grab active:cursor-grabbing
                         hover:bg-white border border-transparent hover:border-gray-200 transition-colors"
            >
              <span
                className="w-2.5 h-2.5 rounded-full shrink-0"
                style={{ backgroundColor: NODE_DEFAULTS[tool.type]?.color }}
              />
              <div>
                <p className="font-medium">{tool.label}</p>
                <p className="text-gray-400">{tool.desc}</p>
              </div>
            </div>
          ))}
        </div>

        {/* Canvas */}
        <div ref={reactFlowWrapper} className="flex-1" onDrop={onDrop} onDragOver={onDragOver}>
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange as OnNodesChange}
            onEdgesChange={onEdgesChange as OnEdgesChange}
            onConnect={onConnect}
            onNodeClick={onNodeClick}
            onPaneClick={onPaneClick}
            nodeTypes={nodeTypes}
            fitView
            deleteKeyCode={['Backspace', 'Delete']}
            snapToGrid
            snapGrid={[15, 15]}
            onInit={(inst) => { reactFlowInstanceRef.current = inst }}
          >
            <Controls />
            <MiniMap
              nodeStrokeWidth={3}
              nodeColor={n => NODE_DEFAULTS[n.type || '']?.color || '#666'}
              style={{ width: 150, height: 100 }}
            />
            <Background color="#f0f0f0" gap={15} />
          </ReactFlow>
        </div>

        {/* Right Inspector — 可拖拽调整宽度 */}
        <div
          ref={inspectorRef}
          className="relative bg-white border-l overflow-y-auto shrink-0"
          style={{ width: inspectorWidth }}
        >
          {/* 拖拽手柄 */}
          <div
            onMouseDown={handlePanelResizeStart}
            className="absolute left-0 top-0 bottom-0 w-1.5 cursor-col-resize hover:bg-blue-400 active:bg-blue-500 transition-colors z-10 group"
          >
            <div className="absolute left-0.5 top-1/2 -translate-y-1/2 w-0.5 h-8 bg-gray-300 rounded-full group-hover:bg-white" />
          </div>
          {selectedNode ? (
            <NodeInspector
              nodeData={selectedNode}
              onUpdate={(data) => updateNodeData(selectedNode.id, data)}
              onClose={() => setSelectedNode(null)}
            />
          ) : (
            <div className="p-4 text-center text-gray-400 text-xs mt-8">
              点击节点查看配置
            </div>
          )}
        </div>
        </div>
      </div>
    </ReactFlowProvider>
  )
}

/** 右侧节点配置面板 */
function NodeInspector({
  nodeData, onUpdate, onClose,
}: {
  nodeData: SelectedNodeData
  onUpdate: (data: Record<string, unknown>) => void
  onClose: () => void
}) {
  const config = (nodeData.config || {}) as Record<string, unknown>
  const [localConfig, setLocalConfig] = useState(config)

  useEffect(() => { setLocalConfig(config) }, [nodeData.id, config])

  const handleChange = (key: string, value: unknown) => {
    setLocalConfig(p => ({ ...p, [key]: value }))
  }

  const applyConfig = () => {
    onUpdate({ config: localConfig })
  }

  return (
    <div className="p-4">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <span className="w-2.5 h-2.5 rounded-full" style={{
            backgroundColor: NODE_DEFAULTS[nodeData.type]?.color || '#666'
          }} />
          <span className="font-medium text-sm">{nodeData.label}</span>
        </div>
        <button onClick={onClose} className="text-gray-400 hover:text-black">
          <X size={14} />
        </button>
      </div>

      <div className="space-y-3">
        <div>
          <label className="text-xs text-gray-500 mb-1 block">节点名称</label>
          <input
            value={nodeData.label}
            onChange={e => handleChange('label', e.target.value)}
            className="w-full border rounded-lg px-3 py-1.5 text-sm"
          />
        </div>

        {/* Type-specific config */}
        {nodeData.type === 'connector' && (
          <ConnectorInspector
            config={localConfig}
            onChange={handleChange}
          />
        )}
        {nodeData.type === 'storage' && (
          <StorageInspector
            config={localConfig}
            onChange={handleChange}
          />
        )}
        {nodeData.type === 'transform' && (
          <TransformInspector
            config={localConfig}
            onChange={handleChange}
            nodeId={nodeData.id}
          />
        )}
        {nodeData.type === 'output' && (
          <OutputInspector
            config={localConfig}
            onChange={handleChange}
          />
        )}
      </div>

      <button
        onClick={applyConfig}
        className="w-full mt-4 px-3 py-2 bg-black text-white text-sm rounded-lg hover:bg-gray-800"
      >
        应用配置
      </button>
    </div>
  )
}
