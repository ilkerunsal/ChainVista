using System;
using System.Collections.Generic;

namespace BlockchainAnalyticsApi
{
    /// <summary>
    /// Represents an audit entry for natural language queries processed by the API.
    /// Logs include the role of the caller, tenant identifier, the original query,
    /// the generated SQL (if any), and the timestamp. This information can be
    /// used for compliance auditing and replaying historical queries.
    /// </summary>
    public record QueryAuditLog(string Role, string TenantId, string Query, string? Sql, DateTime Timestamp);

    /// <summary>
    /// In-memory store for query audit logs. This static store retains a recent
    /// history of processed queries. In production, this could be backed by a
    /// database or persistent log system for durability and querying across
    /// multiple API instances.
    /// </summary>
    public static class QueryAuditStore
    {
        // Internal list to hold logs. A simple lock protects concurrent access.
        private static readonly List<QueryAuditLog> _logs = new();
        private static readonly object _lock = new();
        private const int MaxEntries = 1000;

        /// <summary>
        /// Adds a log entry to the store. If the maximum number of entries is
        /// exceeded, the oldest entry is removed. This approximates a basic
        /// FIFO buffer to prevent unbounded memory growth.
        /// </summary>
        public static void AddLog(QueryAuditLog log)
        {
            lock (_lock)
            {
                _logs.Add(log);
                if (_logs.Count > MaxEntries)
                {
                    _logs.RemoveAt(0);
                }
            }
        }

        /// <summary>
        /// Returns a snapshot of all stored logs. The returned list is read-only
        /// to prevent external modifications. Consumers can enumerate over it
        /// without mutating the underlying storage.
        /// </summary>
        public static IReadOnlyList<QueryAuditLog> GetLogs()
        {
            lock (_lock)
            {
                return _logs.ToArray();
            }
        }
    }
}