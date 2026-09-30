'use client'

import { useEffect, useMemo, useRef, useState } from 'react'
import type cytoscape from 'cytoscape'
import { ExternalLink, Info, Loader2, Maximize2, Minus, Plus, RefreshCw, RotateCcw } from 'lucide-react'
import { Button } from '@/components/ui/button'

type GraphState = 'ready' | 'empty' | 'unavailable'
type GraphNodeType = 'Listing' | 'RelatedListing' | 'Ward' | 'FormerAdminArea' | 'Street' | 'Amenity'
type LabelMode = 'clean' | 'names' | 'full'

interface GraphNode {
  id: string
  type: GraphNodeType
  label: string
  properties: Record<string, unknown>
}

interface GraphEdge {
  id: string
  source: string
  target: string
  type: string
  label?: string
  properties: Record<string, unknown>
}

interface PropertyGraph {
  property_id: string
  listing_id: string
  state: GraphState
  nodes: GraphNode[]
  edges: GraphEdge[]
  amenity_categories: string[]
}

interface SharedRelationship {
  type?: string
  id?: string
  name?: string
  category?: string
}

interface RelatedProperty {
  id?: string | number
  listing_id?: string | number
  title?: string
  price_range?: string | number
  area?: number | null
  address?: string
  bedrooms?: number | null
  bathrooms?: number | null
  similarity_score?: number
  graph_evidence?: {
    listing_node_id?: string
    shared_count?: number
    shared_relationships?: SharedRelationship[]
  }
}

interface SelectedElement {
  type: 'node' | 'edge'
  label: string
  properties: Record<string, unknown>
  listingId?: string
}

interface KnowledgeGraphSectionProps {
  propertyId: string
}

const TYPE_LABELS: Record<GraphNodeType, string> = {
  Listing: 'Bất động sản',
  RelatedListing: 'BĐS liên quan',
  Ward: 'Phường/Xã',
  FormerAdminArea: 'Khu vực hành chính cũ',
  Street: 'Đường',
  Amenity: 'Tiện ích',
}

const RELATIONSHIP_LABELS: Record<string, string> = {
  IN_WARD: 'Thuộc phường/xã',
  IN_FORMER_AREA: 'Thuộc khu vực cũ',
  ON_STREET: 'Nằm trên đường',
  NEAR_AMENITY: 'Gần',
  RELATED_LISTING: 'BĐS liên quan',
  SHARED_RELATIONSHIP: 'Quan hệ chung',
}

const AMENITY_LABELS: Record<string, string> = {
  metro: 'Ga metro',
  bus_stop: 'Trạm xe buýt',
  school: 'Trường học',
  college_university: 'Trường đại học',
  hospital: 'Bệnh viện',
  mall: 'Trung tâm thương mại',
  market: 'Chợ',
  supermarket: 'Siêu thị',
  park: 'Công viên',
}

const AMENITY_LINK_PRIORITY = [
  'metro', 'school', 'hospital', 'mall', 'supermarket',
  'park', 'market', 'bus_stop', 'college_university',
]

const NODE_COLORS: Record<GraphNodeType, string> = {
  Listing: '#E03C31',
  RelatedListing: '#f59e0b',
  Ward: '#2563eb',
  FormerAdminArea: '#7c3aed',
  Street: '#0891b2',
  Amenity: '#16a34a',
}

const LABEL_MODE_OPTIONS: Array<{ value: LabelMode; label: string; title: string }> = [
  { value: 'clean', label: 'Gọn', title: 'Chỉ hiện nhãn cạnh khi hover' },
  { value: 'names', label: 'Tên', title: 'Luôn hiện tên các node' },
  { value: 'full', label: 'Đầy đủ', title: 'Hiện tên node và nhãn cạnh' },
]

const EMPTY_GRAPH: PropertyGraph = {
  property_id: '',
  listing_id: '',
  state: 'empty',
  nodes: [],
  edges: [],
  amenity_categories: [],
}

