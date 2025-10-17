// ==== Usings (eksikleri tamamlandı) ====
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Http;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.DependencyInjection;

using Microsoft.AspNetCore.Authentication.JwtBearer;
using Microsoft.IdentityModel.Tokens;

using System;
using System.Collections.Generic;
using System.Linq;
using System.Net.Http;
using System.Net.Http.Json;
using System.Text.Json;
using System.Text.Json.Serialization;
using System.Threading.Tasks;

using BlockchainAnalyticsApi;

// ==== Top-level statements BAŞLANGIÇ ====
var builder = WebApplication.CreateBuilder(args);

// AuthN/AuthZ
builder.Services.AddAuthentication(JwtBearerDefaults.AuthenticationScheme)
    .AddJwtBearer(options =>
    {
        options.TokenValidationParameters = new TokenValidationParameters
        {
            ValidateIssuer = false,
            ValidateAudience = false,
            ValidateLifetime = false,
            ValidateIssuerSigningKey = false
        };
    });
builder.Services.AddAuthorization();

// CORS
builder.Services.AddCors(options =>
{
    options.AddPolicy("AllowAll", policy =>
    {
        policy.AllowAnyOrigin()
              .AllowAnyHeader()
              .AllowAnyMethod();
    });
});

// DI kayıtları
builder.Services.AddSingleton<IHttpContextAccessor, HttpContextAccessor>();
builder.Services.AddScoped<ITenantService, TenantService>();
builder.Services.AddScoped<IRoleService, RoleService>();
builder.Services.AddHttpClient();
builder.Services.AddSingleton<INotificationService, NotificationService>();
builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSwaggerGen();
builder.Services.AddSingleton<IHttpContextAccessor, HttpContextAccessor>();
builder.Services.AddScoped<ITenantService, TenantService>();


var app = builder.Build();

// Middlewareler
app.UseMiddleware<TenantResolutionMiddleware>();
app.UseMiddleware<RoleResolutionMiddleware>();
app.UseMiddleware<RateLimitingMiddleware>();

app.UseHttpsRedirection();
app.UseHsts();
app.UseCors("AllowAll");
app.UseAuthentication();
app.UseAuthorization();
app.UseSwagger();
app.UseSwaggerUI(c =>
{
    c.SwaggerEndpoint("/swagger/v1/swagger.json", "Blockchain Analytics API v1");
    c.RoutePrefix = "swagger"; // UI: /swagger
});


// Endpoints
app.MapGet("/status", () => Results.Ok(new { status = "ok" }));

app.MapPost("/ask", async (HttpRequest request) =>
{
    var roleService = request.HttpContext.RequestServices.GetService(typeof(IRoleService)) as IRoleService;
    var role = roleService?.CurrentRole;
    if (role != "admin" && role != "analyst") return Results.Forbid();

    var askRequest = await JsonSerializer.DeserializeAsync<AskRequest>(request.Body);
    if (askRequest == null || string.IsNullOrWhiteSpace(askRequest.Query))
        return Results.BadRequest(new { error = "No query provided" });

    if (askRequest.Query.Length > 2000)
        return Results.BadRequest(new { error = "Query too long" });

    var sql = NlToSqlTranslator.Translate(askRequest.Query);
    var tenantService = request.HttpContext.RequestServices.GetService(typeof(ITenantService)) as ITenantService;
    var tenantId = tenantService?.CurrentTenant?.Id;

    if (sql == null)
    {
        var tenantIdFail = tenantId ?? "unknown";
        QueryAuditStore.AddLog(new QueryAuditLog(role ?? "unknown", tenantIdFail, askRequest.Query, null, DateTime.UtcNow));
        return Results.Ok(new { message = "Could not translate query", query = askRequest.Query });
    }

    if (!string.IsNullOrEmpty(tenantId))
        sql = sql.TrimEnd(';') + $"\nAND tenant_id = '{tenantId}';";

    QueryAuditStore.AddLog(new QueryAuditLog(role ?? "unknown", tenantId ?? "unknown", askRequest.Query, sql, DateTime.UtcNow));
    return Results.Ok(new { sql });
}).RequireAuthorization();

app.MapGet("/alerts", (HttpContext ctx) =>
{
    var roleService = ctx.RequestServices.GetService(typeof(IRoleService)) as IRoleService;
    var role = roleService?.CurrentRole;
    if (role != "admin" && role != "analyst") return Results.Forbid();
    return Results.Ok(Array.Empty<object>());
}).RequireAuthorization();

