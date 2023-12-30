# Copyright 2022 Pants project contributors (see CONTRIBUTORS.md).
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import itertools
import logging
from collections import defaultdict
from dataclasses import dataclass
from typing import (
    Any,
    Callable,
    Iterable,
    Iterator,
    NamedTuple,
    Protocol,
    Sequence,
    Tuple,
    Type,
    TypeVar,
)

from pants.base.specs import Specs
from pants.core.goals.lint import (
    AbstractLintRequest,
    LintFilesRequest,
    LintResult,
    LintTargetsRequest,
    _get_partitions_by_request_type,
    _MultiToolGoalSubsystem,
)
from pants.core.goals.multi_tool_goal_helper import BatchSizeOption, OnlyOption
from pants.core.util_rules.partitions import PartitionerType, PartitionMetadataT
from pants.core.util_rules.partitions import Partitions as UntypedPartitions
from pants.engine.collection import Collection
from pants.engine.console import Console
from pants.engine.engine_aware import EngineAwareReturnType
from pants.engine.environment import EnvironmentName
from pants.engine.fs import Digest, MergeDigests, PathGlobs, Snapshot, SnapshotDiff, Workspace
from pants.engine.goal import Goal, GoalSubsystem
from pants.engine.process import FallibleProcessResult, ProcessResult
from pants.engine.rules import Get, MultiGet, collect_rules, goal_rule, rule
from pants.engine.unions import UnionMembership, UnionRule, distinct_union_type_per_subclass, union
from pants.option.option_types import BoolOption
from pants.util.collections import partition_sequentially
from pants.util.docutil import bin_name
from pants.util.logging import LogLevel
from pants.util.ordered_set import FrozenOrderedSet
from pants.util.strutil import Simplifier, softwrap

logger = logging.getLogger(__name__)


class FixSubsystem(GoalSubsystem):
    name = "fix"
    help = "Autofix source code."

    @classmethod
    def activated(cls, union_membership: UnionMembership) -> bool:
        return AbstractFixRequest in union_membership

    only = OnlyOption("fixer", "autoflake", "pyupgrade")
    skip_formatters = BoolOption(
        default=False,
        help=softwrap(
            f"""
            If true, skip running all formatters.

            FYI: when running `{bin_name()} fix fmt ::`, there should be diminishing performance
            benefit to using this flag. Pants attempts to reuse the results from `fmt` when running
            `fix` where possible.
            """
        ),
    )
    batch_size = BatchSizeOption(uppercase="Fixer", lowercase="fixer")


class Fix(Goal):
    subsystem_cls = FixSubsystem
    environment_behavior = Goal.EnvironmentBehavior.LOCAL_ONLY


@goal_rule
async def fix(
    console: Console,
    specs: Specs,
    fix_subsystem: FixSubsystem,
    workspace: Workspace,
    union_membership: UnionMembership,
) -> Fix:
    return await _do_fix(
        sorted(
            (
                request_type
                for request_type in union_membership.get(AbstractFixRequest)
                if not (request_type.is_formatter and fix_subsystem.skip_formatters)
            ),
            # NB: We sort the core request types so that fixers are first. This is to ensure that, between
            # fixers and formatters, re-running isn't necessary due to tool conflicts (re-running may
            # still be necessary within formatters). This is because fixers are expected to modify
            # code irrespective of formattint, and formatters aren't expected to be modifying the code
            # in a way that needs to be fixed.
            key=lambda request_type: request_type.is_fixer,
            reverse=True,
        ),
        union_membership.get(FixTargetsRequest.PartitionRequest),
        union_membership.get(FixFilesRequest.PartitionRequest),
        Fix,
        fix_subsystem,
        specs,
        workspace,
        console,
        lambda request_type: Get(Partitions, FixTargetsRequest.PartitionRequest, request_type),
        lambda request_type: Get(Partitions, FixFilesRequest.PartitionRequest, request_type),
    )


@rule
async def fix_batch(
    request: _FixBatchRequest,
) -> _FixBatchResult:
    current_snapshot = await Get(Snapshot, PathGlobs(request[0].files))

    results = []
    for request_type, tool_name, files, key in request:
        batch = request_type(tool_name, files, key, current_snapshot)
        result = await Get(  # noqa: PNT30: this is inherently sequential
            FixResult, AbstractFixRequest.Batch, batch
        )
        results.append(result)

        assert set(result.output.files) == set(
            batch.files
        ), f"Expected {result.output.files} to match {batch.files}"
        current_snapshot = result.output
    return _FixBatchResult(tuple(results))


@rule(level=LogLevel.DEBUG)
async def convert_fix_result_to_lint_result(fix_result: FixResult) -> LintResult:
    return LintResult(
        1 if fix_result.did_change else 0,
        fix_result.stdout,
        fix_result.stderr,
        linter_name=fix_result.tool_name,
        _render_message=False,  # Don't re-render the message
    )


def rules():
    return collect_rules()
