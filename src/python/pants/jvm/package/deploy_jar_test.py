# Copyright 2021 Pants project contributors (see CONTRIBUTORS.md).
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

from textwrap import dedent
from typing import Iterable

import pytest

from pants.backend.java.compile.javac import rules as javac_rules
from pants.backend.java.dependency_inference.rules import rules as java_dep_inf_rules
from pants.backend.java.target_types import JavaSourcesGeneratorTarget
from pants.backend.java.target_types import rules as target_types_rules
from pants.build_graph.address import Address
from pants.core.goals.package import BuiltPackage
from pants.core.util_rules.system_binaries import BashBinary, UnzipBinary
from pants.engine.process import Process, ProcessResult
from pants.jvm import jdk_rules
from pants.jvm.classpath import rules as classpath_rules
from pants.jvm.jar_tool import jar_tool
from pants.jvm.jdk_rules import InternalJdk, JvmProcess
from pants.jvm.package.deploy_jar import DeployJarFieldSet
from pants.jvm.package.deploy_jar import rules as deploy_jar_rules
from pants.jvm.resolve import jvm_tool
from pants.jvm.resolve.coursier_fetch import CoursierResolvedLockfile
from pants.jvm.resolve.coursier_test_util import EMPTY_JVM_LOCKFILE
from pants.jvm.shading.rules import rules as shading_rules
from pants.jvm.strip_jar import strip_jar
from pants.jvm.target_types import (
    JVM_SHADING_RULE_TYPES,
    DeployJarDuplicateRule,
    DeployJarTarget,
    JvmArtifactTarget,
)
from pants.jvm.testutil import maybe_skip_jdk_test
from pants.jvm.util_rules import rules as util_rules
from pants.testutil.rule_runner import PYTHON_BOOTSTRAP_ENV, QueryRule, RuleRunner
from pants.util.logging import LogLevel


@pytest.fixture
def rule_runner() -> RuleRunner:
    rule_runner = RuleRunner(
        rules=[
            *classpath_rules(),
            *jvm_tool.rules(),
            *strip_jar.rules(),
            *jar_tool.rules(),
            *deploy_jar_rules(),
            *javac_rules(),
            *jdk_rules.rules(),
            *java_dep_inf_rules(),
            *target_types_rules(),
            *util_rules(),
            *shading_rules(),
            QueryRule(BashBinary, ()),
            QueryRule(UnzipBinary, ()),
            QueryRule(InternalJdk, ()),
            QueryRule(BuiltPackage, (DeployJarFieldSet,)),
            QueryRule(ProcessResult, (JvmProcess,)),
            QueryRule(ProcessResult, (Process,)),
        ],
        target_types=[
            JavaSourcesGeneratorTarget,
            JvmArtifactTarget,
            DeployJarTarget,
        ],
        objects={
            DeployJarDuplicateRule.alias: DeployJarDuplicateRule,
            **{rule.alias: rule for rule in JVM_SHADING_RULE_TYPES},
        },
    )
    rule_runner.set_options(args=[], env_inherit=PYTHON_BOOTSTRAP_ENV)
    return rule_runner


JAVA_LIB_SOURCE = dedent(
    """
    package org.pantsbuild.example.lib;

    public class ExampleLib {
        public static String hello() {
            return "Hello, World!";
        }
    }
    """
)


JAVA_JSON_MANGLING_LIB_SOURCE = dedent(
    """
    package org.pantsbuild.example.lib;

    import com.fasterxml.jackson.databind.ObjectMapper;

    public class ExampleLib {

        private String template = "{\\"contents\\": \\"Hello, World!\\"}";

        public String getGreeting() {
            ObjectMapper mapper = new ObjectMapper();
            try {
                SerializedThing thing = mapper.readValue(template, SerializedThing.class);
                return thing.contents;
            } catch (Exception e) {
                throw new RuntimeException(e);
            }
        }

        public static String hello() {
            return new ExampleLib().getGreeting();
        }
    }

    class SerializedThing {
        public String contents;
    }
    """
)


JAVA_MAIN_SOURCE = dedent(
    """
    package org.pantsbuild.example;

    import org.pantsbuild.example.lib.ExampleLib;

    public class Example {
        public static void main(String[] args) {
            System.out.println(ExampleLib.hello());
        }
    }
    """
)

