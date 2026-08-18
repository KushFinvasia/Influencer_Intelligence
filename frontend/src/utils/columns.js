/** Column definitions matching the FinIntel Platform table design. */

export const COLUMNS = [
  { id: 'platform',    label: 'Platform',    sortable: true,  defaultVisible: true },
  { id: 'name',        label: 'Creator',     sortable: true,  defaultVisible: true },
  { id: 'followers',   label: 'Followers',   sortable: true,  defaultVisible: true },
  { id: 'format',      label: 'Format',      sortable: true,  defaultVisible: true },
  { id: 'avg_views',   label: 'Avg Views',   sortable: true,  defaultVisible: true },
  { id: 'avg_likes',   label: 'Avg Likes',   sortable: true,  defaultVisible: true },
  { id: 'avg_comments', label: 'Avg Comments', sortable: true, defaultVisible: true },
  { id: 'engagement',  label: 'Eng. Rate',   sortable: true,  defaultVisible: true },
  { id: 'broker',      label: 'Broker',      sortable: true,  defaultVisible: true },
  { id: 'email',       label: 'Email',       sortable: true,  defaultVisible: true },
  { id: 'phone',       label: 'Phone',       sortable: true,  defaultVisible: true },
  { id: 'category',    label: 'Category',    sortable: true,  defaultVisible: true },
  { id: 'language',    label: 'Language',    sortable: true,  defaultVisible: true },
  { id: 'social_handles', label: 'Socials',   sortable: false, defaultVisible: true },
  { id: 'performance', label: 'Performance Breakdown', sortable: true, defaultVisible: false },
  { id: 'website',     label: 'Website',     sortable: false, defaultVisible: false },
]

export const DEFAULT_ORDER = COLUMNS.map(c => c.id)
export const DEFAULT_HIDDEN = COLUMNS.filter(c => !c.defaultVisible).map(c => c.id)
