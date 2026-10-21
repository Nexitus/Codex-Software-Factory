# Contributing

Open an issue describing the bug or enhancement and its acceptance criteria. Submit changes with focused tests. Before PR creation, run:

```bash
python -m unittest discover -s tests -v
python -m py_compile factory.py install.py
```

Do not remove fail-closed checks, grant reviewers write access, add production credentials to fixtures or silently enable automatic merges or deployments. Never include `.factory/` generated prompts/reports in PRs. Follow the MIT license.
