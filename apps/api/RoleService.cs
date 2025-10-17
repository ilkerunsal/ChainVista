using System.Threading.Tasks;

namespace BlockchainAnalyticsApi
{
    /// <summary>
    /// Default implementation of <see cref="IRoleService"/>.
    /// Stores the role in a property scoped to a single request.
    /// </summary>
    public class RoleService : IRoleService
    {
        /// <inheritdoc />
        public string? CurrentRole { get; private set; }

        /// <inheritdoc />
        public Task SetCurrentRoleAsync(string? role)
        {
            CurrentRole = role;
            return Task.CompletedTask;
        }
    }
}