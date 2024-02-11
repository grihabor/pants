# Copyright 2024 Pants project contributors (see CONTRIBUTORS.md).
# Licensed under the Apache License, Version 2.0 (see LICENSE).
from __future__ import annotations

import itertools
import logging
from dataclasses import dataclass
from typing import cast

from pants.base.specs import AddressLiteralSpec
from pants.engine.internals.native_engine import AddressInput
from pants.engine.internals.selectors import MultiGet
from pants.engine.rules import Get, collect_rules, rule
from pants.engine.unions import UnionMembership, UnionRule, union
from pants.util.frozendict import FrozenDict
from pants.vcs.changed import ChangedAddresses, ChangedOptions, ChangedRequest
from pants.vcs.git import GitWorktree

logger = logging.getLogger(__name__)


@union
@dataclass(frozen=True)
class ChangedAddressLiteralSpecsRequest:
    """Union for changed AddressLiteralSpecsSpec requests.

    If you want to add your own logic, subclass this union and add register
    `UnionRule(ChangedAddressLiteralSpecsRequest, MyChangedAddressLiteralSpecsRequest)`.
    """

    changed_options: ChangedOptions
    git_worktree: GitWorktree


@dataclass(frozen=True)
class ChangedAddressLiteralSpecs:
    include: tuple[AddressLiteralSpecsSpec, ...]
    exclude: tuple[AddressLiteralSpecsSpec, ...]


@dataclass(frozen=True)
class DefaultChangedAddressLiteralSpecsRequest(ChangedAddressLiteralSpecsRequest):
    """Default implementation for ChangedAddressLiteralSpecsRequest union.

    Use `Get(AllChangedAddressLiteralSpecs, AllChangedAddressLiteralSpecsRequest)` to merge specs of
    all implementors of ChangedAddressLiteralSpecsRequest union.
    """


@rule
async def find_default_changed_address_literal_specs(
    request: DefaultChangedAddressLiteralSpecsRequest,
) -> ChangedAddressLiteralSpecs:
    changed_files = tuple(request.changed_options.changed_files(request.git_worktree))
    changed_request = ChangedRequest(
        sources=changed_files,
        dependents=request.changed_options.dependents,
    )
    changed_addresses = await Get(ChangedAddresses, ChangedRequest, changed_request)
    logger.debug("changed addresses: %s", changed_addresses)

    address_literal_specs = []
    for address in cast(ChangedAddresses, changed_addresses):
        address_input = AddressInput.parse(address.spec, description_of_origin="`--changed-since`")
        address_literal_specs.append(
            AddressLiteralSpec(
                path_component=address_input.path_component,
                target_component=address_input.target_component,
                generated_component=address_input.generated_component,
                parameters=FrozenDict(address_input.parameters),
            )
        )
    return ChangedAddressLiteralSpecs(
        include=tuple(address_literal_specs),
        exclude=(),
    )


@dataclass(frozen=True)
class AllChangedAddressLiteralSpecsRequest:
    changed_options: ChangedOptions
    git_worktree: GitWorktree


@dataclass(frozen=True)
class AllChangedAddressLiteralSpecs:
    includes: tuple[AddressLiteralSpecsSpec, ...]
    excludes: tuple[AddressLiteralSpecsSpec, ...]


@rule
async def merge_all_changed_address_literal_specs(
    request: AllChangedAddressLiteralSpecsRequest,
    union_membership: UnionMembership,
) -> AllChangedAddressLiteralSpecs:
    requests = union_membership[ChangedAddressLiteralSpecsRequest]
    all_specs = await MultiGet(
        Get(
            ChangedAddressLiteralSpecs,
            ChangedAddressLiteralSpecsRequest,
            request_cls(request.changed_options, request.git_worktree),
        )
        for request_cls in requests
    )

    include = itertools.chain.from_iterable(specs.include for specs in all_specs)
    exclude = itertools.chain.from_iterable(specs.exclude for specs in all_specs)
    return AllChangedAddressLiteralSpecs(includes=tuple(include), excludes=tuple(exclude))


def rules():
    return [
        *collect_rules(),
        UnionRule(ChangedAddressLiteralSpecsRequest, DefaultChangedAddressLiteralSpecsRequest),
    ]
