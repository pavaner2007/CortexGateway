/** Cortex Gateway — API error format */
export interface ApiError {
  code: string
  message: string
}

export interface ApiErrorResponse {
  error: ApiError
  detail?: string
}

export interface PaginationMeta {
  page: number
  page_size: number
  total: number
}
