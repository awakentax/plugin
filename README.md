# Awaken for Cursor

Connect Cursor to your [Awaken](https://awaken.tax) crypto tax workspace through OAuth. Install the plugin, sign in to Awaken, and choose the workspace and access level on the consent page.

The plugin includes a hosted MCP connection at `https://mcp.awaken.tax/mcp` and Awaken's published `awaken` skill for transaction review, missing cost-basis investigation, and reports. No local server or runtime is needed to use the MCP connection.

The bundled skill is an unchanged copy of [api.awaken.tax/skill](https://api.awaken.tax/skill), version **1.0.1**, with its companion [cookbook.md](https://api.awaken.tax/skill/cookbook.md). The skill prefers connected MCP tools and also documents a separate direct-API workflow. Refresh both bundled files together when updating the published skill.

## Connect

1. Install **Awaken** from Cursor's Customize page once the marketplace listing is available.
2. Enable the `awaken` MCP server and start its authentication flow in Cursor.
3. In the browser, sign in to Awaken and select the workspace you want to connect.
4. Review the requesting app and choose **Allow read access** or **Allow read + write**, then return to Cursor.
5. Start a new agent chat and ask it to list the available Awaken tools and verify access with a read operation.

Awaken checks workspace membership and Connected Apps eligibility during consent and token use. If a workspace is unavailable, choose an eligible workspace. No API key or manually entered Awaken client ID is required for the MCP connection. An API-key option for the plugin's MCP connection is deferred to a later version.

The plugin requests `read` and `write` so the consent page can offer both access levels. You can approve read-only access. Write tools may still appear in discovery; Awaken enforces the scopes you actually approved when a tool runs.

## Try it

Invoke `/awaken`, or ask Cursor:

- “Review my largest taxable events for 2025 and flag missing cost basis.”
- “Find my unreviewed transactions and explain proposed labels before editing.”
- “Generate my Form 8949 for 2025 and give me the download link when ready.”

Edits require approved write access and authorization for the requested changes. Report availability depends on your workspace and the server's tools.

## Reconnect or disconnect

Cursor handles OAuth tokens and refresh. If the connection expires or authentication fails, reconnect the `awaken` server through Cursor and complete consent again. For a write operation blocked by read-only access, follow Cursor's scope-approval flow or reconnect and approve read + write.

To revoke access, disconnect Cursor from **Connected Apps** in Awaken Settings. Disabling the server in Cursor stops its use there; revoking the grant in Awaken invalidates the authorization.

## OAuth configuration

The MCP configuration uses Cursor's public OAuth identity:

```json
{
  "mcpServers": {
    "awaken": {
      "url": "https://mcp.awaken.tax/mcp",
      "auth": {
        "CLIENT_ID": "https://cursor.com/oauth/mcp-client.json",
        "scopes": ["read", "write"]
      }
    }
  }
}
```

`CLIENT_ID` identifies the Cursor application; it is not an Awaken workspace ID. There is no client secret. Cursor performs the authorization-code flow with PKCE and uses Awaken's published discovery endpoints:

- [Protected resource](https://mcp.awaken.tax/.well-known/oauth-protected-resource/mcp)
- [Authorization server](https://mcp.awaken.tax/.well-known/oauth-authorization-server)
- [Cursor client metadata](https://cursor.com/oauth/mcp-client.json)

Awaken recognizes this Cursor metadata identity and validates its advertised callbacks. It supports authorization-code and refresh-token grants with `S256` PKCE; it does not advertise dynamic client registration. Explicitly setting the public client identity uses that existing flow. See [Cursor's OAuth configuration](https://cursor.com/docs/mcp#static-oauth-for-remote-servers).

## Troubleshooting

- **Plugin missing:** check the manifest location, local-import policy, competing marketplace installation, and reload Cursor.
- **No login prompt or `invalid_client`:** check that the shipped `auth.CLIENT_ID` is intact and that the installed Cursor version supports remote OAuth. Awaken accepts the recognized Cursor metadata identity; arbitrary registered client IDs are unsupported.
- **Workspace unavailable:** Awaken checks direct workspace membership and Connected Apps eligibility. Use the intended eligible workspace.
- **Edit denied:** approve write access through OAuth consent; tool visibility alone does not grant write access.
- **Report preparing:** use status/retrieval tools instead of starting duplicate exports. See [Awaken reports](https://awaken.tax/docs/consumer/reports).

## Data access

The package connects directly to Awaken's hosted MCP service. OAuth access is bound to the selected workspace and approved scopes. Tool arguments go to Awaken; returned data is available to Cursor's agent. The package adds no analytics or local executable hooks. OAuth credentials apply to the canonical MCP endpoint and must not be used for GraphQL or other Awaken API surfaces.

For service details, see [Awaken documentation](https://awaken.tax/docs).

## License

Plugin code and instructions are MIT licensed; see [LICENSE](LICENSE). The Awaken logo is an Awaken brand asset and is not covered by the code license. Its source is `https://awaken.tax/docs/awaken-word.svg`.
