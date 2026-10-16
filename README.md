# AZ-MODS Mod Index

The list of community mod repositories that every XDJ-AZ running AZ-MODS shows by
default, under Mod Menu > Community Mods > Repositories.

Each entry is a GitHub repository that publishes one or more community mods (an
`azmods-repo.json` at its root, packages attached to its releases). Being listed
here means the repository has been reviewed against the rules below. DJs can still
add any other repository on their deck by name; mods from a repository that is not on
this list show a "Not in the community list" note.

To write a mod, start with the [AZ-MODS SDK](https://github.com/Kyle-Hosman/az-mods-sdk).
To get your repository listed, see [CONTRIBUTING.md](CONTRIBUTING.md).

## `azmods-repos.json`

```json
{
  "azmods_repos": 1,
  "repos": [
    "https://github.com/someone/az-beat-counter",
    "https://github.com/someone-else/az-mods"
  ]
}
```

| Field | Meaning |
|---|---|
| `azmods_repos` | the format version, always `1` |
| `repos` | repository URLs, each exactly `https://github.com/OWNER/REPO` (no trailing slash, no `.git`), each listed once |

For each repository, a deck fetches
`https://raw.githubusercontent.com/OWNER/REPO/HEAD/azmods-repo.json`. The format of
that file, and of the packages it points to, is documented in the SDK's guide,
[Packaging and publishing](https://github.com/Kyle-Hosman/az-mods-sdk/blob/main/docs/06-publishing.md).

## Checks

Every pull request, every push to `main`, and a weekly run check that:

- this file follows the schema above and stays sorted (`tools/check.py`);
- every mod in every listed repository has a `version`, and any `min_core`, of the form
  `MAJOR.MINOR.PATCH`, numbers only, each 0 to 9999. A deck offers an update only for a
  higher number of that form, so `1.2` or `1.0.0-beta.1` would never update;
- no mod id appears twice across the list;
- every listed repository's index and every package in it pass `azmod-pack validate`:
  every check a deck runs before it loads a mod, and some stricter ones.

A repository that stops passing can be removed from the list until it is fixed.

## Trust

Community Mods are made by other people. Listing a repository here means it passed
the review in [CONTRIBUTING.md](CONTRIBUTING.md) when it was added; it is not a
guarantee that a mod is safe. Mods run with full access to the deck. Install what
you trust, and keep a spare stick for trying new mods.

AZ-MODS is a community project. It is not made, supported or endorsed by Pioneer DJ
or AlphaTheta.

## License

The list itself is MIT licensed (see [LICENSE](LICENSE)). Each listed mod has its
own license, stated in its repository.
