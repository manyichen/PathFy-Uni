export interface GraphGuard {
  graph_revision?: number
  locked?: boolean
  locked_task_id?: number
  [key: string]: unknown
}

export interface GraphStats extends Record<string, number> {}

export interface GraphTask {
  id: number
  status: string
  task_type?: string
  input_file_name?: string
  files?: Array<Record<string, unknown>>
  options?: Record<string, unknown>
  [key: string]: unknown
}

export interface GraphTaskList {
  items: GraphTask[]
  total: number
  page: number
  page_size: number
  [key: string]: unknown
}

export interface GraphChangeGroup {
  items?: Array<Record<string, unknown>>
  total?: number
  page?: number
  page_size?: number
  [key: string]: unknown
}
