namespace BlockchainAnalyticsApi
{
    /// <summary>
    /// Service that stores the current user's role for the lifetime of a request.
    /// The role is resolved from a JWT claim or a custom header (X-Role).
    /// </summary>
    public interface IRoleService
    {
        /// <summary>
        /// Gets the role of the current user. May be null or empty if not resolved.
        /// </summary>
        string? CurrentRole { get; }

        /// <summary>
        /// Sets the current user role.
        /// </summary>
        /// <param name="role">The role to set.</param>
        Task SetCurrentRoleAsync(string? role);
    }
}