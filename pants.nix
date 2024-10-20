{
  lib,
  python3,
  stdenv,
  protobuf,
  makeRustPlatform,
  rustc,
  cargo,
}: let
  fs = lib.fileset;
  python = python3;
  rustPlatform = makeRustPlatform {
    inherit cargo rustc;
  };
  sourceFiles = fs.gitTracked ./.;
  src = fs.toSource {
    root = ./.;
    fileset = sourceFiles;
  };
  version = "0.1.0";
  pants-engine = stdenv.mkDerivation rec {
    inherit src version;
    pname = "pants-engine";
    cargoDeps = rustPlatform.importCargoLock {
      lockFile = ./src/rust/engine/Cargo.lock;
      outputHashes = {
        "deepsize-0.2.0" = "sha256-E73xdzYfpJASps3yz6sjL48Kimy44F2LvxndWzgV3dU=";
        "deepsize_derive-0.1.2" = "sha256-E73xdzYfpJASps3yz6sjL48Kimy44F2LvxndWzgV3dU=";
        "globset-0.4.10" = "sha256-1ucpIHxISBqjvKBAea7o2wSddWiIQr6tBiInk4kg0P0=";
        "ignore-0.4.20" = "sha256-1ucpIHxISBqjvKBAea7o2wSddWiIQr6tBiInk4kg0P0=";
        "lmdb-rkv-0.14.0" = "sha256-yj0+3wRQkAyp5EYOe2WQeUt1D/3cXZK0XrH6qcxhaWw=";
        "lmdb-rkv-sys-0.11.0" = "sha256-c9lKJuE74Xp/sIwSFXFsl2EKffY3oC7Prnglt6p1Ah0=";
        "notify-5.0.0-pre.15" = "sha256-LG6e3dSIqQcHbNA/uYSVJwn/vgcAH0noHK4x3QQdqVI=";
        "prodash-16.0.0" = "sha256-Dkn4BmsF1SnSDAoqW5QkjdzGHEq41y7S20Q/DkRCpVQ=";
        "tree-sitter-dockerfile-0.2.0" = "sha256-UQSdcOWRH1QsFWVgxyx9/E7419Ue5zi79ngWNsWuQBc=";
      };
    };

    sourceRoot = "${src.name}/src/rust/engine";

    nativeBuildInputs = [
      python
      protobuf
      rustPlatform.cargoSetupHook
    ];

    buildPhase = ''
      export CARGO_BUILD_RUSTC=${rustc}/bin/rustc

      # https://github.com/pantsbuild/pants/blob/release_2.20.0/src/rust/engine/.cargo/config#L4
      export RUSTFLAGS="--cfg tokio_unstable"

      # https://github.com/pantsbuild/pants/blob/release_2.20.0/src/rust/engine/BUILD#L32
      ${cargo}/bin/cargo build \
        --features=extension-module \
        --release \
        -p engine \
        -p client
    '';

    installPhase = ''
      mkdir -p $out/lib/
      cp target/release/libengine.so $out/lib/native_engine.so

      mkdir -p $out/bin/
      cp target/release/pants $out/bin/native_client
    '';
  };
in
  pants-engine
#  with python.pkgs;
#    buildPythonApplication {
#      inherit version src;
#      pname = "pants";
#      pyproject = true;
#
#      buildInputs = [
#        setuptools
#      ];
#
#      # curl -L -O https://raw.githubusercontent.com/pantsbuild/pants/release_2.20.0/3rdparty/python/requirements.txt
#      propagatedBuildInputs = [
#        ansicolors
#        chevron
#        fasteners
#        freezegun
#        ijson
#        node-semver
#        packaging
#        pex
#        psutil
#        pytest
#        python-lsp-jsonrpc
#        pyyaml
#        requests
#        setproctitle
#        setuptools
#        toml
#        types-freezegun
#        types-pyyaml
#        types-requests
#        types-setuptools
#        types-toml
#        typing-extensions
#      ];
#
#      # https://github.com/pantsbuild/pants/blob/release_2.20.0/src/python/pants/BUILD#L27-L39
#      configurePhase = ''
#        cat > setup.py << EOF
#        from setuptools import setup, Extension
#
#        setup(
#            ext_modules=[Extension(name="dummy_twAH5rHkMN", sources=[])],
#        )
#        EOF
#
#        cat > pyproject.toml << EOF
#        [build-system]
#        requires = ["setuptools"]
#        build-backend = "setuptools.build_meta"
#
#        [project]
#        name = "pants"
#        version = "$version"
#        requires-python = ">=3.8.*"
#        dependencies = [
#          "packaging",
#        ]
#
#        [tool.setuptools]
#        include-package-data = true
#
#        [tool.setuptools.packages.find]
#        where = ["src/python"]
#        include = ["pants", "pants.*"]
#        namespaces = false
#
#        [project.scripts]
#        pants = "pants.bin.pants_loader:main"
#
#        EOF
#
#        echo ${version} > src/python/pants/_version/VERSION
#
#        cat > MANIFEST.in << EOF
#        include src/python/pants/_version/VERSION
#        include src/python/pants/engine/internals/native_engine.so
#        include src/python/pants/bin/native_client
#        recursive-include src/python/pants *.lock *.java *.scala *.lockfile.txt
#        EOF
#
#        find src/python -type d -exec bash -c "if [ -n \"$ls {}/*.py\" ]; then touch {}/__init__.py; fi" \;
#      '';
#
#      prePatch =
#        lib.strings.concatMapStrings
#        (patch_path: "patch -p1 --batch -u -i ${./patch-process-manager.txt}")
#        patches;
#
#      preBuild = ''
#
#        # https://github.com/pantsbuild/pants/blob/release_2.20.0/src/python/pants/engine/internals/BUILD#L28
#        cp ${pants-engine}/lib/native_engine.so src/python/pants/engine/internals/
#
#        # https://github.com/pantsbuild/pants/blob/release_2.20.0/build-support/bin/rust/bootstrap_code.sh#L34
#        cp ${pants-engine}/bin/native_client src/python/pants/bin/
#      '';
#
#      postInstall = ''
#        wrapProgram "$out/bin/pants" \
#          --set NO_SCIE_WARNING 1 \
#          --run "if [ -f .pants.bootstrap ]; then . .pants.bootstrap; fi"
#      '';
#    }

