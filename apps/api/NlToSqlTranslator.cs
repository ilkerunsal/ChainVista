using System;
using System.Text.RegularExpressions;
using System.Collections.Generic;
using System.Collections.Concurrent;

namespace BlockchainAnalyticsApi
{
    /// <summary>
    /// A very naive translator that converts a limited set of natural language Turkish queries
    /// into SQL statements for demonstration purposes. In production, replace this with a proper
    /// NL→SQL model or service.
    /// </summary>
    public static class NlToSqlTranslator
    {
        // Simple in-memory cache for translated queries. This acts as a semantic
        // cache to avoid recomputing translations for the same natural
        // language inputs. In a production implementation you might use
        // an LRU structure with query signatures and cost-based eviction.
        private static readonly ConcurrentDictionary<string, string?> _cache = new();
        private static readonly ConcurrentQueue<string> _cacheOrder = new();
        private const int CacheCapacity = 100;
        /// <summary>
        /// Translates a natural language query into a SQL string. If the query is not recognised,
        /// returns null.
        /// </summary>
        /// <param name="query">User's natural language query</param>
        /// <returns>SQL statement or null</returns>
        public static string? Translate(string? query)
        {
            if (string.IsNullOrWhiteSpace(query))
            {
                return null;
            }

            // Normalize the query to lower case for caching and pattern matching
            var q = query!.ToLowerInvariant();
            // Check if result is already in cache
            if (_cache.TryGetValue(q, out var cached))
            {
                return cached;
            }

            // Example pattern: "bu adrese son 30 günde kaç erc-20 girmiş?"
            // Check for ERC-20 keyword (with or without hyphen)
            if (q.Contains("erc-20") || q.Contains("erc20"))
            {
                // Extract address (0x...)
                var addressMatch = Regex.Match(q, @"0x[a-f0-9]{40}");
                var address = addressMatch.Success ? addressMatch.Value : null;
                if (string.IsNullOrEmpty(address))
                {
                    return null;
                }

                // Extract day window (e.g. "son 30 günde", "son 7 gün")
                int days = 30;
                var daysMatch = Regex.Match(q, @"son\s*(\d+)\s*gün");
                if (daysMatch.Success && int.TryParse(daysMatch.Groups[1].Value, out var parsedDays))
                {
                    days = parsedDays;
                }

                // Determine whether the user asks for count or sum. Turkish "kaç" implies "how many" (count),
                // whereas phrases like "ne kadar" or "toplam" imply a sum of values.
                bool wantsCount = Regex.IsMatch(q, @"\bkaç\b");

                // Determine direction: if the query mentions "çık"/"çıkan"/"giden"/"gönder" then count outgoing
                // transfers (from_address). Otherwise default to incoming (to_address). Turkish verbs for incoming
                // include "gelen", "girmiş", "alınan".
                string directionColumn = "to_address";
                if (Regex.IsMatch(q, @"\b(çık|çıkan|giden|gönder)\w*", RegexOptions.CultureInvariant))
                {
                    directionColumn = "from_address";
                }

                // Build SELECT clause
                string selectClause = wantsCount ? "COUNT(*) AS total_count" : "SUM(value) AS total_amount";

                // Check for explicit date range e.g. "from 2025-01-01 to 2025-01-31"
                var rangeMatch = Regex.Match(q, @"from\s*(\d{4}-\d{2}-\d{2})\s*to\s*(\d{4}-\d{2}-\d{2})");
                string dateFilter;
                if (rangeMatch.Success)
                {
                    var start = rangeMatch.Groups[1].Value;
                    var end = rangeMatch.Groups[2].Value;
                    // Use BETWEEN for inclusive range. Append time boundaries to cover full days.
                    dateFilter = $"timestamp BETWEEN '{start} 00:00:00' AND '{end} 23:59:59'";
                }
                else
                {
                    // Default to a relative date window
                    dateFilter = $"timestamp >= CURRENT_TIMESTAMP - INTERVAL '{days} days'";
                }

                var sql = $@"SELECT {selectClause}\nFROM erc20_transfers\nWHERE {directionColumn} = '{address}'\n  AND {dateFilter};";
                AddToCache(q, sql);
                return sql;
            }

            // Unrecognised query
            // Unrecognised query. Cache the null result to avoid re-parsing the same input.
            AddToCache(q, null);
            return null;
        }

        /// <summary>
        /// Adds a query and its translation to the cache. If the cache
        /// capacity is exceeded, the oldest entry is removed. This simple
        /// queue-based eviction approximates an LRU cache.
        /// </summary>
        private static void AddToCache(string normalizedQuery, string? translation)
        {
            // Only add if not already cached. TryAdd returns false if key exists.
            if (_cache.TryAdd(normalizedQuery, translation))
            {
                _cacheOrder.Enqueue(normalizedQuery);
                // Remove oldest entries beyond capacity
                while (_cacheOrder.Count > CacheCapacity)
                {
                    if (_cacheOrder.TryDequeue(out var oldest))
                    {
                        _cache.TryRemove(oldest, out _);
                    }
                    else
                    {
                        break;
                    }
                }
            }
        }
    }
}