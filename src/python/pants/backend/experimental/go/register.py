# Copyright 2021 Pants project contributors (see CONTRIBUTORS.md).
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from pants.backend.go import target_type_rules
from pants.backend.go.goals import custom_goals, package_binary, tailor
from pants.backend.go.lint import fmt
from pants.backend.go.lint.gofmt import skip_field as gofmt_skip_field
from pants.backend.go.lint.gofmt.rules import rules as gofmt_rules
from pants.backend.go.subsystems import golang
from pants.backend.go.target_types import (
    GoBinaryTarget,
    GoExternalPackageTarget,
    GoModTarget,
    GoPackage,
)
from pants.backend.go.util_rules import (
    assembly,
    build_go_pkg,
    compile,
    external_module,
    go_mod,
    go_pkg,
    import_analysis,
    link,
    sdk,
    tests_analysis,
)


def target_types():
    return [GoModTarget, GoPackage, GoExternalPackageTarget, GoBinaryTarget]


def rules():
    return [
        *assembly.rules(),
        *build_go_pkg.rules(),
        *compile.rules(),
        *external_module.rules(),
        *golang.rules(),
        *import_analysis.rules(),
        *go_mod.rules(),
        *go_pkg.rules(),
        *link.rules(),
        *sdk.rules(),
        *tests_analysis.rules(),
        *tailor.rules(),
        *target_type_rules.rules(),
        *custom_goals.rules(),
        *package_binary.rules(),
        # Gofmt
        *fmt.rules(),
        *gofmt_rules(),
        *gofmt_skip_field.rules(),
    ]
