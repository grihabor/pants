# Copied from nixpkgs:
# https://raw.githubusercontent.com/NixOS/nixpkgs/refs/heads/nixos-24.05/pkgs/development/python-modules/libcst/default.nix
{
  lib,
  stdenv,
  buildPythonPackage,
  fetchFromGitHub,
  fetchpatch,
  cargo,
  hypothesis,
  libiconv,
  pytestCheckHook,
  python,
  pythonOlder,
  pyyaml,
  rustPlatform,
  rustc,
  setuptools-rust,
  setuptools-scm,
  typing-extensions,
  typing-inspect,
}:

buildPythonPackage rec {
  pname = "libcst";
  version = "1.3.0";
  format = "pyproject";

  disabled = pythonOlder "3.7";

  src = fetchFromGitHub {
    owner = "instagram";
    repo = "libcst";
    rev = "refs/tags/v${version}";
    hash = "sha256-1qAb6iS1iGoZLry/ZHzl/xvEJX0ouqVBL/3i61YEgac=";
  };

  cargoDeps = rustPlatform.fetchCargoTarball {
    inherit src;
    sourceRoot = "${src.name}/${cargoRoot}";
    name = "${pname}-${version}";
    hash = "sha256-IaxgjcFmgaeLHmIrVpzrJ/Ue1A9+PkFl9mV0G2HVQkI=";
  };

  cargoRoot = "native";

  postPatch = ''
    # avoid infinite recursion by not formatting the release files
    substituteInPlace libcst/codegen/generate.py \
      --replace '"ufmt"' '"true"'
  '';

  nativeBuildInputs = [
    setuptools-rust
    setuptools-scm
    rustPlatform.cargoSetupHook
    cargo
    rustc
  ];

  buildInputs = lib.optionals stdenv.isDarwin [ libiconv ];

  propagatedBuildInputs = [
    typing-extensions
    typing-inspect
    pyyaml
  ];

  nativeCheckInputs = [
    hypothesis
    pytestCheckHook
  ];

  preCheck = ''
    # otherwise import libcst.native fails
    cp build/lib.*/libcst/native.* libcst/

    ${python.interpreter} -m libcst.codegen.generate visitors
    ${python.interpreter} -m libcst.codegen.generate return_types

    # Can't run all tests due to circular dependency on hypothesmith -> libcst
    rm -r {libcst/tests,libcst/codegen/tests,libcst/m*/tests}
  '';

  disabledTests = [
    # No files are generated
    "test_codemod_formatter_error_input"
  ];

  pythonImportsCheck = [ "libcst" ];

  meta = with lib; {
    description = "Concrete Syntax Tree (CST) parser and serializer library for Python";
    homepage = "https://github.com/Instagram/libcst";
    changelog = "https://github.com/Instagram/LibCST/blob/v${version}/CHANGELOG.md";
    license = with licenses; [
      mit
      asl20
      psfl
    ];
    maintainers = with maintainers; [ ];
  };
}