JAVA_MAIN_SOURCE_NO_DEPS = dedent(
    """
    package org.pantsbuild.example;

    public class Example {
        public static void main(String[] args) {
            System.out.println("Hello, World!");
        }
    }
    """
)


COURSIER_LOCKFILE_SOURCE = dedent(
    """\
    # This lockfile was autogenerated by Pants. To regenerate, run:
    #
    #    ./pants generate-lockfiles
    #
    # --- BEGIN PANTS LOCKFILE METADATA: DO NOT EDIT OR REMOVE ---
    # {
    #   "version": 1,
    #   "generated_with_requirements": ["com.fasterxml.jackson.core:jackson-databind:2.12.5,url=not_provided,jar=not_provided"]
    # }
    # --- END PANTS LOCKFILE METADATA ---

    [[entries]]

    directDependencies = []
    dependencies = []
    file_name = "jackson-annotations-2.12.5.jar"

    [entries.coord]
    group = "com.fasterxml.jackson.core"
    artifact = "jackson-annotations"
    version = "2.12.5"
    packaging = "jar"

    [entries.file_digest]
    fingerprint = "517926d9fe04cadd55120790d0b5355e4f656ffe2969e4d480a0e7f95a983e9e"
    serialized_bytes_length = 75704

    [[entries]]

    directDependencies = []
    dependencies = []
    file_name = "jackson-core-2.12.5.jar"

    [entries.coord]
    group = "com.fasterxml.jackson.core"
    artifact = "jackson-core"
    version = "2.12.5"
    packaging = "jar"

    [entries.file_digest]
    fingerprint = "0c9860b8fb6f24f59e083e0b92a17c515c45312951fc272d093e4709faed6356"
    serialized_bytes_length = 365536

    [[entries]]

    file_name = "jackson-databind-2.12.5.jar"

    [entries.coord]
    group = "com.fasterxml.jackson.core"
    artifact = "jackson-databind"
    version = "2.12.5"
    packaging = "jar"

    [[entries.directDependencies]]
    group = "com.fasterxml.jackson.core"
    artifact = "jackson-annotations"
    version = "2.12.5"
    packaging = "jar"

    [[entries.directDependencies]]
    group = "com.fasterxml.jackson.core"
    artifact = "jackson-core"
    version = "2.12.5"
    packaging = "jar"

    [[entries.dependencies]]
    group = "com.fasterxml.jackson.core"
    artifact = "jackson-core"
    version = "2.12.5"
    packaging = "jar"

    [[entries.dependencies]]
    group = "com.fasterxml.jackson.core"
    artifact = "jackson-annotations"
    version = "2.12.5"
    packaging = "jar"

    [entries.file_digest]
    fingerprint = "d49cdfd82443fa5869d75fe53680012cef2dd74621b69d37da69087c40f1575a"
    serialized_bytes_length = 1515991
"""
)


@maybe_skip_jdk_test
def test_deploy_jar_no_deps(rule_runner: RuleRunner) -> None:
    rule_runner.write_files(
        {
            "BUILD": dedent(
                """\
                    deploy_jar(
                        name="example_app_deploy_jar",
                        main="org.pantsbuild.example.Example",
                        output_path="dave.jar",
                        dependencies=[
                            ":example",
                        ],
                    )

                    java_sources(
                        name="example",
                    )
                """
            ),
            "3rdparty/jvm/default.lock": CoursierResolvedLockfile(()).to_serialized().decode(),
            "Example.java": JAVA_MAIN_SOURCE_NO_DEPS,
        }
    )

    _deploy_jar_test(rule_runner, "example_app_deploy_jar")


@maybe_skip_jdk_test
def test_deploy_jar_local_deps(rule_runner: RuleRunner) -> None:
    rule_runner.write_files(
        {
            "BUILD": dedent(
                """\
                    deploy_jar(
                        name="example_app_deploy_jar",
                        main="org.pantsbuild.example.Example",
                        output_path="dave.jar",
                        dependencies=[
                            ":example",
                        ],
                    )

                    java_sources(
                        name="example",
                        sources=["**/*.java", ],
                    )
                """
            ),
            "3rdparty/jvm/default.lock": CoursierResolvedLockfile(()).to_serialized().decode(),
            "Example.java": JAVA_MAIN_SOURCE,
            "lib/ExampleLib.java": JAVA_LIB_SOURCE,
        }
    )

    _deploy_jar_test(rule_runner, "example_app_deploy_jar")


