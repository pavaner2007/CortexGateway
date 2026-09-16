/** Auth types — derived from backend Pydantic schemas */

/** GET /api/v1/auth/me */
export interface MeResponse {
  organization_id: string
  team_id: string
  api_key_id: string
  role: 'admin' | 'member'
}

/** GET /api/v1/organizations/{org_id} */
export interface OrganizationResponse {
  id: string
  name: string
  slug: string
  created_at: string
  updated_at: string
}

/** GET /api/v1/organizations/{org_id}/teams */
export interface TeamResponse {
  id: string
  organization_id: string
  name: string
  slug: string
  created_at: string
  updated_at: string
}

export interface TeamListResponse {
  teams: TeamResponse[]
}

/** GET /api/v1/teams/{team_id}/keys */
export interface APIKeyResponse {
  id: string
  name: string
  key_prefix: string
  role: 'admin' | 'member'
  expires_at: string | null
  revoked_at: string | null
  created_at: string
  last_used_at: string | null
}

/** POST /api/v1/teams/{team_id}/keys — plaintext returned once */
export interface APIKeyCreatedResponse {
  id: string
  name: string
  key: string           // plaintext — shown ONCE only
  key_prefix: string
  role: 'admin' | 'member'
  expires_at: string | null
  created_at: string
}

export interface APIKeyListResponse {
  keys: APIKeyResponse[]
}

/** POST /api/v1/teams/{team_id}/keys body */
export interface APIKeyCreate {
  name: string
  role: 'admin' | 'member'
  expires_at?: string | null
}

/** Session stored in sessionStorage — never includes plaintext key after creation */
export interface Session {
  apiKey: string         // stored for Authorization header
  organization_id: string
  team_id: string
  api_key_id: string
  role: 'admin' | 'member'
}

export const SESSION_KEY = 'cxg_session'
