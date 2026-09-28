#!/usr/bin/env python3
"""Print the generations of a Morph deck and the two agent briefs with paths filled in.

Usage: briefs.py <repo> <deck.json> [--branch NAME] [--model claude-sonnet-5] [--base main]

Reads the flat deck (a JSON list of cards), layers the cards by ``depends_on``
(Kahn), splits code cards from ``-judge`` cards, and prints: the layers, the
per-generation card ids, and the executor and judge briefs from ``../references``
with ``<REPO>``, ``<BRANCH>``, ``<DECK>``, ``claude-sonnet-5`` and ``<base>``
substituted. Standard library only; nothing is written or run.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REFS = os.path.join(HERE, "..", "references")


def layers(cards):
    by_id = {c["custom_id"]: c for c in cards}
    deps = {cid: set(c.get("depends_on") or []) for cid, c in by_id.items()}
    unknown = sorted({d for ds in deps.values() for d in ds if d not in by_id})
    if unknown:
        sys.exit(f"depends_on names unknown cards: {', '.join(unknown)}")
    done, out = set(), []
    while len(done) < len(by_id):
        layer = sorted(cid for cid, ds in deps.items() if cid not in done and ds <= done)
        if not layer:
            sys.exit("cycle in depends_on among: " + ", ".join(sorted(set(by_id) - done)))
        out.append(layer)
        done.update(layer)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("repo")
    ap.add_argument("deck")
    ap.add_argument("--branch", default=None, help="work branch (default: current branch of repo)")
    ap.add_argument("--model", default="claude-sonnet-5")
    ap.add_argument("--base", default="main")
    args = ap.parse_args(argv)

    repo = os.path.abspath(args.repo)
    deck_path = args.deck if os.path.isabs(args.deck) else os.path.join(repo, args.deck)
    with open(deck_path, encoding="utf-8") as fh:
        cards = json.load(fh)
    if isinstance(cards, dict):
        cards = [cards]
    branch = args.branch
    if branch is None:
        head = os.path.join(repo, ".git", "HEAD")
        try:
            with open(head, encoding="utf-8") as fh:
                ref = fh.read().strip()
            branch = ref.rsplit("/", 1)[-1] if ref.startswith("ref:") else ref[:10]
        except OSError:
            branch = "<BRANCH>"

    gens = layers(cards)
    code = [c["custom_id"] for c in cards if not c["custom_id"].endswith("-judge")]
    judge = [c["custom_id"] for c in cards if c["custom_id"].endswith("-judge")]
    print(f"deck: {deck_path}")
    print(f"cards: {len(cards)} ({len(code)} code, {len(judge)} judge); generations: {len(gens)}")
    for i, g in enumerate(gens, 1):
        print(f"  gen {i}: {', '.join(g)}")
    print()

    subs = {"<REPO>": repo, "<BRANCH>": branch, "<DECK>": os.path.relpath(deck_path, repo),
            "claude-sonnet-5": args.model, "<base>": args.base}
    for name, title in (("executor-brief.md", "EXECUTOR BRIEF"), ("judge-brief.md", "JUDGE BRIEF")):
        if name == "judge-brief.md" and not judge:
            print("== no judge cards in this deck; skip the judge agent ==")
            continue
        with open(os.path.join(REFS, name), encoding="utf-8") as fh:
            text = fh.read()
        block = text.split("```", 2)[1].strip("\n")
        for k, v in subs.items():
            block = block.replace(k, v)
        print(f"== {title} ==")
        print(block)
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