@maybe_skip_jdk_test
def test_deploy_jar_coursier_deps(rule_runner: RuleRunner) -> None:
    rule_runner.write_files(
        {
            "BUILD": dedent(
                """\
                    deploy_jar(
                        name="example_app_deploy_jar",
                        main="org.pantsbuild.example.Example",
                        output_path="dave.jar",
                        dependencies=[
                            ":example",
                        ],
                    )

                    java_sources(
                        name="example",
                        sources=["**/*.java", ],
                        dependencies=[
                            ":com.fasterxml.jackson.core_jackson-databind",
                        ],
                    )

                    jvm_artifact(
                        name = "com.fasterxml.jackson.core_jackson-databind",
                        group = "com.fasterxml.jackson.core",
                        artifact = "jackson-databind",
                        version = "2.12.5",
                    )
                """
            ),
            "3rdparty/jvm/default.lock": COURSIER_LOCKFILE_SOURCE,
            "Example.java": JAVA_MAIN_SOURCE,
            "lib/ExampleLib.java": JAVA_JSON_MANGLING_LIB_SOURCE,
        }
    )

    _deploy_jar_test(rule_runner, "example_app_deploy_jar")


@maybe_skip_jdk_test
def test_deploy_jar_coursier_deps_duplicate_policy(rule_runner: RuleRunner) -> None:
    rule_runner.write_files(
        {
            "BUILD": dedent(
                """\
                    deploy_jar(
                        name="example_app_deploy_jar",
                        main="org.pantsbuild.example.Example",
                        output_path="dave.jar",
                        dependencies=[
                            ":example",
                        ],
                        duplicate_policy=[
                            duplicate_rule(pattern="^org/pantsbuild/example/lib", action="replace")
                        ]
                    )

                    java_sources(
                        name="example",
                        sources=["**/*.java", ],
                        dependencies=[
                            ":com.fasterxml.jackson.core_jackson-databind",
                        ],
                    )

                    jvm_artifact(
                        name = "com.fasterxml.jackson.core_jackson-databind",
                        group = "com.fasterxml.jackson.core",
                        artifact = "jackson-databind",
                        version = "2.12.5",
                    )
                """
            ),
            "3rdparty/jvm/default.lock": COURSIER_LOCKFILE_SOURCE,
            "Example.java": JAVA_MAIN_SOURCE,
            "lib/ExampleLib.java": JAVA_JSON_MANGLING_LIB_SOURCE,
        }
    )

    _deploy_jar_test(rule_runner, "example_app_deploy_jar")


@maybe_skip_jdk_test
def test_deploy_jar_shaded(rule_runner: RuleRunner) -> None:
    rule_runner.write_files(
        {
            "BUILD": dedent(
                """\
                    deploy_jar(
                        name="example_app_deploy_jar",
                        main="org.pantsbuild.example.Example",
                        output_path="dave.jar",
                        dependencies=[
                            ":example",
                        ],
                        shading_rules=[
                            shading_rename(
                                pattern="com.fasterxml.jackson.core.**",
                                replacement="jackson.core.@1",
                            )
                        ]
                    )

                    java_sources(
                        name="example",
                        sources=["**/*.java", ],
                        dependencies=[
                            ":com.fasterxml.jackson.core_jackson-databind",
                        ],
                    )

                    jvm_artifact(
                        name = "com.fasterxml.jackson.core_jackson-databind",
                        group = "com.fasterxml.jackson.core",
                        artifact = "jackson-databind",
                        version = "2.12.5",
                    )
                """
            ),
            "3rdparty/jvm/default.lock": COURSIER_LOCKFILE_SOURCE,
            "Example.java": JAVA_MAIN_SOURCE,
            "lib/ExampleLib.java": JAVA_JSON_MANGLING_LIB_SOURCE,
        }
    )

    _deploy_jar_test(rule_runner, "example_app_deploy_jar")


