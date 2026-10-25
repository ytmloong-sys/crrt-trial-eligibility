# How to create the GitHub repository and Zenodo DOI

This folder is GitHub-ready, but **a DOI cannot be created without your GitHub/Zenodo
account**. Follow the steps below.

## 1. Install Git (one time)

Windows:

1. Download Git for Windows: https://git-scm.com/download/win
2. Install with default options.
3. Open PowerShell and check:

```powershell
git --version
```

## 2. Create the GitHub repository

### Option A: GitHub web UI

1. Sign in to https://github.com
2. Click **New repository**
3. Name: `crrt-trial-eligibility`
4. Visibility: **Public**
5. Do **not** initialize with README/LICENSE/.gitignore (this folder already has them)
6. Click **Create repository**

### Option B: GitHub CLI

```powershell
gh auth login
gh repo create crrt-trial-eligibility --public --source . --remote origin --push
```

## 3. Push this folder

```powershell
cd "C:\Users\28212\Documents\deepseek-harness\default-workspace\crrt_liberation\manuscript\github_repo"
git init
git add .
git commit -m "CRRT trial eligibility analysis code v1.0.0"
git branch -M main
git remote add origin https://github.com/[USER]/crrt-trial-eligibility.git
git push -u origin main
```

Replace `[USER]` with your GitHub username.

## 4. Connect GitHub to Zenodo

1. Sign in to https://zenodo.org with your GitHub account.
2. Go to **Settings → GitHub**.
3. Find `crrt-trial-eligibility` and toggle it **ON**.
4. Zenodo will now archive each GitHub release.

## 5. Create the release that generates the DOI

On GitHub:

1. Go to **Releases → Draft a new release**
2. Tag: `v1.0.0`
3. Title: `CRRT trial eligibility analysis v1.0.0`
4. Publish release

Zenodo will archive the release and assign a DOI. It usually appears within a few
minutes at:

```
https://zenodo.org/account/settings/github/
```

## 6. Put the DOI into the manuscript

Replace:

```
**Code availability:** Analysis code is provided as Supplementary Code and will be deposited in a public repository before publication.
```

with:

```
**Code availability:** Analysis code is available at https://github.com/[USER]/crrt-trial-eligibility and archived at https://doi.org/[ZENODO_DOI].
```

Also update:

- `CITATION.cff` → `repository-code` and `url`
- `.zenodo.json` → creators/affiliations
- `README.md` → DOI

## 7. If you do not want to use GitHub

You can upload a ZIP directly to Zenodo:

1. https://zenodo.org → **New upload**
2. Upload `ICM_analysis_code.zip`
3. Fill title, authors, description, keywords, license
4. Publish
5. Zenodo assigns a DOI immediately

This is faster but gives a DOI for the ZIP only, not a versioned GitHub repository.

## What I could not do here

This environment has **no Git, no GitHub CLI, and no GitHub/Zenodo credentials**.
Therefore I could not create the remote repository or mint the DOI. The folder is
ready; the steps above are the complete manual procedure.
