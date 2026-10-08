# Awaken for Cursor

Connect Cursor to your [Awaken](https://awaken.tax) crypto tax workspace through OAuth. Install the plugin, sign in to Awaken, and choose the workspace and access level on the consent page.

The plugin includes a hosted MCP connection at `https://mcp.awaken.tax/mcp` and Awaken's published `awaken` skill for transaction review, missing cost-basis investigation, and reports. No local server or runtime is needed to use the MCP connection.

The bundled skill is an unchanged copy of [api.awaken.tax/skill](https://api.awaken.tax/skill), version **1.0.1**, with its companion [cookbook.md](https://api.awaken.tax/skill/cookbook.md). The skill prefers connected MCP tools and also documents a separate direct-API workflow. Refresh both bundled files together when updating the published skill.

## Connect

1. Install **Awaken** from Cursor's Customize page once the marketplace listing is available, or use the local installation below.
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

## Test locally before publishing

From the repository root, run:

```sh
python3 scripts/validate.py
mkdir -p "$HOME/.cursor/plugins/local/awaken"
rsync -a --exclude='.git' --exclude='.github' --exclude='.env*' ./ "$HOME/.cursor/plugins/local/awaken/"
```

Keep the copied MCP configuration as shipped; no credential substitution is needed. If upgrading a previous local copy configured with an API key, copying this version replaces that configuration. Revoke the old key in Awaken if it is no longer needed.

Run **Developer: Reload Window** or restart Cursor. Confirm the `awaken` skill and MCP server appear in Customize, then complete OAuth login and consent.

- Verify tool discovery and a read operation against the selected workspace.
- With read-only consent, confirm an edit is denied or asks for additional consent.
- With write consent, test one explicitly authorized reversible change and read the affected record back.
- Verify a report request completes and returns a download link.
- Verify reconnect and revocation through Awaken Connected Apps.

Local imports must be permitted by your team's policy. Use a real directory copy: Cursor skips symlinks pointing outside its local plugins directory. An installed marketplace plugin of the same name takes precedence. See [Cursor's local testing guide](https://cursor.com/docs/plugins#test-plugins-locally).

Package checks and public OAuth discovery checks do not establish that the browser login, consent, callback, refresh, or authenticated tool use succeed in a particular Cursor installation. Complete those checks before submission.

### Troubleshooting

- **Plugin missing:** check the manifest location, local-import policy, competing marketplace installation, and reload Cursor.
- **No login prompt or `invalid_client`:** check that the shipped `auth.CLIENT_ID` is intact and that the installed Cursor version supports remote OAuth. Awaken accepts the recognized Cursor metadata identity; arbitrary registered client IDs are unsupported.
- **Workspace unavailable:** Awaken checks direct workspace membership and Connected Apps eligibility. Use the intended eligible workspace.
- **Edit denied:** approve write access through OAuth consent; tool visibility alone does not grant write access.
- **Report preparing:** use status/retrieval tools instead of starting duplicate exports. See [Awaken reports](https://awaken.tax/docs/consumer/reports).

## Data access

The package connects directly to Awaken's hosted MCP service. OAuth access is bound to the selected workspace and approved scopes. Tool arguments go to Awaken; returned data is available to Cursor's agent. The package adds no analytics or local executable hooks. OAuth credentials apply to the canonical MCP endpoint and must not be used for GraphQL or other Awaken API surfaces.

For service details, see [Awaken documentation](https://awaken.tax/docs).

## Submit to the Cursor marketplace

- [ ] Run the package checks and complete the authenticated local tests above.
- [ ] Confirm the plugin name `awaken` is available during review.
- [ ] Publish this repository at `https://github.com/awakentax/plugin` and verify it is public.
- [ ] Sign in at [Publish a plugin](https://cursor.com/marketplace/publish) and submit that repository URL.
- [ ] Address review feedback and keep the listing, setup instructions, and version current.

Suggested listing description:

> Connect Cursor to Awaken with OAuth to review crypto transactions, investigate missing cost basis, and generate tax reports in your chosen workspace.

Cursor manually reviews submissions and updates. See the [submission checklist](https://cursor.com/docs/reference/plugins#submission-checklist).

## License

Plugin code and instructions are MIT licensed; see [LICENSE](LICENSE). The Awaken logo is an Awaken brand asset and is not covered by the code license. Its source is `https://awaken.tax/docs/awaken-word.svg`.
