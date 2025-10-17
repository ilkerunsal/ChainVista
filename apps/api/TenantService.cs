using BlockchainAnalyticsApi.Models;
using Microsoft.AspNetCore.Http;

namespace BlockchainAnalyticsApi
{
    public class TenantService : ITenantService
    {
        private readonly IHttpContextAccessor _httpContextAccessor;
        private const string TenantItemKey = "__CurrentTenant__";

        public TenantService(IHttpContextAccessor httpContextAccessor)
        {
            _httpContextAccessor = httpContextAccessor;
        }

        public Tenant? CurrentTenant
        {
            get
            {
                var ctx = _httpContextAccessor.HttpContext;
                if (ctx == null) return null;
                return ctx.Items.TryGetValue(TenantItemKey, out var obj) ? obj as Tenant : null;
            }
        }

        public Task SetCurrentTenantAsync(string tenantId)
        {
            var ctx = _httpContextAccessor.HttpContext;
            if (ctx != null)
            {
                ctx.Items[TenantItemKey] = new Tenant { Id = tenantId };
            }
            return Task.CompletedTask;
        }
    }
}
