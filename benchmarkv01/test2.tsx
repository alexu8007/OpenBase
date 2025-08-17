"use client"

import { useState, useEffect, useMemo } from "react"
import { IconGitBranch, IconStar, IconGitFork, IconCheck, IconChevronDown, IconChevronUp } from "@tabler/icons-react"
import { toast } from "sonner"

import { Button } from "@/components/ui/button"
import { 
  Dialog, 
  DialogContent, 
  DialogDescription, 
  DialogFooter,
  DialogHeader, 
  DialogTitle, 
  DialogTrigger 
} from "./ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import { Separator } from "@/components/ui/separator"
import { Card, CardContent } from "@/components/ui/card"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"

import { type GitHubRepositoryResponse } from "@/lib/types"

interface AddRepositoryModalProps {
  children: React.ReactNode
  onRepositoryAdded?: (repositories: GitHubRepositoryResponse[]) => void
}

export function AddRepositoryModal({ children, onRepositoryAdded }: AddRepositoryModalProps) {
  const [open, setOpen] = useState(false)
  const [repositories, setRepositories] = useState<GitHubRepositoryResponse[]>([])
  const [selectedRepos, setSelectedRepos] = useState<Set<number>>(new Set())
  const [searchQuery, setSearchQuery] = useState("")
  const [debouncedSearchQuery, setDebouncedSearchQuery] = useState("")
  const [loading, setLoading] = useState(false)
  const [collapsedGroups, setCollapsedGroups] = useState<Set<string>>(new Set())
  const [visibilityFilter, setVisibilityFilter] = useState<'all' | 'public' | 'private'>('all')
  const [ownerTypeFilter, setOwnerTypeFilter] = useState<'all' | 'Organization' | 'User'>('all')

  // Debounce search query
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearchQuery(searchQuery)
    }, 300)

    return () => clearTimeout(timer)
  }, [searchQuery])

  // Reset state when modal opens/closes
  const resetModalState = () => {
    setSearchQuery("")
    setDebouncedSearchQuery("")
    setVisibilityFilter('all')
    setOwnerTypeFilter('all')
    setSelectedRepos(new Set())
    setCollapsedGroups(new Set())
  }

  useEffect(() => {
    if (open) {
      resetModalState()
      
      const abortController = new AbortController()
      
      const fetchData = async () => {
        setLoading(true)
        
        try {
          // TODO: Implement actual GitHub API call
          // const response = await fetch('/api/github/repositories', {
          //   signal: abortController.signal
          // })
          // if (!response.ok) {
          //   throw new Error(`Failed to fetch repositories: ${response.statusText}`)
          // }
          // const data = await response.json()
          // if (!abortController.signal.aborted) {
          //   setRepositories(data || [])
          // }
          
          // For now, set empty array until API is implemented
          if (!abortController.signal.aborted) {
            setRepositories([])
          }
        } catch (error) {
          if (!abortController.signal.aborted) {
            console.error('Error fetching repositories:', error)
            toast.error('Failed to fetch repositories. Please try again.')
            setRepositories([])
          }
        } finally {
          if (!abortController.signal.aborted) {
            setLoading(false)
          }
        }
      }
      
      fetchData()
      
      return () => {
        abortController.abort()
      }
    }
  }, [open])

  const filteredRepositories = useMemo(() => {
    return repositories.filter(repo => {
      // Search filter (using debounced search)
      const matchesSearch = debouncedSearchQuery === "" || 
        repo.name.toLowerCase().includes(debouncedSearchQuery.toLowerCase()) ||
        repo.description?.toLowerCase().includes(debouncedSearchQuery.toLowerCase()) ||
        repo.owner.login.toLowerCase().includes(debouncedSearchQuery.toLowerCase())
      
      // Visibility filter
      const matchesVisibility = visibilityFilter === 'all' || 
        (visibilityFilter === 'public' && !repo.private) ||
        (visibilityFilter === 'private' && repo.private)
      
      // Owner type filter
      const matchesOwnerType = ownerTypeFilter === 'all' || repo.owner.type === ownerTypeFilter
      
      return matchesSearch && matchesVisibility && matchesOwnerType
    })
  }, [repositories, debouncedSearchQuery, visibilityFilter, ownerTypeFilter])

  // Group repositories by owner
  const sortedGroups = useMemo(() => {
    const groupedRepositories = filteredRepositories.reduce((acc, repo) => {
      const owner = repo.owner.login
      if (!acc[owner]) {
        acc[owner] = {
          owner: repo.owner.login,
          owner_type: repo.owner.type,
          owner_avatar_url: repo.owner.avatar_url,
          repositories: []
        }
      }
      acc[owner].repositories.push(repo)
      return acc
    }, {} as Record<string, { owner: string; owner_type: string; owner_avatar_url: string; repositories: GitHubRepositoryResponse[] }>)

    // Sort groups by owner type (Organizations first, then Users) and then alphabetically
    return Object.values(groupedRepositories).sort((a, b) => {
      if (a.owner_type !== b.owner_type) {
        return a.owner_type === 'Organization' ? -1 : 1
      }
      return a.owner.localeCompare(b.owner)
    })
  }, [filteredRepositories])

  const handleSelectRepository = (repoId: number) => {
    setSelectedRepos(prev => {
      const newSelected = new Set(prev)
      if (newSelected.has(repoId)) {
        newSelected.delete(repoId)
      } else {
        newSelected.add(repoId)
      }
      return newSelected
    })
  }

  const handleSelectAll = () => {
    if (filteredRepositories.length === 0) return
    const allFilteredIds = new Set(filteredRepositories.map(repo => repo.id))
    setSelectedRepos(allFilteredIds)
  }

  const handleDeselectAll = () => {
    setSelectedRepos(new Set())
  }

  const isAllSelected = useMemo(() => {
    return filteredRepositories.length > 0 && 
      filteredRepositories.every(repo => selectedRepos.has(repo.id))
  }, [filteredRepositories, selectedRepos])

  const handleAddRepositories = () => {
    if (selectedRepos.size === 0) return

    const selectedRepositories = repositories.filter(repo => selectedRepos.has(repo.id))
    
    // Call the callback with selected repositories
    onRepositoryAdded?.(selectedRepositories)
    
    // Show success message
    toast.success(`Added ${selectedRepositories.length} repository(ies) successfully!`)
    
    // Close modal and reset state
    setOpen(false)
    // State will be reset when modal reopens due to useEffect
  }

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric'
    })
  }

  // Clear all filters helper
  const clearAllFilters = () => {
    setSearchQuery("")
    setDebouncedSearchQuery("")
    setVisibilityFilter('all')
    setOwnerTypeFilter('all')
  }

  const getLanguageColor = (language: string | null) => {
    const colors: Record<string, string> = {
      'TypeScript': 'bg-blue-500',
      'JavaScript': 'bg-yellow-500',
      'Python': 'bg-green-500',
      'Java': 'bg-red-500',
      'Go': 'bg-cyan-500'
    }
    return language ? colors[language] || 'bg-gray-500' : 'bg-gray-500'
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        {children}
      </DialogTrigger>
      <DialogContent className="max-w-5xl max-h-[85vh] flex flex-col z-[10001]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <IconGitBranch className="h-5 w-5" />
            Add Repository
            {repositories.length > 0 && (
              <Badge variant="secondary" className="ml-2">
                {repositories.length} available
              </Badge>
            )}
          </DialogTitle>
          <DialogDescription>
            Select repositories from your GitHub account to add to your dashboard.
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-col gap-4 flex-1 min-h-0">
          {/* Search and Filters */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <Label htmlFor="search">Search repositories</Label>
              <div className="flex items-center gap-2">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={isAllSelected ? handleDeselectAll : handleSelectAll}
                  className="text-xs"
                  disabled={filteredRepositories.length === 0}
                >
                  {isAllSelected ? 'Deselect All' : 'Select All'}
                </Button>
                <div className="text-sm text-muted-foreground">
                  {selectedRepos.size} selected
                </div>
              </div>
            </div>
            
            <Input
              id="search"
              placeholder="Search by name, description, or organization..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
            
            {/* Filters */}
            <div className="flex gap-4">
              <div className="flex-1">
                <Label className="text-sm">Visibility</Label>
                <Select value={visibilityFilter} onValueChange={(value: 'all' | 'public' | 'private') => setVisibilityFilter(value)}>
                  <SelectTrigger className="w-full">
                    <SelectValue placeholder="Filter by visibility" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Repositories</SelectItem>
                    <SelectItem value="public">Public Only</SelectItem>
                    <SelectItem value="private">Private Only</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              
              <div className="flex-1">
                <Label className="text-sm">Owner Type</Label>
                <Select value={ownerTypeFilter} onValueChange={(value: 'all' | 'Organization' | 'User') => setOwnerTypeFilter(value)}>
                  <SelectTrigger className="w-full">
                    <SelectValue placeholder="Filter by owner type" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Types</SelectItem>
                    <SelectItem value="Organization">Organizations</SelectItem>
                    <SelectItem value="User">Personal</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
          </div>

          <Separator />

          {/* Filter Summary */}
          <div className="flex items-center justify-between text-sm text-muted-foreground">
            <span>
              Showing {filteredRepositories.length} of {repositories.length} repositories
              {(visibilityFilter !== 'all' || ownerTypeFilter !== 'all') && (
                <span className="ml-1">
                  (filtered by {visibilityFilter !== 'all' ? visibilityFilter : ''} 
                  {visibilityFilter !== 'all' && ownerTypeFilter !== 'all' ? ' & ' : ''}
                  {ownerTypeFilter !== 'all' ? ownerTypeFilter.toLowerCase() : ''})
                </span>
              )}
            </span>
            {(debouncedSearchQuery || visibilityFilter !== 'all' || ownerTypeFilter !== 'all') && (
              <Button
                variant="ghost"
                size="sm"
                onClick={clearAllFilters}
                className="text-xs"
              >
                Clear Filters
              </Button>
            )}
          </div>

          {/* Repository Table */}
          <div className="flex-1 overflow-hidden flex flex-col">
            {loading ? (
              <div className="flex items-center justify-center py-12">
                <div className="text-center">
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto mb-2"></div>
                  <p className="text-sm text-muted-foreground">Loading repositories...</p>
                </div>
              </div>
            ) : sortedGroups.length === 0 ? (
              <div className="text-center py-12">
                <p className="text-muted-foreground">No repositories found.</p>
                {(debouncedSearchQuery || visibilityFilter !== 'all' || ownerTypeFilter !== 'all') ? (
                  <div className="mt-4 space-y-2">
                    <p className="text-sm text-muted-foreground">
                      Try adjusting your filters or search terms.
                    </p>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={clearAllFilters}
                    >
                      Clear All Filters
                    </Button>
                  </div>
                ) : (
                  <p className="text-sm text-muted-foreground mt-2">
                    No repositories available from your GitHub account.
                  </p>
                )}
              </div>
            ) : (
              <div className="space-y-4 flex-1 max-h-[500px] overflow-y-auto">
                {sortedGroups.map((group) => (
                  <div key={group.owner} className="space-y-2">
                    {/* Organization/User Header */}
                    <div 
                      className="flex items-center gap-3 px-2 py-2 border-b cursor-pointer hover:bg-muted/50 rounded-md"
                      onClick={() => {
                        const newCollapsed = new Set(collapsedGroups)
                        if (newCollapsed.has(group.owner)) {
                          newCollapsed.delete(group.owner)
                        } else {
                          newCollapsed.add(group.owner)
                        }
                        setCollapsedGroups(newCollapsed)
                      }}
                    >
                      <Avatar className="h-6 w-6">
                        <AvatarImage src={group.owner_avatar_url} alt={group.owner} />
                        <AvatarFallback>{group.owner[0]?.toUpperCase()}</AvatarFallback>
                      </Avatar>
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-sm">{group.owner}</span>
                        <Badge variant="outline" className="text-xs">
                          {group.owner_type}
                        </Badge>
                      </div>
                      <div className="ml-auto flex items-center gap-2">
                        <div className="text-xs text-muted-foreground">
                          {group.repositories.length} repo{group.repositories.length !== 1 ? 's' : ''}
                        </div>
                        {collapsedGroups.has(group.owner) ? (
                          <IconChevronDown className="h-4 w-4" />
                        ) : (
                          <IconChevronUp className="h-4 w-4" />
                        )}
                      </div>
                    </div>

                    {/* Repository Cards */}
                    {!collapsedGroups.has(group.owner) && (
                      <div className="space-y-2 pl-2">
                        {group.repositories.map((repo) => (
                        <Card
                          key={repo.id}
                          className={`cursor-pointer transition-all hover:shadow-md ${
                            selectedRepos.has(repo.id) 
                              ? 'ring-2 ring-primary bg-primary/5' 
                              : 'hover:bg-muted/50'
                          }`}
                          onClick={() => handleSelectRepository(repo.id)}
                        >
                          <CardContent className="p-4">
                            <div className="flex items-start justify-between">
                              <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-2 mb-2">
                                  <IconGitBranch className="h-4 w-4 text-muted-foreground" />
                                  <span className="font-medium text-sm">{repo.name}</span>
                                  <Badge variant={repo.private ? "destructive" : "default"} className="text-xs">
                                    {repo.private ? 'Private' : 'Public'}
                                  </Badge>
                                  {selectedRepos.has(repo.id) && (
                                    <IconCheck className="h-4 w-4 text-primary ml-auto" />
                                  )}
                                </div>
                                
                                {repo.description && (
                                  <div className="text-xs text-muted-foreground mb-3" 
                                     style={{
                                       display: '-webkit-box',
                                       WebkitLineClamp: 2,
                                       WebkitBoxOrient: 'vertical',
                                       overflow: 'hidden'
                                     }}>
                                    {repo.description}
                                  </div>
                                )}
                                
                                <div className="flex items-center gap-4 text-xs text-muted-foreground">
                                  {repo.language && (
                                    <div className="flex items-center gap-1">
                                      <div className={`w-2 h-2 rounded-full ${getLanguageColor(repo.language)}`} />
                                      <span>{repo.language}</span>
                                    </div>
                                  )}
                                  
                                  <div className="flex items-center gap-1">
                                    <IconStar className="h-3 w-3" />
                                    <span>{repo.stargazers_count}</span>
                                  </div>
                                  
                                  <div className="flex items-center gap-1">
                                    <IconGitFork className="h-3 w-3" />
                                    <span>{repo.forks_count}</span>
                                  </div>
                                  
                                  <div className="ml-auto">
                                    {formatDate(repo.updated_at)}
                                  </div>
                                </div>
                              </div>
                            </div>
                          </CardContent>
                        </Card>
                      ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        <DialogFooter className="flex items-center justify-between">
          <p className="text-sm text-muted-foreground">
            {selectedRepos.size} repository(ies) selected
          </p>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button 
              onClick={handleAddRepositories}
              disabled={selectedRepos.size === 0}
            >
              <IconCheck className="h-4 w-4 mr-2" />
              Add Selected ({selectedRepos.size})
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
} 