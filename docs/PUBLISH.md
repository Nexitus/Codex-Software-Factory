# Publish this framework as a new GitHub repository

The ChatGPT GitHub connector used to research this project cannot create a new repository. Publishing the source requires a repo already created in GitHub or a local GitHub CLI credential.

Recommended repository: `Nexitus/agentic-software-factory` (MIT license). The repository did not exist when checked on 2026-10-20.

## GitHub CLI route (from the extracted folder)

```bash
gh auth login
cd agentic-software-factory
git init -b main
git add .
git -c user.name="Your Name" -c user.email="you@example.com" commit -m "feat: initial dual-provider software factory"
gh repo create Nexitus/agentic-software-factory --public --source=. --remote=origin --push
```

Replace the `user.name`/`user.email` placeholders with your real GitHub Git identity. If you prefer private, replace `--public` with `--private`.

If the repository already exists and is empty, use:

```bash
git remote add origin git@github.com:Nexitus/agentic-software-factory.git
git push -u origin main
```

## Configure the new repository

Enable main branch protection, required CI checks, secret scanning, dependency updates and protected tags in GitHub settings. The framework repository's own CI only tests the supervisor. Each target application repository must configure its own deterministic test/lint/security/build/UI gates.

The `--publish-pr` flag in `factory.py` is for publishing **generated application changes** to application repositories, not for creating the software-factory framework repository itself.
