import { Outlet, useLocation} from 'react-router-dom'

export default function PipelinesLayout() {
  const location = useLocation()

  // Builder 页面使用全屏布局，不显示标题
  const isBuilder = /^\/pipelines\/(?!connections|datasets|transforms|curated$)[a-f0-9-]+$/i.test(location.pathname)

  if (isBuilder) {
    return <Outlet />
  }

  return (
    <div>
      <h1 className="text-2xl font-bold mb-4">数据管道</h1>
      <Outlet />
    </div>
  )
}
