import React, { createContext, useContext, useState } from 'react';
import type { TrendDetail, TrendListItem } from '@/types';

interface SearchModeContextType {
  mode: 'daily' | 'search';
  searchTopic: string;
  searchRunId: string;
  searchTrends: TrendListItem[];
  searchBrief: TrendDetail | null;
  enterSearch: (runId: string, topic: string, trends: TrendListItem[]) => Promise<void>;
  clearSearch: () => void;
}

const SearchModeContext = createContext<SearchModeContextType | undefined>(undefined);

export function SearchModeProvider({ children }: { children: React.ReactNode }) {
  const [mode, setMode] = useState<'daily' | 'search'>('daily');
  const [searchTopic, setSearchTopic] = useState('');
  const [searchRunId, setSearchRunId] = useState('');
  const [searchTrends, setSearchTrends] = useState<TrendListItem[]>([]);
  const [searchBrief, setSearchBrief] = useState<TrendDetail | null>(null);

  async function enterSearch(runId: string, topic: string, trends: TrendListItem[]) {
    setMode('search');
    setSearchTopic(topic);
    setSearchRunId(runId);
    setSearchTrends(trends);
    setSearchBrief(null);

    if (trends.length > 0) {
      try {
        const res = await fetch(`/api/search/runs/${runId}/trends/${trends[0].slug}`);
        if (res.ok) setSearchBrief(await res.json() as TrendDetail);
      } catch { /* ignore */ }
    }
  }

  function clearSearch() {
    setMode('daily');
    setSearchTopic('');
    setSearchRunId('');
    setSearchTrends([]);
    setSearchBrief(null);
    const url = new URL(window.location.href);
    url.searchParams.delete('q');
    window.history.pushState({}, '', url.toString());
  }

  return (
    <SearchModeContext.Provider value={{ mode, searchTopic, searchRunId, searchTrends, searchBrief, enterSearch, clearSearch }}>
      {children}
    </SearchModeContext.Provider>
  );
}

export function useSearchMode() {
  const ctx = useContext(SearchModeContext);
  if (!ctx) throw new Error('useSearchMode must be used within SearchModeProvider');
  return ctx;
}
