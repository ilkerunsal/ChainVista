using System.Threading.Tasks;
using BlockchainAnalyticsApi.Models;
using Microsoft.AspNetCore.Http;

namespace BlockchainAnalyticsApi
{
    /// <summary>
    /// Middleware that resolves the current tenant from the incoming HTTP request.
    /// The tenant identifier is expected in the <c>X-Tenant-ID</c> header. For most
    /// endpoints, if this header is absent a 400 Bad Request response is returned.
    /// An exception is made for the <c>/status</c> endpoint to allow unauthenticated
    /// health checks without specifying a tenant.
    /// </summary>
    public class TenantResolutionMiddleware
    {
        private readonly RequestDelegate _next;

        public TenantResolutionMiddleware(RequestDelegate next) => _next = next;

        public async Task InvokeAsync(HttpContext context, ITenantService tenantSvc, IHostEnvironment env)
        {
            var path = context.Request.Path.Value ?? string.Empty;

            // 1) Swagger ve public uçlar BYPASS
            if (path.StartsWith("/swagger", StringComparison.OrdinalIgnoreCase) ||
                path.Equals("/status", StringComparison.OrdinalIgnoreCase) ||
                path.StartsWith("/health", StringComparison.OrdinalIgnoreCase))
            {
                await _next(context);
                return;
            }

            // 2) Header ya da query'den tenant al
            var tenantId =
                context.Request.Headers["X-Tenant-Id"].FirstOrDefault()
                ?? context.Request.Query["tenantId"].FirstOrDefault();

            // 3) Dev ortamda default tenant'a düş (opsiyonel ama pratik)
            if (string.IsNullOrWhiteSpace(tenantId) && env.IsDevelopment())
            {
                tenantId = "dev";
            }

            if (string.IsNullOrWhiteSpace(tenantId))
            {
                context.Response.StatusCode = StatusCodes.Status400BadRequest;
                await context.Response.WriteAsync("Tenant ID missing.");
                return;
            }

            await tenantSvc.SetCurrentTenantAsync(tenantId);   // <-- async imzaya göre çağır
            await _next(context);
        }
    }

}