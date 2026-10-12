# Getting your repository listed

## 1. Before you open a pull request

- Your repository is public and publishes at least one mod: an `azmods-repo.json` at
  the root of its default branch, with packages attached to GitHub releases. The SDK's guide,
  [Packaging and publishing](https://github.com/Kyle-Hosman/az-mods-sdk/blob/main/docs/06-publishing.md),
  walks through it.
- This passes on your repository:

  ```sh
  azmod-pack repo check OWNER/REPO --download
  ```

- Every mod id is unique across the whole list: no listed repository uses any of your ids
  (the check compares them without regard to case). An id names the mod's folder on the USB
  stick and its settings and files on the deck, so two mods with the same id cannot both be
  installed. The SDK's guide explains
  [how to pick an id](https://github.com/Kyle-Hosman/az-mods-sdk/blob/main/docs/06-publishing.md#pick-an-id-that-stays-yours).
- You have installed your mods from your repository on a real deck and tested them as
  described in the SDK's guide,
  [Testing on your deck](https://github.com/Kyle-Hosman/az-mods-sdk/blob/main/docs/04-testing.md).

## 2. Open the pull request

Add one line to `repos` in `azmods-repos.json`: your repository URL, exactly
`https://github.com/OWNER/REPO`. Keep the list sorted, one repository per pull request.

In the pull request description, say:

- what each mod does, in a sentence or two
- which firmware tags you tested on, and on what (deck, views, themes)
- whether any mod uses hooks, the network, or writes files, and why

The checks run automatically. A pull request with failing checks is not reviewed until
they pass.

## 3. What the review looks at

1. **Public source.** Every mod's `source` points at its public source, with a
   license compatible with the SDK's GPL-3.0. The code in the release is built from
   that source (builds in the SDK container are reproducible, so a reviewer can
   check).
2. **The validator passes.** `azmod-pack` accepts every package: the manifest, the
   library (aarch64, the deck's C library, one exported symbol, only allowed
   libraries) and the icon.
3. **The guidelines.** The code follows the SDK's
   [GUIDELINES.md](https://github.com/Kyle-Hosman/az-mods-sdk/blob/main/docs/GUIDELINES.md):
   unknown means do nothing, nothing in a constructor, nothing slow on the hot paths,
   hooks only with exact firmware tags. A reviewer reads the code with these in mind.
4. **An honest description.** The summary and description say plainly what the mod
   changes on the deck, including network access, file writes, control or audio
   changes, and code patching. No hidden behavior.
5. **Nothing that is not yours to share.** No firmware files or update files, no keys,
   no decompiled firmware code, no firmware art, in the repository or its releases.

Review is done by people, in their spare time. It can take a while, and it can come
back with questions or requested changes.

## After you are listed

- Releasing new versions needs no pull request here: decks read your
  `azmods-repo.json` directly. Keep each new release passing the validator.
- Never change a published mod's id. A deck keeps a mod's settings and files under its id,
  and an id that changes is a different mod. A new mod you add later needs an id no listed
  repository uses; the weekly check reports a clash.
- If the weekly check finds your repository broken (an index that no longer
  validates, a package that no longer matches its hash, a source URL that is gone),
  the maintainers open an issue on your repository, and it may be removed from the list until it is
  fixed.
- A repository can be removed at any time if a mod is found to break the guidelines,
  in particular anything that risks crashing a DJ's set or hides what it does.
- To remove your own repository, open a pull request that deletes its line.
