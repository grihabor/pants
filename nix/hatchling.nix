# Fixes the error:
# > ERROR Missing dependencies:
# >        hatchling<1.22.0
#
# TODO remove the file once pex upgrades to a newer version of hatchling.
#
# The package was copied from nixpkgs:
# https://raw.githubusercontent.com/NixOS/nixpkgs/7f1305d3d2666813654c14e0b7bb97d65d5602e0/pkgs/development/python-modules/hatchling/default.nix
{ lib
, buildPythonPackage
, fetchPypi
, pythonOlder

# runtime
, editables
, packaging
, pathspec
, pluggy
, tomli
, trove-classifiers

# tests
, build
, python
, requests
, virtualenv
}:

buildPythonPackage rec {
  pname = "hatchling";
  version = "1.21.1";
  format = "pyproject";
  disabled = pythonOlder "3.8";

  src = fetchPypi {
    inherit pname version;
    hash = "sha256-u6RARToiTn1EeEV/oujYw2M3Zbr6Apdaa1O5v5F5gLw=";
  };

  # listed in backend/pyproject.toml
  propagatedBuildInputs = [
    editables
    packaging
    pathspec
    pluggy
    trove-classifiers
  ] ++ lib.optionals (pythonOlder "3.11") [
    tomli
  ];

  pythonImportsCheck = [
    "hatchling"
    "hatchling.build"
  ];

  # tries to fetch packages from the internet
  doCheck = false;

  # listed in /backend/tests/downstream/requirements.txt
  nativeCheckInputs = [
    build
    requests
    virtualenv
  ];

  preCheck = ''
    export HOME=$TMPDIR
  '';

  checkPhase = ''
    runHook preCheck
    ${python.interpreter} tests/downstream/integrate.py
    runHook postCheck
  '';

  meta = with lib; {
    description = "Modern, extensible Python build backend";
    homepage = "https://hatch.pypa.io/latest/";
    changelog = "https://github.com/pypa/hatch/releases/tag/hatchling-v${version}";
    license = licenses.mit;
    maintainers = with maintainers; [ hexa ofek ];
  };
}
