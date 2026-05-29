export declare const ALL_FILTER: string

export declare const STATUS_FILTER_OPTIONS: ReadonlyArray<{
  label: string
  value: string
}>

export declare const MODE_FILTER_OPTIONS: ReadonlyArray<{
  label: string
  value: string
}>

export declare const SORT_OPTIONS: ReadonlyArray<{
  label: string
  value: string
}>

export interface ProjectListFilterOptions {
  searchQuery?: string
  statusFilter?: string
  modeFilter?: string
}

export interface ProjectListSortOptions extends ProjectListFilterOptions {
  sortBy?: string
  sortOrder?: string
}

export interface ProjectListItem {
  name?: string
  project_status?: string
  require_entity_validation?: boolean
  create_time?: string
  last_modified?: string
  [key: string]: unknown
}

export declare function hasActiveProjectFilters(options: ProjectListFilterOptions): boolean

export declare function filterAndSortProjects(
  items: ProjectListItem[] | null | undefined,
  options: ProjectListSortOptions
): ProjectListItem[]
