using System.Linq;
using System.Security.Claims;
using System.Threading.Tasks;
using Microsoft.AspNetCore.Http;

namespace BlockchainAnalyticsApi
{
    /// <summary>
    /// Middleware that resolves the user's role from JWT claims or a custom header (X-Role)
    /// and stores it in an <see cref="IRoleService"/> for the duration of the request.
    /// </summary>
    public class RoleResolutionMiddleware
    {
        private readonly RequestDelegate _next;

        public RoleResolutionMiddleware(RequestDelegate next)
        {
            _next = next;
        }

        public async Task InvokeAsync(HttpContext context, IRoleService roleService)
        {
            string? role = null;
            // Try to extract role from claims (e.g., "role" or ClaimTypes.Role)
            var claim = context.User.Claims.FirstOrDefault(c => c.Type == ClaimTypes.Role || c.Type == "role");
            if (claim != null && !string.IsNullOrEmpty(claim.Value))
            {
                role = claim.Value;
            }
            else
            {
                // Fallback: check custom header
                if (context.Request.Headers.TryGetValue("X-Role", out var roles))
                {
                    role = roles.FirstOrDefault();
                }
            }
            await roleService.SetCurrentRoleAsync(role);
            await _next(context);
        }
    }
}