function formatNumber(value: unknown, maximumFractionDigits = 1) {
  if (typeof value !== 'number' || !Number.isFinite(value)) return null
  return new Intl.NumberFormat('vi-VN', { maximumFractionDigits }).format(value)
}

function getEdgeLabel(edge: GraphEdge) {
  if (edge.type === 'RELATED_LISTING') {
    const score = edge.properties.similarity_score
    const sharedCount = edge.properties.shared_count
    if (typeof sharedCount === 'number' && sharedCount > 0) {
      const scoreLabel = typeof score === 'number' ? ` · ${formatNumber(score, 2)}` : ''
      return `${formatNumber(sharedCount, 0)} liên kết chung${scoreLabel}`
    }
    if (typeof score === 'number') return `Tương đồng ${formatNumber(score, 2)}`
    return RELATIONSHIP_LABELS[edge.type] || edge.type
  }
  if (edge.type === 'SHARED_RELATIONSHIP') {
    const name = edge.properties.shared_name
    return name ? `Chung ${truncateLabel(name, 24)}` : 'Quan hệ chung'
  }
  if (edge.type !== 'NEAR_AMENITY') return RELATIONSHIP_LABELS[edge.type] || edge.type
  const distance = formatNumber(edge.properties.driving_distance_km ?? edge.properties.straight_line_km)
  const duration = formatNumber(edge.properties.driving_duration_min, 1)
  if (distance && duration) return `${distance} km · ${duration} phút`
  if (distance) return `${distance} km`
  return 'Gần'
}

function truncateLabel(value: unknown, maxLength: number) {
  const text = String(value || '').replace(/\s+/g, ' ').trim()
  return text.length > maxLength ? `${text.slice(0, maxLength - 1)}…` : text
}

function getNodeCanvasLabel(node: GraphNode) {
  const shortName = truncateLabel(node.label, node.type === 'Listing' ? 28 : 22)
  if (node.type === 'Listing') return `BĐS hiện tại\n${shortName}`
  if (node.type === 'RelatedListing') return `BĐS liên quan\n${shortName}`
  if (node.type === 'Amenity') {
    const category = String(node.properties.category || '')
    return `${AMENITY_LABELS[category] || 'Tiện ích'}\n${shortName}`
  }
  return `${TYPE_LABELS[node.type]}\n${shortName}`
}

function normalizeSharedName(value: unknown) {
  return String(value || '').replace(/\s+/g, ' ').trim().toLocaleLowerCase()
}

function findSharedGraphNode(nodes: GraphNode[], shared: SharedRelationship) {
  const targetType = shared.type === 'ward' ? 'Ward' : shared.type === 'street' ? 'Street' : shared.type === 'amenity' ? 'Amenity' : null
  if (!targetType) return undefined
  if (shared.id) {
    const namespacedId = `${targetType.toLocaleLowerCase()}:${shared.id}`
    const nodeById = nodes.find((node) => node.id === namespacedId)
    if (nodeById) return nodeById
  }
  const normalizedName = normalizeSharedName(shared.name)
  if (!normalizedName) return undefined
  return nodes.find((node) => {
    if (node.type !== targetType) return false
    const nodeName = normalizeSharedName(node.properties.name || node.label)
    if (nodeName !== normalizedName) return false
    if (targetType === 'Amenity' && shared.category) {
      return String(node.properties.category || '') === String(shared.category)
    }
    return true
  })
}

