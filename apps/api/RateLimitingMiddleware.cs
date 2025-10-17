using System;
using System.Collections.Concurrent;
using System.Threading.Tasks;
using Microsoft.AspNetCore.Http;

namespace BlockchainAnalyticsApi
{
    /// <summary>
    /// Simple in-memory rate limiting middleware. Limits the number of requests per identifier
    /// (tenant ID or client IP) within a fixed time window. When the limit is exceeded, returns
    /// HTTP 429 Too Many Requests.
    /// </summary>
    public class RateLimitingMiddleware
    {
        private readonly RequestDelegate _next;

        // Use a concurrent dictionary to store request counts per key
        private static readonly ConcurrentDictionary<string, RateLimitState> _states = new();

        // Configure the limit and window duration
        private const int RequestLimit = 100; // max requests per window
        private static readonly TimeSpan WindowDuration = TimeSpan.FromMinutes(1);

        public RateLimitingMiddleware(RequestDelegate next)
        {
            _next = next;
        }

        public async Task InvokeAsync(HttpContext context)
        {
            var now = DateTime.UtcNow;
            // Determine the key to track: prefer tenant ID, then client IP, then fallback
            string key = context.Request.Headers.TryGetValue("X-Tenant-ID", out var tenantVals) && !string.IsNullOrEmpty(tenantVals)
                ? tenantVals.ToString()
                : context.Connection.RemoteIpAddress?.ToString() ?? "anonymous";

            // Get or create state
            var state = _states.GetOrAdd(key, _ => new RateLimitState { Timestamp = now, Count = 0 });

            bool limitExceeded = false;
            lock (state)
            {
                // If the window has expired, reset
                if (now - state.Timestamp > WindowDuration)
                {
                    state.Timestamp = now;
                    state.Count = 1;
                }
                else
                {
                    state.Count++;
                }
                if (state.Count > RequestLimit)
                {
                    limitExceeded = true;
                }
            }

            if (limitExceeded)
            {
                context.Response.StatusCode = StatusCodes.Status429TooManyRequests;
                context.Response.ContentType = "application/json";
                await context.Response.WriteAsync("{\"error\":\"Too Many Requests\"}");
                return;
            }

            await _next(context);
        }

        private class RateLimitState
        {
            public DateTime Timestamp;
            public int Count;
        }
    }
}