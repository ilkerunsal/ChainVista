using System;
using System.Net.Http;
using System.Net.Http.Json;
using System.Text;
using System.Text.Json;
using System.Threading.Tasks;
using Microsoft.Extensions.Logging;
using System.Collections.Generic;
using System.Linq;

namespace BlockchainAnalyticsApi
{
    /// <summary>
    /// Interface for sending alert notifications to multiple channels (e.g., Slack, email, webhook).
    /// </summary>
    public interface INotificationService
    {
        /// <summary>
        /// Sends an alert message for the given tenant. If channels is null or empty, the alert
        /// will be sent via all available channels configured via environment variables. If channels
        /// are specified, only those channels will be used (e.g., "slack", "email", "webhook").
        /// </summary>
        /// <param name="tenantId">Tenant identifier used for logging and templating.</param>
        /// <param name="message">The message to send.</param>
        /// <param name="channels">Optional list of channels to target; if null, send on all configured channels.</param>
        /// <returns>A task that completes when notifications have been attempted.</returns>
        Task SendAlertAsync(string tenantId, string message, IEnumerable<string>? channels = null);
    }

    /// <summary>
    /// Default implementation of <see cref="INotificationService"/>. Supports Slack incoming webhooks.
    /// Additional channels can be added by extending <see cref="SendAlertAsync"/>.
    /// </summary>
    public class NotificationService : INotificationService
    {
        private readonly IHttpClientFactory _clientFactory;
        private readonly ILogger<NotificationService> _logger;

        public NotificationService(IHttpClientFactory clientFactory, ILogger<NotificationService> logger)
        {
            _clientFactory = clientFactory;
            _logger = logger;
        }

        public async Task SendAlertAsync(string tenantId, string message, IEnumerable<string>? channels = null)
        {
            // Determine which channels to send. If channels list is null or empty, send to all configured.
            var targetChannels = channels != null ? new HashSet<string>(channels.Select(c => c.ToLowerInvariant())) : null;

            // Slack notification
            var slackWebhook = Environment.GetEnvironmentVariable("SLACK_WEBHOOK_URL");
            if (!string.IsNullOrEmpty(slackWebhook) && (targetChannels == null || targetChannels.Contains("slack")))
            {
                try
                {
                    var client = _clientFactory.CreateClient();
                    var payload = new { text = message };
                    var response = await client.PostAsJsonAsync(slackWebhook, payload);
                    if (!response.IsSuccessStatusCode)
                    {
                        _logger.LogWarning("Failed to post Slack notification: {StatusCode}", response.StatusCode);
                    }
                    else
                    {
                        _logger.LogInformation("Slack notification sent for tenant {TenantId}", tenantId);
                    }
                }
                catch (Exception ex)
                {
                    _logger.LogError(ex, "Error sending Slack notification");
                }
            }

            // Generic webhook notification
            var genericWebhook = Environment.GetEnvironmentVariable("GENERIC_WEBHOOK_URL");
            if (!string.IsNullOrEmpty(genericWebhook) && (targetChannels == null || targetChannels.Contains("webhook")))
            {
                try
                {
                    var client = _clientFactory.CreateClient();
                    var payload = new { tenantId, message };
                    var response = await client.PostAsJsonAsync(genericWebhook, payload);
                    if (!response.IsSuccessStatusCode)
                    {
                        _logger.LogWarning("Failed to post generic webhook notification: {StatusCode}", response.StatusCode);
                    }
                    else
                    {
                        _logger.LogInformation("Generic webhook notification sent for tenant {TenantId}", tenantId);
                    }
                }
                catch (Exception ex)
                {
                    _logger.LogError(ex, "Error sending generic webhook notification");
                }
            }

            // Email notification
            var smtpHost = Environment.GetEnvironmentVariable("EMAIL_SMTP_HOST");
            var smtpPortStr = Environment.GetEnvironmentVariable("EMAIL_SMTP_PORT");
            var smtpUser = Environment.GetEnvironmentVariable("EMAIL_SMTP_USER");
            var smtpPass = Environment.GetEnvironmentVariable("EMAIL_SMTP_PASS");
            var fromAddress = Environment.GetEnvironmentVariable("EMAIL_FROM_ADDRESS") ?? smtpUser;
            var toAddresses = Environment.GetEnvironmentVariable("NOTIFICATION_EMAIL_TO");
            if (!string.IsNullOrEmpty(smtpHost) && !string.IsNullOrEmpty(toAddresses) && (targetChannels == null || targetChannels.Contains("email")))
            {
                try
                {
                    var port = 25;
                    if (!string.IsNullOrEmpty(smtpPortStr) && int.TryParse(smtpPortStr, out var parsed))
                    {
                        port = parsed;
                    }
                    using var smtpClient = new System.Net.Mail.SmtpClient(smtpHost, port)
                    {
                        Credentials = !string.IsNullOrEmpty(smtpUser) ? new System.Net.NetworkCredential(smtpUser, smtpPass) : null,
                        EnableSsl = true
                    };
                    var mailMessage = new System.Net.Mail.MailMessage
                    {
                        From = new System.Net.Mail.MailAddress(fromAddress ?? "no-reply@example.com"),
                        Subject = $"Blockchain Analytics Alert (Tenant {tenantId})",
                        Body = message
                    };
                    foreach (var addr in toAddresses.Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries))
                    {
                        mailMessage.To.Add(addr);
                    }
                    await smtpClient.SendMailAsync(mailMessage);
                    _logger.LogInformation("Email notification sent for tenant {TenantId}", tenantId);
                }
                catch (Exception ex)
                {
                    _logger.LogError(ex, "Error sending email notification");
                }
            }
        }
    }
}