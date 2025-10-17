namespace BlockchainAnalyticsApi
{
    /// <summary>
    /// Represents tenant-specific information such as ID and name. Extend this class with
    /// additional configuration fields (e.g. theme colour, DB connection string) as needed.
    /// </summary>
    public class TenantInfo
    {
        public string Id { get; set; } = string.Empty;
        public string Name { get; set; } = string.Empty;
    }
}