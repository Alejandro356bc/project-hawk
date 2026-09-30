# Security Policy

## Reporting a Vulnerability

Please do not open a public issue for suspected vulnerabilities.

Until GitHub private vulnerability reporting is enabled for the repository,
send the report privately to the project maintainer. Include:

- The affected version or commit
- Steps to reproduce
- Expected and actual behavior
- Any logs or screenshots that help explain impact

After the GitHub repository is created, enable private vulnerability reporting
and update this file with the repository-specific reporting link.

## Operational Cautions

Quorum can give models access to local files and shell commands when users opt
in to those features. Treat that like running an assistant inside the current
working directory.

- Keep `.env` private and never commit API keys.
- Keep `.env.example` limited to empty values and obvious placeholders.
- Enable `*_TOOLS=on` only in directories you trust.
- Enable `CODEX_BYPASS_SANDBOX=on` only when you understand the local impact.
- Use `CLAUDE_PERMISSION_MODE=bypassPermissions` only in trusted environments.
- Review model-written changes before committing them.

## If a Credential Is Committed

Treat it as exposed even if the repository is private or the commit was not
intended to be published.

1. Revoke or rotate the credential at the provider immediately.
2. Remove it from the current tree.
3. Rewrite the affected Git history before making the repository public.
4. Run the repository secret scan again and verify the replacement credential
   exists only in an ignored local `.env`.

Deleting a credential in a later commit does not remove it from Git history.