function selectSharedGraphLinks(nodes: GraphNode[], relationships: SharedRelationship[]) {
  const matched = relationships
    .map((shared) => ({ shared, node: findSharedGraphNode(nodes, shared) }))
    .filter((item): item is { shared: SharedRelationship; node: GraphNode } => Boolean(item.node))

  const unique = matched.filter((item, index, items) => (
    items.findIndex((candidate) => candidate.node.id === item.node.id) === index
  ))
  const amenities = unique
    .filter((item) => item.node.type === 'Amenity')
    .sort((left, right) => {
      const leftPriority = AMENITY_LINK_PRIORITY.indexOf(String(left.shared.category || ''))
      const rightPriority = AMENITY_LINK_PRIORITY.indexOf(String(right.shared.category || ''))
      const categoryCompare = (leftPriority < 0 ? Number.MAX_SAFE_INTEGER : leftPriority)
        - (rightPriority < 0 ? Number.MAX_SAFE_INTEGER : rightPriority)
      return categoryCompare || left.node.label.localeCompare(right.node.label)
    })
  const street = unique.find((item) => item.node.type === 'Street')
  const ward = unique.find((item) => item.node.type === 'Ward')

  // Keep the graph readable while making the recommendation explainable:
  // show the shared address anchors plus two representative amenities. The
  // complete list remains available on the direct related-listing edge.
  return [street, ward, ...amenities.slice(0, 2)].filter(
    (item): item is { shared: SharedRelationship; node: GraphNode } => Boolean(item),
  )
}

