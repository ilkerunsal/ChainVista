using BlockchainAnalyticsApi.Models;

namespace BlockchainAnalyticsApi
{
    public interface ITenantService
    {
        Tenant? CurrentTenant { get; }                 // Id özelliği olan model
        Task SetCurrentTenantAsync(string tenantId);   // async imza
    }
}