app.MapGet("/metrics", (HttpContext ctx) =>
{
    var roleService = ctx.RequestServices.GetService(typeof(IRoleService)) as IRoleService;
    if (roleService?.CurrentRole != "admin") return Results.Forbid();
    return Results.Ok(new { uptime = "0s" });
});

app.MapGet("/flows", (HttpContext context) =>
{
    var roleService = context.RequestServices.GetService(typeof(IRoleService)) as IRoleService;
    var roleVal = roleService?.CurrentRole;
    if (roleVal != "admin" && roleVal != "analyst") return Results.Forbid();

    var address = context.Request.Query["address"].ToString();
    if (string.IsNullOrWhiteSpace(address))
        return Results.BadRequest(new { error = "Address query parameter is required" });

    string Normalize(string addr) => addr.Length > 10 ? addr[..6] + "..." + addr[^4..] : addr;

    var related = new List<string>();
    for (int i = 0; i < 4; i++) related.Add($"0x{Guid.NewGuid():N}"[..40]);

    var nodes = new List<object> { new { id = address, label = Normalize(address) } };
    foreach (var r in related) nodes.Add(new { id = r, label = Normalize(r) });

    var rand = new Random(address.GetHashCode());
    var edges = new List<object>();
    foreach (var r in related)
    {
        edges.Add(new { source = address, target = r, weight = rand.Next(1, 10) });
        if (rand.NextDouble() > 0.5)
            edges.Add(new { source = r, target = address, weight = rand.Next(1, 10) });
    }

    return Results.Ok(new { nodes, edges });
}).RequireAuthorization();

app.MapPost("/anomaly", async (HttpRequest request) =>
{
    var roleService = request.HttpContext.RequestServices.GetService(typeof(IRoleService)) as IRoleService;
    var role = roleService?.CurrentRole;
    if (role != "admin" && role != "analyst") return Results.Forbid();

    var anomalyReq = await JsonSerializer.DeserializeAsync<AnomalyRequestCSharp>(request.Body);
    if (anomalyReq == null || anomalyReq.Values == null)
        return Results.BadRequest(new { error = "Invalid anomaly request" });

    var serviceUrl = Environment.GetEnvironmentVariable("AI_SERVICE_URL")
                    ?? Environment.GetEnvironmentVariable("AI_ANOMALY_URL")
                    ?? "http://localhost:8000";

    try
    {
        using var httpClient = new HttpClient { BaseAddress = new Uri(serviceUrl) };
        var response = await httpClient.PostAsJsonAsync("/anomaly", anomalyReq);
        if (!response.IsSuccessStatusCode)
            return Results.Problem($"AI service responded with {response.StatusCode}: {await response.Content.ReadAsStringAsync()}");

        var anomalyRes = await response.Content.ReadFromJsonAsync<AnomalyResponseCSharp>();
        if (anomalyRes == null) return Results.Problem("Invalid response from AI anomaly service");

        if (anomalyRes.IsAnomaly)
        {
            var threshold = anomalyReq.Threshold ?? 3.0;
            string severity = anomalyRes.Score >= threshold * 2 ? "critical" : "warning";

            var tenantService = request.HttpContext.RequestServices.GetService(typeof(ITenantService)) as ITenantService;
            var tenantId = tenantService?.CurrentTenant?.Id ?? "unknown";
            var alertMessage = $"Anomaly detected for tenant {tenantId}: score={anomalyRes.Score:0.00}, threshold={threshold:0.00}, severity={severity}";

            var roleSvc = request.HttpContext.RequestServices.GetService(typeof(IRoleService)) as IRoleService;
            var userRole = roleSvc?.CurrentRole?.ToLowerInvariant() ?? "unknown";
            IEnumerable<string>? channels = userRole switch
            {
                "security" => new[] { "email" },
                "compliance" => new[] { "webhook" },
                "analyst" => new[] { "slack" },
                "admin" => null,
                _ => null
            };

            var notifSvc = request.HttpContext.RequestServices.GetService(typeof(INotificationService)) as INotificationService;
            if (notifSvc != null)
                _ = Task.Run(() => notifSvc.SendAlertAsync(tenantId, alertMessage, channels));

            return Results.Ok(new { anomalyRes.Score, anomalyRes.IsAnomaly, anomalyRes.Message, severity });
        }

        return Results.Ok(anomalyRes);
    }
    catch (Exception ex)
    {
        return Results.Problem($"Error calling AI anomaly service: {ex.Message}");
    }
}).RequireAuthorization();