function formatPropertyValue(key: string, value: unknown) {
  if (value === null || value === undefined || value === '') return null
  if (typeof value === 'boolean') return value ? 'Có' : 'Không'
  if (typeof value === 'number') {
    const decimals = key.includes('distance') || key.includes('duration') ? 1 : 2
    return formatNumber(value, decimals)
  }
  if (Array.isArray(value)) return value.map(String).join(', ')
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

function detailRows(properties: Record<string, unknown>) {
  const labels: Record<string, string> = {
    category: 'Loại',
    address: 'Địa chỉ',
    address_new: 'Địa chỉ hiện tại',
    address_old: 'Địa chỉ cũ',
    city_province: 'Tỉnh/thành phố',
    former_city_province: 'Tỉnh/thành phố cũ',
    old_address: 'Địa chỉ cũ',
    property_type: 'Loại hình',
    price_range: 'Giá (tỷ)',
    area: 'Diện tích (m²)',
    bedrooms: 'Phòng ngủ',
    bathrooms: 'Phòng tắm',
    driving_distance_km: 'Khoảng cách lái xe (km)',
    straight_line_km: 'Khoảng cách đường thẳng (km)',
    driving_duration_min: 'Thời gian lái xe (phút)',
    threshold_km: 'Ngưỡng (km)',
    within_threshold: 'Trong ngưỡng',
    similarity_score: 'Điểm tương đồng',
    shared_count: 'Số liên kết chung',
    shared_relationships: 'Liên kết chung',
  }
  return Object.entries(properties)
    .map(([key, value]) => {
      const formatted = formatPropertyValue(key, value)
      return formatted ? { key, label: labels[key] || key, value: formatted } : null
    })
    .filter((row): row is { key: string; label: string; value: string } => row !== null)
}

export function KnowledgeGraphSection({ propertyId }: KnowledgeGraphSectionProps) {
  const graphContainerRef = useRef<HTMLDivElement>(null)
  const cyRef = useRef<cytoscape.Core | null>(null)
  const relatedControllerRef = useRef<AbortController | null>(null)
  const [graph, setGraph] = useState<PropertyGraph | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [visibleCategories, setVisibleCategories] = useState<string[]>([])
  const [selected, setSelected] = useState<SelectedElement | null>(null)
  const [retryKey, setRetryKey] = useState(0)
  const [relatedProperties, setRelatedProperties] = useState<RelatedProperty[]>([])
  const [showRelated, setShowRelated] = useState(false)
  const [relatedLoading, setRelatedLoading] = useState(false)
  const [relatedLoaded, setRelatedLoaded] = useState(false)
  const [relatedError, setRelatedError] = useState<string | null>(null)
  const [zoomLevel, setZoomLevel] = useState(1)
  const [labelMode, setLabelMode] = useState<LabelMode>('clean')

  useEffect(() => {
    const controller = new AbortController()
    setLoading(true)
    setError(null)
    setSelected(null)
    setGraph(null)
    setRelatedProperties([])
    setShowRelated(false)
    setRelatedLoaded(false)
    setRelatedError(null)
    setLabelMode('clean')

    fetch(`/api/properties/${encodeURIComponent(propertyId)}/graph`, {
      signal: controller.signal,
      cache: 'no-store',
    })
      .then(async (response) => {
        const payload = await response.json().catch(() => ({}))
        if (!response.ok) throw new Error(payload.detail || 'Không thể tải dữ liệu knowledge graph')
        return payload
      })
      .then((payload) => {
        const nextGraph: PropertyGraph = payload.data || EMPTY_GRAPH
        setGraph(nextGraph)
        setVisibleCategories(nextGraph.amenity_categories || [])
      })
      .catch((requestError: unknown) => {
        if (requestError instanceof DOMException && requestError.name === 'AbortError') return
        setError(requestError instanceof Error ? requestError.message : 'Không thể tải knowledge graph')
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false)
      })

    return () => {
      controller.abort()
      relatedControllerRef.current?.abort()
      relatedControllerRef.current = null
    }
  }, [propertyId, retryKey])

  const relatedGraph = useMemo(() => {
    const listingNode = graph?.nodes.find((node) => node.type === 'Listing')
    if (!graph || !listingNode || relatedProperties.length === 0) {
      return { nodes: [] as GraphNode[], edges: [] as GraphEdge[] }
    }

    const nodes: GraphNode[] = []
    const edges: GraphEdge[] = []
    const seenIds = new Set<string>()
    for (const property of relatedProperties) {
      const rawListingId = property.listing_id ?? property.id
      if (rawListingId === undefined || rawListingId === null) continue
      const listingId = String(rawListingId)
      const rawNodeId = property.graph_evidence?.listing_node_id || listingId
      const nodeId = `related-listing:${rawNodeId}`
      if (seenIds.has(nodeId) || nodeId === listingNode.id) continue
      seenIds.add(nodeId)

      const sharedRelationships = property.graph_evidence?.shared_relationships || []
      nodes.push({
        id: nodeId,
        type: 'RelatedListing',
        label: property.title || `BĐS ${listingId}`,
        properties: {
          listing_id: listingId,
          title: property.title,
          price_range: property.price_range,
          area: property.area,
          bedrooms: property.bedrooms,
          bathrooms: property.bathrooms,
          address: property.address,
        },
      })
      edges.push({
        id: `${listingNode.id}|RELATED_LISTING|${nodeId}`,
        source: listingNode.id,
        target: nodeId,
        type: 'RELATED_LISTING',
        properties: {
          similarity_score: property.similarity_score,
          shared_count: property.graph_evidence?.shared_count,
          shared_relationships: sharedRelationships
            .map((item) => item.name || item.category || item.type)
            .filter(Boolean),
        },
      })

      // Reuse shared Ward/Street/Amenity nodes already visible in the main
      // graph. Resolve valid UI nodes before applying the display limit so an
      // internal GeoCluster entry cannot accidentally hide amenity evidence.
      for (const { shared, node: sharedNode } of selectSharedGraphLinks(graph.nodes, sharedRelationships)) {
        edges.push({
          id: `${nodeId}|SHARED_RELATIONSHIP|${sharedNode.id}`,
          source: nodeId,
          target: sharedNode.id,
          type: 'SHARED_RELATIONSHIP',
          properties: {
            shared_type: shared.type,
            shared_name: shared.name,
            category: shared.category,
          },
        })
      }
    }
    return { nodes, edges }
  }, [graph, relatedProperties])

  const visibleNodes = useMemo(() => {
    if (!graph) return []
    const baseNodes = graph.nodes.filter((node) => {
      if (node.type !== 'Amenity') return true
      return visibleCategories.includes(String(node.properties.category || ''))
    })
    return showRelated ? [...baseNodes, ...relatedGraph.nodes] : baseNodes
  }, [graph, relatedGraph.nodes, showRelated, visibleCategories])

  const visibleEdges = useMemo(() => {
    if (!graph) return []
    return showRelated ? [...graph.edges, ...relatedGraph.edges] : graph.edges
  }, [graph, relatedGraph.edges, showRelated])

  const visibleNodeIds = useMemo(() => new Set(visibleNodes.map((node) => node.id)), [visibleNodes])

  const loadRelatedProperties = async () => {
    if (showRelated) {
      setShowRelated(false)
      return
    }
    if (relatedLoaded) {
      setShowRelated(true)
      return
    }

    relatedControllerRef.current?.abort()
    const controller = new AbortController()
    relatedControllerRef.current = controller
    setRelatedLoading(true)
    setRelatedError(null)
    try {
      const response = await fetch(`/api/properties/${encodeURIComponent(propertyId)}/similar?limit=5`, {
        signal: controller.signal,
        cache: 'no-store',
      })
      const payload = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(payload.error || 'Không thể tải BĐS liên quan')
      const results = Array.isArray(payload.data?.results) ? payload.data.results : []
      setRelatedProperties(results.slice(0, 5))
      setRelatedLoaded(true)
      setShowRelated(true)
    } catch (requestError: unknown) {
      if (requestError instanceof DOMException && requestError.name === 'AbortError') return
      setRelatedError(requestError instanceof Error ? requestError.message : 'Không thể tải BĐS liên quan')
    } finally {
      if (!controller.signal.aborted) setRelatedLoading(false)
    }
  }

  useEffect(() => {
    let disposed = false
    let instance: cytoscape.Core | null = null

    if (!graph || graph.state !== 'ready' || !graphContainerRef.current || visibleNodes.length === 0) {
      cyRef.current?.destroy()
      cyRef.current = null
      return () => undefined
    }

    const elements: cytoscape.ElementDefinition[] = [
      ...visibleNodes.map((node) => ({
        group: 'nodes' as const,
        data: {
          id: node.id,
          label: getNodeCanvasLabel(node),
          type: node.type,
          related: node.type === 'RelatedListing',
          nodeProperties: node.properties,
        },
      })),
      ...visibleEdges
        .filter((edge) => visibleNodeIds.has(edge.source) && visibleNodeIds.has(edge.target))
        .map((edge) => ({
          group: 'edges' as const,
          data: {
            id: edge.id,
            source: edge.source,
            target: edge.target,
            label: getEdgeLabel(edge),
            type: edge.type,
            edgeProperties: edge.properties,
          },
        })),
    ]

    const createGraph = async () => {
      const module = await import('cytoscape')
      if (disposed || !graphContainerRef.current) return
      const cytoscapeFactory = module.default
      setZoomLevel(1)
      instance = cytoscapeFactory({
        container: graphContainerRef.current,
        elements,
        style: [
          {
            selector: 'node',
            style: {
              'background-color': '#64748b',
              label: 'data(label)',
              color: '#0f172a',
              'font-size': '11px',
              'text-wrap': 'wrap',
              'text-max-width': '108px',
              'text-valign': 'bottom',
              'text-margin-y': 8,
              'min-zoomed-font-size': '8px',
              'text-opacity': 1,
              width: '34px',
              height: '34px',
              'border-width': '2px',
              'border-color': '#ffffff',
              'overlay-opacity': 0,
            },
          },
          ...Object.entries(NODE_COLORS).map(([type, color]) => ({
            selector: `node[type = "${type}"]`,
            style: { 'background-color': color },
          })),
          {
            selector: 'node[type = "Listing"]',
            style: {
              width: '58px',
              height: '58px',
              'font-size': '12px',
              'font-weight': 'bold',
              'text-max-width': '160px',
            },
          },
          {
            selector: 'node[related = "true"]',
            style: {
              shape: 'round-rectangle',
              width: '46px',
              height: '46px',
              'font-size': '10px',
              'text-max-width': '150px',
              'border-style': 'dashed',
            },
          },
          {
            selector: '.labels-hidden',
            style: { 'text-opacity': 0 },
          },
          {
            selector: 'node.labels-hidden[type = "Listing"], node.labels-hidden[type = "RelatedListing"]',
            style: { 'text-opacity': 1 },
          },
          {
            selector: 'node.names-visible, node.full-labels',
            style: { 'text-opacity': 1 },
          },
          {
            selector: 'edge',
            style: {
              width: '1.5px',
              'line-color': '#94a3b8',
              'target-arrow-color': '#94a3b8',
              'target-arrow-shape': 'triangle',
              'curve-style': 'bezier',
              label: '',
              color: '#475569',
              'font-size': '9px',
              'text-opacity': 0,
              'text-background-color': '#ffffff',
              'text-background-opacity': 0.85,
              'text-background-padding': '2px',
            },
          },
          {
            selector: 'edge[type = "RELATED_LISTING"]',
            style: {
              'line-color': '#f59e0b',
              'target-arrow-color': '#f59e0b',
              'line-style': 'dashed',
            },
          },
          {
            selector: 'edge[type = "SHARED_RELATIONSHIP"]',
            style: {
              'line-color': '#f59e0b',
              'target-arrow-color': '#f59e0b',
              'target-arrow-shape': 'none',
              'line-style': 'dotted',
            },
          },
          {
            selector: 'edge.edge-label-visible',
            style: {
              label: 'data(label)',
              'text-opacity': 1,
            },
          },
          {
            selector: 'edge.edge-label-visible.labels-hidden',
            style: { 'text-opacity': 1 },
          },
          {
            selector: 'edge.full-labels',
            style: {
              label: 'data(label)',
              'text-opacity': 1,
            },
          },
          {
            selector: ':selected',
            style: {
              'border-width': '4px',
              'border-color': '#f59e0b',
              'line-color': '#f59e0b',
              'target-arrow-color': '#f59e0b',
            },
          },
        ],
        layout: { name: 'cose', animate: false, padding: 36 },
        minZoom: 0.35,
        maxZoom: 2.5,
      })
      if (disposed) {
        instance.destroy()
        return
      }
      cyRef.current = instance
      const updateZoomPresentation = () => {
        if (!instance) return
        const zoom = instance.zoom()
        setZoomLevel(zoom)
        instance.elements().removeClass('labels-hidden names-visible full-labels')
        if (labelMode === 'full') {
          instance.nodes().addClass('full-labels')
          instance.edges().addClass('full-labels')
        } else if (labelMode === 'names') {
          instance.nodes().addClass('names-visible')
        } else if (zoom < 0.72) {
          instance.nodes().addClass('labels-hidden')
        }
        if (labelMode !== 'full' && zoom < 0.98) instance.edges().addClass('labels-hidden')
      }
      instance.on('zoom', updateZoomPresentation)
      instance.on('mouseover', 'edge', (event) => {
        event.target.addClass('edge-label-visible')
      })
      instance.on('mouseout', 'edge', (event) => {
        event.target.removeClass('edge-label-visible')
      })
      instance.on('tap', 'node', (event) => {
        const data = event.target.data()
        const listingId = data.type === 'RelatedListing' && data.nodeProperties?.listing_id
          ? String(data.nodeProperties.listing_id)
          : undefined
        setSelected({ type: 'node', label: data.label || data.type, properties: data.nodeProperties || {}, listingId })
      })
      instance.on('tap', 'edge', (event) => {
        const data = event.target.data()
        setSelected({
          type: 'edge',
          label: RELATIONSHIP_LABELS[data.type] || data.type,
          properties: { relationship: data.label, ...(data.edgeProperties || {}) },
        })
      })
      updateZoomPresentation()
      instance.fit(undefined, 32)
    }

    void createGraph()
    return () => {
      disposed = true
      instance?.destroy()
      if (cyRef.current === instance) cyRef.current = null
    }
  }, [graph, labelMode, visibleEdges, visibleNodeIds, visibleNodes])

  const resetGraph = () => {
    cyRef.current?.layout({ name: 'cose', animate: false, padding: 36 }).run()
    cyRef.current?.fit(undefined, 32)
  }

  const toggleCategory = (category: string) => {
    setVisibleCategories((current) =>
      current.includes(category) ? current.filter((item) => item !== category) : [...current, category],
    )
  }

  return (
    <section className="space-y-4 pb-6 border-b border-border" aria-labelledby="knowledge-graph-title">
      <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 id="knowledge-graph-title" className="text-xl font-bold text-foreground">
            Knowledge Graph khu vực
          </h2>
          <p className="text-sm text-muted-foreground">
            Khám phá các địa điểm và tiện ích liên kết với bất động sản này.
          </p>
        </div>
        {graph?.state === 'ready' && (
          <div className="flex items-center gap-2">
            <Button type="button" variant="outline" size="sm" onClick={() => void loadRelatedProperties()} disabled={relatedLoading}>
              {relatedLoading ? <Loader2 className="h-4 w-4 mr-1.5 animate-spin" /> : <ExternalLink className="h-4 w-4 mr-1.5" />}
              {showRelated ? 'Ẩn BĐS liên quan' : relatedLoaded ? `Hiện BĐS liên quan (${relatedProperties.length})` : 'Hiện BĐS liên quan'}
            </Button>
            <Button type="button" variant="outline" size="sm" onClick={() => cyRef.current?.fit(undefined, 32)}>
              <Maximize2 className="h-4 w-4 mr-1.5" />
              Căn vừa màn hình
            </Button>
            <div className="flex items-center rounded-md border border-border bg-background">
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="h-9 w-9 rounded-r-none"
                aria-label="Thu nhỏ graph"
                onClick={() => {
                  if (cyRef.current) cyRef.current.zoom(Math.max(cyRef.current.minZoom(), cyRef.current.zoom() / 1.25))
                }}
              >
                <Minus className="h-4 w-4" />
              </Button>
              <span className="min-w-12 px-1 text-center text-xs tabular-nums text-muted-foreground">
                {Math.round(zoomLevel * 100)}%
              </span>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="h-9 w-9 rounded-l-none"
                aria-label="Phóng to graph"
                onClick={() => {
                  if (cyRef.current) cyRef.current.zoom(Math.min(cyRef.current.maxZoom(), cyRef.current.zoom() * 1.25))
                }}
              >
                <Plus className="h-4 w-4" />
              </Button>
            </div>
            <Button type="button" variant="outline" size="icon" aria-label="Đặt lại graph" onClick={resetGraph}>
              <RotateCcw className="h-4 w-4" />
            </Button>
          </div>
        )}
      </div>

      {loading && (
        <div className="h-[400px] sm:h-[480px] rounded-lg border border-border bg-muted/40 flex flex-col items-center justify-center gap-3">
          <Loader2 className="h-7 w-7 animate-spin text-[#E03C31]" />
          <p className="text-sm text-muted-foreground">Đang tải knowledge graph...</p>
        </div>
      )}

      {!loading && error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-6 text-center dark:border-red-900 dark:bg-red-950/30">
          <p className="text-sm text-red-700 dark:text-red-300">{error}</p>
          <Button type="button" variant="outline" size="sm" className="mt-4" onClick={() => setRetryKey((key) => key + 1)}>
            <RefreshCw className="h-4 w-4 mr-1.5" />
            Thử lại
          </Button>
        </div>
      )}

      {!loading && !error && graph?.state === 'unavailable' && (
        <div className="rounded-lg border border-border bg-muted/40 p-6 text-center">
          <p className="font-medium text-foreground">Knowledge graph hiện chưa khả dụng</p>
          <p className="text-sm text-muted-foreground mt-1">Thông tin bất động sản vẫn được hiển thị bình thường.</p>
          <Button type="button" variant="outline" size="sm" className="mt-4" onClick={() => setRetryKey((key) => key + 1)}>
            <RefreshCw className="h-4 w-4 mr-1.5" />
            Thử lại
          </Button>
        </div>
      )}

      {!loading && !error && graph?.state === 'empty' && (
        <div className="rounded-lg border border-border bg-muted/40 p-6 text-center text-sm text-muted-foreground">
          Chưa có dữ liệu liên kết trong knowledge graph cho bất động sản này.
        </div>
      )}

      {!loading && !error && graph?.state === 'ready' && (
        <>
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs font-medium text-muted-foreground">Lọc tiện ích:</span>
            {graph.amenity_categories.map((category) => {
              const active = visibleCategories.includes(category)
              return (
                <button
                  key={category}
                  type="button"
                  aria-pressed={active}
                  onClick={() => toggleCategory(category)}
                  className={`rounded-full border px-2.5 py-1 text-xs transition-colors ${
                    active
                      ? 'border-green-600 bg-green-50 text-green-700 dark:bg-green-950/30 dark:text-green-300'
                      : 'border-border bg-background text-muted-foreground'
                  }`}
                >
                  {AMENITY_LABELS[category] || category}
                </button>
              )
            })}
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs font-medium text-muted-foreground">Chế độ hiển thị:</span>
            <div className="flex items-center rounded-md border border-border bg-background p-0.5" role="group" aria-label="Chế độ hiển thị graph">
              {LABEL_MODE_OPTIONS.map((option) => {
                const active = labelMode === option.value
                return (
                  <button
                    key={option.value}
                    type="button"
                    title={option.title}
                    aria-pressed={active}
                    onClick={() => setLabelMode(option.value)}
                    className={`rounded px-2.5 py-1 text-xs transition-colors ${
                      active ? 'bg-[#E03C31] text-white' : 'text-muted-foreground hover:bg-muted'
                    }`}
                  >
                    {option.label}
                  </button>
                )
              })}
            </div>
          </div>

          {relatedError && <p className="text-sm text-red-600">{relatedError}</p>}
          {showRelated && relatedLoaded && relatedProperties.length === 0 && (
            <p className="text-sm text-muted-foreground">Chưa tìm thấy bất động sản liên quan.</p>
          )}

          <div
            ref={graphContainerRef}
            className="h-[400px] sm:h-[480px] w-full rounded-lg border border-border bg-white"
            role="img"
            aria-label="Knowledge graph của bất động sản"
          />

          <div className="flex flex-wrap gap-x-4 gap-y-2 text-xs text-muted-foreground">
            {(Object.keys(TYPE_LABELS) as GraphNodeType[]).map((type) => (
              <span key={type} className="flex items-center gap-1.5">
                <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: NODE_COLORS[type] }} />
                {TYPE_LABELS[type]}
              </span>
            ))}
            <span className="flex items-center gap-1.5">
              <span className="w-5 border-t-2 border-dotted border-amber-500" />
              Quan hệ chung
            </span>
          </div>

          {selected && (
            <div className="rounded-lg border border-border bg-card p-4" aria-live="polite">
              <div className="flex items-center gap-2 mb-3">
                <Info className="h-4 w-4 text-[#E03C31]" />
                <p className="font-semibold text-foreground">{selected.label}</p>
                {selected.listingId && (
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="ml-auto"
                    onClick={() => window.location.assign(`/chi-tiet/${encodeURIComponent(selected.listingId as string)}`)}
                  >
                    <ExternalLink className="h-3.5 w-3.5 mr-1.5" />
                    Xem chi tiết
                  </Button>
                )}
              </div>
              <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-2 text-sm">
                {detailRows(selected.properties).map((row) => (
                  <div key={row.key} className="flex flex-col">
                    <dt className="text-xs text-muted-foreground">{row.label}</dt>
                    <dd className="text-foreground break-words">{row.value}</dd>
                  </div>
                ))}
              </dl>
            </div>
          )}
        </>
      )}
    </section>
  )
}
