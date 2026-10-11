# Move this repository into its own GitHub repository

1. On GitHub, create `ODIN3797/robot-incident-analyzer` as a **private** empty repository (do not initialize with README, license, or gitignore).
2. Clone or unpack the project root, run the unit tests, and publish through a normal Git remote.
3. Enable GitHub Actions, read the README's limitation statements, and check branches before making the repository public.

```bash
cd robot-incident-analyzer-v0.4.4-standalone
python3 -m unittest discover -s tests -v
git init
git add .
git commit -m 'Initial robot incident analyzer v0.4.4 alpha'
git branch -M main
git remote add origin https://github.com/ODIN3797/robot-incident-analyzer.git
git push -u origin main
```

GitHub login/authentication is required. This repository is research-alpha only.
