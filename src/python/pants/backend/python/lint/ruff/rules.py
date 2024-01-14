# Copyright 2023 Pants project contributors (see CONTRIBUTORS.md).
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Tuple

from typing_extensions import assert_never

from pants.backend.python.lint.ruff.subsystem import Ruff, RuffFieldSet, RuffMode
from pants.backend.python.util_rules import pex
from pants.backend.python.util_rules.pex import PexRequest, VenvPex, VenvPexProcess
from pants.core.goals.fix import FixResult, FixTargetsRequest
from pants.core.goals.fmt import FmtResult, FmtTargetsRequest
from pants.core.goals.lint import AbstractLintRequest, LintResult, LintTargetsRequest
from pants.core.util_rules.config_files import ConfigFiles, ConfigFilesRequest
from pants.core.util_rules.partitions import PartitionerType
from pants.core.util_rules.source_files import SourceFiles, SourceFilesRequest
from pants.engine.fs import Digest, MergeDigests
from pants.engine.internals.native_engine import Snapshot
from pants.engine.process import FallibleProcessResult
from pants.engine.rules import Get, MultiGet, Rule, collect_rules, rule
from pants.engine.unions import UnionRule
from pants.util.logging import LogLevel
from pants.util.meta import classproperty
from pants.util.strutil import pluralize


class RuffFixRequest(FixTargetsRequest):
    field_set_type = RuffFieldSet
    tool_subsystem = Ruff
    partitioner_type = PartitionerType.DEFAULT_SINGLE_PARTITION

    @classproperty
    def tool_name(cls) -> str:
        return "ruff check --fix"

    @classproperty
    def tool_id(self) -> str:
        return "ruff-check"


class RuffCheckLintRequest(LintTargetsRequest):
    field_set_type = RuffFieldSet
    tool_subsystem = Ruff
    partitioner_type = PartitionerType.DEFAULT_SINGLE_PARTITION

    @classproperty
    def tool_name(cls) -> str:
        return "ruff check"

    @classproperty
    def tool_id(self) -> str:
        return "ruff-check"


class RuffFmtRequest(FmtTargetsRequest):
    field_set_type = RuffFieldSet
    tool_subsystem = Ruff
    partitioner_type = PartitionerType.DEFAULT_SINGLE_PARTITION

    @classproperty
    def tool_name(cls) -> str:
        return "ruff format"

    @classproperty
    def tool_id(self) -> str:
        return "ruff-format"


class RuffFormatLintRequest(LintTargetsRequest):
    field_set_type = RuffFieldSet
    tool_subsystem = Ruff
    partitioner_type = PartitionerType.DEFAULT_SINGLE_PARTITION

    @classproperty
    def tool_name(cls) -> str:
        return "ruff format --check"

    @classproperty
    def tool_id(self) -> str:
        return "ruff-format"


@dataclass(frozen=True)
class _RunRuffRequest:
    snapshot: Snapshot
    mode: RuffMode


@rule(level=LogLevel.DEBUG)
async def run_ruff(
    request: _RunRuffRequest,
    ruff: Ruff,
) -> FallibleProcessResult:
    ruff_pex_get = Get(VenvPex, PexRequest, ruff.to_pex_request())

    config_files_get = Get(
        ConfigFiles, ConfigFilesRequest, ruff.config_request(request.snapshot.dirs)
    )

    ruff_pex, config_files = await MultiGet(ruff_pex_get, config_files_get)

    input_digest = await Get(
        Digest,
        MergeDigests((request.snapshot.digest, config_files.snapshot.digest)),
    )

    conf_args = [f"--config={ruff.config}"] if ruff.config else []

    extra_initial_args: Tuple[str, ...] = ()
    if request.mode is RuffMode.FMT:
        extra_initial_args = ("format",)
    elif request.mode is RuffMode.FMT_LINT:
        extra_initial_args = ("format", "--check")
    elif request.mode is RuffMode.FIX:
        extra_initial_args = ("check", "--fix")
    elif request.mode is RuffMode.CHECK_LINT:
        extra_initial_args = ("check",)
    else:
        assert_never(request.mode)

    # `--force-exclude` applies file excludes from config to files provided explicitly
    # The format argument must be passed before force-exclude if Ruff is used for formatting.
    # For other cases, the flags should work the same regardless of the order.
    initial_args = extra_initial_args + ("--force-exclude",)

    result = await Get(
        FallibleProcessResult,
        VenvPexProcess(
            ruff_pex,
            argv=(*initial_args, *conf_args, *ruff.args, *request.snapshot.files),
            input_digest=input_digest,
            output_files=request.snapshot.files,
            description=f"Run ruff {' '.join(initial_args)} on {pluralize(len(request.snapshot.files), 'file')}.",
            level=LogLevel.DEBUG,
        ),
    )
    return result


@rule(desc="Fix with ruff check --fix", level=LogLevel.DEBUG)
async def ruff_fix(request: RuffFixRequest.Batch, ruff: Ruff) -> FixResult:
    result = await Get(
        FallibleProcessResult, _RunRuffRequest(snapshot=request.snapshot, mode=RuffMode.FIX)
    )
    return await FixResult.create(request, result)


@rule(desc="Lint with ruff check", level=LogLevel.DEBUG)
async def ruff_check_lint(request: RuffCheckLintRequest.Batch[RuffFieldSet, Any]) -> LintResult:
    source_files = await Get(
        SourceFiles, SourceFilesRequest(field_set.source for field_set in request.elements)
    )
    result = await Get(
        FallibleProcessResult,
        _RunRuffRequest(snapshot=source_files.snapshot, mode=RuffMode.CHECK_LINT),
    )
    return LintResult.create(request, result)


@rule(desc="Lint with ruff format --check", level=LogLevel.DEBUG)
async def ruff_format_lint(request: RuffFormatLintRequest.Batch[RuffFieldSet, Any]) -> LintResult:
    source_files = await Get(
        SourceFiles, SourceFilesRequest(field_set.source for field_set in request.elements)
    )
    result = await Get(
        FallibleProcessResult,
        _RunRuffRequest(snapshot=source_files.snapshot, mode=RuffMode.FMT_LINT),
    )
    return LintResult.create(request, result)


@rule(desc="Format with ruff format", level=LogLevel.DEBUG)
async def ruff_fmt(request: RuffFmtRequest.Batch, ruff: Ruff) -> FmtResult:
    result = await Get(
        FallibleProcessResult,
        _RunRuffRequest(snapshot=request.snapshot, mode=RuffMode.FMT),
    )
    return await FmtResult.create(request, result)


def without_lint(rules: Iterable[Rule]) -> Iterable[Rule]:
    return (
        rule
        for rule in rules
        if not isinstance(rule, UnionRule)
        or (
            rule.union_base is not AbstractLintRequest
            and rule.union_base is not AbstractLintRequest.Batch
        )
    )


def rules():
    return [
        *collect_rules(),
        *without_lint(RuffFixRequest.rules()),
        *RuffCheckLintRequest.rules(),
        *RuffFormatLintRequest.rules(),
        *without_lint(RuffFmtRequest.rules()),
        *pex.rules(),
    ]