app.MapPost("/label", async (HttpRequest request) =>
{
    var roleService = request.HttpContext.RequestServices.GetService(typeof(IRoleService)) as IRoleService;
    var role = roleService?.CurrentRole;
    if (role != "admin" && role != "analyst") return Results.Forbid();

    var labelReq = await JsonSerializer.DeserializeAsync<LabelRequestCSharp>(request.Body);
    if (labelReq == null || string.IsNullOrWhiteSpace(labelReq.Address))
        return Results.BadRequest(new { error = "Invalid label request" });

    var serviceUrl = Environment.GetEnvironmentVariable("AI_SERVICE_URL")
                    ?? Environment.GetEnvironmentVariable("AI_ANOMALY_URL")
                    ?? "http://localhost:8000";

    try
    {
        using var httpClient = new HttpClient { BaseAddress = new Uri(serviceUrl) };
        var response = await httpClient.PostAsJsonAsync("/label", labelReq);
        if (!response.IsSuccessStatusCode)
            return Results.Problem($"AI service responded with {response.StatusCode}: {await response.Content.ReadAsStringAsync()}");

        var labelRes = await response.Content.ReadFromJsonAsync<LabelResponseCSharp>();
        return Results.Ok(labelRes);
    }
    catch (Exception ex)
    {
        return Results.Problem($"Error calling AI anomaly service: {ex.Message}");
    }
}).RequireAuthorization();

app.MapPost("/notify", async (HttpRequest request) =>
{
    var roleService = request.HttpContext.RequestServices.GetService(typeof(IRoleService)) as IRoleService;
    var role = roleService?.CurrentRole;
    if (role != "admin" && role != "analyst") return Results.Forbid();

    var notifyReq = await JsonSerializer.DeserializeAsync<NotifyRequest>(request.Body);
    if (notifyReq == null || string.IsNullOrWhiteSpace(notifyReq.Message))
        return Results.BadRequest(new { error = "Invalid notification request" });

    var tenantService = request.HttpContext.RequestServices.GetService(typeof(ITenantService)) as ITenantService;
    var tenantId = tenantService?.CurrentTenant?.Id ?? "unknown";

    var roleSvc = request.HttpContext.RequestServices.GetService(typeof(IRoleService)) as IRoleService;
    var currentRole = roleSvc?.CurrentRole?.ToLowerInvariant();

    IEnumerable<string>? channels = notifyReq.Channels;
    if (channels == null || !channels.Any())
    {
        channels = currentRole switch
        {
            "security" => new[] { "email" },
            "compliance" => new[] { "webhook" },
            "analyst" => new[] { "slack" },
            "admin" => null,
            _ => null
        };
    }

    var notifService = request.HttpContext.RequestServices.GetService(typeof(INotificationService)) as INotificationService;
    if (notifService == null) return Results.Problem("Notification service is not available");

    try
    {
        await notifService.SendAlertAsync(tenantId, notifyReq.Message, channels);
        return Results.Ok(new { message = "Notification sent" });
    }
    catch (Exception ex)
    {
        return Results.Problem($"Error sending notification: {ex.Message}");
    }
}).RequireAuthorization();

app.Run(); // <-- Top-level statements burada biter.
// ==== Top-level statements BİTİŞ ====


// ==== Tip/record tanımları (artık dosyanın sonunda) ====
public record AskRequest([property: JsonPropertyName("query")] string Query);

public record AnomalyRequestCSharp(
    [property: JsonPropertyName("values")] List<double> Values,
    [property: JsonPropertyName("threshold")] double? Threshold);

public record AnomalyResponseCSharp(
    [property: JsonPropertyName("score")] double Score,
    [property: JsonPropertyName("is_anomaly")] bool IsAnomaly,
    [property: JsonPropertyName("message")] string Message);

public record LabelRequestCSharp(
    [property: JsonPropertyName("address")] string Address,
    [property: JsonPropertyName("chain")] string? Chain);

public record LabelResponseCSharp(
    [property: JsonPropertyName("label")] string Label,
    [property: JsonPropertyName("confidence")] double Confidence,
    [property: JsonPropertyName("details")] Dictionary<string, object> Details);

public record NotifyRequest(
    [property: JsonPropertyName("message")] string Message,
    [property: JsonPropertyName("channels")] IEnumerable<string>? Channels);
