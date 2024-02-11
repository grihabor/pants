# Copyright 2024 Pants project contributors (see CONTRIBUTORS.md).
# Licensed under the Apache License, Version 2.0 (see LICENSE).
from __future__ import annotations

import itertools
from dataclasses import dataclass

from pants.base.specs import FileLiteralSpec
from pants.core.util_rules.system_binaries import GitBinary
from pants.engine.environment import EnvironmentName
from pants.engine.internals.selectors import MultiGet
from pants.engine.rules import Get, collect_rules, rule
from pants.engine.unions import UnionMembership, UnionRule, union
from pants.vcs.changed import ChangedOptions
from pants.vcs.git import GitWorktree, GitWorktreeRequest, MaybeGitWorktree


@union
@dataclass(frozen=True)
class ChangedFileLiteralSpecsRequest:
    """Union for changed FileLiteralSpec requests.

    If you want to add your own logic, subclass this union and add register
    `UnionRule(ChangedFileLiteralSpecsRequest, MyChangedFileLiteralSpecsRequest)`.
    """

    changed_options: ChangedOptions


@dataclass(frozen=True)
class ChangedFileLiteralSpecs:
    include: tuple[FileLiteralSpec, ...]
    exclude: tuple[FileLiteralSpec, ...]


@dataclass(frozen=True)
class DefaultChangedFileLiteralSpecsRequest(ChangedFileLiteralSpecsRequest):
    """Default implementation for ChangedFileLiteralSpecsRequest union.

    Use `Get(AllChangedFileLiteralSpecs, AllChangedFileLiteralSpecsRequest)` to merge specs of all
    implementors of ChangedFileLiteralSpecsRequest union.
    """


@rule
async def find_default_changed_file_literal_specs(
    request: DefaultChangedFileLiteralSpecsRequest,
) -> ChangedFileLiteralSpecs:
    # maybe_git_worktree = await Get(MaybeGitWorktree, GitWorktreeRequest())
    if maybe_git_worktree.git_worktree is None:
        raise ValueError("git_worktree is None")

    changed_files = tuple(request.changed_options.changed_files(maybe_git_worktree.git_worktree))
    return ChangedFileLiteralSpecs(
        include=tuple(FileLiteralSpec(f) for f in changed_files),
        exclude=(),
    )


@dataclass(frozen=True)
class AllChangedFileLiteralSpecsRequest:
    changed_options: ChangedOptions


@dataclass(frozen=True)
class AllChangedFileLiteralSpecs:
    include: tuple[FileLiteralSpec, ...]
    exclude: tuple[FileLiteralSpec, ...]


@rule
async def merge_all_changed_file_literal_specs(
    request: AllChangedFileLiteralSpecsRequest,
    union_membership: UnionMembership,
) -> AllChangedFileLiteralSpecs:
    requests = union_membership[ChangedFileLiteralSpecsRequest]
    all_specs = await MultiGet(
        Get(
            ChangedFileLiteralSpecs,
            ChangedFileLiteralSpecsRequest,
            request_cls(request.changed_options),
        )
        for request_cls in requests
    )

    include = itertools.chain.from_iterable(specs.include for specs in all_specs)
    exclude = itertools.chain.from_iterable(specs.exclude for specs in all_specs)
    specs = AllChangedFileLiteralSpecs(include=tuple(include), exclude=tuple(exclude))
    return specs


def rules():
    return [
        *collect_rules(),
        UnionRule(ChangedFileLiteralSpecsRequest, DefaultChangedFileLiteralSpecsRequest),
    ]