@maybe_skip_jdk_test
def test_deploy_jar_shaded_in_subdir(rule_runner: RuleRunner) -> None:
    rule_runner.write_files(
        {
            "subdir/BUILD": dedent(
                """\
                    deploy_jar(
                        name="example_app_deploy_jar",
                        main="org.pantsbuild.example.Example",
                        output_path="subdir/dave.jar",
                        dependencies=[
                            ":example",
                        ],
                        shading_rules=[
                            shading_rename(
                                pattern="com.fasterxml.jackson.core.**",
                                replacement="jackson.core.@1",
                            )
                        ]
                    )

                    java_sources(
                        name="example",
                        sources=["**/*.java", ],
                        dependencies=[
                            ":com.fasterxml.jackson.core_jackson-databind",
                        ],
                    )

                    jvm_artifact(
                        name = "com.fasterxml.jackson.core_jackson-databind",
                        group = "com.fasterxml.jackson.core",
                        artifact = "jackson-databind",
                        version = "2.12.5",
                    )
                """
            ),
            "3rdparty/jvm/default.lock": COURSIER_LOCKFILE_SOURCE,
            "subdir/Example.java": JAVA_MAIN_SOURCE,
            "subdir/lib/ExampleLib.java": JAVA_JSON_MANGLING_LIB_SOURCE,
        }
    )

    _deploy_jar_test(rule_runner, "example_app_deploy_jar", path="subdir")


@maybe_skip_jdk_test
def test_deploy_jar_reproducible(rule_runner: RuleRunner) -> None:
    rule_runner.set_options(args=["--jvm-reproducible-jars"], env_inherit=PYTHON_BOOTSTRAP_ENV)
    rule_runner.write_files(
        {
            "BUILD": dedent(
                """\
                    deploy_jar(
                        name="example_app_deploy_jar",
                        main="org.pantsbuild.example.Example",
                        output_path="dave.jar",
                        dependencies=[
                            ":example",
                        ],
                    )

                    java_sources(
                        name="example",
                    )
                """
            ),
            "3rdparty/jvm/default.lock": EMPTY_JVM_LOCKFILE,
            "Example.java": JAVA_MAIN_SOURCE_NO_DEPS,
        }
    )

    tgt = rule_runner.get_target(Address("", target_name="example_app_deploy_jar"))
    fat_jar = rule_runner.request(
        BuiltPackage,
        [DeployJarFieldSet.create(tgt)],
    )

    bash = rule_runner.request(BashBinary, [])
    unzip = rule_runner.request(UnzipBinary, [])

    process_result = rule_runner.request(
        ProcessResult,
        [
            Process(
                argv=[
                    bash.path,
                    "-c",
                    f"{unzip.path} -qq {fat_jar.artifacts[0].relpath} && /bin/date -Idate -r META-INF/MANIFEST.MF && /bin/date -Idate -r org/pantsbuild/example/Example.class",
                ],
                input_digest=fat_jar.digest,
                description="Unzip jar and get date of classfile",
                level=LogLevel.TRACE,
            )
        ],
    )

    assert process_result.stdout.decode() == "2000-01-01\n2000-01-01\n"


def _deploy_jar_test(
    rule_runner: RuleRunner,
    target_name: str,
    args: Iterable[str] | None = None,
    path: str = "",
) -> None:
    rule_runner.set_options(args=(args or ()), env_inherit=PYTHON_BOOTSTRAP_ENV)

    tgt = rule_runner.get_target(Address(path, target_name=target_name))
    jdk = rule_runner.request(InternalJdk, [])
    fat_jar = rule_runner.request(
        BuiltPackage,
        [DeployJarFieldSet.create(tgt)],
    )

    process_result = rule_runner.request(
        ProcessResult,
        [
            JvmProcess(
                jdk=jdk,
                argv=("-jar", "dave.jar"),
                classpath_entries=[],
                description="Run that test jar",
                input_digest=fat_jar.digest,
                use_nailgun=False,
            )
        ],
    )

    assert process_result.stdout.decode("utf-8").strip() == "Hello, World!"
